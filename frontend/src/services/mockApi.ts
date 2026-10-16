// 模拟后端服务层。所有函数都是异步的，用来演示加载态；页面组件不得直接访问 mocks。
// 失败场景可通过 options.fail 触发，便于测试错误提示与重试。
import type { RunStep, Workflow, EvalTask, LogEntry } from '@/types'
import { retrievalPresets } from '@/mocks/data'

export interface MockOptions {
  delay?: number
  fail?: boolean
}

export class MockApiError extends Error {}

export function simulate<T>(value: () => T, { delay = 600, fail = false }: MockOptions = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    window.setTimeout(() => {
      if (fail) reject(new MockApiError('模拟故障：服务暂时不可用，请稍后重试（演示数据）'))
      else resolve(value())
    }, delay)
  })
}

export function runRetrieval(
  mode: 'bm25' | 'vector' | 'hybrid',
  opts: MockOptions = {},
) {
  return simulate(() => {
    const bm25 = retrievalPresets.bm25
    const vector = retrievalPresets.vector
    const merged = mode === 'hybrid' ? [...bm25, ...vector] : mode === 'bm25' ? bm25 : vector
    return { bm25: mode === 'vector' ? [] : bm25, vector: mode === 'bm25' ? [] : vector, merged, isMock: true as const }
  }, { delay: 700, ...opts })
}

export function runWorkflow(workflow: Workflow, opts: MockOptions & { failAt?: string } = {}) {
  return simulate((): { steps: RunStep[]; logId: string } => {
    const steps: RunStep[] = []
    for (const node of workflow.nodes) {
      const failed = opts.failAt === node.id
      steps.push({
        nodeId: node.id,
        label: node.label,
        status: failed ? 'failed' : 'success',
        durationMs: 200 + Math.round(Math.random() * 600),
        input: `来自上游节点的输入（${node.type}）`,
        output: failed ? '' : `节点 ${node.type} 输出（模拟）`,
        error: failed ? `模拟失败：节点「${node.label}」执行异常` : undefined,
      })
      if (failed) break
    }
    return { steps, logId: `task-${Math.random().toString(16).slice(2, 8)}` }
  }, { delay: 300, ...opts })
}

export function runEvaluation(name: string, target: string, caseCount: number, opts: MockOptions = {}) {
  return simulate((): EvalTask => ({
    id: `ev-${Date.now()}`,
    name,
    target,
    caseCount,
    progress: 100,
    status: 'success',
    recall: Number((0.8 + Math.random() * 0.15).toFixed(2)),
    relevance: Number((0.82 + Math.random() * 0.12).toFixed(2)),
    faithfulness: Number((0.85 + Math.random() * 0.1).toFixed(2)),
    failures: [],
    isMock: true,
  }), { delay: 1500, ...opts })
}

export function buildLog(partial: Omit<LogEntry, 'id' | 'isMock'>): LogEntry {
  return { ...partial, id: `task-${Math.random().toString(16).slice(2, 8)}`, isMock: true }
}

export function uploadDocument(file: { name: string; size: number }, opts: MockOptions = {}) {
  return simulate(() => ({ name: file.name, sizeKb: Math.max(1, Math.round(file.size / 1024)) }), { delay: 500, ...opts })
}
