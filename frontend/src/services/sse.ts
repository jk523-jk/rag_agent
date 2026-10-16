// SSE 文本流解析：把缓冲区切成“已完整的事件”和“尚未结束的残片”。
// 后端按 `data: ...\n\n` 输出；网络分包可能把一个事件切成两半，残片必须留给下一轮拼接。
export function parseSse(buffer: string): { events: string[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''

  const events = blocks
    .map((block) =>
      block
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).replace(/^ /, ''))
        .join('\n'),
    )
    .filter((data) => data.length > 0)

  return { events, rest }
}
