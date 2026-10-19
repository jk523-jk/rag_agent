"""巡检运行记录存储：JSON 文件 + 原子写（复制 agents/store.py 的模式）。

MySQL 账号只读，运行记录不能建表；与 agents.json 同属「平台运行数据」边界。
data/runs/index.json   最近 N 次摘要（列表页只读这个）
data/runs/<run_id>.json 完整报告
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.workflows.models import CheckResult, Finding, RunReport

log = logging.getLogger(__name__)

_LOCK = threading.RLock()


def _runs_dir() -> Path:
    d = get_settings().workflow_runs_dir
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # 目录建不出来（磁盘只读/权限不足）时不要炸掉整次巡检：
        # 判定结果比留痕更重要，但必须留下明确告警，不能假装写成功了。
        log.error("巡检记录目录不可用（%s），本次运行将不被保存：%s", d, exc)
        raise
    return d


def _index_path() -> Path:
    return _runs_dir() / "index.json"


def _report_path(run_id: str, directory: Path | None = None) -> Path:
    # 防路径穿越：run_id 只允许安全字符
    safe = "".join(ch for ch in run_id if ch.isalnum() or ch in "-_")
    return (directory or _runs_dir()) / f"{safe}.json"


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _report_to_dict(r: RunReport) -> dict[str, Any]:
    d = r.to_dict()
    d["checks"] = [c.__dict__ for c in r.checks]
    d["findings"] = [f.to_dict() for f in r.findings]
    return d


def _report_from_dict(d: dict[str, Any]) -> RunReport:
    return RunReport(
        run_id=d["run_id"], workflow_id=d["workflow_id"], workflow_name=d["workflow_name"],
        started_at=d["started_at"], finished_at=d["finished_at"], duration_ms=d["duration_ms"],
        status=d["status"], as_of=d["as_of"], params=d.get("params") or {},
        counts=d.get("counts") or {}, incomplete_reason=d.get("incomplete_reason") or "",
        checks=[CheckResult(**c) for c in d.get("checks", [])],
        findings=[Finding(**f) for f in d.get("findings", [])],
    )


def save_report(report: RunReport) -> None:
    s = get_settings()
    with _LOCK:
        _atomic_write(_report_path(report.run_id), _report_to_dict(report))
        index = _read_index()
        index.insert(0, {
            "run_id": report.run_id,
            "workflow_id": report.workflow_id,
            "workflow_name": report.workflow_name,
            "started_at": report.started_at,
            "status": report.status,
            "counts": report.counts,
            "duration_ms": report.duration_ms,
        })
        # 保留最近 N 次，超出删文件
        keep = max(1, s.workflow_run_retention)
        for stale in index[keep:]:
            p = _report_path(stale["run_id"])
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        _atomic_write(_index_path(), index[:keep])


def _read_index() -> list[dict]:
    return _read_index_from(get_settings().workflow_runs_dir)


def _read_index_from(directory: Path) -> list[dict]:
    """纯读取：不建目录、不抛异常。目录不存在或不可读一律当作空历史。

    读取路径不能调 _runs_dir()——那个函数会 mkdir 并在失败时抛错，
    导致「只想查历史」的操作把整次巡检带崩。
    """
    p = directory / "index.json"
    try:
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def list_runs(workflow_id: str | None = None, limit: int = 20) -> list[dict]:
    with _LOCK:
        items = _read_index()
    if workflow_id:
        items = [i for i in items if i["workflow_id"] == workflow_id]
    return items[: max(1, min(limit, 100))]


def load_report(run_id: str) -> RunReport | None:
    directory = get_settings().workflow_runs_dir
    p = _report_path(run_id, directory)
    try:
        if not p.exists():
            return None
        return _report_from_dict(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as exc:
        log.warning("巡检报告损坏 %s：%s", run_id, exc)
        return None


def latest_success_report(workflow_id: str) -> RunReport | None:
    for item in list_runs(workflow_id=workflow_id, limit=10):
        if item["status"] == "success":
            return load_report(item["run_id"])
    return None
