"""准入判定工具组。所有 SQL 参数化，不允许字符串拼接。

check_lab_access 是全项目最重要的工具：三闸判定写死在 SQL 里，顺序固定为
资质闸 → 授权闸 → 双人闸。这是为了防住最常见的人工失误——只看了授权、忘了资质。

本文件修正的问题：
1. 实验室不存在时，原实现会答「未找到人员」，把运维问题说成数据问题。
   现先单独校验实验室编号。
2. 资质多条时（换证/复审），原实现按 JOIN 结果逐行判定，同一人可能出现
   互相矛盾的结论。现每人只取 expire_date 最新的一条合格证。
3. 双人闸取证：原实现取当天**第一条**门禁事件的 companion_no，既不校验
   auth_result，也不看方向，顺序稍有变化结论就翻转。现聚合当天所有
   「进 + 验证通过」的事件取最大同行人数——任一次满足即为满足，
   查不到记录则 fail-closed（判「需双人同行」而非放行）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.db.connection import fetch_all
from app.db.sql_guard import GuardError
from app.tools.lab_resolver import resolve_lab

log = logging.getLogger(__name__)

_SQL_LAB = """
SELECT lab_id, lab_name, hazmat_class, needs_double, mgr_name
FROM labs WHERE lab_id = %(lab_id)s LIMIT 1
"""

# 每人只保留一条安全考试合格证：按 expire_date 倒序，取最新
_SQL_PERSON_GATES = """
SELECT
    p.id            AS person_id,
    p.name          AS name,
    p.emp_no        AS emp_no,
    p.role          AS role,
    p.dept          AS dept,
    l.lab_name      AS lab_name,
    l.needs_double  AS needs_double,
    q.cert_no       AS cert_no,
    q.issue_date    AS cert_issue,
    q.expire_date   AS cert_expire,
    q.status        AS cert_status,
    a.auth_from     AS auth_from,
    a.auth_to       AS auth_to,
    a.status        AS auth_status,
    a.grantor       AS grantor
FROM persons p
LEFT JOIN qualifications q
       ON q.person_id = p.id AND q.cert_type = '安全考试合格证'
LEFT JOIN lab_authorizations a
       ON a.person_id = p.id AND a.lab_id = %(lab_id)s
-- 实验室信息（实验室名、是否要求双人）必须显式 JOIN：
-- 之前漏了这一句，SELECT 里的 l.lab_name 会报 Unknown column（1054）。
LEFT JOIN labs l
       ON l.lab_id = %(lab_id)s
WHERE p.emp_no = %(person)s OR p.name = %(person)s
ORDER BY p.id, q.expire_date DESC
LIMIT 20
"""

# 双人闸取证：只认「进 + 验证通过」，取当天最大同行人数
_SQL_DAY_COMPANION = """
SELECT COUNT(*)                AS entry_count,
       MAX(companion_no)       AS max_companion,
       SUM(CASE WHEN companion_no IS NULL OR companion_no < 1 THEN 1 ELSE 0 END) AS solo_count
FROM access_events
WHERE person_id = %(person_id)s
  AND lab_id    = %(lab_id)s
  AND event_time >= %(t0)s AND event_time <= %(t1)s
  AND direction  = '进'
  AND auth_result = '通过'
"""


def _parse_time(at_time: str) -> datetime | None:
    """解析 YYYY-MM-DD 或 YYYY-MM-DD HH:MM(:SS)，也接受 ISO 的 T 分隔。"""
    raw = at_time.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _judge(row: dict, at_date: date, companion: int | None,
           entry_count: int = 0) -> tuple[str, list[str]]:
    """三闸判定。返回（结论, 判定说明列表）。顺序固定：资质闸 → 授权闸 → 双人闸。"""
    reasons: list[str] = []

    ok_cert = (
        row.get("cert_status") == "有效"
        and row.get("cert_expire") is not None
        and row["cert_expire"] >= at_date                      # 当天到期算有效
    )
    reasons.append(
        f"资质闸：{'通过' if ok_cert else '未通过'}"
        f"（安全考试合格证 {row.get('cert_no') or '无'}，"
        f"有效期至 {row.get('cert_expire') or '无'}，状态 {row.get('cert_status') or '无'}"
        f"{'；台账状态字段为「有效」，但已过有效期，以日期为准' if row.get('cert_status') == '有效' and row.get('cert_expire') is not None and row['cert_expire'] < at_date else ''}）"
    )
    if not ok_cert:
        reasons.append("授权闸：未判定（前序闸未通过）")
        reasons.append(
            f"双人闸：未判定（前序闸未通过；实验室{'要求' if row.get('needs_double') else '不要求'}双人同行）"
        )
        return "资质过期", reasons

    ok_auth = (
        row.get("auth_status") == "有效"
        and row.get("auth_from") is not None
        and row.get("auth_to") is not None
        and row["auth_from"] <= at_date <= row["auth_to"]
    )
    reasons.append(
        f"授权闸：{'通过' if ok_auth else '未通过'}"
        f"（{row.get('auth_from') or '无'} ~ {row.get('auth_to') or '无'}，"
        f"状态 {row.get('auth_status') or '无'}，授权人 {row.get('grantor') or '无'}）"
    )
    if not ok_auth:
        reasons.append(
            f"双人闸：未判定（前序闸未通过；实验室{'要求' if row.get('needs_double') else '不要求'}双人同行）"
        )
        return "无授权", reasons

    if row.get("needs_double"):
        if companion is None:
            reasons.append(
                f"双人闸：无法确认（当日无「进 + 验证通过」的门禁记录，"
                f"共 {entry_count} 条）。该实验室要求双人准入，需现场核实"
            )
            return "需双人同行", reasons
        if companion < 1:
            reasons.append(
                f"双人闸：未通过（当日最大同行人数 {companion}，"
                f"该实验室要求至少 1 名同行）"
            )
            return "需双人同行", reasons
        reasons.append(f"双人闸：通过（当日最大同行人数 {companion}）")

    reasons.append("结论：三闸全部通过")
    return "准予进入", reasons


@tool
async def check_lab_access(person: str, lab_id: str, at_time: str | None = None) -> str:
    """判定某人某时能否进入某实验室，同时校验资质闸、授权闸、双人闸。

    Args:
        person: 姓名或工号（重名时返回多行，请用工号二次确认）。
        lab_id: 实验室编号，如 LAB-3。
        at_time: 时间点，格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM。
            用户没有明确说具体时间时**必须留空**，留空即按服务器当前时间判定。
            切勿自行推断「今天」是哪一天——模型对当前日期的认知不可靠，
            一旦填错日期，三闸判定会整体错位（曾出现把今天写成 2024-04-05、
            导致「资质已过期」被判为「资质有效」的情况）。
    """
    raw = (at_time or "").strip()
    if raw in ("", "今天", "现在", "当前", "today", "now"):
        at = datetime.now()
    else:
        at = _parse_time(raw)
    if at is None:
        return f"时间格式无法识别：{at_time}，请用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM。"

    lab_id, lab_note = await resolve_lab(lab_id)
    if lab_note:
        return lab_note

    # 先确认实验室存在，避免把「编号写错」误报成「查无此人」
    lab_rows = await fetch_all(_SQL_LAB, {"lab_id": lab_id})
    if not lab_rows:
        return f"实验室编号「{lab_id}」不存在。请确认编号（如 LAB-1 ~ LAB-5）。"
    lab = lab_rows[0]

    rows = await fetch_all(_SQL_PERSON_GATES, {"person": person, "lab_id": lab_id})
    if not rows:
        return f"未在人员库中找到「{person}」。请确认姓名或工号（重名请用工号）。"

    # 同一人可能因换证/复审产生多条合格证记录，按 person_id 去重只留最新一条
    seen: dict[int, dict] = {}
    for r in rows:
        seen.setdefault(r["person_id"], r)
    persons = list(seen.values())

    t0 = at.replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = at.replace(hour=23, minute=59, second=59, microsecond=0)

    lines: list[str] = []
    for row in persons:
        ev = await fetch_all(
            _SQL_DAY_COMPANION,
            {"person_id": row["person_id"], "lab_id": lab_id, "t0": t0, "t1": t1},
        )
        stats = ev[0] if ev else {}
        raw_companion = stats.get("max_companion")
        companion = int(raw_companion) if raw_companion is not None else None
        entry_count = int(stats.get("entry_count") or 0)

        verdict, reasons = _judge(row, at.date(), companion, entry_count)
        lines.append(
            f"人员：{row['name']}（{row['emp_no']}，{row.get('role') or '身份未登记'}）\n"
            f"实验室：{lab_id} {lab.get('lab_name') or ''}"
            f"（负责人 {lab.get('mgr_name') or '未登记'}）\n"
            f"判定时间：{at:%Y-%m-%d}\n"
            f"结论：{verdict}\n"
            + "\n".join(f"  - {r}" for r in reasons)
        )

    header = (
        f"⚠ 姓名「{person}」匹配到 {len(persons)} 人，以下为逐人判定，请以工号为准：\n\n"
        if len(persons) > 1 else ""
    )
    return header + "\n\n".join(lines)


@tool
async def get_person_qualification(person: str) -> str:
    """查询某人的全部准入资质及其有效期与状态（安全考试合格证、危化品操作证、特种作业证等）。"""
    rows = await fetch_all(
        """
        SELECT p.id AS person_id, p.name, p.emp_no, p.role, p.dept,
               q.cert_type, q.cert_no, q.issue_date, q.expire_date, q.status
        FROM persons p
        LEFT JOIN qualifications q ON q.person_id = p.id
        WHERE p.emp_no = %(person)s OR p.name = %(person)s
        ORDER BY p.id, q.expire_date DESC
        LIMIT 60
        """,
        {"person": person},
    )
    if not rows:
        return f"未找到「{person}」的资质记录。请确认姓名或工号。"

    # 按人分组——原实现只看 rows[0]，同名多人的资质会混在一个人名下
    grouped: dict[int, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["person_id"], []).append(r)

    blocks: list[str] = []
    for recs in grouped.values():
        head = recs[0]
        lines = [
            f"{head['name']}（{head['emp_no']}"
            f"{'，' + head['role'] if head.get('role') else ''}"
            f"{'，' + head['dept'] if head.get('dept') else ''}）"
        ]
        certs = [r for r in recs if r["cert_type"] is not None]
        if not certs:
            lines.append("  （无任何资质记录）")
        for r in certs:
            lines.append(
                f"  - {r['cert_type']}｜编号 {r['cert_no'] or '无'}｜"
                f"{r['issue_date']} ~ {r['expire_date']}｜状态 {r['status']}"
            )
        blocks.append("\n".join(lines))

    header = (
        f"⚠ 姓名「{person}」匹配到 {len(grouped)} 人，请以工号为准：\n\n"
        if len(grouped) > 1 else ""
    )
    return header + "\n\n".join(blocks)


# ======================= query_records（NL2SQL + 护栏） =======================

DIALECT_PROMPT = """你是一个 MySQL 8 查询生成器。只输出一条 SELECT 语句，不要解释，不要分号。
约束：
1. 只允许 SELECT；禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE。
2. 聚合查询必须给所有非聚合列加 GROUP BY（实例已关闭 ONLY_FULL_GROUP_BY，但仍请写规范）。
3. 方言函数对照：按年 YEAR(col)、今天 CURDATE()、日期差 DATEDIFF(a,b)、近 N 天
   DATE_SUB(CURDATE(), INTERVAL N DAY)。
4. 时间范围用半开区间：
   col >= DATE_SUB(CURDATE(), INTERVAL N DAY) AND col < CURDATE() + INTERVAL 1 DAY。
5. 化学品匹配优先用 cas_no，其次 chem_name 的精确匹配；不要用 LIKE '%x%' 做兜底猜测。
6. 判定「某人某时的资质状态」必须同时看 status 与 expire_date：
   状态字段可能未及时更新，expire_date 才是硬标准。
7. **涉及人员或设备时，结果必须带出可读名称，不能只留 ID。**
   凡是输出里出现 person_id / keeper_id / witness_id / approver 等人员标识，
   必须 JOIN persons 并额外选出姓名与工号，且把姓名放在工号之前：
       LEFT JOIN persons p ON p.id = <人员标识列>
       ... p.name AS 姓名, p.emp_no AS 工号 ...
   只输出「工号1的人员」这类无姓名结果视为不合格：读的人无法确认是谁，
   工号也要回库再查一次。设备同理：出现 equip_id 时必须 JOIN equipment 带出 equip_name，
   出现 lab_id 时应带出 labs.lab_name。若一个 ID 对应的名称可能缺失，
   用 LEFT JOIN，不要用 INNER JOIN 把记录直接过滤掉。
8. 表结构如下（含中文含义）：
{ddl}
"""


@lru_cache
def _load_ddl() -> str:
    """拼接全部建表脚本（含 COMMENT）作为 NL2SQL 的表结构上下文。

    刻意不查 information_schema —— 只读护栏已把它列为敏感库并拒绝访问。
    脚本清单由 config.resolve_ddl_paths() 给出：扫描 init 目录下所有含
    CREATE TABLE 的 .sql。原实现只读 01_schema.sql 单文件，equipment 域
    （定义在 05_equipment.sql）因此从未进入提示词，模型看不到这两张表。
    """
    paths = get_settings().resolve_ddl_paths()
    if not paths:
        log.warning("未找到建表脚本，NL2SQL 将缺少表结构上下文")
        return "（未找到建表脚本，请依据列名常识谨慎生成 SQL）"
    log.info("NL2SQL 表结构上下文来源：%s", ", ".join(p.name for p in paths))
    parts: list[str] = []
    for p in paths:
        parts.append(f"-- ===== {p.name} =====")
        parts.append(p.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts)


def ddl_available() -> bool:
    """供启动自检：DDL 是否可读。"""
    return bool(get_settings().resolve_ddl_paths())


async def _generate_sql(question: str) -> str:
    s = get_settings()
    llm = ChatOpenAI(
        model=s.llm_model, base_url=s.llm_base_url, api_key=s.llm_api_key, temperature=0
    )
    msg = await llm.ainvoke(DIALECT_PROMPT.format(ddl=_load_ddl()) + f"\n\n问题：{question}")
    text = (msg.content or "").strip()
    # 去掉可能的 ```sql 围栏
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text.strip("`")
        text = text.rsplit("```", 1)[0]
    return text.strip().rstrip(";")


def _rows_to_markdown(rows: list[dict], max_rows: int = 50) -> str:
    """把查询结果渲染成 Markdown。人员姓名已由 _enrich_person_names 补在 ID 列之前。"""
    if not rows:
        return "无结果。"
    cols = list(rows[0].keys())
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = [
        "| " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) + " |"
        for r in rows[:max_rows]
    ]
    tail = f"\n（共 {len(rows)} 行，仅显示前 {max_rows} 行）" if len(rows) > max_rows else ""

    return "\n".join([head, sep, *body]) + tail


# 结果里一旦出现这些列名，就说明问题答案是「谁」，必须把姓名带出来。
# 若不补，模型只能回答「工号1的人员」，读的人无法确认是谁。
_ID_COLS_TO_NAMES = {
    "person_id": "姓名",
    "person": "姓名",
    "keeper_id": "保管人",
    "witness_id": "见证人",
}


async def _enrich_person_names(rows: list[dict]) -> list[dict]:
    """兜底补名：结果含人员 ID 列且没有姓名列时，批量查出 name/emp_no 插到 ID 列前。

    为什么要有这一层（而不是只靠提示词）：DIALECT_PROMPT 第 7 条已经要求 JOIN persons，
    但那是软约束——模型漏写时，用户看到的就是「工号1的人员」这种无法核对的答案。
    这里做机械补全，成本是一次额外查询，换来答案可读。
    查不到姓名的（ID 不存在）显式标「未登记」，不静默留空。
    """
    if not rows:
        return rows

    cols = set(rows[0].keys())
    if "姓名" in cols:
        return rows                      # 模型已经带出姓名，不必再查

    targets = [(c, label) for c, label in _ID_COLS_TO_NAMES.items() if c in cols]
    if not targets:
        return rows

    id_col = targets[0][0]
    ids = sorted({r.get(id_col) for r in rows if r.get(id_col) is not None})
    if not ids:
        return rows

    try:
        placeholders = ", ".join(f"%(p{i})s" for i in range(len(ids)))
        params = {f"p{i}": v for i, v in enumerate(ids)}
        people = await fetch_all(
            f"SELECT id, name, emp_no FROM persons WHERE id IN ({placeholders})",
            params,
        )
    except Exception as exc:                                      # noqa: BLE001
        log.warning("补查人员姓名失败（结果仍按原样返回）：%s: %s", type(exc).__name__, exc)
        return rows

    name_of = {p["id"]: p["name"] for p in people}
    emp_of = {p["id"]: p["emp_no"] for p in people}

    out: list[dict] = []
    for r in rows:
        pid = r.get(id_col)
        name = name_of.get(pid) or "未登记"
        emp = emp_of.get(pid)
        new_row: dict = {}
        for k, v in r.items():
            if k == id_col:
                # 「姓名（工号）」在前，原始 ID 保留在后，两处都不丢
                new_row["姓名"] = f"{name}（{emp}）" if emp else name
                new_row[k] = v
            else:
                new_row[k] = v
        out.append(new_row)
    return out


@tool
async def query_records(question: str) -> str:
    """对资质、授权、门禁流水、危化品台账、领用记录做结构化查询。

    用于回答"实际发生了什么"类问题：某人某时的通行记录、某实验室某时段的进入次数、
    某人的资质明细、某化学品的结存与领用情况。不用于回答"应该怎么做"（那用 search_policy）。
    """
    try:
        sql = await _generate_sql(question)
    except Exception as exc:                                      # noqa: BLE001
        return f"生成查询语句失败（{type(exc).__name__}），请换个问法或稍后重试。"

    try:
        rows = await fetch_all(sql)
    except GuardError as exc:
        return f"生成的 SQL 未通过只读护栏：{exc}\n请改写后重试。"
    except Exception as exc:                                      # noqa: BLE001
        log.warning("query_records 执行失败：%s: %s", type(exc).__name__, exc)
        return (
            f"查询执行失败（{type(exc).__name__}）。"
            "请调整问题，或改用更明确的化学名/CAS 号。"
        )

    if not rows:
        return (
            "查询条件在库中未匹配到任何记录。\n"
            "注意区分两种情况：(1) 确实不存在该记录；(2) 化学品名称匹配失败"
            "（例如问「双氧水」而台账登记为「过氧化氢」）。请尝试提供 CAS 号确认。"
        )
    # 兜底补人名：模型没按提示词 JOIN persons 时，这里机械补上「姓名（工号）」
    rows = await _enrich_person_names(rows)
    return _rows_to_markdown(rows)
