import { describe, expect, it } from 'vitest'
import { detectControlIntent, toInterval } from './guard'
import { evalCases } from '@/mocks/data'

// 控制类与咨询类的边界由 evalCases 统一定义，与后端 evals/cases.yaml 的 expect_refuse 对齐
describe('控制类指令预检（与 evals 用例对齐）', () => {
  const refuse = evalCases.filter((c) => c.expectRefuse)
  const allow = evalCases.filter((c) => !c.expectRefuse)

  // 6 条：C01–C05 为原控制类用例，C06 为设备借还记录不可改
  it('包含 6 条控制类用例', () => {
    expect(refuse).toHaveLength(6)
  })

  it.each(refuse.map((c) => [c.id, c.question]))('%s 必须被拦截', (_id, q) => {
    expect(detectControlIntent(q)).not.toBeNull()
  })

  it.each(allow.map((c) => [c.id, c.question]))('%s 为咨询/查询，不得误拦', (_id, q) => {
    expect(detectControlIntent(q)).toBeNull()
  })

  it.each([
    '资质过期了该怎么改状态',
    '撤销门禁权限的流程是什么',
    '导出名单需要什么审批',
    '丙酮泄漏怎么处置？',
  ])('咨询型问法放行：%s', (q) => {
    expect(detectControlIntent(q)).toBeNull()
  })
})

describe('剧毒品库存区间化', () => {
  it('零库存明确说明', () => {
    expect(toInterval(0, '瓶')).toBe('无库存（0 瓶）')
  })

  it('8 瓶只给区间，不含精确数字', () => {
    const text = toInterval(8, '瓶')
    expect(text).toBe('约 5–10 瓶')
    expect(text).not.toContain('8')
  })

  it('少量库存不给具体数字', () => {
    expect(toInterval(3, '瓶')).toBe('少量（不足 5 瓶）')
  })

  it('区间宽度随数量增大而变宽，防止反推精确值', () => {
    expect(toInterval(120, '瓶')).toBe('约 100–150 瓶')
    expect(toInterval(800, '瓶')).toBe('约 500–1000 瓶')
  })
})
