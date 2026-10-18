"""Agent 配置接口：CRUD + 启停。

边界说明：
- 这是**平台配置**的写接口，不触碰实验数据（那些仍然只读）。
- 工具白名单在这里只做格式校验；真正的强制执行在 `tools_for()`
  （即使绕过 API 直接改 JSON 文件，装配时也会被拦下）。
- 配置变更后调用 `invalidate_agent()`，下次请求按新配置重建 Agent。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.graph import invalidate_agent
from app.agents.models import AgentValidationError
from app.agents.store import (
    create_agent,
    delete_agent,
    get_agent,
    list_agents,
    set_status,
    update_agent,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=200)
    icon: str = Field(default="shield", max_length=16)
    model: str = Field(default="qwen-plus", max_length=40)
    temperature: float = Field(default=0.0, ge=0, le=1)
    max_tokens: int = Field(default=2048, ge=128, le=8192)
    system_prompt: str = Field(default="", max_length=2000)
    tools: list[str] = Field(default_factory=list)
    status: str = Field(default="enabled", max_length=16)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(enabled|disabled)$")


def _payload(body: AgentIn) -> dict:
    return {
        "name": body.name,
        "description": body.description,
        "icon": body.icon,
        "model": body.model,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "system_prompt": body.system_prompt,
        "tools": body.tools,
        "status": body.status,
    }


def _bad_request(exc: AgentValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail={"message": "参数校验失败", "errors": exc.errors})


@router.get("")
async def list_agents_api() -> dict:
    agents = list_agents()
    return {
        "agents": [a.to_dict(with_prompt=False) for a in agents],
        "count": len(agents),
        "enabled": sum(1 for a in agents if a.status == "enabled"),
    }


@router.get("/{agent_id}")
async def get_agent_api(agent_id: str) -> dict:
    cfg = get_agent(agent_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")
    return cfg.to_dict(with_prompt=True)


@router.post("", status_code=201)
async def create_agent_api(body: AgentIn) -> dict:
    try:
        cfg = create_agent(_payload(body))
    except AgentValidationError as exc:
        raise _bad_request(exc) from exc
    invalidate_agent(cfg.id)
    return cfg.to_dict(with_prompt=True)


@router.put("/{agent_id}")
async def update_agent_api(agent_id: str, body: AgentIn) -> dict:
    try:
        cfg = update_agent(agent_id, _payload(body))
    except AgentValidationError as exc:
        raise _bad_request(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在") from exc
    invalidate_agent(agent_id)                 # 让下一次请求按新配置重建
    return cfg.to_dict(with_prompt=True)


@router.post("/{agent_id}/status")
async def set_status_api(agent_id: str, body: StatusIn) -> dict:
    try:
        cfg = set_status(agent_id, body.status)
    except AgentValidationError as exc:
        raise _bad_request(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在") from exc
    invalidate_agent(agent_id)
    return cfg.to_dict(with_prompt=False)


@router.delete("/{agent_id}")
async def delete_agent_api(agent_id: str) -> dict:
    try:
        delete_agent(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    invalidate_agent(agent_id)
    return {"deleted": agent_id}
