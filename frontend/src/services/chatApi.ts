import { parseSse } from '@/services/sse'

// 真实后端的流式对话（契约见开发文档 §8）。仅在 VITE_API_MODE=backend 时由页面调用。
// 使用 fetch 而非 EventSource：EventSource 只支持 GET，无法携带 thread_id。
export async function streamChatFromBackend(
  question: string,
  threadId: string,
  agentId: string,
  onDelta: (delta: string) => void,
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
      const obj = JSON.parse(data) as { delta?: string; error?: string }
      if (obj.error) throw new Error(obj.error)
      if (obj.delta) onDelta(obj.delta)
    }
  }
}
