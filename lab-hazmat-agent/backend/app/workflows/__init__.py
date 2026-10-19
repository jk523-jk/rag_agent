"""巡检工作流注册表 + 导入期断言。

与 app/tools/__init__.py 同款护栏：模板引用的 check 必须存在且唯一，
防止有人改了 checks/__init__.py 忘了改 spec，线上 500 才知道。
"""
from __future__ import annotations

from app.workflows.checks import CHECKS
from app.workflows.models import CHECK_LABEL
from app.workflows.spec import WORKFLOWS


def _audit() -> None:
    check_ids = {c.id for c in CHECKS}
    assert len(check_ids) == len(CHECKS), "check id 存在重复"
    for cid in check_ids:
        assert cid in CHECK_LABEL, f"check {cid} 缺少展示名（CHECK_LABEL）"
    for wf in WORKFLOWS.values():
        missing = set(wf.checks) - check_ids
        assert not missing, f"模板 {wf.id} 引用了不存在的 check：{sorted(missing)}"


_audit()

__all__ = ["CHECKS", "CHECK_LABEL", "WORKFLOWS"]
