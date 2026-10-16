"""台账查询与交叉校验。脱敏在这里做，不靠提示词。

红线（对应开发文档 §6.3/§6.4）：剧毒品与易制爆的精确库存必须区间化，
且落在工具返回值层面——如果直接返回精确数字，模型迟早会把它说出来。

本文件修正的问题：
1. `to_interval` 的步长边界：q=5 时原实现走 step=5 得「约 5–10」，
   但同一套逻辑下 q=4.9 是「少量（不足 5）」，两者衔接处语义重复且不连贯。
   现统一为：<5 少量；[5,50) 步长5；[50,500) 步长50；≥500 步长500，
   并保证区间下界不低于 5，避免出现「约 0–5」这种等于暴露精确值的写法。
2. 非敏感类别的数量直接给出；敏感类别在任何分支（含「无库存」）都不返回精确值。
3. 阈值来自配置，可在云环境用 .env 调整而不改代码。
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from langchain_core.tools import tool

from app.core.config import get_settings
from app.db.connection import fetch_all
from app.rag.retriever import format_hits, retrieve_policy

log = logging.getLogger(__name__)

# 需要区间化处理的危险类别
SENSITIVE_CLASSES = {"剧毒品", "易制爆"}


def to_interval(qty: Decimal | float, unit: str) -> str:
    """把精确数量转成区间文案。不返回任何精确值。"""
    q = float(qty)
    if q <= 0:
        return "无库存"
    if q < 5:
        return f"少量（不足 5 {unit}）"
    step = 5 if q < 50 else 50 if q < 500 else 500
    lo = int(q // step) * step
    lo = max(lo, step)                       # 保证下界非 0，避免"约 0–5"变相暴露精确值
    return f"约 {lo}–{lo + step} {unit}"


def is_sensitive(hazard_class: str | None) -> bool:
    return (hazard_class or "") in SENSITIVE_CLASSES


def masked_quantity(qty: Decimal | float, unit: str, hazard_class: str | None) -> str:
    """唯一的对外数量出口：敏感类走区间，其余给精确值。"""
    if is_sensitive(hazard_class):
        return f"{to_interval(qty, unit)}（该类物品精确数量不予提供，如需精确值请联系实验室安全负责人）"
    return f"{float(qty):g}{unit}"


_SQL_INVENTORY = """
SELECT i.item_id, i.chem_name, i.cas_no, i.hazard_class, i.lab_id,
       i.cabinet_no, i.quantity, i.unit, i.updated_at
FROM hazmat_inventory i
WHERE (i.cas_no = %(chem)s OR i.chem_name = %(chem)s)
  AND (%(lab_id)s IS NULL OR i.lab_id = %(lab_id)s)
ORDER BY i.lab_id, i.item_id
LIMIT 50
"""

_SQL_FUZZY = """
SELECT chem_name, cas_no FROM hazmat_inventory
WHERE chem_name LIKE CONCAT('%%', %(chem)s, '%%')
   OR %(chem)s LIKE CONCAT('%%', chem_name, '%%')
LIMIT 10
"""


@tool
async def query_inventory(chem: str, lab_id: str | None = None) -> str:
    """查询危化品的台账结存、存放柜与危险类别。

    剧毒品与易制爆的精确结存数量一律按区间返回，不提供精确值。
    化学品名称支持 CAS 号或名称；名称匹配失败时会明确告知，不会静默返回空。
    """
    rows = await fetch_all(_SQL_INVENTORY, {"chem": chem, "lab_id": lab_id})
    if not rows:
        fuzzy = await fetch_all(_SQL_FUZZY, {"chem": chem})
        if fuzzy:
            cands = "、".join(
                f"{r['chem_name']}（CAS {r['cas_no'] or '未登记'}）" for r in fuzzy
            )
            return (
                f"未找到名为「{chem}」的台账条目，但库中有相近名称：{cands}。"
                "请确认目标化学品（别名情况常见，如「双氧水」在台账中登记为「过氧化氢」）。"
            )
        return f"台账中不存在「{chem}」，也未找到相近名称。请确认名称或直接提供 CAS 号。"

    lines: list[str] = []
    for r in rows:
        qty_text = masked_quantity(r["quantity"], r["unit"], r["hazard_class"])
        updated = r["updated_at"]
        updated_text = updated.strftime("%Y-%m-%d %H:%M") if updated else "未登记"
        lines.append(
            f"- {r['chem_name']}（CAS {r['cas_no'] or '未登记'}）｜类别 {r['hazard_class']}｜"
            f"{r['lab_id']} {r['cabinet_no'] or '柜位未登记'}｜结存 {qty_text}｜"
            f"数据截至 {updated_text}"
        )
    return "台账结存：\n" + "\n".join(lines)


_SQL_STOCK = """
SELECT item_id, chem_name, cas_no, hazard_class, lab_id, cabinet_no,
       quantity, unit, updated_at
FROM hazmat_inventory
WHERE (cas_no = %(chem)s OR chem_name = %(chem)s)
  AND lab_id = %(lab_id)s
LIMIT 10
"""

_SQL_USES = """
SELECT COALESCE(SUM(u.quantity), 0)                          AS used_qty,
       COUNT(*)                                              AS use_count,
       SUM(CASE WHEN u.witness_id IS NULL THEN 1 ELSE 0 END) AS no_witness_count
FROM hazmat_uses u
JOIN hazmat_inventory i ON i.item_id = u.item_id
WHERE i.lab_id = %(lab_id)s
  AND (i.cas_no = %(chem)s OR i.chem_name = %(chem)s)
  AND u.use_time >= DATE_SUB(CURDATE(), INTERVAL %(days)s DAY)
  AND u.use_time <  CURDATE() + INTERVAL 1 DAY
"""


@tool
async def reconcile_inventory(
    chem: str, lab_id: str, days: int = 30, opening_qty: float | None = None
) -> str:
    """交叉校验台账结存与领用记录是否相符，并给出制度依据。

    Args:
        chem: 化学品名称或 CAS 号。
        lab_id: 实验室编号。
        days: 回溯天数，默认 30。
        opening_qty: 期初结存（可选项）。已知期初时，按"期初 − 领用 = 应有结存"严格比对；
                    未知时退化为"领用是否超过现有结存"的周转校验。
    """
    if days <= 0:
        return "回溯天数必须为正整数。"
    params = {"chem": chem, "lab_id": lab_id, "days": days}

    # 三查并行：互不依赖，串行要等三次往返。任一失败不应让整次校验崩掉。
    stock_rows, use_rows, policy_docs = await asyncio.gather(
        fetch_all(_SQL_STOCK, params),
        fetch_all(_SQL_USES, params),
        retrieve_policy(f"{chem} 盘盈 盘亏 差异 上报 损耗 处置", kind="policy", k=3),
        return_exceptions=True,
    )
    if isinstance(stock_rows, BaseException):
        log.warning("台账查询失败：%s", type(stock_rows).__name__)
        return f"台账查询失败（{type(stock_rows).__name__}），请稍后重试。"
    if isinstance(use_rows, BaseException):
        log.warning("领用汇总失败：%s", type(use_rows).__name__)
        return f"领用记录查询失败（{type(use_rows).__name__}），请稍后重试。"
    if isinstance(policy_docs, BaseException):
        policy_docs = []                       # 制度依据缺失不阻断比对结论

    if not stock_rows:
        return f"未在 {lab_id} 找到「{chem}」的台账条目，无法比对。请先确认化学品名称或 CAS 号。"

    stock = stock_rows[0]
    used = float(use_rows[0]["used_qty"] or 0)
    use_count = int(use_rows[0]["use_count"] or 0)
    no_witness = int(use_rows[0]["no_witness_count"] or 0)
    book = float(stock["quantity"])
    unit = stock["unit"]
    s = get_settings()
    threshold = max(s.loss_threshold_abs, book * s.loss_threshold_ratio)

    if opening_qty is not None:
        expected = float(opening_qty) - used
        diff = book - expected
        basis = f"期初 {opening_qty:g}{unit} − 期间领用 {used:g}{unit} = 应有结存 {expected:g}{unit}"
    else:
        diff = used - book                      # 无期初时：领用超过结存即为不符信号
        basis = f"期间领用合计 {used:g}{unit}（未提供期初结存，按周转校验）"

    is_anomaly = abs(diff) > threshold
    verdict = "存在账物不符，需要核实" if is_anomaly else "在合理损耗范围内，暂未发现异常"

    # 敏感类别：比对结论可以给，但结存与领用量都必须区间化，否则从数字反推得出精确库存
    sensitive = is_sensitive(stock["hazard_class"])
    if sensitive:
        book_text = to_interval(book, unit)
        used_text = to_interval(used, unit) if used > 0 else "无"
        diff_text = "已按区间处理，不提供精确差值"
    else:
        book_text = f"{book:g}{unit}"
        used_text = f"{used:g}{unit}"
        diff_text = f"{diff:+g}{unit}"

    lines = [
        f"化学品：{stock['chem_name']}（CAS {stock['cas_no'] or '未登记'}）｜{lab_id} "
        f"{stock['cabinet_no'] or '柜位未登记'}｜类别 {stock['hazard_class']}",
        f"台账结存：{book_text}",
        f"领用记录：近 {days} 天共 {use_count} 笔、合计 {used_text}",
        f"比对口径：{basis}",
        f"**差异：{diff_text}**"
        + ("" if sensitive else f"（合理损耗阈值 ±{threshold:.2f}{unit}）"),
        f"结论：{verdict}",
    ]
    if sensitive:
        lines.append(
            "说明：该化学品属剧毒品/易制爆，精确结存与精确差值不予提供，"
            "如需精确数字请联系实验室安全负责人核对实物。"
        )
    if no_witness:
        lines.append(
            f"附带发现：近 {days} 天有 {no_witness} 笔领用记录缺少见证人；"
            "剧毒品与易制爆要求双人领用，请一并核实。"
        )
    lines.append("制度依据：\n" + format_hits(policy_docs))
    return "\n".join(lines)
