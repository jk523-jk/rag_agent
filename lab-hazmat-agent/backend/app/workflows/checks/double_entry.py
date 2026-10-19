"""双人闸：要求双人准入的实验室出现单人进入。

必须与 access_tools 双人闸同口径：按（人, 实验室, 天）聚合取 MAX(companion_no)，
任一次满足即为满足；NULL 与 0 均视为单人。
"""
from __future__ import annotations

from app.db.connection import fetch_all
from app.workflows.models import CHECK_LABEL, CheckContext, Finding, bump

_SQL = """
SELECT d.person_id, p.name, p.emp_no, d.lab_id, l.lab_name, l.hazmat_class, l.mgr_name,
       COUNT(*)   AS solo_days,
       MIN(d.day) AS first_day,
       MAX(d.day) AS last_day
FROM (
    SELECT person_id, lab_id, DATE(event_time) AS day, MAX(companion_no) AS max_companion
    FROM access_events
    WHERE direction = '进' AND auth_result = '通过'
      AND event_time >= %(t0)s AND event_time <= %(t1)s
      AND (%(lab_id)s IS NULL OR lab_id = %(lab_id)s)
    GROUP BY person_id, lab_id, DATE(event_time)
) d
JOIN labs l    ON l.lab_id = d.lab_id AND l.needs_double = 1
JOIN persons p ON p.id = d.person_id
WHERE d.max_companion < 1 OR d.max_companion IS NULL
GROUP BY d.person_id, p.name, p.emp_no, d.lab_id, l.lab_name, l.hazmat_class, l.mgr_name
ORDER BY solo_days DESC
"""


class DoubleEntryCheck:
    id = "double_entry"
    label = CHECK_LABEL[id]

    async def run(self, ctx: CheckContext) -> list[Finding]:
        rows = await fetch_all(_SQL, {
            "t0": ctx.window_from.strftime("%Y-%m-%d %H:%M:%S"),
            "t1": ctx.window_to.strftime("%Y-%m-%d %H:%M:%S"),
            "lab_id": ctx.params.get("lab_id") or None,
        })
        out: list[Finding] = []
        for r in rows:
            solo_days = int(r["solo_days"] or 0)
            hazmat = r["hazmat_class"] or ""
            sev = "high" if "剧毒品" in hazmat else "medium"
            if solo_days >= 3:
                sev = bump(sev)  # type: ignore[arg-type]
            out.append(Finding(
                key=f"double_entry:{r['person_id']}:{r['lab_id']}",
                check=self.id,
                severity=sev,  # type: ignore[arg-type]
                title=(
                    f"{r['name']} 单人进入要求双人准入的 {r['lab_id']}（{r['lab_name']}），"
                    f"窗口内 {solo_days} 天"
                ),
                subject_type="person",
                subject_id=str(r["person_id"]),
                subject_label=f"{r['name']}（{r['emp_no']}）",
                evidence=[
                    {"label": "实验室", "value": f"{r['lab_id']} {r['lab_name']}（{hazmat}）"},
                    {"label": "单人进入天数", "value": f"{solo_days} 天"},
                    {"label": "首日", "value": str(r["first_day"])},
                    {"label": "末日", "value": str(r["last_day"])},
                    {"label": "同行记录", "value": "未记录同行人数（companion_no 为空或 0）"},
                ],
                owner=r["mgr_name"] or "",
                owner_hint="实验室负责人",
                suggest="核实门禁同行记录是否漏录；若确为单人进入，按双人准入制度处理并复盘门禁放行原因。",
                links=[{"label": "人员详情", "to": f"/persons/{r['person_id']}"}],
            ))
        return out


CHECK = DoubleEntryCheck()
