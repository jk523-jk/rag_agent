"""应用入口。

启动策略（针对云数据库联调）：**数据库连不上不让进程起不来**。
原实现 `await init_pool()` 失败会直接抛异常导致 uvicorn 启动失败，容器反复重启，
运维看不到原因。现在改为：连接失败也照常起服，/api/health 返回 degraded 并给出
具体错误类别，`curl /api/health` 就能定位是网络、账号还是 SSL 配置问题。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import build_agent, start_session_reaper, stop_session_reaper
from app.api import chat, health
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.connection import close_pool, init_pool
from app.tools.access_tools import ddl_available

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    log.info("启动 lab-hazmat-agent（实验室安全与资产治理平台）| MySQL=%s ssl=%s chroma=%s",
             s.mysql_endpoint, bool(s.mysql_ssl_args), s.chroma_dir)

    await init_pool()                 # 失败不抛，由 /api/health 暴露状态
    build_agent()
    await start_session_reaper()

    if not ddl_available():
        log.warning("未找到建表脚本（mysql/init/01_schema.sql），"
                    "query_records 将缺少表结构上下文；可用 MYSQL_DDL_PATH 指定")
    if not s.llm_api_key:
        log.warning("LLM_API_KEY 为空，问答与向量检索将失败")

    yield

    await stop_session_reaper()
    await close_pool()


app = FastAPI(title="实验室安全与资产治理智能问答平台", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
