"""料 × 料：台账与领用不符。

口径必须与 reconcile_inventory 对齐：
- 阈值 = max(loss_threshold_abs, 结存 * loss_threshold_ratio)，来自配置
- 无期初结存时按周转校验（领用超过结存）
- 剧毒品/易制爆一律 high；精确值脱敏走 inventory_tools.to_interval（serializer 层）
"""
from __future__ import annotations

from app.core.config import get_settings
from app.db.connection import fetch_all
from app.workflows.models import CHECK_LABEL, CheckContext, Finding

_SQL = """
SELECT i.item_id, i.chem_name, i.cas_no, i.hazard_class, i.lab_id, i.cabinet_no,
       i.quantity AS book_qty, i.unit,
       COALESCE(SUM(u.quantity), 0)                          AS used_qty,
       COUNT(u.id)                                           AS use_count,
       SUM(CASE WHEN u.witness_id IS NULL THEN 1 ELSE 0 END) AS no_witness_count
FROM hazmat_inventory i
LEFT JOIN hazmat_uses u
       ON u.item_id = i.item_id
      AND u.use_time >= %(t0)s AND u.use_time <= %(t1)s
GROUP BY i.item_id, i.chem_name, i.cas_no, i.hazard_class, i.lab_id, i.cabinet_no,
         i.quantity, i.unit
HAVING (COALESCE(SUM(u.quantity), 0) - i.quantity)
       > GREATEST(%(loss_abs)s, i.quantity * %(loss_ratio)s)
ORDER BY (COALESCE(SUM(u.quantity), 0) - i.quantity) DESC
"""

_SENSITIVE = {"剧毒品", "易制爆"}


class MaterialCheck:
    id = "material"
    label = CHECK_LABEL[id]

    async def run(self, ctx: CheckContext) -> list[Finding]:
        s = get_settings()
        rows = await fetch_all(_SQL, {
            "t0": ctx.window_from.strftime("%Y-%m-%d %H:%M:%S"),
            "t1": ctx.window_to.strftime("%Y-%m-%d %H:%M:%S"),
            "loss_abs": s.loss_threshold_abs,
            "loss_ratio": s.loss_threshold_ratio,
        })
        out: list[Finding] = []
        for r in rows:
            book = float(r["book_qty"] or 0)
            used = float(r["used_qty"] or 0)
            diff = used - book
            sensitive = r["hazard_class"] in _SENSITIVE
            threshold = max(s.loss_threshold_abs, book * s.loss_threshold_ratio)
            if sensitive:
                sev = "high"
            elif diff > 2 * threshold:
                sev = "medium"
            else:
                sev = "low"
            out.append(Finding(
                key=f"material:{r['item_id']}",
                check=self.id,
                severity=sev,  # type: ignore[arg-type]
                title=(
                    f"{r['chem_name']}（{r['lab_id']} {r['cabinet_no'] or '柜位未登记'}）"
                    f"窗口内领用超过结存，疑账物不符"
                ),
                subject_type="item",
                subject_id=str(r["item_id"]),
                subject_label=f"{r['chem_name']}（CAS {r['cas_no'] or '未登记'}）",
                evidence=[
                    {"label": "危险类别", "value": r["hazard_class"]},
                    {"label": "台账结存", "value": f"{book:g}{r['unit']}", "raw": book, "unit": r["unit"], "sensitive": sensitive},
                    {"label": "窗口内领用合计", "value": f"{used:g}{r['unit']}", "raw": used, "unit": r["unit"], "sensitive": sensitive},
                    {"label": "超出量", "value": f"{diff:g}{r['unit']}", "raw": diff, "unit": r["unit"], "sensitive": sensitive},
                    {"label": "损耗阈值", "value": f"±{threshold:.2f}{r['unit']}"},
                ],
                owner="",
                owner_hint="实验室安全负责人",
                suggest="核实台账与领用记录是否漏登、错登；必要时盘点实物。",
                links=[{"label": "药剂管理", "to": "/reagents"}],
            ))
            no_witness = int(r["no_witness_count"] or 0)
            if sensitive and no_witness > 0:
                out.append(Finding(
                    key=f"material_witness:{r['item_id']}",
                    check=self.id,
                    severity="high",
                    title=(
                        f"{r['chem_name']} 属{r['hazard_class']}，"
                        f"窗口内有 {no_witness} 笔领用缺见证人"
                    ),
                    subject_type="item",
                    subject_id=str(r["item_id"]),
                    subject_label=f"{r['chem_name']}（CAS {r['cas_no'] or '未登记'}）",
                    evidence=[
                        {"label": "缺见证人笔数", "value": f"{no_witness} 笔"},
                        {"label": "制度要求", "value": "剧毒品与易制爆须双人领用"},
                    ],
                    owner="",
                    owner_hint="实验室安全负责人",
                    suggest="逐笔核实领用记录，补齐见证人；后续领用严格执行双人。",
                    links=[{"label": "药剂管理", "to": "/reagents"}],
                ))
        return out


CHECK = MaterialCheck()
