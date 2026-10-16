// 工作台趋势图的固定演示数据（模拟，不代表真实对话量）。
export interface TrendPoint {
  date: string
  value: number
}

const SEED_7 = [182, 205, 198, 233, 219, 247, 200]
const SEED_30 = [
  121, 134, 128, 150, 163, 158, 171, 166, 180, 177, 169, 188, 194, 185, 201,
  196, 207, 193, 210, 218, 205, 224, 231, 219, 238, 226, 244, 251, 239, 258,
]

function series(values: number[], endDay = '2026-10-15'): TrendPoint[] {
  const end = new Date(`${endDay}T00:00:00`)
  return values.map((value, i) => {
    const d = new Date(end)
    d.setDate(end.getDate() - (values.length - 1 - i))
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return { date: `${mm}-${dd}`, value }
  })
}

export const chatTrend: Record<7 | 30, TrendPoint[]> = {
  7: series(SEED_7),
  30: series(SEED_30),
}
