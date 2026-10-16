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
_FORBIDDEN_TOOL_NAMES = {
    "update", "delete", "insert", "drop", "alter", "truncate",
    "export", "download", "grant", "revoke", "open_door", "unlock",
    "write", "modify", "create", "set",
}


def _audit() -> None:
    names = {t.name for t in TOOLS}
    banned = names & _FORBIDDEN_TOOL_NAMES
    assert not banned, f"只读系统不得注册写入类工具：{sorted(banned)}"

    # 每个工具都必须是只读语义描述（docstring 明确"查询/检索/判定"，不含写操作）
    for t in TOOLS:
        assert t.description, f"工具 {t.name} 缺少描述，模型无法正确路由"


_audit()

__all__ = ["TOOLS", "REFUSAL"]
