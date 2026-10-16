"""问答接口：/api/chat 与 /api/chat/stream（SSE）。"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import agent_config, build_agent
from app.core.guard import detect_control_intent

log = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    thread_id: str = Field(min_length=4, max_length=64)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest) -> dict:
    refusal = detect_control_intent(req.question)
    if refusal:
        return {"reply": refusal, "refused": True}       # 控制类指令：不进 Agent

    result = await build_agent().ainvoke(
        {"messages": [{"role": "user", "content": req.question}]},
        config=agent_config(req.thread_id),
    )
    return {"reply": result["messages"][-1].content, "refused": False}


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    async def event_gen():
        refusal = detect_control_intent(req.question)
        if refusal:
            yield _sse({"delta": refusal})
            yield _sse({"refused": True})
            yield "data: [DONE]\n\n"
            return

        try:
            async for chunk, meta in build_agent().astream(
                {"messages": [{"role": "user", "content": req.question}]},
                config=agent_config(req.thread_id),
                stream_mode="messages",
            ):
                # 只转发最终回答。工具调用与工具返回的中间文本不能流向客户端——
                # 那会把 SQL、原始人员行踪流水吐到前端，与"不回放逐条流水"的
                # 隐私约束冲突。langgraph 在 meta 里用 langgraph_node 标注来源。
                node = (meta or {}).get("langgraph_node", "")
                if "tools" in str(node):
                    continue
                text = getattr(chunk, "content", "") or ""
                if isinstance(text, list):               # 多模态分块，取文本部分
                    text = "".join(
                        p.get("text", "") for p in text
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                if text:
                    yield _sse({"delta": text})
        except Exception as exc:                          # noqa: BLE001
            log.exception("流式问答失败 thread=%s", req.thread_id)
            yield _sse({"error": f"处理失败（{type(exc).__name__}），请稍后重试或换个问法。"})
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",                     # 关掉 nginx 缓冲，否则流式会一次性吐完
        },
    )
