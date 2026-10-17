"""云数据库连通性自检。

用途：在把后端接上云 MySQL 之前，先用这个脚本确认「网络 → TLS → 账号 → 权限 → 表」
五层全部打通。它按层递进探测，**哪一层断了一目了然**，不用靠后端启动日志猜。

用法（在 backend/ 目录下）：
    python -m scripts.db_check
    python -m scripts.db_check --sql "SELECT COUNT(*) FROM persons"

它做的事：
  0) 打印生效配置（不含口令），确认连的是目标实例而不是本地 Docker
  1) TCP 连通性 —— 云实例安全组没放行时，卡在这一步
  2) 账号认证 + TLS —— 密码错、SSL 配置错、白名单没加，卡在这一步
  3) 库是否可访问 + 服务端版本/是否只读实例
  4) 只读护栏自检 —— 确认写语句在研究库里确实被拒
  5) 关键表是否已建（labs/persons/qualifications/...）
  6) 种子数据行数
  7) 可选：执行一条自定义只读 SQL
"""
from __future__ import annotations

import argparse
import asyncio
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings                       # noqa: E402
from app.db.connection import close_pool, describe_connection, fetch_all, init_pool  # noqa: E402
from app.db.sql_guard import GuardError, validate_readonly     # noqa: E402

OK, BAD, WARN, INFO = "  [OK]", "  [!!]", "  [??]", "  [..]"
TABLES = [
    "labs", "persons", "qualifications",
    "lab_authorizations", "access_events", "hazmat_inventory", "hazmat_uses",
]


def _tcp_probe(host: str, port: int, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "TCP 可达"
    except socket.timeout:
        return False, f"连接超时（{timeout}s）——安全组/防火墙很可能未放行 {port}"
    except socket.gaierror as exc:
        return False, f"域名解析失败（{exc}）——主机名拼写或 DNS 配置问题"
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def main() -> int:
    ap = argparse.ArgumentParser(description="云数据库连通性自检")
    ap.add_argument("--sql", default=None, help="额外执行一条只读 SQL")
    ap.add_argument("--skip-guard", action="store_true", help="跳过只读护栏自检")
    args = ap.parse_args()

    s = get_settings()
    failures = 0

    print("=" * 68)
    print("实验室安全与资产治理平台 · 云数据库连通性自检")
    print("=" * 68)
    print("\n[0] 生效配置")
    print(f"{INFO} 端点      : {s.mysql_endpoint}")
    print(f"{INFO} 账号      : {s.mysql_user}")
    print(f"{INFO} SSL       : {'启用' if s.mysql_ssl_args else '未启用'}"
          + (f"  CA={s.mysql_ssl_ca}" if s.mysql_ssl_ca else ""))
    print(f"{INFO} 连接超时  : {s.mysql_connect_timeout}s   连接池: {s.mysql_pool_min}-{s.mysql_pool_max}")
    ddl_paths = s.resolve_ddl_paths()
    ddl_desc = ", ".join(p.name for p in ddl_paths) if ddl_paths else "未找到（NL2SQL 将缺表结构）"
    print(f"{INFO} DDL 脚本  : {ddl_desc}")

    print("\n[1] TCP 连通性")
    ok, msg = _tcp_probe(s.mysql_host, s.mysql_port)
    if ok:
        print(f"{OK} {msg}")
    else:
        print(f"{BAD} {msg}")
        print(f"{INFO} 排查：1) 云控制台安全组是否放行本机公网 IP 到 {s.mysql_port} 端口；"
              f"2) 实例白名单是否加了本机 IP；3) 是否该用内网地址")
        return _summary(failures + 1, skipped=True)

    print("\n[2] 建池 + 账号认证 + TLS")
    await init_pool()
    info = await describe_connection()
    if not info.get("connected"):
        print(f"{BAD} 连接失败：{info.get('error')}")
        print(f"{INFO} 若报 SSL/TLS 相关：云厂商多要求加密，设 MYSQL_SSL=true 重试")
        print(f"{INFO} 若报 Access denied：核对 MYSQL_USER / MYSQL_PASSWORD，"
              f"以及该账号是否被允许从本机 IP 登录（云实例常需 user@'%'）")
        await close_pool()
        return _summary(failures + 1)

    print(f"{OK} 已连接")
    print(f"{INFO} 服务端版本 : {info.get('version')}")
    print(f"{INFO} 当前库     : {info.get('db')}")
    print(f"{INFO} 当前账号   : {info.get('user')}")
    print(f"{INFO} 实例主机名 : {info.get('hostname')}")
    print(f"{INFO} read_only  : {info.get('read_only')}"
          + ("（只读实例，写操作会被服务端拒绝，符合预期）" if info.get("read_only") else ""))

    if not args.skip_guard:
        print("\n[3] 只读护栏自检")
        for sql, should_reject in [
            ("SELECT * FROM persons", False),
            ("DELETE FROM persons WHERE id=1", True),
            ("/*!50000 DELETE */ FROM persons", True),
            ("SELECT * FROM mysql.user", True),
        ]:
            try:
                validate_readonly(sql)
                rejected = False
            except GuardError:
                rejected = True
            if rejected == should_reject:
                print(f"{OK} {'拒绝' if rejected else '放行'}：{sql[:46]}")
            else:
                print(f"{BAD} 护栏异常（{'应拒绝' if should_reject else '应放行'}）：{sql[:46]}")
                failures += 1

    print("\n[4] 关键表")
    try:
        rows = await fetch_all(
            "SELECT TABLE_NAME AS t, TABLE_ROWS AS r FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE()"
        )
        print(f"{BAD} information_schema 查询竟然通过了护栏——这是缺陷，请报告")
        failures += 1
    except GuardError:
        print(f"{OK} information_schema 已按预期被护栏拒绝（改用逐表探测）")

    for t in TABLES:
        try:
            r = await fetch_all(f"SELECT COUNT(*) AS c FROM {t}")
            print(f"{OK} {t:<20} {r[0]['c']:>6} 行")
        except Exception as exc:                                  # noqa: BLE001
            print(f"{BAD} {t:<20} 不可用：{type(exc).__name__}（表未建或账号无 SELECT 权限）")
            failures += 1

    if args.sql:
        print("\n[5] 自定义查询")
        print(f"{INFO} {args.sql}")
        try:
            rows = await fetch_all(args.sql)
            for r in rows[:10]:
                print(f"{INFO} {r}")
            if len(rows) > 10:
                print(f"{INFO} … 共 {len(rows)} 行")
        except Exception as exc:                                  # noqa: BLE001
            print(f"{BAD} {type(exc).__name__}: {exc}")
            failures += 1

    await close_pool()
    return _summary(failures)


def _summary(failures: int, skipped: bool = False) -> int:
    print("\n" + "=" * 68)
    if failures == 0:
        print("结论：全部通过，可以启动后端并开始端到端联调。")
    else:
        print(f"结论：{failures} 项未通过，请按上面的提示逐项排查。")
    print("=" * 68)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
