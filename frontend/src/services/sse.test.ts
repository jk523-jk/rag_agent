import { afterEach, describe, expect, it, vi } from 'vitest'
import { parseSse } from './sse'
import { streamChatFromBackend } from './chatApi'

describe('parseSse', () => {
  it('解析完整事件并保留未结束的残片', () => {
    const { events, rest } = parseSse('data: {"delta":"a"}\n\ndata: {"delta":"b"')
    expect(events).toEqual(['{"delta":"a"}'])
    expect(rest).toBe('data: {"delta":"b"')
  })

  it('兼容 CRLF 分隔符', () => {
    const { events } = parseSse('data: x\r\n\r\n')
    expect(events).toEqual(['x'])
  })

  it('忽略非 data 行', () => {
    const { events } = parseSse('event: message\ndata: hi\n\n')
    expect(events).toEqual(['hi'])
  })
})

function sseResponse(parts: string[]): Response {
  const enc = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const p of parts) controller.enqueue(enc.encode(p))
      controller.close()
    },
  })
  return new Response(body, { status: 200 })
}

describe('streamChatFromBackend', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('事件被网络切成两半时仍能正确拼接', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      sseResponse(['data: {"delta":"你', '好"}\n\ndata: {"delta":"！"}\n\n', 'data: [DONE]\n\n']),
    ))
    const received: string[] = []
    await streamChatFromBackend('q', 'thread-1', 'agt-access', (d) => received.push(d), new AbortController().signal)
    expect(received.join('')).toBe('你好！')
  })

  it('后端返回 error 事件时抛出可读错误', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(['data: {"error":"处理失败，请稍后重试"}\n\n'])))
    await expect(
      streamChatFromBackend('q', 'thread-1', 'agt-access', () => {}, new AbortController().signal),
    ).rejects.toThrow('处理失败，请稍后重试')
  })

  it('HTTP 错误状态直接失败', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 500 })))
    await expect(
      streamChatFromBackend('q', 'thread-1', 'agt-access', () => {}, new AbortController().signal),
    ).rejects.toThrow('HTTP 500')
  })
})
