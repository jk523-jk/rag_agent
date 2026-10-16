// LocalStorage 封装：带版本号，损坏或版本不兼容时安全回退到默认值，所有读写都 try/catch。
// 版本 2：实验室管理重构，workspace 结构由 RAG（知识库/文档/分块）改为实验室领域，
// 旧存档一律回退为演示数据。
export const STORAGE_VERSION = 2

interface Envelope<T> {
  version: number
  data: T
}

export function loadState<T>(key: string, fallback: T, validate?: (v: unknown) => v is T): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Envelope<T>
    if (parsed?.version !== STORAGE_VERSION) return fallback
    if (validate && !validate(parsed.data)) return fallback
    return parsed.data
  } catch {
    return fallback
  }
}

export function saveState<T>(key: string, data: T): void {
  try {
    window.localStorage.setItem(key, JSON.stringify({ version: STORAGE_VERSION, data } satisfies Envelope<T>))
  } catch {
    // 隐私模式或配额超限：静默降级，页面仍可用
  }
}

export function removeState(key: string): void {
  try {
    window.localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}
