"""人 × 环：资质过期仍通行。

口径必须与 access_tools._judge 对齐：
- 每人只取最新一条「安全考试合格证」（MAX(expire_date)）
- 双人实验室同一问题升一级
"""
from __future__ import annotations

from app.db.connection import fetch_all
from app.workflows.models import CHECK_LABEL, CheckContext, Finding, bump

_SQL = """
SELECT p.id AS person_id, p.name, p.emp_no,
       l.lab_id, l.lab_name, l.needs_double, l.mgr_name,
       MAX(q.expire_date)                      AS cert_expire,
       DATEDIFF(%(as_of)s, MAX(q.expire_date)) AS expired_days,
       COUNT(*)                                AS entry_count,
       MAX(a.event_time)                       AS last_entry_at
FROM access_events a
JOIN persons p       ON p.id = a.person_id
JOIN labs l          ON l.lab_id = a.lab_id
JOIN qualifications q
     ON q.person_id = p.id AND q.cert_type = '安全考试合格证'
WHERE a.direction = '进'
  AND a.auth_result = '通过'
  AND a.event_time >= %(t0)s AND a.event_time <= %(t1)s
  AND (%(lab_id)s IS NULL OR a.lab_id = %(lab_id)s)
GROUP BY p.id, p.name, p.emp_no, l.lab_id, l.lab_name, l.needs_double, l.mgr_name
HAVING MAX(q.expire_date) < %(as_of)s
ORDER BY expired_days DESC
"""


def _severity(expired_days: int, needs_double: int, entry_count: int) -> str:
    if expired_days > 30:
        s = "high"
    elif expired_days > 7:
        s = "medium"
    else:
        s = "low"
    if needs_double:
        s = bump(s)  # type: ignore[arg-type]
    if entry_count >= 3:
        s = bump(s)  # type: ignore[arg-type]
    return s


class PersonEnvCheck:
    id = "person_env"
    label = CHECK_LABEL[id]

    async def run(self, ctx: CheckContext) -> list[Finding]:
        rows = await fetch_all(_SQL, {
            "as_of": ctx.as_of.strftime("%Y-%m-%d"),
            "t0": ctx.window_from.strftime("%Y-%m-%d %H:%M:%S"),
            "t1": ctx.window_to.strftime("%Y-%m-%d %H:%M:%S"),
            "lab_id": ctx.params.get("lab_id") or None,
        })
        out: list[Finding] = []
        for r in rows:
            expired = int(r["expired_days"] or 0)
            entries = int(r["entry_count"] or 0)
            nd = int(r["needs_double"] or 0)
            out.append(Finding(
                key=f"person_env:{r['person_id']}:{r['lab_id']}",
                check=self.id,
                severity=_severity(expired, nd, entries),  # type: ignore[arg-type]
                title=(
                    f"{r['name']} 资质过期 {expired} 天，"
                    f"窗口内仍有 {r['lab_id']} 通行 {entries} 次"
                ),
                subject_type="person",
                subject_id=str(r["person_id"]),
                subject_label=f"{r['name']}（{r['emp_no']}）",
                evidence=[
                    {"label": "实验室", "value": f"{r['lab_id']} {r['lab_name']}"},
                    {"label": "合格证有效期至", "value": str(r["cert_expire"])},
                    {"label": "已过期", "value": f"{expired} 天"},
                    {"label": "窗口内进入次数", "value": f"{entries} 次"},
                    {"label": "最近通行", "value": str(r["last_entry_at"])},
                ],
                owner=r["mgr_name"] or "",
                owner_hint="实验室负责人",
                suggest=(
                    "核实门禁是否应在资质过期后拦截，并安排复审；"
                    "在此之前建议由负责人确认其操作范围。"
                ),
                links=[{"label": "人员详情", "to": f"/persons/{r['person_id']}"}],
            ))
        return out


CHECK = PersonEnvCheck()
