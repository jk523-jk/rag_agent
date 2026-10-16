import { parseSse } from '@/services/sse'

// 真实后端的流式对话（契约见开发文档 §8）。仅在 VITE_API_MODE=backend 时由页面调用。
// 使用 fetch 而非 EventSource：EventSource 只支持 GET，无法携带 thread_id。
export async function streamChatFromBackend(
  question: string,
  threadId: string,
  onDelta: (delta: string) => void,
  signal: AbortSignal,
): Promise<void> {
  const resp = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, thread_id: threadId }),
    signal,
  })
  if (!resp.ok || !resp.body) throw new Error(`服务返回 HTTP ${resp.status}`)

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
