"""报告序列化与脱敏出口。

audience=admin（默认）：与 api/data.py 同口径，管理控制台看完整值。
audience=agent：凡 evidence 标了 sensitive=true 的条目，精确值一律走
inventory_tools.to_interval 区间化——与工具层同一脱敏函数，避免两套口径。
"""
from __future__ import annotations

from typing import Any

from app.tools.inventory_tools import to_interval
from app.workflows.models import RunReport

_MASK_NOTE = "（该类物品精确数量不予提供，如需精确值请联系实验室安全负责人）"


def _mask_evidence(ev: dict[str, Any]) -> dict[str, Any]:
    if not ev.get("sensitive") or "raw" not in ev:
        return {k: v for k, v in ev.items() if k not in ("raw", "sensitive")}
    try:
        masked = to_interval(float(ev["raw"]), str(ev.get("unit") or ""))
    except (TypeError, ValueError):
        masked = "已按区间处理，不提供精确值"
    out = {k: v for k, v in ev.items() if k not in ("raw", "unit", "sensitive")}
    out["value"] = masked + _MASK_NOTE if masked != "无库存" else masked
    return out


def serialize_report(report: RunReport, audience: str = "admin") -> dict[str, Any]:
    d = report.to_dict()
    d["checks"] = [c.__dict__ for c in report.checks]
    findings = []
    for f in report.findings:
        fd = f.to_dict()
        if audience == "agent":
            fd["evidence"] = [_mask_evidence(ev) for ev in fd.get("evidence", [])]
        else:
            fd["evidence"] = [
                {k: v for k, v in ev.items() if k not in ("raw", "sensitive")}
                for ev in fd.get("evidence", [])
            ]
        findings.append(fd)
    d["findings"] = findings
    return d
