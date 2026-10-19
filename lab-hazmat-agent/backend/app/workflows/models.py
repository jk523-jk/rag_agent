"""巡检工作流的数据模型。

与 agent 工具层的关键差异：
- 工具返回**给人/模型看的字符串**；巡检返回**结构化 Finding**，可排序、可去重、可跳转。
- 判定函数不做任何 I/O 之外的动作，时间一律用 ctx.as_of（不传 CURDATE），
  保证离线测试可复现（与 sql_guard 顶层只认 Select/Union 的约束一致）。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

Severity = Literal["high", "medium", "low"]
CheckStatus = Literal["ok", "error", "skipped"]
RunStatus = Literal["success", "partial", "failed"]

CHECK_LABEL: dict[str, str] = {
    "person_env": "人 × 环：资质过期仍通行",
    "material": "料 × 料：台账与领用不符",
    "machine_machine": "机 × 机：在用但校准过期",
    "machine_person": "机 × 人：设备借出逾期",
    "double_entry": "双人闸：要求双人的实验室单人进入",
}

_SEVERITY_RANK: dict[str, int] = {"high": 3, "medium": 2, "low": 1}


def bump(severity: Severity, steps: int = 1) -> Severity:
    """升一级（封顶 high）。"""
    target = min(_SEVERITY_RANK[severity] + steps, 3)
    for name, rank in (("high", 3), ("medium", 2), ("low", 1)):
        if rank == target:
            return name  # type: ignore[return-value]
    return "high"


@dataclass(frozen=True)
class CheckContext:
    """一次运行内所有 check 共享的上下文。as_of 是唯一时间源。"""

    as_of: datetime
    window_from: datetime
    window_to: datetime
    params: dict[str, Any]


@dataclass
class Finding:
    key: str
    check: str
    severity: Severity
    title: str
    subject_type: Literal["person", "equipment", "item", "lab"]
    subject_id: str
    subject_label: str
    evidence: list[dict] = field(default_factory=list)
    owner: str = ""
    owner_hint: str = ""
    suggest: str = ""
    links: list[dict] = field(default_factory=list)
    first_seen: str = ""
    days_open: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckResult:
    id: str
    label: str
    status: CheckStatus
    duration_ms: int
    count: int
    error: str = ""


@dataclass
class RunReport:
    run_id: str
    workflow_id: str
    workflow_name: str
    started_at: str
    finished_at: str
    duration_ms: int
    status: RunStatus
    as_of: str
    params: dict
    counts: dict[str, int]
    checks: list[CheckResult]
    findings: list[Finding]
    incomplete_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Check(Protocol):
    id: str
    label: str

    async def run(self, ctx: CheckContext) -> list[Finding]: ...


def sort_findings(items: list[Finding], check_order: list[str]) -> list[Finding]:
    """高危 > 积压久 > 检查项固定顺序。"""
    order = {cid: i for i, cid in enumerate(check_order)}
    return sorted(
        items,
        key=lambda f: (
            -_SEVERITY_RANK.get(f.severity, 0),
            -f.days_open,
            order.get(f.check, 99),
        ),
    )
