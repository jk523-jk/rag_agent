"""巡检模板注册。

模板写死在代码里：三闸顺序、校准口径、脱敏类别都是安全要求，
不允许用户通过配置调换（否则等于允许配出一个错误的安全判定）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowSpec:
    id: str
    name: str
    description: str
    checks: tuple[str, ...]
    window_days: int = 1
    params: tuple[dict, ...] = ()


WORKFLOWS: dict[str, WorkflowSpec] = {
    "ins-daily-risk": WorkflowSpec(
        id="ins-daily-risk",
        name="日终风险巡检",
        description="五类交叉校验全量扫描，输出按严重度排序的风险清单。",
        checks=("person_env", "material", "machine_machine", "machine_person", "double_entry"),
        window_days=1,
    ),
    "ins-access-review": WorkflowSpec(
        id="ins-access-review",
        name="准入复核",
        description="复核指定实验室在时间窗内的通行，找出不应进入的记录。",
        checks=("person_env", "double_entry"),
        window_days=7,
        params=(
            {
                "name": "lab_id",
                "label": "实验室",
                "type": "select",
                "required": False,
                "options": ["LAB-1", "LAB-2", "LAB-3", "LAB-4", "LAB-5"],
            },
        ),
    ),
    "ins-equipment-weekly": WorkflowSpec(
        id="ins-equipment-weekly",
        name="设备周检",
        description="校准到期与借出逾期集中排查。",
        checks=("machine_machine", "machine_person"),
        window_days=7,
        params=(
            {"name": "calibrate_warn_days", "label": "校准预警窗口（天）", "type": "number", "default": 30},
            {"name": "include_category_gap", "label": "同时比对分类标配缺口", "type": "boolean", "default": False},
        ),
    ),
}


def get_workflow(workflow_id: str) -> WorkflowSpec | None:
    return WORKFLOWS.get(workflow_id)


def list_workflows() -> list[WorkflowSpec]:
    return list(WORKFLOWS.values())
