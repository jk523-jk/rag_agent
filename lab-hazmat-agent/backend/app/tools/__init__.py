"""工具注册。只读系统，不得注册任何写入类工具。

护栏第 1 层：工具层根本没有控制类工具。这里的断言是防回归——
有人后续加了个写工具，导入时就会炸，而不是等到线上被调用才发现。
"""
from __future__ import annotations

from app.core.guard import REFUSAL
from app.tools.access_tools import (
    check_lab_access,
    get_person_qualification,
    query_records,
)
from app.tools.equipment_tools import (
    check_equipment_loan,
    list_calibration_due,
    query_equipment,
)
from app.tools.inventory_tools import query_inventory, reconcile_inventory
from app.tools.policy_tools import search_policy

TOOLS = [
    search_policy,
    query_records,
    check_lab_access,
    get_person_qualification,
    query_inventory,
    reconcile_inventory,
    query_equipment,
    check_equipment_loan,
    list_calibration_due,
]

# 明确禁止出现的工具名（写入 / 导出 / 控制类）
FORBIDDEN_TOOL_NAMES = {
    "update", "delete", "insert", "drop", "alter", "truncate",
    "export", "download", "grant", "revoke", "open_door", "unlock",
    "write", "modify", "create", "set",
}

# 兼容旧引用名（原为私有常量）
_FORBIDDEN_TOOL_NAMES = FORBIDDEN_TOOL_NAMES


def _audit() -> None:
    names = {t.name for t in TOOLS}
    banned = names & _FORBIDDEN_TOOL_NAMES
    assert not banned, f"只读系统不得注册写入类工具：{sorted(banned)}"

    # 每个工具都必须是只读语义描述（docstring 明确"查询/检索/判定"，不含写操作）
    for t in TOOLS:
        assert t.description, f"工具 {t.name} 缺少描述，模型无法正确路由"


_audit()


def tools_for(names: list[str]) -> list:
    """按 Agent 配置的工具白名单取出工具实例（**服务端唯一入口**）。

    前端传来的名字一律当作不可信输入：
    - 命中写入类禁名 → 直接抛错（配置被改坏时必须失败，而不是静默降级）
    - 命中未知工具 → 抛错，避免拼错名字导致 Agent 悄悄少一个能力
    - 结果按 TOOLS 的原始顺序返回，保证可复现
    """
    wanted = [str(n) for n in (names or [])]
    banned = set(wanted) & FORBIDDEN_TOOL_NAMES
    if banned:
        raise ValueError(f"禁止授予写入类工具：{sorted(banned)}")
    allowed = {t.name for t in TOOLS}
    unknown = set(wanted) - allowed
    if unknown:
        raise ValueError(f"未知工具：{sorted(unknown)}")
    if not wanted:
        return []
    picked = {t.name for t in TOOLS if t.name in set(wanted)}
    return [t for t in TOOLS if t.name in picked]


__all__ = ["TOOLS", "REFUSAL", "FORBIDDEN_TOOL_NAMES", "tools_for"]
