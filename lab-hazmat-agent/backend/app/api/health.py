"""健康检查。

接云数据库联调时，这一组接口是主要的排障入口：
- GET /api/health        存活 + MySQL 连通性（k8s / docker healthcheck 用这个）
- GET /api/health/detail 连接详情：实际连到的实例版本、库名、账号、是否只读，
                          用来确认没有连错环境（比如误连生产库）
- GET /api/health/ready  就绪探针：MySQL 与 LLM Key 都就绪才返 200
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.agent.graph import active_session_count
from app.core.config import get_settings
from app.db.connection import describe_connection, ping
from app.tools.access_tools import ddl_available

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    ok = await ping()
    return {"status": "ok" if ok else "degraded", "mysql": ok}


@router.get("/health/detail")
async def health_detail() -> dict:
    """连接自检。不返回口令，可安全贴在工单里。"""
    s = get_settings()
    info = await describe_connection()
    return {
        "mysql": info,
        "config": {
            "endpoint": s.mysql_endpoint,
            "user": s.mysql_user,
            "ssl": bool(s.mysql_ssl_args),
            "pool": f"{s.mysql_pool_min}-{s.mysql_pool_max}",
            "connect_timeout": s.mysql_connect_timeout,
        },
        "llm": {"model": s.llm_model, "embed_model": s.embed_model,
                "api_key_set": bool(s.llm_api_key)},
        "chroma_dir": s.chroma_dir,
        "ddl_found": ddl_available(),
        "active_sessions": active_session_count(),
    }


@router.get("/health/ready")
async def ready() -> JSONResponse:
    """就绪探针：不满足条件返回 503，便于容器编排把流量挡在外面。"""
    s = get_settings()
    mysql_ok = await ping()
    llm_ok = bool(s.llm_api_key)
    ready_ = mysql_ok and llm_ok
    body = {
        "ready": ready_,
        "mysql": mysql_ok,
        "llm_api_key": llm_ok,
        "ddl_found": ddl_available(),
    }
    return JSONResponse(body, status_code=200 if ready_ else 503)
