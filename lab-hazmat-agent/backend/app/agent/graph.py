"""Agent 装配：create_agent + 工具 + system prompt + 中间件 + checkpointer。

会话存储用 InMemorySaver（进程内存）。它**只增不减**——会话数随访问累积，
长期运行会持续吃内存。因此这里配套一个按 SESSION_TTL_SECONDS 过期清理的后台任务
（start_session_reaper）。多副本部署时应换成持久化 checkpointer（如 PostgresSaver），
否则同一 thread_id 的请求落到不同副本会丢失上下文。
"""
from __future__ import annotations

import asyncio
import logging
import time

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.middleware import MIDDLEWARE
from app.agent.prompts import SYSTEM_PROMPT
from app.core.config import get_settings
from app.tools import TOOLS

log = logging.getLogger(__name__)

_agent = None
_checkpointer = InMemorySaver()
_thread_touched: dict[str, float] = {}          # thread_id -> 最近使用时间戳
_reaper_task: asyncio.Task | None = None


def build_agent():
    global _agent
    if _agent is not None:
        return _agent

    s = get_settings()
    llm = ChatOpenAI(
        model=s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        timeout=s.llm_timeout,
        temperature=0,
    )
    _agent = create_agent(
        model=llm,
        tools=TOOLS,                      # create_agent 的工具选择本身就是路由
        system_prompt=SYSTEM_PROMPT,
        middleware=MIDDLEWARE,
        checkpointer=_checkpointer,       # 短期会话；旧版本别名为 MemorySaver
    )
    return _agent


def agent_config(thread_id: str) -> dict:
    touch_thread(thread_id)
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 25}


def touch_thread(thread_id: str) -> None:
    """记录会话活跃时间，供过期清理使用。"""
    _thread_touched[thread_id] = time.monotonic()


async def _reap_expired() -> None:
    """删除超过 TTL 未活动的会话，释放 checkpointer 占用的内存。"""
    ttl = get_settings().session_ttl_seconds
    if ttl <= 0:
        return
    now = time.monotonic()
    expired = [tid for tid, ts in _thread_touched.items() if now - ts > ttl]
    for tid in expired:
        _thread_touched.pop(tid, None)
        try:
            await _checkpointer.adelete_thread(tid)
        except Exception as exc:                                  # noqa: BLE001
            log.debug("会话清理失败 thread=%s：%s", tid, type(exc).__name__)
    if expired:
        log.info("已清理 %d 个过期会话（TTL %ds），在线会话 %d 个",
                 len(expired), ttl, len(_thread_touched))


async def start_session_reaper() -> None:
    """随应用生命周期启动后台清理任务。"""
    global _reaper_task
    if _reaper_task is not None and not _reaper_task.done():
        return

    async def loop() -> None:
        interval = max(60, get_settings().session_ttl_seconds // 4)
        while True:
            try:
                await asyncio.sleep(interval)
                await _reap_expired()
            except asyncio.CancelledError:
                raise
            except Exception as exc:                              # noqa: BLE001
                log.warning("会话清理任务异常：%s: %s", type(exc).__name__, exc)

    _reaper_task = asyncio.create_task(loop(), name="session-reaper")
    log.info("会话清理任务已启动，TTL=%ds", get_settings().session_ttl_seconds)


async def stop_session_reaper() -> None:
    global _reaper_task
    if _reaper_task is not None:
        _reaper_task.cancel()
        try:
            await _reaper_task
        except (asyncio.CancelledError, Exception):               # noqa: BLE001
            pass
        _reaper_task = None


def active_session_count() -> int:
    return len(_thread_touched)
