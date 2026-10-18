"""限流中间件：防止 Agent 死循环烧钱。

每个 Agent 单独构造一份，避免多个 Agent 共享带状态的中间件实例。
`run_limit / exit_behavior` 参数名随 langchain 版本可能微调，升级后按实际签名核对。
"""
from __future__ import annotations

from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

# 单轮最多 8 次模型调用（多步推理够用，超了就是绕圈）
MODEL_CALL_LIMIT_N = 8

# 单轮最多 12 次工具调用（"逐人校验"这类题会多次调 check_lab_access）
TOOL_CALL_LIMIT_N = 12


def make_middleware() -> list:
    """为单个 Agent 生成一套新的限流中间件。"""
    return [
        ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT_N, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=TOOL_CALL_LIMIT_N, exit_behavior="end"),
    ]


# 兼容旧引用点
MIDDLEWARE = make_middleware()
