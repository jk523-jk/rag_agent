"""巡检工作流 API。只读：运行只产生平台侧 JSON 记录，不写业务库。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.connection import pool_ready
from app.workflows import runner
from app.workflows.serializer import serialize_report
from app.workflows.spec import get_workflow, list_workflows
from app.workflows.store import list_runs, load_report

router = APIRouter(prefix="/workflows", tags=["workflows"])
log = logging.getLogger("app.api.workflows")


class RunBody(BaseModel):
    params: dict | None = None
    audience: str = "admin"


@router.get("")
def workflows() -> dict:
    return {
        "workflows": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "checks": list(w.checks),
                "windowDays": w.window_days,
                "params": list(w.params),
            }
            for w in list_workflows()
        ]
    }


@router.post("/{workflow_id}/run")
async def run(workflow_id: str, body: RunBody | None = None):
    spec = get_workflow(workflow_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"巡检模板不存在：{workflow_id}")
    if not pool_ready():
        raise HTTPException(status_code=503, detail="数据库未就绪，请查看 /api/health")
    body = body or RunBody()
    audience = body.audience if body.audience in ("admin", "agent") else "admin"
    try:
        report = await runner.run_workflow(spec, body.params or {})
    except runner.WorkflowBusyError:
        raise HTTPException(status_code=409, detail="该巡检正在运行中，请稍后重试")
    return serialize_report(report, audience)


@router.get("/runs")
def runs(workflow_id: str | None = None, limit: int = Query(20, ge=1, le=100)) -> dict:
    return {"runs": list_runs(workflow_id=workflow_id, limit=limit)}


@router.get("/runs/{run_id}")
def run_detail(run_id: str, audience: str = Query("admin")):
    report = load_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"运行记录不存在：{run_id}")
    aud = audience if audience in ("admin", "agent") else "admin"
    return serialize_report(report, aud)
