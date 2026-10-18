"""Agent 配置的持久化：JSON 文件 + 原子写。

为什么不用数据库：
本项目的 MySQL 账号是**只读**的（`GRANT SELECT ON lab_hazmat.*`），
为了存几条 Agent 配置就去申请写账号，等于把写能力引进只读系统，
代价远大于收益。配置量级极小（个位数到几十条），文件足够。

代价（写清楚，别假装没有）：
- 不支持多副本并发写（本机单进程没问题；多副本部署时应换成数据库或配置中心）
- 需要用锁保证读-改-写不互相覆盖
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from app.agents.models import (
    AgentConfig,
    AgentValidationError,
    is_valid_id,
    new_agent_id,
    now_stamp,
    validate_payload,
)
from app.core.config import get_settings

log = logging.getLogger(__name__)

_LOCK = threading.RLock()
_CACHE: dict[str, Any] | None = None      # {"path": str, "agents": [...]}


def _store_path() -> Path:
    return get_settings().agents_path


def _seed_agents() -> list[dict]:
    """首次启动写入的内置 Agent（与前端原有 4 个保持一致）。"""
    return [
        {
            "id": "agt-access",
            "name": "准入判定助手",
            "description": "判定某人某时能否进入某实验室，逐条校验资质闸、授权闸、双人闸。",
            "icon": "shield",
            "model": "qwen-plus",
            "temperature": 0.0,
            "max_tokens": 2048,
            "system_prompt": "你负责准入判定。用户问「某人能不能进某实验室」时，必须调用 "
                             "check_lab_access 逐条说明三闸结论，不要自己拼 SQL。",
            "tools": ["check_lab_access", "get_person_qualification", "query_records"],
            "status": "enabled",
            "is_builtin": True,
        },
        {
            "id": "agt-policy",
            "name": "规程问答助手",
            "description": "检索实验室安全规程、危化品管理制度与重点试剂 SDS 要点，回答"
                           "「应该怎么做」。",
            "icon": "book",
            "model": "qwen-plus",
            "temperature": 0.0,
            "max_tokens": 2048,
            "system_prompt": "你负责规程与 SDS 问答。所有结论必须来自检索结果，"
                             "查不到就回答「规程中未找到相关规定」，不要用常识补。",
            "tools": ["search_policy"],
            "status": "enabled",
            "is_builtin": True,
        },
        {
            "id": "agt-inventory",
            "name": "台账核查助手",
            "description": "交叉比对台账结存、领用记录与制度条款，输出账物差异结论。",
            "icon": "flask",
            "model": "qwen-plus",
            "temperature": 0.0,
            "max_tokens": 2048,
            "system_prompt": "你负责台账账实核对。必须同时查台账、领用汇总与制度三处，"
                             "优先使用 reconcile_inventory；剧毒品与易制爆只给区间。",
            "tools": ["query_inventory", "reconcile_inventory", "search_policy"],
            "status": "enabled",
            "is_builtin": True,
        },
        {
            "id": "agt-equipment",
            "name": "设备与校准助手",
            "description": "查询设备台账、借还状态与校准到期情况，指出逾期未还与校准过期风险。",
            "icon": "flask",
            "model": "qwen-plus",
            "temperature": 0.0,
            "max_tokens": 2048,
            "system_prompt": "你负责设备与校准。涉及设备必须查库；校准是否过期一律以"
                             "校准有效期字段为准，不许依据状态字段下结论。",
            "tools": ["query_equipment", "check_equipment_loan", "list_calibration_due"],
            "status": "enabled",
            "is_builtin": True,
        },
    ]


def _bootstrap(path: Path) -> dict[str, Any]:
    """文件不存在时写入内置 Agent。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    agents = []
    for raw in _seed_agents():
        raw = dict(raw)
        raw["updated_at"] = stamp
        agents.append(raw)
    data = {"version": 1, "agents": agents}
    _write(path, data)
    log.info("已初始化 Agent 配置文件：%s（内置 %d 个）", path, len(agents))
    return data


def _read(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _bootstrap(path)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Agent 配置文件损坏，重建为内置配置：%s（%s）", path, exc)
        return _bootstrap(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("agents"), list):
        return _bootstrap(path)
    return raw


def _write(path: Path, data: dict[str, Any]) -> None:
    """原子写：先写临时文件再替换，避免进程中断留下半个 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load() -> list[AgentConfig]:
    """读缓存；路径或文件 mtime 变化时重载（支持手工改文件）。"""
    global _CACHE
    path = _store_path()
    mtime = path.stat().st_mtime if path.exists() else 0
    with _LOCK:
        if _CACHE and _CACHE["path"] == str(path) and _CACHE["mtime"] == mtime:
            return _CACHE["agents"]
        data = _read(path)                       # 可能新建文件，mtime 需重新取
        mtime = path.stat().st_mtime if path.exists() else 0
        agents = [AgentConfig.from_dict(a) for a in data["agents"] if a.get("id")]
        _CACHE = {"path": str(path), "mtime": mtime, "agents": agents}
        return agents


def _persist(agents: list[AgentConfig]) -> None:
    global _CACHE
    path = _store_path()
    data = {"version": 1, "agents": [a.__dict__ | {"updated_at": a.updated_at} for a in agents]}
    # dataclass 字段名就是存储字段名（system_prompt / max_tokens / is_builtin）
    _write(path, data)
    _CACHE = {"path": str(path), "mtime": path.stat().st_mtime, "agents": agents}


def list_agents() -> list[AgentConfig]:
    return sorted(_load(), key=lambda a: (not a.is_builtin, a.id))


def get_agent(agent_id: str) -> AgentConfig | None:
    return next((a for a in _load() if a.id == agent_id), None)


def create_agent(payload: dict[str, Any]) -> AgentConfig:
    errors = validate_payload(payload)
    if errors:
        raise AgentValidationError(errors)
    agents = _load()
    agent_id = str(payload.get("id") or "").strip() or new_agent_id()
    if not is_valid_id(agent_id):
        raise AgentValidationError({"id": "id 需形如 agt-xxxxxx"})
    if any(a.id == agent_id for a in agents):
        raise AgentValidationError({"id": "该 id 已存在"})

    cfg = AgentConfig(
        id=agent_id,
        name=str(payload["name"]).strip(),
        description=str(payload.get("description") or ""),
        icon=str(payload.get("icon") or "shield"),
        model=str(payload.get("model") or "qwen-plus"),
        temperature=float(payload.get("temperature") or 0.0),
        max_tokens=int(payload.get("max_tokens") or 2048),
        system_prompt=str(payload.get("system_prompt") or ""),
        tools=[str(t) for t in (payload.get("tools") or [])],
        status=str(payload.get("status") or "enabled"),
        is_builtin=False,
        updated_at=now_stamp(),
    )
    _persist([*agents, cfg])
    log.info("新建 Agent：%s（%s）", cfg.id, cfg.name)
    return cfg


def update_agent(agent_id: str, payload: dict[str, Any]) -> AgentConfig:
    errors = validate_payload(payload)
    if errors:
        raise AgentValidationError(errors)
    agents = _load()
    cfg = next((a for a in agents if a.id == agent_id), None)
    if cfg is None:
        raise KeyError(agent_id)

    cfg.name = str(payload["name"]).strip()
    cfg.description = str(payload.get("description") or "")
    cfg.icon = str(payload.get("icon") or cfg.icon)
    cfg.model = str(payload.get("model") or cfg.model)
    cfg.temperature = float(payload.get("temperature") or 0.0)
    cfg.max_tokens = int(payload.get("max_tokens") or cfg.max_tokens)
    cfg.system_prompt = str(payload.get("system_prompt") or "")
    cfg.tools = [str(t) for t in (payload.get("tools") or [])]
    cfg.status = str(payload.get("status") or cfg.status)
    cfg.updated_at = now_stamp()
    _persist(agents)
    log.info("更新 Agent：%s（工具 %d 个）", cfg.id, len(cfg.tools))
    return cfg


def set_status(agent_id: str, status: str) -> AgentConfig:
    if status not in ("enabled", "disabled"):
        raise AgentValidationError({"status": "状态只能是 enabled / disabled"})
    agents = _load()
    cfg = next((a for a in agents if a.id == agent_id), None)
    if cfg is None:
        raise KeyError(agent_id)
    cfg.status = status
    cfg.updated_at = now_stamp()
    _persist(agents)
    return cfg


def delete_agent(agent_id: str) -> None:
    agents = _load()
    cfg = next((a for a in agents if a.id == agent_id), None)
    if cfg is None:
        raise KeyError(agent_id)
    if cfg.is_builtin:
        raise PermissionError("内置 Agent 不允许删除，可以停用")
    _persist([a for a in agents if a.id != agent_id])
    log.info("删除 Agent：%s", agent_id)


def reset_store() -> None:
    """重建为内置配置（测试与演示重置用）。"""
    global _CACHE
    with _LOCK:
        _CACHE = None
        path = _store_path()
        if path.exists():
            path.unlink()
        _load()
