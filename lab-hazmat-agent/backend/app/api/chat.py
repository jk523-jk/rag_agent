"""问答接口：/api/chat 与 /api/chat/stream（SSE）。

本轮改造：请求体新增 `agent_id`，真正按前端选中的 Agent 执行。
- 未传时回落到 `agt-access`，保证旧调用方不加字段也能用。
- Agent 不存在 → 404；已停用 → 403。**不静默回落到默认 Agent**，
  否则用户以为切换了、实际还在用另一个 Agent，这种"看起来生效其实没生效"最坑。
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import agent_config, get_agent, resolve_agent
from app.core.guard import detect_control_intent

log = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    thread_id: str = Field(min_length=4, max_length=64)
    agent_id: str = Field(default="agt-access", min_length=4, max_length=32)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _load_agent(req: ChatRequest):
    """解析并校验 Agent。异常统一转成 HTTP 码。"""
    try:
        return resolve_agent(req.agent_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:                 # 工具白名单被改坏
        log.error("Agent %s 配置非法：%s", req.agent_id, exc)
        raise HTTPException(status_code=500, detail=f"该 Agent 配置有误：{exc}") from exc


@router.post("/chat")
async def chat(req: ChatRequest) -> dict:
    refusal = detect_control_intent(req.question)
    if refusal:
        return {"reply": refusal, "refused": True, "agent_id": req.agent_id}

    cfg = _load_agent(req)
    result = await get_agent(cfg).ainvoke(
        {"messages": [{"role": "user", "content": req.question}]},
        config=agent_config(req.thread_id),
    )
    return {
        "reply": result["messages"][-1].content,
        "refused": False,
        "agent_id": cfg.id,
        "agent_name": cfg.name,
    }


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    # 控制类拦截与 Agent 校验都放在建流之前：错误要以 HTTP 状态码返回，
    # 而不是先 200 再在流里吐一个 error 事件。
    refusal = detect_control_intent(req.question)
    cfg = None if refusal else _load_agent(req)

    async def event_gen():
        if refusal:
            yield _sse({"delta": refusal})
            yield _sse({"refused": True})
            yield "data: [DONE]\n\n"
            return

        try:
            async for chunk, meta in get_agent(cfg).astream(
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
            log.exception("流式问答失败 agent=%s thread=%s", cfg.id if cfg else "-", req.thread_id)
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
