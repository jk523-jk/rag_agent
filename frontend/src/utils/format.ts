// 通用格式化与工具函数。时间统一使用演示时钟，避免真实日期造成与模拟数据的错位。
export function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  const s = ms / 1000
  return s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)} m ${Math.round(s % 60)} s`
}

export function newId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

// 深拷贝为纯对象。不能用 structuredClone —— Vue 的响应式对象是 Proxy，会抛 DataCloneError。
export function plainClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function downloadText(filename: string, content: string, type = 'application/json') {
  try {
    const blob = new Blob([content], { type: `${type};charset=utf-8` })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    /* 导出失败时由调用方提示 */
  }
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
