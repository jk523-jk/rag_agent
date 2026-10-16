import type { Chunk } from '@/types'

// 应急处置小节里不允许出现的储存类措辞（红线 1：SDS 按小节隔离，不能串段）
const STORAGE_TERMS = /储存|存放|防火柜|密封保存/

export interface SdsIssue {
  chunkId: string
  message: string
}

// 对 SDS 分块做前端侧的小节隔离校验：只做提示，真正的切分正确性以后端入库前的人工抽查为准
export function checkSdsSectionIsolation(chunks: Chunk[]): SdsIssue[] {
  const issues: SdsIssue[] = []
  for (const c of chunks) {
    if (c.meta.kind !== 'sds') continue
    if (!c.section) {
      issues.push({ chunkId: c.id, message: '缺少小节标签，无法确认是否隔离' })
      continue
    }
    if (c.section === '应急处置' && STORAGE_TERMS.test(c.text)) {
      issues.push({ chunkId: c.id, message: '应急处置小节中出现储存类措辞，疑似串段' })
    }
  }
  return issues
}
