"""机 × 机：在用但校准过期（或将在预警窗口内到期）。

红线：只看 calibrate_due，不看 status——台账存在「在用但校准过期」（EQ-0002）。
储存设施 calibrate_due 为空，天然排除；报废设备排除；维修中保留。
"""
from __future__ import annotations

from app.db.connection import fetch_all
from app.workflows.models import CHECK_LABEL, CheckContext, Finding, bump

_SQL = """
SELECT e.equip_id, e.equip_name, e.category, e.lab_id, e.status,
       e.calibrate_due, p.name AS keeper_name, k.mgr_name,
       DATEDIFF(e.calibrate_due, %(as_of)s) AS days_left
FROM equipment e
LEFT JOIN persons p ON p.id = e.keeper_id
LEFT JOIN labs k    ON k.lab_id = e.lab_id
WHERE e.calibrate_due IS NOT NULL
  AND e.status <> '报废'
  AND DATEDIFF(e.calibrate_due, %(as_of)s) <= %(warn_days)s
ORDER BY e.calibrate_due
"""

_DATA_INSTRUMENTS = {"分析仪器", "检测仪器"}


class MachineMachineCheck:
    id = "machine_machine"
    label = CHECK_LABEL[id]

    async def run(self, ctx: CheckContext) -> list[Finding]:
        warn_days = int(ctx.params.get("calibrate_warn_days") or 0)
        rows = await fetch_all(_SQL, {
            "as_of": ctx.as_of.strftime("%Y-%m-%d"),
            "warn_days": warn_days,
        })
        out: list[Finding] = []
        for r in rows:
            days_left = r["days_left"]
            if days_left is None:
                continue
            days_left = int(days_left)
            if days_left < -60:
                sev = "high"
            elif days_left < 0:
                sev = "medium"
            else:
                sev = "low"
            if r["category"] in _DATA_INSTRUMENTS:
                sev = bump(sev)  # type: ignore[arg-type]
            if days_left < 0:
                calib_text = f"已过期 {abs(days_left)} 天"
            else:
                calib_text = f"{days_left} 天后到期"
            out.append(Finding(
                key=f"machine_machine:{r['equip_id']}",
                check=self.id,
                severity=sev,  # type: ignore[arg-type]
                title=f"{r['equip_id']} {r['equip_name']} 校准{calib_text}，状态仍为「{r['status']}」",
                subject_type="equipment",
                subject_id=r["equip_id"],
                subject_label=f"{r['equip_id']} {r['equip_name']}",
                evidence=[
                    {"label": "实验室", "value": r["lab_id"]},
                    {"label": "类别", "value": r["category"]},
                    {"label": "校准有效期至", "value": str(r["calibrate_due"])},
                    {"label": "校准状态", "value": calib_text},
                    {"label": "台账状态", "value": r["status"]},
                ],
                owner=r["keeper_name"] or r["mgr_name"] or "",
                owner_hint="保管人" if r["keeper_name"] else "实验室负责人",
                suggest="校准过期设备不得用于出具数据，请安排送检；到期前完成检定。",
                links=[{"label": "设备详情", "to": f"/equipment/{r['equip_id']}"}],
            ))
        return out


CHECK = MachineMachineCheck()
