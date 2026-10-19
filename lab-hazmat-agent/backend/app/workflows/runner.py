"""巡检执行器。

语义（见方案 §2.5）：
- 统一 as_of：一次运行所有 check 共享同一时间快照，SQL 传参不用 CURDATE()。
- 单检查隔离：任一 check 异常记 error，整单转 partial，绝不输出「无风险」。
- 并发：信号量 = workflow_concurrency；总超时 = workflow_timeout_seconds。
- 去重继承：同 key 继承上一成功报告的 first_seen，累计 days_open。
- 互斥：每个 workflow_id 一把锁，重复触发返回 409（由 API 层判断）。
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.db.connection import pool_ready
from app.workflows import CHECKS
from app.workflows.models import (
    CHECK_LABEL,
    CheckContext,
    CheckResult,
    Finding,
    RunReport,
    sort_findings,
)
from app.workflows.spec import WorkflowSpec
from app.workflows.store import latest_success_report, save_report

log = logging.getLogger(__name__)

_LOCKS: dict[str, asyncio.Lock] = {}
_LOCKS_GUARD = asyncio.Lock()


class WorkflowBusyError(RuntimeError):
    """同一模板已有运行在进行。"""


async def _lock_for(workflow_id: str) -> asyncio.Lock:
    async with _LOCKS_GUARD:
        if workflow_id not in _LOCKS:
            _LOCKS[workflow_id] = asyncio.Lock()
        return _LOCKS[workflow_id]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def run_workflow(spec: WorkflowSpec, params: dict | None = None) -> RunReport:
    """同步执行一个巡检模板，返回完整报告（已落盘）。"""
    if not pool_ready():
        raise RuntimeError("数据库连接池不可用，请检查 MYSQL_HOST/账号/网络与 MYSQL_SSL 配置。")

    lock = await _lock_for(spec.id)
    if lock.locked():
        raise WorkflowBusyError(spec.id)
    async with lock:
        return await _run_locked(spec, params or {})


async def _run_locked(spec: WorkflowSpec, params: dict) -> RunReport:
    s = get_settings()
    started = datetime.now().replace(microsecond=0)
    as_of = started
    window_days = int(params.get("window_days") or spec.window_days)
    window_from = as_of - timedelta(days=window_days)
    ctx = CheckContext(as_of=as_of, window_from=window_from, window_to=as_of, params=params)

    run_id = f"run-{started.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
    selected = [c for c in CHECKS if c.id in set(spec.checks)]
    sem = asyncio.Semaphore(max(1, s.workflow_concurrency))

    async def _one(check) -> tuple[str, list[Finding], CheckResult]:
        t0 = time.perf_counter()
        async with sem:
            try:
                findings = await check.run(ctx)
                ms = int((time.perf_counter() - t0) * 1000)
                return check.id, findings, CheckResult(
                    id=check.id, label=check.label, status="ok",
                    duration_ms=ms, count=len(findings),
                )
            except Exception as exc:  # noqa: BLE001
                ms = int((time.perf_counter() - t0) * 1000)
                log.warning("巡检检查 %s 失败：%s: %s", check.id, type(exc).__name__, exc)
                return check.id, [], CheckResult(
                    id=check.id, label=check.label, status="error",
                    duration_ms=ms, count=0, error=f"{type(exc).__name__}: {exc}",
                )

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[_one(c) for c in selected]),
            timeout=s.workflow_timeout_seconds,
        )
    except asyncio.TimeoutError:
        results = []
        for c in selected:
            results.append((c.id, [], CheckResult(
                id=c.id, label=c.label, status="error",
                duration_ms=s.workflow_timeout_seconds * 1000, count=0,
                error="TimeoutError: 整体超时",
            )))

    findings: list[Finding] = []
    check_results: list[CheckResult] = []
    failed_checks: list[str] = []
    for _cid, fs, cr in results:
        findings.extend(fs)
        check_results.append(cr)
        if cr.status == "error":
            failed_checks.append(f"{cr.id}（{cr.error}）")

    # 去重继承：同 key 沿用上一成功报告的 first_seen，累计 days_open
    prev = latest_success_report(spec.id)
    prev_first_seen: dict[str, str] = {}
    if prev:
        for pf in prev.findings:
            prev_first_seen[pf.key] = pf.first_seen or prev.as_of[:10]
    today = as_of.strftime("%Y-%m-%d")
    for f in findings:
        first = prev_first_seen.get(f.key, today)
        f.first_seen = first
        try:
            f.days_open = max(0, (datetime.strptime(today, "%Y-%m-%d")
                                  - datetime.strptime(first, "%Y-%m-%d")).days)
        except ValueError:
            f.days_open = 0

    findings = sort_findings(findings, list(spec.checks))
    counts = {
        "high": sum(1 for f in findings if f.severity == "high"),
        "medium": sum(1 for f in findings if f.severity == "medium"),
        "low": sum(1 for f in findings if f.severity == "low"),
        "total": len(findings),
    }

    finished = datetime.now().replace(microsecond=0)
    status = "partial" if failed_checks else "success"
    incomplete = "" if not failed_checks else "检查失败：" + "；".join(failed_checks)
    report = RunReport(
        run_id=run_id,
        workflow_id=spec.id,
        workflow_name=spec.name,
        started_at=_fmt(started),
        finished_at=_fmt(finished),
        duration_ms=int((finished - started).total_seconds() * 1000),
        status=status,  # type: ignore[arg-type]
        as_of=_fmt(as_of),
        params=params,
        counts=counts,
        checks=check_results,
        findings=findings,
        incomplete_reason=incomplete,
    )
    try:
        save_report(report)
    except OSError as exc:
        # 留痕失败（目录不可写/磁盘满）不应让用户拿不到判定结果，
        # 但必须在日志里说清楚「这次运行没被保存」，否则历史列表会悄悄缺记录。
        log.error("巡检报告保存失败，本次运行不在历史中：%s（%s）", run_id, exc)
    log.info("巡检完成 %s：%s，%d 项（%s）", spec.id, run_id, len(findings), status)
    return report
