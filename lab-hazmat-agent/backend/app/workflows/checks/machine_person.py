"""机 × 人：设备借出逾期未还。

以 return_time IS NULL 判未还，不看 status 字段（与 check_equipment_loan 一致）。
"""
from __future__ import annotations

from app.db.connection import fetch_all
from app.workflows.models import CHECK_LABEL, CheckContext, Finding

_SQL = """
SELECT l.id AS loan_id, l.equip_id, e.equip_name, e.lab_id, e.status AS equip_status,
       l.person_id, p.name, p.emp_no,
       l.borrow_time, l.due_time, l.approver, l.purpose,
       DATEDIFF(%(as_of)s, DATE(l.due_time)) AS overdue_days
FROM equipment_loans l
JOIN equipment e ON e.equip_id = l.equip_id
LEFT JOIN persons p ON p.id = l.person_id
WHERE l.return_time IS NULL
  AND l.due_time < %(as_of)s
ORDER BY overdue_days DESC
"""


class MachinePersonCheck:
    id = "machine_person"
    label = CHECK_LABEL[id]

    async def run(self, ctx: CheckContext) -> list[Finding]:
        rows = await fetch_all(_SQL, {"as_of": ctx.as_of.strftime("%Y-%m-%d %H:%M:%S")})
        out: list[Finding] = []
        for r in rows:
            od = int(r["overdue_days"] or 0)
            if od <= 0:
                continue
            sev = "high" if od > 7 else "medium"
            evidence = [
                {"label": "借用人", "value": f"{r['name'] or '未登记'}（{r['emp_no'] or '-'}）"},
                {"label": "借出时间", "value": str(r["borrow_time"])},
                {"label": "应还时间", "value": str(r["due_time"])},
                {"label": "已逾期", "value": f"{od} 天"},
            ]
            if r["equip_status"] == "维修中":
                evidence.append({"label": "附注", "value": "设备已转维修，需核实状态是否未同步"})
            out.append(Finding(
                key=f"machine_person:{r['equip_id']}:{r['loan_id']}",
                check=self.id,
                severity=sev,  # type: ignore[arg-type]
                title=f"{r['equip_id']} {r['equip_name']} 借出逾期 {od} 天未还",
                subject_type="equipment",
                subject_id=r["equip_id"],
                subject_label=f"{r['equip_id']} {r['equip_name']}",
                evidence=evidence,
                owner=r["approver"] or "",
                owner_hint="批准人",
                suggest="催还并核对设备状态；如需续借请走线下审批后更新应还时间。",
                links=[
                    {"label": "设备详情", "to": f"/equipment/{r['equip_id']}"},
                    *([{"label": "借用人详情", "to": f"/persons/{r['person_id']}"}] if r["person_id"] else []),
                ],
            ))
        return out


CHECK = MachinePersonCheck()
