"""问答接口：/api/chat 与 /api/chat/stream（SSE）。

本轮改造：请求体新增 `agent_id`，真正按前端选中的 Agent 执行。
- 未传时回落到 `agt-access`，保证旧调用方不加字段也能用。
- Agent 不存在 → 404；已停用 → 403。**不静默回落到默认 Agent**，
  否则用户以为切换了、实际还在用另一个 Agent，这种"看起来生效其实没生效"最坑。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from app.portal.auth import Principal, system_admin
from fastapi.responses import StreamingResponse
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field

from app.agent.graph import agent_config, get_agent, resolve_agent
from app.agent.verify import VerifyResult, verify_reply
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


def _tool_texts(messages: list) -> list[str]:
    """收集本轮工具返回原文，作为核对证据。"""
    out: list[str] = []
    for m in messages:
        if isinstance(m, ToolMessage) or getattr(m, "type", "") == "tool":
            content = getattr(m, "content", "")
            if isinstance(content, str) and content:
                out.append(content)
    return out


def _verify(text: str, messages: list, question: str) -> VerifyResult:
    return verify_reply(
        text,
        _tool_texts(messages),
        question=question,
        now_text=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# 触发重试的问题类型：模型一次工具都没调，或工具说没查到却给了数值
_RETRY_KINDS = {"no_evidence", "not_found_but_asserted"}

_RETRY_HINT = (
    "【系统校验】上一次回答没有可用的工具查询依据，已作废。"
    "这次必须先调用工具查询，再依据工具返回回答；"
    "如果工具没查到，就直接说明未查到，禁止给出任何具体数量、区间或日期。"
)


async def _run_with_retry(cfg, req: ChatRequest) -> tuple[list, VerifyResult]:
    """跑一轮；若校验发现"回答没有工具依据"，带强指令重试一次。

    为什么要重试而不是只拦截：实测模型会跳过工具直接编答案（约 3 次里出现 2 次），
    只拦截会让用户拿不到任何结果。重试一次能把大多数情况救回来。
    """
    agent = get_agent(cfg)
    messages = [{"role": "user", "content": req.question}]
    result = await agent.ainvoke({"messages": messages}, config=agent_config(req.thread_id))
    msgs = result["messages"]
    verified = _verify(msgs[-1].content, msgs, req.question)

    if any(i.kind in _RETRY_KINDS for i in verified.issues):
        log.warning("回答缺少工具依据，带强指令重试一次 agent=%s", cfg.id)
        retry_msgs = [{"role": "user", "content": f"{req.question}\n\n{_RETRY_HINT}"}]
        result = await agent.ainvoke(
            {"messages": retry_msgs}, config=agent_config(f"{req.thread_id}-retry")
        )
        msgs = result["messages"]
        verified = _verify(msgs[-1].content, msgs, req.question)
    return msgs, verified


@router.post("/chat")
async def chat(req: ChatRequest, p: Principal = Depends(system_admin)) -> dict:
    req.thread_id = f"{p.id}:{req.thread_id}"
    refusal = detect_control_intent(req.question)
    if refusal:
        return {"reply": refusal, "refused": True, "agent_id": req.agent_id}

    cfg = _load_agent(req)
    _messages, verified = await _run_with_retry(cfg, req)
    return {
        "reply": verified.reply,
        "refused": False,
        "agent_id": cfg.id,
        "agent_name": cfg.name,
        "verify": verified.to_dict(),
    }


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, p: Principal = Depends(system_admin)) -> StreamingResponse:
    req.thread_id = f"{p.id}:{req.thread_id}"
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
            collected: list[str] = []
            tool_texts: list[str] = []
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
                    # 工具返回仍要收集起来做校验证据，但**不发**给客户端
                    content = getattr(chunk, "content", "")
                    if isinstance(content, str) and content:
                        tool_texts.append(content)
                    continue
                text = getattr(chunk, "content", "") or ""
                if isinstance(text, list):               # 多模态分块，取文本部分
                    text = "".join(
                        p.get("text", "") for p in text
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                if text:
                    collected.append(text)
                    yield _sse({"delta": text})

            # 流结束后统一核对：能改就下发替换事件，前端覆盖已显示的内容
            full = "".join(collected)
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
            verified = verify_reply(full, tool_texts, question=req.question, now_text=now_text)

            # 模型跳过了工具直接编答案：带强指令重跑一次，用重跑结果整体替换
            if any(i.kind in _RETRY_KINDS for i in verified.issues):
                log.warning("流式回答缺少工具依据，带强指令重试一次 agent=%s", cfg.id)
                retry_result = await get_agent(cfg).ainvoke(
                    {"messages": [{"role": "user", "content": f"{req.question}\n\n{_RETRY_HINT}"}]},
                    config=agent_config(f"{req.thread_id}-retry"),
                )
                retry_msgs = retry_result["messages"]
                verified = verify_reply(
                    retry_msgs[-1].content,
                    _tool_texts(retry_msgs),
                    question=req.question,
                    now_text=datetime.now().strftime("%Y-%m-%d %H:%M"),
                )
                yield _sse({"replace": verified.reply})
            elif verified.reply.strip() != full.strip():
                log.warning("回答已校正 agent=%s severity=%s issues=%d",
                            cfg.id, verified.severity, len(verified.issues))
                yield _sse({"replace": verified.reply})

            if verified.issues:
                yield _sse({"verify": verified.to_dict()})
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
