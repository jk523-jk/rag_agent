"""Agent 装配：按配置构造，而不是全局单例。

改造要点：
- 原来 `build_agent()` 返回**唯一**一个 Agent（固定 prompt + 全部 9 个工具），
  前端「Agent 管理」因此只是界面摆设。
- 现在按 `AgentConfig` 构造：每个 Agent 有独立的模型参数、system prompt、工具白名单。
- 工具白名单由 `tools_for()` 在**服务端**过滤——前端传来的名字一律不可信。
- system prompt 由 `compose_prompt()` 拼装，只读硬规则永远在前面，用户改不掉。

缓存策略：以 (id, updated_at, 工具列表, prompt, 模型参数) 作为指纹。
配置一改，指纹变化，下次请求自动重建，无需重启服务。

会话存储仍是 InMemorySaver（进程内存，只增不减），因此配套 SESSION_TTL 清理任务。
多副本部署时应换成持久化 checkpointer（如 PostgresSaver）。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.middleware import make_middleware
from app.agent.prompts import compose_prompt
from app.agents.models import AgentConfig
from app.agents.store import get_agent as load_agent
from app.core.config import get_settings
from app.tools import tools_for

log = logging.getLogger(__name__)

_DEFAULT_AGENT_ID = "agt-access"

_agents: dict[str, tuple[tuple, Any]] = {}      # agent_id -> (指纹, agent)
_checkpointer = InMemorySaver()
_thread_touched: dict[str, float] = {}          # thread_id -> 最近使用时间戳
_reaper_task: asyncio.Task | None = None


def _fingerprint(cfg: AgentConfig) -> tuple:
    """配置指纹：任何影响行为的字段变化都会导致重建。"""
    return (
        cfg.updated_at,
        cfg.model,
        cfg.temperature,
        cfg.max_tokens,
        cfg.system_prompt,
        tuple(cfg.tools),
    )


def _build_llm(cfg: AgentConfig) -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=cfg.model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        timeout=s.llm_timeout,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )


def get_agent(cfg: AgentConfig):
    """按配置返回 Agent 实例（带指纹缓存）。"""
    stamp = _fingerprint(cfg)
    hit = _agents.get(cfg.id)
    if hit and hit[0] == stamp:
        return hit[1]

    tools = tools_for(cfg.tools)                 # 非法白名单直接抛错，不静默降级
    if not tools:
        log.warning("Agent %s 未授予任何工具，将只能依据提示词作答", cfg.id)

    agent = create_agent(
        model=_build_llm(cfg),
        tools=tools,
        system_prompt=compose_prompt(cfg.system_prompt),
        middleware=make_middleware(),
        checkpointer=_checkpointer,
    )
    _agents[cfg.id] = (stamp, agent)
    log.info("已装配 Agent %s（%s）：模型 %s，温度 %s，工具 %d 个",
             cfg.id, cfg.name, cfg.model, cfg.temperature, len(tools))
    return agent


def resolve_agent(agent_id: str | None) -> AgentConfig:
    """取配置并校验可用性。不可用时抛 LookupError / PermissionError，由 API 层转 HTTP 码。"""
    aid = (agent_id or _DEFAULT_AGENT_ID).strip()
    cfg = load_agent(aid)
    if cfg is None:
        raise LookupError(f"Agent {aid} 不存在")
    if cfg.status != "enabled":
        raise PermissionError(f"Agent「{cfg.name}」已停用")
    return cfg


def build_agent(agent_id: str | None = None):
    """兼容旧调用点：按 id 装配，缺省用默认 Agent。"""
    return get_agent(resolve_agent(agent_id))


def invalidate_agent(agent_id: str) -> None:
    _agents.pop(agent_id, None)


def loaded_agent_ids() -> list[str]:
    return sorted(_agents)


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


__all__ = [
    "get_agent", "resolve_agent", "build_agent", "invalidate_agent", "loaded_agent_ids",
    "agent_config", "touch_thread", "start_session_reaper", "stop_session_reaper",
    "active_session_count",
]
