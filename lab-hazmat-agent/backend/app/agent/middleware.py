"""限流中间件：防止 Agent 死循环烧钱。

run_limit / exit_behavior 参数名随 langchain 版本可能微调，安装后按实际签名核对一次。
"""
from __future__ import annotations

from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

# 单轮最多 8 次模型调用（多步推理够用，超了就是绕圈）
MODEL_CALL_LIMIT = ModelCallLimitMiddleware(run_limit=8, exit_behavior="end")

# 单轮最多 12 次工具调用（"逐人校验"这类题会多次调 check_lab_access）
TOOL_CALL_LIMIT = ToolCallLimitMiddleware(run_limit=12, exit_behavior="end")

MIDDLEWARE = [MODEL_CALL_LIMIT, TOOL_CALL_LIMIT]
