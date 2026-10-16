"""把 mysql/init 下的建表/种子脚本按序导入目标 MySQL。

和 db_check.py（面向只读账号的自检）不同，本脚本面向**高权限账号**（需要
CREATE DATABASE / CREATE TABLE / CREATE USER 权限），用于把仓库里的 SQL
一次性灌进空的云数据库实例。

用法（在 backend/ 目录下）：
    python -m scripts.init_db --host <地址> --port 3306 --user root --password <口令>
    # 可选：先删库再重建（清掉历史脏数据）
    python -m scripts.init_db ... --recreate
    # 云端要求 TLS 时
    python -m scripts.init_db ... --ssl

参数缺省时会从 app.core.config 读取 .env 里的 MySQL 配置。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymysql

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# 执行顺序即文件名排序（01_、02_ …）
INIT_DIR_CANDIDATES = [
    BACKEND_DIR.parent / "mysql" / "init",   # 仓库根：lab-hazmat-agent/mysql/init
    BACKEND_DIR / "mysql" / "init",          # 兜底
]

DDL_FILES = [
    "01_schema.sql",
    "02_readonly_user.sql",
    "03_seed.sql",
    "04_labs.sql",
    "05_equipment.sql",
    "06_equipment_seed.sql",
    "07_lab_categories_seed.sql",
]


def resolve_init_dir(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_dir():
            raise SystemExit(f"指定的 SQL 目录不存在：{p}")
        return p
    for p in INIT_DIR_CANDIDATES:
        if p.is_dir():
            return p
    raise SystemExit("未找到 mysql/init 目录，请用 --dir 指定")


def split_statements(sql: str) -> list[str]:
    """按分号拆分语句，跳过 -- 行注释、/* */ 块注释，并保护引号内的分号。"""
    stmts: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    quote: str | None = None
    while i < n:
        ch = sql[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote in ("'", '"'):
                if i + 1 < n:
                    buf.append(sql[i + 1])
                    i += 2
                    continue
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            if j == -1:
                break
            i = j + 1
            continue
        if ch == "/" and sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j == -1:
                break
            i = j + 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def build_ssl(args) -> dict | None:
    if not args.ssl:
        return None
    opts: dict = {}
    if args.ssl_ca:
        opts["ca"] = args.ssl_ca
    return opts


def connect(args, db: str | None):
    kwargs: dict = dict(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        charset=args.charset,
        autocommit=True,
        connect_timeout=args.timeout,
    )
    if db:
        kwargs["database"] = db
    ssl_opts = build_ssl(args)
    if ssl_opts is not None:
        kwargs["ssl"] = ssl_opts
    return pymysql.connect(**kwargs)


def main() -> int:
    ap = argparse.ArgumentParser(description="把 mysql/init 的 SQL 导入目标 MySQL")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--user", default=None)
    ap.add_argument("--password", default=None)
    ap.add_argument("--db", default=None, help="目标库名，默认取 .env 的 MYSQL_DB")
    ap.add_argument("--dir", default=None, help="SQL 脚本目录，默认 mysql/init")
    ap.add_argument("--charset", default=None)
    ap.add_argument("--timeout", type=int, default=15, help="连接超时（秒）")
    ap.add_argument("--ssl", action="store_true", help="启用 TLS（云实例常用）")
    ap.add_argument("--ssl-ca", default=None, help="CA 证书路径")
    ap.add_argument("--recreate", action="store_true", help="先 DROP DATABASE 再重建")
    args = ap.parse_args()

    # 缺省值回落到 .env
    try:
        from app.core.config import get_settings
        s = get_settings()
        args.host = args.host or s.mysql_host
        args.port = args.port or s.mysql_port
        args.user = args.user or s.mysql_user
        args.password = args.password if args.password is not None else s.mysql_password
        args.db = args.db or s.mysql_db
        args.charset = args.charset or s.mysql_charset
    except Exception:                                    # noqa: BLE001
        args.host = args.host or "127.0.0.1"
        args.port = args.port or 3306
        args.dbfallback = None
        args.charset = args.charset or "utf8mb4"
    args.db = args.db or "lab_hazmat"
    args.charset = args.charset or "utf8mb4"

    init_dir = resolve_init_dir(args.dir)
    files = [init_dir / f for f in DDL_FILES if (init_dir / f).is_file()]
    if not files:
        extra = sorted(p for p in init_dir.glob("*.sql") if p.name not in DDL_FILES)
        files = extra
    if not files:
        raise SystemExit(f"{init_dir} 下没有可执行的 .sql 文件")

    print("=" * 68)
    print("SQL 导入目标 MySQL")
    print("=" * 68)
    print(f"  端点 : {args.host}:{args.port}")
    print(f"  账号 : {args.user}")
    print(f"  库名 : {args.db}")
    print(f"  TLS  : {'启用' if args.ssl else '未启用'}")
    print(f"  目录 : {init_dir}")
    print(f"  脚本 : {', '.join(p.name for p in files)}")
    print("-" * 68)

    # [1] 连通性
    try:
        conn = connect(args, db=None)
    except Exception as exc:                             # noqa: BLE001
        print(f"[!!] 连接失败：{type(exc).__name__}: {exc}")
        print("     排查：1) 腾讯云控制台安全组/白名单是否放行本机公网 IP；"
              "2) 是否该用内网地址；3) 若提示 SSL 相关，加 --ssl 重试")
        return 1
    print(f"[OK] 已连接，服务端版本 {conn.get_server_info()}")

    with conn.cursor() as cur:
        cur.execute("SELECT @@read_only, @@hostname")
        ro, hostname = cur.fetchone()
        print(f"[..] 实例主机名 {hostname}，read_only={ro}")
        if ro:
            print("[!!] 该实例是只读实例，无法写入，请改用主实例")
            conn.close()
            return 1

        if args.recreate:
            print(f"[..] DROP DATABASE IF EXISTS `{args.db}`")
            cur.execute(f"DROP DATABASE IF EXISTS `{args.db}`")

    # [2] 逐文件执行
    failures = 0
    total_stmt = 0
    for path in files:
        sql = path.read_text(encoding="utf-8")
        stmts = split_statements(sql)
        print(f"\n[..] {path.name} —— {len(stmts)} 条语句")
        ok = 0
        with conn.cursor() as cur:
            for stmt in stmts:
                try:
                    cur.execute(stmt)
                    ok += 1
                    total_stmt += 1
                except Exception as exc:                 # noqa: BLE001
                    failures += 1
                    head = " ".join(stmt.split())[:90]
                    print(f"[!!] 失败：{type(exc).__name__}: {exc}")
                    print(f"     语句：{head}…")
        print(f"[OK] {path.name} 完成：{ok}/{len(stmts)} 条")

    # [3] 结果核对
    print("\n" + "-" * 68)
    print("[..] 核对库表与行数")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
            (args.db,),
        )
        tables = cur.fetchall()
        if not tables:
            print("[!!] 目标库下没有表")
            failures += 1
        for name, approx in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{args.db}`.`{name}`")
                exact = cur.fetchone()[0]
            except Exception:                            # noqa: BLE001
                exact = "?"
            print(f"[OK] {name:<22} {exact!s:>6} 行")

    conn.close()
    print("\n" + "=" * 68)
    if failures:
        print(f"结论：执行 {total_stmt} 条语句，{failures} 处失败，请按上面的提示排查。")
    else:
        print(f"结论：全部成功，共执行 {total_stmt} 条语句。")
    print("=" * 68)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
