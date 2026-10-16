import { describe, expect, it } from 'vitest'
import { checkSdsSectionIsolation } from './sdsCheck'
import { chunks } from '@/mocks/data'

describe('SDS 小节隔离校验', () => {
  it('演示数据中的 SDS 分块全部通过', () => {
    expect(checkSdsSectionIsolation(chunks)).toEqual([])
  })

  it('应急处置小节混入储存措辞会被标出', () => {
    const bad = chunks.map((c) =>
      c.id === 'ck-002' ? { ...c, text: '泄漏处置：吸附后装入防火柜，远离火源。' } : c,
    )
    const issues = checkSdsSectionIsolation(bad)
    expect(issues).toHaveLength(1)
    expect(issues[0].chunkId).toBe('ck-002')
  })

  it('缺少小节标签的 SDS 分块会被标出', () => {
    const bad = chunks.map((c) => (c.id === 'ck-003' ? { ...c, section: '' } : c))
    expect(checkSdsSectionIsolation(bad).map((i) => i.chunkId)).toEqual(['ck-003'])
  })

  it('规程类分块不参与 SDS 校验', () => {
    const policy = chunks.find((c) => c.meta.kind === 'policy')!
    const withStorage = { ...policy, section: '应急处置', text: '储存于防火柜中' }
    expect(checkSdsSectionIsolation([withStorage])).toEqual([])
  })
})
