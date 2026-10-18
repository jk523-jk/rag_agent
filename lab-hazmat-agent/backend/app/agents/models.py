"""Agent 配置：数据模型与校验。

设计边界（重要）：
- 这里存的是**平台配置**，不是实验数据。实验数据仍然只读。
- 配置里没有任何写权限入口：`tools` 只能是 TOOLS 里的只读工具，
  且最终 system_prompt = 服务端固定的 SAFETY_PREFIX + 用户补充，用户改不掉只读约束。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

MAX_NAME = 40
MAX_DESC = 200
MAX_PROMPT = 2000
MAX_TOKENS_LIMIT = 8192

ALLOWED_MODELS = ("qwen-plus", "qwen-max", "qwen-turbo", "qwen-long")
ALLOWED_ICONS = ("shield", "book", "flask")
ALLOWED_STATUS = ("enabled", "disabled")

_ID_RE = re.compile(r"^agt-[a-z0-9]{4,24}$")


class AgentValidationError(ValueError):
    """字段校验失败，携带逐字段错误信息。"""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


@dataclass
class AgentConfig:
    id: str
    name: str
    description: str = ""
    icon: str = "shield"
    model: str = "qwen-plus"
    temperature: float = 0.0
    max_tokens: int = 2048
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    status: str = "enabled"
    is_builtin: bool = False
    updated_at: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AgentConfig":
        return cls(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            description=str(raw.get("description") or ""),
            icon=str(raw.get("icon") or "shield"),
            model=str(raw.get("model") or "qwen-plus"),
            temperature=float(raw.get("temperature") or 0.0),
            max_tokens=int(raw.get("max_tokens") or 2048),
            system_prompt=str(raw.get("system_prompt") or ""),
            tools=[str(t) for t in (raw.get("tools") or [])],
            status=str(raw.get("status") or "enabled"),
            is_builtin=bool(raw.get("is_builtin")),
            updated_at=str(raw.get("updated_at") or ""),
        )

    def to_dict(self, *, with_prompt: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "model": self.model,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "tools": list(self.tools),
            "status": self.status,
            "isBuiltin": self.is_builtin,
            "updatedAt": self.updated_at,
        }
        if with_prompt:
            out["systemPrompt"] = self.system_prompt
        return out


def known_tool_names() -> set[str]:
    """当前注册的只读工具名。延迟导入避免循环依赖。"""
    from app.tools import TOOLS

    return {t.name for t in TOOLS}


def forbidden_tool_names() -> set[str]:
    from app.tools import FORBIDDEN_TOOL_NAMES

    return set(FORBIDDEN_TOOL_NAMES)


def validate_payload(payload: dict[str, Any], *, require_name: bool = True) -> dict[str, str]:
    """返回逐字段错误；空字典表示通过。"""
    errors: dict[str, str] = {}

    if require_name:
        name = str(payload.get("name") or "").strip()
        if not name:
            errors["name"] = "名称不能为空"
        elif len(name) > MAX_NAME:
            errors["name"] = f"名称不超过 {MAX_NAME} 字"

    desc = str(payload.get("description") or "")
    if len(desc) > MAX_DESC:
        errors["description"] = f"描述不超过 {MAX_DESC} 字"

    icon = payload.get("icon", "shield")
    if icon not in ALLOWED_ICONS:
        errors["icon"] = f"图标只能是 {'/'.join(ALLOWED_ICONS)}"

    model = payload.get("model", "qwen-plus")
    if model not in ALLOWED_MODELS:
        errors["model"] = f"模型只能是 {'/'.join(ALLOWED_MODELS)}"

    try:
        temperature = float(payload.get("temperature", 0))
        if not 0 <= temperature <= 1:
            errors["temperature"] = "温度需在 0–1 之间"
    except (TypeError, ValueError):
        errors["temperature"] = "温度必须是数字"

    try:
        max_tokens = int(payload.get("max_tokens", 2048))
        if not 128 <= max_tokens <= MAX_TOKENS_LIMIT:
            errors["max_tokens"] = f"最大输出 Token 需在 128–{MAX_TOKENS_LIMIT} 之间"
    except (TypeError, ValueError):
        errors["max_tokens"] = "最大输出 Token 必须是整数"

    prompt = str(payload.get("system_prompt") or "")
    if len(prompt) > MAX_PROMPT:
        errors["systemPrompt"] = f"系统提示词不超过 {MAX_PROMPT} 字"

    tools = payload.get("tools")
    if tools is None:
        tools = []
    if not isinstance(tools, list):
        errors["tools"] = "工具必须是数组"
    else:
        names = [str(t) for t in tools]
        banned = set(names) & forbidden_tool_names()
        if banned:
            errors["tools"] = f"禁止授予写入类工具：{', '.join(sorted(banned))}"
        else:
            unknown = set(names) - known_tool_names()
            if unknown:
                errors["tools"] = f"未知工具：{', '.join(sorted(unknown))}"

    status = payload.get("status", "enabled")
    if status not in ALLOWED_STATUS:
        errors["status"] = "状态只能是 enabled / disabled"

    return errors


def new_agent_id() -> str:
    """生成 agt-xxxxxx 形式的 id。"""
    import secrets
    import string

    alphabet = string.ascii_lowercase + string.digits
    return "agt-" + "".join(secrets.choice(alphabet) for _ in range(6))


def is_valid_id(agent_id: str) -> bool:
    return bool(_ID_RE.match(agent_id or ""))


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
