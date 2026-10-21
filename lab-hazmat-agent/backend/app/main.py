"""应用入口。

启动策略（针对云数据库联调）：**数据库连不上不让进程起不来**。
原实现 `await init_pool()` 失败会直接抛异常导致 uvicorn 启动失败，容器反复重启，
运维看不到原因。现在改为：连接失败也照常起服，/api/health 返回 degraded 并给出
具体错误类别，`curl /api/health` 就能定位是网络、账号还是 SSL 配置问题。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import start_session_reaper, stop_session_reaper
from app.agents.store import list_agents
from app.api import agents, chat, data, health, workflows
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.connection import close_pool, init_pool
from app.tools.access_tools import ddl_available
from app.portal import auth as portal_auth, api as portal_api
from app.portal.auth import system_admin

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    log.info("启动 实验室智能管理agent | MySQL=%s ssl=%s chroma=%s",
             s.mysql_endpoint, bool(s.mysql_ssl_args), s.chroma_path)

    if s.business_data_source == "mysql":
        await init_pool()             # 应用数据模式不依赖 MySQL 连接
    # Agent 改为按需装配（get_agent）：启动时只做配置自检与日志，不预先建实例。
    try:
        items = list_agents()
        log.info("Agent 配置就绪：%d 个（启用 %d）｜%s",
                 len(items), sum(1 for a in items if a.status == "enabled"), s.agents_path)
    except Exception as exc:                                  # noqa: BLE001
        log.error("Agent 配置加载失败：%s: %s", type(exc).__name__, exc)
    await start_session_reaper()

    if not ddl_available():
        log.warning("未找到建表脚本（mysql/init/01_schema.sql），"
                    "query_records 将缺少表结构上下文；可用 MYSQL_DDL_PATH 指定")
    if not s.llm_api_key:
        log.warning("LLM_API_KEY 为空，问答与向量检索将失败")

    yield

    await stop_session_reaper()
    await close_pool()


app = FastAPI(title="实验室智能管理agent", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(health.router, prefix="/api")
app.include_router(portal_auth.router, prefix="/api")
app.include_router(portal_api.router, prefix="/api")
app.include_router(chat.router, prefix="/api", dependencies=[Depends(system_admin)])
app.include_router(data.router, prefix="/api")
app.include_router(agents.router, prefix="/api", dependencies=[Depends(system_admin)])
app.include_router(workflows.router, prefix="/api", dependencies=[Depends(system_admin)])


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response
