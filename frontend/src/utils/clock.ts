// 统一「今天」的来源。
//
// 演示数据（@/mocks/labData）里的日期相对 DEMO_TODAY 编排，直接用系统时间会全部错位；
// 真实数据（MySQL）的种子是按 CURDATE() 生成的，必须用系统时间。
// 页面一律从这里取，不要各自定义常量，否则切模式后判定口径会不一致。
import { DEMO_TODAY } from '@/mocks/labData'

/** true = 走真实后端数据；false = 使用本地演示数据 */
export const USE_BACKEND = true

function fmt(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 用于「是否过期 / 是否逾期」比较的日期锚点（YYYY-MM-DD） */
export const todayIso = USE_BACKEND ? fmt(new Date()) : DEMO_TODAY
