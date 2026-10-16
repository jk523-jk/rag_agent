"""设备台账查询与借还状态判定。只读，不做任何写入。

设计约束：
1. 本系统是只读问答系统，借还记录由线下流程产生，这里只查不写。
2. 校准到期判定以 `calibrate_due` 字段为准，**不看 status 字段**——
   设备台账里存在「状态仍为在用、但校准早已过期」的记录（与人员资质
   「状态有效但已过期」同类），只看 status 会漏判。储存设施无校准要求，
   `calibrate_due` 为空，不参与校准判定。
3. 逾期判定以 `due_time` 与当前时间比对，`return_time` 为空表示未归还。
   查不到借还记录时按「未借出」处理，但会明确说明是查无记录而非确认可借。
"""
from __future__ import annotations

import logging

from langchain_core.tools import tool

from app.db.connection import fetch_all

log = logging.getLogger(__name__)

# 校准到期预警窗口（天）
CALIBRATION_WARN_DAYS = 30

_SQL_EQUIPMENT = """
SELECT e.equip_id, e.equip_name, e.category, e.model_no, e.lab_id,
       e.keeper_id, p.name AS keeper_name, e.status, e.calibrate_due, e.remark,
       DATEDIFF(e.calibrate_due, CURDATE()) AS calibrate_days_left
FROM equipment e
LEFT JOIN persons p ON p.id = e.keeper_id
WHERE (%(equip)s    IS NULL OR e.equip_id = %(equip)s OR e.equip_name = %(equip)s)
  AND (%(lab_id)s   IS NULL OR e.lab_id = %(lab_id)s)
  AND (%(category)s IS NULL OR e.category = %(category)s)
  AND (%(status)s   IS NULL OR e.status = %(status)s)
ORDER BY e.lab_id, e.equip_id
LIMIT 50
"""


def _calibrate_text(due, days_left) -> str:
    """校准状态文案。无校准要求的设备明确说明，不误报为过期。"""
    if due is None:
        return "无校准要求"
    if days_left is None:
        return f"有效期至 {due}"
    if days_left < 0:
        return f"已过期 {abs(int(days_left))} 天（有效期至 {due}）"
    if days_left <= CALIBRATION_WARN_DAYS:
        return f"{int(days_left)} 天后到期（有效期至 {due}）"
    return f"有效期至 {due}"


@tool
async def query_equipment(
    equip: str | None = None,
    lab_id: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> str:
    """查询实验室设备的台账信息：设备名称、类别、所在实验室、保管人、状态与校准有效期。

    参数可任选其一或组合；全部留空则返回设备总览（最多 50 台）。
    设备编号（如 EQ-0002）或设备名称均可匹配。
    校准是否过期以校准有效期字段为准，设备状态字段可能未及时更新。
    """
    if not any([equip, lab_id, category, status]):
        return "请至少指定一个查询条件：设备编号/名称、实验室编号、设备类别或设备状态。"

    rows = await fetch_all(
        _SQL_EQUIPMENT,
        {"equip": equip, "lab_id": lab_id, "category": category, "status": status},
    )
    if not rows:
        conds = "、".join(
            f"{k}={v}" for k, v in
            [("设备", equip), ("实验室", lab_id), ("类别", category), ("状态", status)]
            if v
        )
        return (
            f"未找到符合条件的设备（{conds}）。"
            "请确认设备编号或名称（可用 query_equipment 不加条件先看总览），"
            "实验室编号形如 LAB-1 ~ LAB-5。"
        )

    lines: list[str] = []
    for r in rows:
        keeper = r["keeper_name"] or "保管人未登记"
        lines.append(
            f"- {r['equip_id']} {r['equip_name']}（{r['category']}"
            f"{'，' + r['model_no'] if r['model_no'] else ''}）｜{r['lab_id']}｜"
            f"保管人 {keeper}｜状态 {r['status']}｜校准 {_calibrate_text(r['calibrate_due'], r['calibrate_days_left'])}"
            + (f"｜备注 {r['remark']}" if r["remark"] else "")
        )

    overdue = [r for r in rows if r["calibrate_days_left"] is not None and r["calibrate_days_left"] < 0]
    header = f"设备台账（共 {len(rows)} 台）："
    out = [header, *lines]
    if overdue:
        out.append(
            f"⚠ 其中 {len(overdue)} 台校准已过期："
            + "、".join(f"{r['equip_id']} {r['equip_name']}" for r in overdue)
            + "。校准过期的设备按规定不得用于出具数据，请及时送检。"
        )
    return "\n".join(out)


_SQL_LOAN_CURRENT = """
SELECT l.id, l.equip_id, e.equip_name, e.lab_id, l.person_id, p.name AS person_name,
       p.emp_no, l.borrow_time, l.due_time, l.return_time, l.purpose, l.approver, l.status,
       DATEDIFF(CURDATE(), DATE(l.due_time)) AS overdue_days
FROM equipment_loans l
JOIN equipment e ON e.equip_id = l.equip_id
LEFT JOIN persons p ON p.id = l.person_id
WHERE l.equip_id = %(equip)s
  AND l.return_time IS NULL
ORDER BY l.borrow_time DESC
LIMIT 10
"""

_SQL_LOAN_HISTORY = """
SELECT l.id, l.equip_id, l.person_id, p.name AS person_name, p.emp_no,
       l.borrow_time, l.due_time, l.return_time, l.purpose, l.approver, l.status
FROM equipment_loans l
LEFT JOIN persons p ON p.id = l.person_id
WHERE l.equip_id = %(equip)s
ORDER BY l.borrow_time DESC
LIMIT 20
"""

_SQL_EQUIP_STATUS = """
SELECT equip_id, equip_name, category, lab_id, status, calibrate_due,
       DATEDIFF(calibrate_due, CURDATE()) AS calibrate_days_left
FROM equipment
WHERE equip_id = %(equip)s OR equip_name = %(equip)s
LIMIT 5
"""


@tool
async def check_equipment_loan(equip: str) -> str:
    """查询某台设备的借还状态：当前是否被借出、持有人是谁、是否逾期，并附借还历史。

    设备编号或名称均可。未查到时明确告知，不会推断为"可借"。
    维修中与报废的设备无论是否被借出，都不可借出。
    """
    equip_rows = await fetch_all(_SQL_EQUIP_STATUS, {"equip": equip})
    if not equip_rows:
        return (
            f"未找到设备「{equip}」。请确认设备编号（形如 EQ-0001）或设备名称，"
            "可先用 query_equipment 查看设备总览。"
        )

    current, history = await fetch_all(_SQL_LOAN_CURRENT, {"equip": equip}), await fetch_all(
        _SQL_LOAN_HISTORY, {"equip": equip}
    )

    # 同一编号可能匹配多行（编号与名称各自命中），逐台输出避免混淆
    blocks: list[str] = []
    for e in equip_rows:
        lines = [
            f"设备：{e['equip_id']} {e['equip_name']}（{e['category']}）｜{e['lab_id']}｜状态 {e['status']}",
            f"校准：{_calibrate_text(e['calibrate_due'], e['calibrate_days_left'])}",
        ]

        # 该设备对应的未归还记录
        held = [c for c in current if c["equip_id"] == e["equip_id"]]
        if held:
            for c in held:
                who = c["person_name"] or "借用人未登记"
                emp = f"（{c['emp_no']}）" if c["emp_no"] else ""
                borrow = c["borrow_time"].strftime("%Y-%m-%d %H:%M") if c["borrow_time"] else "未登记"
                due = c["due_time"].strftime("%Y-%m-%d %H:%M") if c["due_time"] else "未登记"
                overdue = c["overdue_days"] is not None and c["overdue_days"] > 0
                lines.append(f"当前持有人：{who}{emp}｜借出 {borrow}｜应还 {due}")
                if overdue:
                    lines.append(
                        f"**已逾期 {int(c['overdue_days'])} 天**（记录状态 {c['status']}），"
                        "请催还并核对设备状态。"
                    )
                else:
                    lines.append(f"状态：借用中，尚未到期（记录状态 {c['status']}）。")
                if c["approver"]:
                    lines.append(f"批准人：{c['approver']}｜用途：{c['purpose'] or '未填写'}")
            if e["status"] == "维修中":
                lines.append("⚠ 该设备台账状态为「维修中」，存在未归还的借用记录，需核实状态是否未同步。")
        else:
            lines.append("当前无人持有：未查到未归还的借还记录。")
            if e["status"] in {"维修中", "报废"}:
                lines.append(f"⚠ 但设备状态为「{e['status']}」，仍不可借出。")
            elif e["calibrate_days_left"] is not None and e["calibrate_days_left"] < 0:
                lines.append("⚠ 但校准已过期，按规定不得用于出具数据，送检合格前不得借出。")

        my_history = [h for h in history if h["equip_id"] == e["equip_id"]]
        if my_history:
            lines.append(f"借还历史（最近 {len(my_history)} 条）：")
            for h in my_history:
                who = h["person_name"] or "借用人未登记"
                b = h["borrow_time"].strftime("%Y-%m-%d") if h["borrow_time"] else "未登记"
                r = h["return_time"].strftime("%Y-%m-%d") if h["return_time"] else "未归还"
                lines.append(f"  - {who}｜借 {b}｜还 {r}｜{h['status']}｜用途 {h['purpose'] or '未填写'}")
        else:
            lines.append("借还历史：无记录。")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


_SQL_CALIBRATION_DUE = """
SELECT e.equip_id, e.equip_name, e.category, e.lab_id, e.status,
       p.name AS keeper_name, e.calibrate_due,
       DATEDIFF(e.calibrate_due, CURDATE()) AS days_left
FROM equipment e
LEFT JOIN persons p ON p.id = e.keeper_id
WHERE e.calibrate_due IS NOT NULL
  AND DATEDIFF(e.calibrate_due, CURDATE()) <= %(days)s
  AND e.status <> '报废'
ORDER BY e.calibrate_due
LIMIT 100
"""


@tool
async def list_calibration_due(days: int = 30) -> str:
    """列出校准已过期或将在指定天数内到期的设备清单。

    Args:
        days: 预警窗口天数，默认 30。设 0 只看已过期的设备。

    已报废的设备不列入（不再送检）。校准有效期字段为空的储存设施不列入。
    """
    if days < 0:
        return "预警天数不能为负数。"
    rows = await fetch_all(_SQL_CALIBRATION_DUE, {"days": days})
    if not rows:
        scope = "已过期" if days == 0 else f"已过期或将在 {days} 天内到期"
        return f"当前没有{scope}的设备（已报废设备不列入）。"

    expired = [r for r in rows if r["days_left"] is not None and r["days_left"] < 0]
    soon = [r for r in rows if r["days_left"] is not None and r["days_left"] >= 0]

    lines: list[str] = []
    if expired:
        lines.append(f"**校准已过期（{len(expired)} 台）**")
        for r in expired:
            lines.append(
                f"- {r['equip_id']} {r['equip_name']}｜{r['lab_id']}｜"
                f"保管人 {r['keeper_name'] or '未登记'}｜已过期 {abs(int(r['days_left']))} 天"
                f"（有效期至 {r['calibrate_due']}）｜状态 {r['status']}"
            )
    if soon:
        lines.append(f"**将在 {days} 天内到期（{len(soon)} 台）**")
        for r in soon:
            lines.append(
                f"- {r['equip_id']} {r['equip_name']}｜{r['lab_id']}｜"
                f"保管人 {r['keeper_name'] or '未登记'}｜{int(r['days_left'])} 天后到期"
                f"（有效期至 {r['calibrate_due']}）｜状态 {r['status']}"
            )
    lines.append(
        "提示：校准过期的设备按规定不得用于出具数据，请在到期前安排送检；"
        "是否需要停用请咨询实验室安全负责人。"
    )
    return "\n".join(lines)
