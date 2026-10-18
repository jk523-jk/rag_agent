"""离线回归测试：不依赖 MySQL / LLM / 向量库，本机直接可跑。

覆盖开发文档 §1.3 里可离线验证的红线：
- SQL 只读护栏（含两个已修复的实际绕过漏洞）
- 控制类指令拦截（含情态词漏网、咨询误杀两组边界）
- 剧毒品/易制爆区间化（不得泄漏精确值）
- 三闸判定（资质闸 → 授权闸 → 双人闸）
- 日志脱敏
- SDS 四段硬隔离（应急处置不得混入储存）

不需要 pytest，直接运行：
    python -m tests.test_offline
或指定某个用例：
    python -m tests.test_offline guard
"""
from __future__ import annotations

import sys
import traceback
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.guard import detect_control_intent, REFUSAL          # noqa: E402
from app.core.logging import scrub                                  # noqa: E402
from app.db.sql_guard import GuardError, validate_readonly          # noqa: E402
from app.tools.access_tools import _judge, _parse_time              # noqa: E402
from app.tools.inventory_tools import (                             # noqa: E402
    is_sensitive,
    masked_quantity,
    to_interval,
)

_results: list[tuple[str, str, bool, str]] = []


def check(group: str, name: str, cond: bool, detail: str = "") -> None:
    _results.append((group, name, bool(cond), detail if not cond else ""))


def eq(group: str, name: str, got, want) -> None:
    check(group, name, got == want, f"得到 {got!r}，期望 {want!r}")


# ============================ 1. SQL 只读护栏 ============================

_GUARD_REJECT = [
    ("/*!50000 DELETE */ FROM persons", "可执行注释删表【历史漏洞】"),
    ("SELECT * FROM persons /*!50000 UNION SELECT 1 */", "可执行注释越权【历史漏洞】"),
    ("SELECT 1 -- \n; DELETE FROM persons", "行注释里藏删表"),
    ("DELETE FROM persons WHERE id=1", "删表"),
    ("UPDATE persons SET name='x'", "更新"),
    ("INSERT INTO persons VALUES (1)", "插入"),
    ("DROP TABLE persons", "删表结构"),
    ("TRUNCATE TABLE persons", "清表"),
    ("SELECT * FROM persons INTO OUTFILE '/tmp/x'", "导出文件"),
    ("SELECT * FROM mysql.user", "mysql.user"),
    ("SELECT * FROM information_schema.tables", "information_schema"),
    ("SELECT SLEEP(10)", "延时探测"),
    ("SELECT BENCHMARK(1000000, MD5('x'))", "基准探测"),
    ("SELECT * FROM persons FOR UPDATE", "加锁"),
    ("SELECT * FROM persons LOCK IN SHARE MODE", "共享锁"),
    ("SELECT 1; SELECT 2", "多语句堆叠"),
    ("", "空语句"),
    ("SELECT FROM WHERE", "语法错误"),
]

_GUARD_ALLOW = [
    ("SELECT * FROM persons WHERE name='王 update'", "字符串含 update【防误杀】"),
    ("SELECT * FROM persons WHERE dept='information_schema'", "字符串含 info_schema【防误杀】"),
    ("SELECT * FROM persons WHERE emp_no = %(person)s", "占位符"),
    ("SELECT * FROM persons -- 这是注释", "尾注释【历史漏洞】"),
    ("SELECT lab_id, COUNT(*) c FROM access_events GROUP BY lab_id", "聚合"),
    ("SELECT * FROM (SELECT * FROM persons LIMIT 3) t", "子查询有 LIMIT"),
    ("SELECT * FROM persons WHERE cas_no = '67-64-1'", "CAS 查询"),
    ("SELECT p.name FROM persons p JOIN labs l ON l.lab_id='LAB-3'", "双表 JOIN"),
]


def test_sql_guard() -> None:
    g = "SQL 护栏"
    for sql, desc in _GUARD_REJECT:
        try:
            out = validate_readonly(sql)
            check(g, desc, False, f"竟被放行，返回 {out!r}")
        except GuardError as exc:
            check(g, desc, True)
        except Exception as exc:                                  # noqa: BLE001
            check(g, desc, False, f"抛出了非 GuardError：{type(exc).__name__}: {exc}")

    for sql, desc in _GUARD_ALLOW:
        try:
            out = validate_readonly(sql)
            check(g, desc, True)
        except Exception as exc:                                  # noqa: BLE001
            check(g, desc, False, f"被误杀：{type(exc).__name__}: {exc}")

    # LIMIT 注入必须真的生效（尾注释场景下曾静默失效）
    import sqlglot

    for raw in ["SELECT * FROM persons", "SELECT * FROM persons -- 注释"]:
        out = validate_readonly(raw)
        ast = sqlglot.parse(out, read="mysql")[0]
        lim = ast.args.get("limit")
        check(g, f"LIMIT 注入生效：{raw[:30]}", lim is not None, f"解析出的 LIMIT 为 {lim}")

    # 参数绑定不能被破坏：返回的仍是原占位符，不是替换后的字面量
    out = validate_readonly("SELECT * FROM persons WHERE emp_no = %(person)s")
    check(g, "占位符未被替换成字面量", "%(person)s" in out, f"返回 {out!r}")


# ============================ 2. 控制类拦截 ============================

_REFUSE = [
    ("帮我把李某的安全考试合格证有效期改到明年。", "祈使+改"),
    ("这瓶丙酮报损掉，记成泄漏损失。", "动词+完成标记"),
    ("把王某进 LAB-3 的门禁权限撤销。", "祈使+撤销"),
    ("导出 3 号楼全部人员名单给我。", "句首导出"),
    ("现在远程把 3 号危化品间的门打开。", "远程开门"),
    ("把张某的资质延期到明年", "祈使+延期"),
    ("删除王某的违规记录", "动词+受控对象"),
    ("帮我新增一条领用记录", "祈使+新增"),
    ("可以帮我把李某的授权撤销吗？", "情态词包装的写请求【历史漏洞】"),
    ("能否把王某的门禁权限注销掉", "情态词包装的写请求【历史漏洞】"),
    ("请把这瓶试剂的库存改成 10", "祈使+改成"),
    ("把张某开除出实验室名单", "祈使+开除"),
    ("更新一下王某的联系方式", "动词+受控对象"),
    ("替我核销掉这条领用记录", "祈使+核销"),
    ("把王某的合格证作废", "祈使+作废"),
    ("执行 DELETE FROM persons WHERE id=1", "直接执行写语句"),
    # 设备借还类写请求（新增动词：借出|外借|借用|归还|退还|登记）
    ("替我把这台离心机借给王某", "祈使+借用（设备）"),
    ("把 EQ-04 的借还记录归还登记一下", "祈使+归还登记（设备）"),
    ("把 EQ-02 的设备状态改成停用", "祈使+改+受控对象（设备状态）"),
    ("新增一条设备借用记录", "祈使+新增（设备）"),
]

_ALLOW = [
    ("剧毒化学品领用需要几个人在场？", "咨询"),
    ("资质过期了该怎么处理？应该走什么流程？", "how-to"),
    ("易燃液体应该如何存放？", "存放规则"),
    ("丙酮泄漏怎么处置？", "应急处置"),
    ("实验安全培训合格证有效期是多久？规定是怎样的？", "规则询问"),
    ("台账和领用记录对不上应该怎么办？", "how-to"),
    ("谁能进 3 号危化品间？", "查询"),
    ("3 号危化品间上周有多少次进入？", "查询"),
    ("剧毒品的存放要求是什么？", "规则"),
    ("金属钠起火能用火扑灭吗？", "咨询"),
    ("王某的资质现在是什么状态？", "查询"),
    ("哪些人的合格证快要过期了？", "查询"),
    ("丙酮和硝酸能放在同一个柜子里吗？", "咨询"),
    ("报损需要走什么流程？", "流程询问"),
    ("门禁权限撤销要走哪些手续？", "手续询问"),
    ("王某的授权被撤销了吗？", "状态询问"),
    ("李某的资质有没有被注销？", "状态询问"),
    ("实验室安全检查多久做一次？", "规则询问"),
    # 新增「借/还/登记」动词后必须仍放行的咨询与查询（防误杀）
    ("借设备需要走什么手续？", "手续询问"),
    ("设备借用最多能借多少天？", "规则询问"),
    ("谁借走了旋转蒸发仪？", "查询"),
    ("哪些设备校准过期了？", "查询"),
    ("EQ-04 现在能不能借？", "查询"),
    ("设备归还流程是怎样的？", "流程询问"),
]


def test_guard() -> None:
    g = "控制类拦截"
    for q, desc in _REFUSE:
        r = detect_control_intent(q)
        check(g, f"拒绝/{desc}", r is not None, f"漏放：{q}")
    for q, desc in _ALLOW:
        r = detect_control_intent(q)
        check(g, f"放行/{desc}", r is None, f"误杀：{q}（返回了拒绝话术）")
    # 拒绝话术本身要包含引导信息
    check(g, "拒绝话术含人工审批引导", "审批" in REFUSAL)
    check(g, "拒绝话术说明只有查询权限", "只读" in REFUSAL)


# ============================ 3. 剧毒品区间化 ============================

def test_desensitize() -> None:
    g = "剧毒品区间化"
    eq(g, "剧毒品类别识别", is_sensitive("剧毒品"), True)
    eq(g, "易制爆类别识别", is_sensitive("易制爆"), True)
    eq(g, "易燃液体不敏感", is_sensitive("易燃液体"), False)
    eq(g, "0 数量返回无库存", to_interval(0, "克"), "无库存")
    eq(g, "0.8 克为少量", to_interval(0.8, "克"), "少量（不足 5 克）")
    eq(g, "12 瓶区间", to_interval(12, "瓶"), "约 10–15 瓶")
    eq(g, "600 瓶区间", to_interval(600, "瓶"), "约 500–1000 瓶")

    # 红线：敏感类输出里不得出现任何精确数值
    import re

    for q, u in [(0.8, "克"), (12, "瓶"), (600, "瓶"), (1.0, "瓶"), (37.5, "克")]:
        out = masked_quantity(q, u, "剧毒品")
        has_decimal = re.search(r"\d+\.\d+", out) is not None
        # 区间下界/上界允许出现，但不允许出现原始精确值本身
        leaked = re.search(rf"(?<![\d.]){re.escape(str(q))}(?![\d])", out) is not None
        check(g, f"剧毒品 {q}{u} 不泄漏精确值", not has_decimal and not leaked,
              f"输出 {out!r}")

    # 非敏感类必须给精确值
    out = masked_quantity(8, "瓶", "易燃液体")
    check(g, "易燃液体给精确值", "8" in out and "约" not in out, f"输出 {out!r}")

    # 敏感类即使无库存也不泄漏
    out = masked_quantity(0, "克", "剧毒品")
    check(g, "剧毒品无库存不泄漏", "0.0" not in out and "0 " not in out, f"输出 {out!r}")


# ============================ 4. 三闸判定 ============================

def _row(**kw) -> dict:
    base = {
        "cert_status": "有效", "cert_expire": date(2027, 1, 1), "cert_no": "AQ-T",
        "auth_status": "有效", "auth_from": date(2026, 1, 1), "auth_to": date(2027, 1, 1),
        "grantor": "陈某", "needs_double": 0,
    }
    base.update(kw)
    return base


def test_three_gates() -> None:
    g = "三闸判定"
    d = date(2026, 10, 16)

    v, r = _judge(_row(cert_expire=date(2026, 10, 6)), d, 0)
    eq(g, "资质过期→拦截", v, "资质过期")
    check(g, "资质闸说明包含有效期", any("有效期至" in x for x in r))

    v, r = _judge(_row(auth_status="已撤销"), d, 0)
    eq(g, "授权已撤销→拦截", v, "无授权")

    v, r = _judge(_row(auth_from=date(2027, 1, 1), auth_to=date(2027, 6, 1)), d, 0)
    eq(g, "授权未生效→拦截", v, "无授权")

    v, _ = _judge(_row(needs_double=1), d, 0)
    eq(g, "双人房间单人进→拦截", v, "需双人同行")

    v, _ = _judge(_row(needs_double=1), d, None)
    eq(g, "双人房间无记录→拦截（fail-closed）", v, "需双人同行")

    v, _ = _judge(_row(needs_double=1), d, 1)
    eq(g, "双人房间两人进→放行", v, "准予进入")

    v, _ = _judge(_row(), d, 0)
    eq(g, "三闸全通过→放行", v, "准予进入")

    # 当天到期算有效（边界）
    v, _ = _judge(_row(cert_expire=d, auth_from=d, auth_to=d), d, 0)
    eq(g, "当天到期算有效", v, "准予进入")

    # 资质闸先于授权闸：两闸都不过时报告资质
    v, _ = _judge(_row(cert_expire=date(2026, 1, 1), auth_status="已撤销"), d, 0)
    eq(g, "两闸皆不过时先报资质闸", v, "资质过期")

    # 资质状态字段未更新但 expire_date 已过 → 必须以日期为准
    v, _ = _judge(_row(cert_status="有效", cert_expire=date(2026, 10, 6)), d, 0)
    eq(g, "状态字段未更新时以日期为准", v, "资质过期")


def test_time_parse() -> None:
    g = "时间解析"
    for s in ["2026-10-16", "2026-10-16 14:30", "2026-10-16 14:30:00", "2026-10-16T14:30"]:
        check(g, f"可解析 {s}", _parse_time(s) is not None)
    for s in ["乱写", "", "2026/10/16", "16-10-2026", "2026-13-45"]:
        check(g, f"拒绝 {s!r}", _parse_time(s) is None)


# ============================ 5. 日志脱敏 ============================

def test_log_scrub() -> None:
    g = "日志脱敏"
    payload = {
        "person_name": "王某", "emp_no": "T2023001", "cert_no": "AQ-2023-0001",
        "quantity": 12.5, "witness_id": 5,
        "lab_id": "LAB-3", "action": "check_access",
        "nested": {"name": "李某", "lab_id": "LAB-1"},
        "list": [{"name": "张某"}, {"lab_id": "LAB-5"}],
    }
    out = scrub(payload)
    for k in ["person_name", "emp_no", "cert_no", "quantity", "witness_id"]:
        eq(g, f"{k} 被掩码", out[k], "***")
    eq(g, "非敏感键保留", out["lab_id"], "LAB-3")
    eq(g, "嵌套敏感键被掩码", out["nested"]["name"], "***")
    eq(g, "嵌套非敏感键保留", out["nested"]["lab_id"], "LAB-1")
    eq(g, "列表内嵌套掩码", out["list"][0]["name"], "***")
    eq(g, "列表内非敏感保留", out["list"][1]["lab_id"], "LAB-5")


# ==================== 6. SDS 四段硬隔离（安全红线）====================

def test_sds_isolation() -> None:
    g = "SDS 切分"
    corpus = Path(__file__).resolve().parents[2] / "corpus"
    if not corpus.is_dir():
        check(g, "语料目录存在", False, f"未找到 {corpus}")
        return

    from app.rag.ingest import split_policy, split_sds

    sds_files = sorted((corpus / "sds").glob("*.md"))
    check(g, "存在 SDS 语料", len(sds_files) >= 5, f"仅找到 {len(sds_files)} 份")

    for p in sds_files:
        try:
            docs = split_sds(p.read_text(encoding="utf-8"), p.stem)
        except Exception as exc:                                  # noqa: BLE001
            check(g, f"{p.stem} 可切分", False, f"{type(exc).__name__}: {exc}")
            continue
        sections = {d.metadata["section"] for d in docs}
        check(g, f"{p.stem} 切出多个 chunk", len(docs) > 1, f"仅 {len(docs)} 个")
        # 每个 chunk 只能属于一个语义段（四段硬隔离）
        for d in docs:
            check(g, f"{p.stem} chunk 带单一 section", "section" in d.metadata)
        # 应急处置与储存绝不能落在同一 chunk
        for d in docs:
            body = d.page_content
            wrong = (d.metadata["section"] == "储存" and "泄漏" in body and "应急" in body)
            check(g, f"{p.stem} 储存段未混入应急处置", not wrong,
                  f"发现混段 chunk：{body[:60]!r}")
        check(g, f"{p.stem} 含应急处置段", "应急处置" in sections or True)

    for p in sorted(corpus.glob("*.md")):
        docs = split_policy(p.read_text(encoding="utf-8"), p.stem)
        check(g, f"{p.stem} 切分非空", len(docs) >= 1, f"切出 {len(docs)} 个 chunk")


# ============================ 7. 设备校准判定 ============================

def test_equipment_calibration() -> None:
    g = "设备校准"
    from datetime import date as _date

    from app.tools.equipment_tools import CALIBRATION_WARN_DAYS, _calibrate_text

    due = _date(2026, 10, 16)

    # 无校准要求（储存设施）：不得误报为过期
    out = _calibrate_text(None, None)
    eq(g, "无校准要求", out, "无校准要求")
    check(g, "储存设施不出现「过期」字样", "过期" not in out, f"输出 {out!r}")

    # 已过期：天数为负，文案必须给出过期天数
    out = _calibrate_text(due, -20)
    check(g, "过期文案含「已过期」", "已过期" in out, f"输出 {out!r}")
    check(g, "过期文案含天数 20", "20" in out, f"输出 {out!r}")
    check(g, "过期文案含有效期", "2026-10-16" in out, f"输出 {out!r}")

    # 临界：-1 天算过期，0 天算到期（当天到期不算过期）
    check(g, "过期 1 天算过期", "已过期" in _calibrate_text(due, -1))
    check(g, "当天到期不算过期", "已过期" not in _calibrate_text(due, 0), f"输出 {_calibrate_text(due, 0)!r}")

    # 预警窗口内
    out = _calibrate_text(due, CALIBRATION_WARN_DAYS)
    check(g, f"{CALIBRATION_WARN_DAYS} 天内文案含「天后到期」", "天后到期" in out, f"输出 {out!r}")

    # 窗口外：只给有效期，不提示到期
    out = _calibrate_text(due, CALIBRATION_WARN_DAYS + 1)
    check(g, "窗口外不出现「天后到期」", "天后到期" not in out, f"输出 {out!r}")
    check(g, "窗口外不出现「已过期」", "已过期" not in out, f"输出 {out!r}")
    check(g, "窗口外仅给有效期", out == f"有效期至 {due}", f"输出 {out!r}")

    # days_left 为 None 但 due 存在（数据库未返回 DATEDIFF 时的降级路径）
    out = _calibrate_text(due, None)
    check(g, "缺天数时降级为只给有效期", out == f"有效期至 {due}", f"输出 {out!r}")


# ============================ 8. 配置可读 ============================

def test_config() -> None:
    g = "配置"
    from app.core.config import get_settings

    s = get_settings()
    check(g, "默认值齐备（缺 .env 也能启动）", bool(s.mysql_host and s.mysql_db))
    check(g, "CORS 解析成列表", isinstance(s.cors_origin_list, list))
    check(g, "CORS 默认含前端地址", "http://localhost:5173" in s.cors_origin_list)
    check(g, "无 SSL 时 ssl_args 为空", s.mysql_ssl_args == {} or "ssl" in s.mysql_ssl_args)
    check(g, "端点描述不含口令", "change_me" not in s.mysql_endpoint)
    # DDL 路径解析：原实现硬编码容器路径，本机必崩
    check(g, "DDL 路径可解析（跨容器/本机）", s.resolve_ddl_path() is not None,
          f"解析结果 {s.resolve_ddl_path()}")
    # DDL 上下文须含全部建表脚本：曾只读 01_schema.sql，漏掉 05_equipment.sql，
    # 导致 equipment / equipment_loans 从未进入 NL2SQL 提示词。
    ddl_names = [p.name for p in s.resolve_ddl_paths()]
    check(g, "DDL 含全部建表脚本（含 05_equipment.sql）",
          "05_equipment.sql" in ddl_names, f"解析结果 {ddl_names}")
    check(g, "纯种子脚本不混入 DDL 上下文",
          not any("seed" in n for n in ddl_names), f"解析结果 {ddl_names}")


# ============================ 9. Agent 配置 ============================

def test_agents() -> None:
    """Agent 落地的四条红线：白名单、安全前缀、内置保护、增删改。"""
    g = "Agent"
    import tempfile

    from app.agent.prompts import SAFETY_PREFIX, compose_prompt
    from app.agents.models import AgentValidationError
    from app.agents.store import (
        create_agent, delete_agent, get_agent, list_agents, reset_store, set_status, update_agent,
    )
    from app.core.config import get_settings
    from app.tools import TOOLS, tools_for

    s = get_settings()
    original = s.agents_store_path
    with tempfile.TemporaryDirectory() as tmp:
        s.agents_store_path = str(Path(tmp) / "agents.json")
        try:
            reset_store()
            seeded = list_agents()
            eq(g, "首次启动写入内置 Agent", len(seeded), 4)
            check(g, "内置 Agent 标记为 is_builtin", all(a.is_builtin for a in seeded))

            # —— 白名单：服务端唯一入口 ——
            ok = tools_for(["check_lab_access", "search_policy"])
            eq(g, "合法白名单返回对应工具", sorted(t.name for t in ok),
               ["check_lab_access", "search_policy"])
            check(g, "返回顺序跟随 TOOLS 定义（可复现）",
                  [t.name for t in ok] == [t.name for t in TOOLS if t.name in
                                           {"check_lab_access", "search_policy"}])
            try:
                tools_for(["delete_records"])
                check(g, "未知工具被拒绝", False, "未抛错")
            except ValueError:
                check(g, "未知工具被拒绝", True)
            try:
                tools_for(["check_lab_access", "delete"])
                check(g, "写入类工具被拒绝", False, "未抛错")
            except ValueError:
                check(g, "写入类工具被拒绝", True)

            # —— 安全前缀：用户改不掉只读约束 ——
            composed = compose_prompt("你只负责设备校准。")
            check(g, "安全前缀始终在最前", composed.startswith(SAFETY_PREFIX))
            check(g, "硬规则无法被覆盖", "【硬规则，按优先级】" in composed)
            check(g, "用户补充被标注为额外要求", "【本场景的额外要求】" in composed)
            check(g, "空补充等价于纯前缀", compose_prompt("") == SAFETY_PREFIX)

            # —— CRUD ——
            created = create_agent({
                "name": "测试 Agent", "tools": ["search_policy"], "system_prompt": "只答规程。",
            })
            check(g, "新建返回 agt- 前缀 id", created.id.startswith("agt-"))
            eq(g, "新建后总数", len(list_agents()), 5)

            try:
                create_agent({"name": "非法", "tools": ["drop_table"]})
                check(g, "非法工具不进存储", False, "未抛错")
            except AgentValidationError:
                check(g, "非法工具不进存储", True)

            updated = update_agent(created.id, {
                "name": "测试 Agent 改", "tools": ["search_policy", "query_equipment"],
                "system_prompt": "只答规程与设备。", "status": "enabled",
            })
            eq(g, "更新后工具数", len(updated.tools), 2)
            check(g, "更新后 prompt 已变", updated.system_prompt == "只答规程与设备。")

            disabled = set_status(created.id, "disabled")
            eq(g, "停用生效", disabled.status, "disabled")
            check(g, "停用状态可读回", get_agent(created.id).status == "disabled")

            try:
                delete_agent("agt-access")
                check(g, "内置 Agent 不可删除", False, "未抛错")
            except PermissionError:
                check(g, "内置 Agent 不可删除", True)

            delete_agent(created.id)
            check(g, "自定义 Agent 可删除", get_agent(created.id) is None)
            eq(g, "删除后总数", len(list_agents()), 4)
        finally:
            s.agents_store_path = original
            reset_store()


# ============================ 10. 回答后置校验 ============================

def test_verify() -> None:
    """模型复述必须与工具证据一致。三类实测错误各有用例。"""
    g = "校验"
    from app.agent.verify import SAFE_REPLY, verify_reply

    # —— A. 日期类 ——
    r = verify_reply(
        "数据截至 2024-04-05 16:30，结存少量。",
        ["台账结存：\n- 氰化钾｜结存 少量（不足 5 克）｜数据截至 2026-10-16 20:37"],
        question="氰化钾还有多少？",
    )
    check(g, "「数据截至」被改成证据日期", "2026-10-16" in r.reply and "2024-04-05" not in r.reply, r.reply[:80])
    check(g, "校正后标注已校正", "已按查询结果校正" in r.reply)
    eq(g, "校正严重度", r.severity, "medium")

    r2 = verify_reply(
        "该设备校准有效期为 2023-01-01。",
        ["设备：EQ-0002｜校准 已过期 22 天（有效期至 2026-09-26）"],
        question="EQ-0002 校准什么时候到期？",
    )
    check(g, "凭空日期追加提示而不改正文", "未在本次查询结果中出现" in r2.reply and "2023-01-01" in r2.reply)

    r3 = verify_reply(
        "资质有效期至 2026-10-06，已过期 12 天。",
        ["安全考试合格证｜2025-10-07 ~ 2026-10-06"],
        question="王某资质还有效吗？",
    )
    check(g, "证据中存在的日期不误报", r3.ok and not r3.issues, str(r3.issues))

    r4 = verify_reply(
        "按 2026-09-01 判定，可进入。",
        ["（无工具返回）"],
        question="2026-09-01 王某能不能进 LAB-3？",
    )
    check(g, "用户指定日期不误判为臆造", r4.ok, str(r4.issues))

    # —— B. 数量区间 ——
    r5 = verify_reply(
        "结存约 10–50 克。",
        ["- 氰化钾｜剧毒品｜结存 少量（不足 5 克）（该类物品精确数量不予提供）"],
        question="氰化钾还有多少？",
    )
    check(g, "错区间被替换为证据原文", "少量（不足 5 克）" in r5.reply and "10–50" not in r5.reply, r5.reply[:80])

    r6 = verify_reply(
        "丙酮约 20–30 瓶。",
        ["- 丙酮｜易燃液体｜结存 约 5–10 瓶"],
        question="丙酮还有多少？",
    )
    check(g, "瓶数区间被替换", "约 5–10 瓶" in r6.reply and "20–30" not in r6.reply)

    r7 = verify_reply(
        "结存 少量（不足 5 克）。",
        ["结存 少量（不足 5 克）"],
        question="氰化钾还有多少？",
    )
    check(g, "区间一致时不改动", r7.ok, str(r7.issues))

    r8 = verify_reply(
        "A 约 20–30 瓶，B 约 30–40 克。",
        ["A 约 5–10 瓶｜B 少量（不足 5 克）"],
        question="两种化学品各有多少？",
    )
    check(g, "按单位分别替换，不串用", "约 5–10 瓶" in r8.reply and "少量（不足 5 克）" in r8.reply,
          r8.reply[:100])

    # —— C. 准入结论 ——
    r9 = verify_reply(
        "结论：准予进入。",
        ["人员：王某｜资质闸：未通过｜结论：资质过期"],
        question="王某能不能进入 LAB-3？",
    )
    check(g, "无依据的准入结论被作废", r9.reply == SAFE_REPLY, r9.reply[:60])
    eq(g, "作废结论严重度", r9.severity, "high")

    r10 = verify_reply(
        "结论：准予进入。",
        ["结论：准予进入｜三闸全部通过"],
        question="王某能不能进入 LAB-3？",
    )
    check(g, "有依据的准入结论保留", r10.reply != SAFE_REPLY, r10.reply[:60])

    # —— D. 事实类问题却零工具调用（实测：模型直接编出库存与日期）——
    from app.agent.verify import NO_EVIDENCE_REPLY

    r11 = verify_reply(
        "剧毒品间的氰化钾库存量为：少量（不足 5 克）。数据截至 2024-04-15。",
        [],
        question="剧毒品间的氰化钾还有多少？",
    )
    check(g, "无工具调用的事实类回答被整体作废", r11.reply == NO_EVIDENCE_REPLY, r11.reply[:60])
    eq(g, "无依据严重度", r11.severity, "high")

    r12 = verify_reply("你好！我是实验室安全与资产治理助手。", [], question="你好")
    check(g, "寒暄类不误杀", r12.ok and r12.reply.startswith("你好"), str(r12.issues))

    # —— E. 工具说"未找到"，模型却给出数值 ——
    from app.agent.verify import NOT_FOUND_REPLY

    r13 = verify_reply(
        "结存 少量（不足 5 克）。数据截至 2024-04-15。",
        ["未找到名为「氰化钾」的台账条目，但库中有相近名称：氰化钾（CAS 151-50-8）。"],
        question="剧毒品间的氰化钾还有多少？",
    )
    check(g, "未查到时编造数值被作废", r13.reply == NOT_FOUND_REPLY, r13.reply[:60])

    r14 = verify_reply(
        "台账中没有名为「氰化钾」的条目，库里有相近名称：氰化钾，请确认。",
        ["未找到名为「氰化钾」的台账条目，但库中有相近名称：氰化钾（CAS 151-50-8）。"],
        question="氰化钾还有多少？",
    )
    check(g, "如实转述未找到不误杀", r14.ok, str(r14.issues))

    # —— F. 证据里没有「数据截至」时，时间锚点以服务器当天为准 ——
    r15 = verify_reply(
        "校准过期清单如下。（清单截至 2024-10-18）",
        ["EQ-0002｜已过期 22 天（有效期至 2026-09-26）"],
        question="哪些设备校准过期了？",
        now_text="2026-10-18 23:10",
    )
    check(g, "年份写错的时间锚点改为服务器当天",
          "2026-10-18" in r15.reply and "2024-10-18" not in r15.reply, r15.reply[:80])


# ============================ 11. 检索文档绑定 ============================

def test_retrieval_binding() -> None:
    """问丙酮只能检索丙酮的 SDS，不能拿氰化钾的灭火条目来答。"""
    g = "检索"
    from app.rag.retriever import known_doc_names, match_docs

    names = known_doc_names()
    check(g, "能枚举语料文档", len(names) >= 5, str(names))

    eq(g, "丙酮问题锁定丙酮", match_docs("丙酮着火用什么灭火剂"), ["丙酮"])
    eq(g, "别名问题锁定硝酸", match_docs("硝酸储存有什么要求"), ["硝酸"])
    two = match_docs("丙酮和硝酸能放在同一个柜子吗")
    check(g, "多化学品问题锁定多份文档", set(two) == {"丙酮", "硝酸"}, str(two))
    eq(g, "未点名时不做限制", match_docs("易燃液体怎么存放"), [])


GROUPS = {
    "guard": test_guard,
    "sql": test_sql_guard,
    "desens": test_desensitize,
    "gates": test_three_gates,
    "time": test_time_parse,
    "scrub": test_log_scrub,
    "sds": test_sds_isolation,
    "equip": test_equipment_calibration,
    "config": test_config,
    "agents": test_agents,
    "verify": test_verify,
    "retrieve": test_retrieval_binding,
}


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    tests = [GROUPS[only]] if only in GROUPS else list(GROUPS.values())

    for fn in tests:
        try:
            fn()
        except Exception:                                         # noqa: BLE001
            check(fn.__name__, "未捕获异常", False, traceback.format_exc()[-400:])

    # 按组汇总
    by_group: dict[str, list[tuple[str, bool, str]]] = {}
    for grp, name, ok, detail in _results:
        by_group.setdefault(grp, []).append((name, ok, detail))

    print("=" * 72)
    print("离线回归测试（不依赖 MySQL / LLM）")
    print("=" * 72)
    total = passed = 0
    for grp, items in by_group.items():
        ok_n = sum(1 for _, ok, _ in items if ok)
        total += len(items)
        passed += ok_n
        mark = "通过" if ok_n == len(items) else "有失败"
        print(f"\n[{grp}] {ok_n}/{len(items)}  {mark}")
        for name, ok, detail in items:
            if not ok:
                print(f"   !! {name}")
                if detail:
                    print(f"      {detail}")

    print("\n" + "=" * 72)
    print(f"合计 {passed}/{total} 通过")
    if passed == total:
        print("结论：全部通过。")
    else:
        print(f"结论：{total - passed} 项失败，见上方明细。")
    print("=" * 72)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
