import { parseSse } from '@/services/sse'

// 真实后端的流式对话（契约见开发文档 §8）。仅在 VITE_API_MODE=backend 时由页面调用。
// 使用 fetch 而非 EventSource：EventSource 只支持 GET，无法携带 thread_id。
//
// 事件类型：
//   {"delta": "..."}      增量文本
//   {"replace": "..."}    后端核对后要求替换全文（日期/区间被校正、结论被作废时）
//   {"verify": {...}}     本轮校验结果（issues 供 UI 提示"已校正 N 处"）
//   {"error": "..."}      处理失败
//   data: [DONE]          结束
export interface VerifyInfo {
  ok: boolean
  severity: 'none' | 'low' | 'medium' | 'high'
  issues: { kind: string; claim: string; evidence: string; fixed: boolean }[]
}

export interface ChatHandlers {
  onDelta: (delta: string) => void
  /** 后端要求覆盖已显示的全文（校验后修正） */
  onReplace?: (text: string) => void
  /** 校验明细，用于在气泡上提示"已按查询结果校正" */
  onVerify?: (info: VerifyInfo) => void
}

export async function streamChatFromBackend(
  question: string,
  threadId: string,
  agentId: string,
  handlers: ChatHandlers,
  signal: AbortSignal,
): Promise<void> {
  const resp = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, thread_id: threadId, agent_id: agentId }),
    signal,
  })
  if (!resp.ok) {
    // 后端把 Agent 不存在（404）/ 已停用（403）/ 配置非法（500）都以状态码返回，
    // 这里把 detail 抛给调用方，避免用户看到"空回答"却不知道原因。
    let detail = `服务返回 HTTP ${resp.status}`
    try {
      const body = (await resp.json()) as { detail?: string }
      if (body?.detail) detail = body.detail
    } catch {
      /* 非 JSON 响应 */
    }
    throw new Error(detail)
  }
  if (!resp.body) throw new Error('服务未返回内容')

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += decoder.decode(value, { stream: true })

    const parsed = parseSse(buffer)
    buffer = parsed.rest
    for (const data of parsed.events) {
      if (data === '[DONE]') return
      const obj = JSON.parse(data) as {
        delta?: string
        replace?: string
        verify?: VerifyInfo
        error?: string
      }
      if (obj.error) throw new Error(obj.error)
      if (obj.replace !== undefined) handlers.onReplace?.(obj.replace)
      if (obj.verify) handlers.onVerify?.(obj.verify)
      if (obj.delta) handlers.onDelta(obj.delta)
    }
  }
}
