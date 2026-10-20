// 控制类指令预检：与后端 core/guard.py 保持一致（前端只做提示，真正的拦截在后端三层）。
//
// ⚠ 这是一个正则 denylist，原理上不可能完备（"开除/更新/变更"这类动词总会有漏网的）。
// 它是第一道便宜的粗筛，兜底靠后端 system prompt + 只读 SQL 护栏 + 只读数据库账号。
//
// 历史修正：
// 原实现把「能否/可以/需要/应当」当作**放行**依据，但情态词不区分咨询与请求——
// 「能否把王景尧的门禁权限注销掉」是对系统的写请求，却被判为咨询放行。
// 现已把情态词从放行词表移除，并改为「控制意图优先、咨询作例外」的判定顺序。
export const CONTROL_REFUSAL =
  '本系统是只读问答系统，只有查询权限，不能修改资质、台账、授权或导出名单，也不能开门放行。\n' +
  '这类操作请通过实验室安全负责人或学校安全管理平台走人工审批流程办理。\n' +
  '我可以帮你查：某人的资质状态与有效期、某人某时能否进入某实验室、某实验室某时段的进入情况、台账与领用记录是否一致。'

// 数据改动 / 门禁控制的动词
const VERBS =
  '改|修改|更正|改成|改到|变更|调整|更新|延|续期|续签|展期|顺延|' +
  '撤销|吊销|注销|解绑|解除|开除|移除|踢出|移出|' +
  '报损|报废|删除|核销|清空|作废|覆盖|' +
  '导出|下载|拷出|' +
  '开门|开闸|放行|解锁|' +
  '新增|添加|录入|写入|导入|补录|' +
  '授予|设定|设置|重置|启用|禁用|开通|关闭|' +
  '借给|借出|外借|借用|归还|退还|登记'

// 受控对象：出现这些词说明动的是一条真实记录，而不是在问流程
const OBJECTS =
  '记录|名单|台账|资质|证书|证件|合格证|授权|权限|门禁|库存|结存|数据|条目|状态|有效期'

// 祈使前缀
const IMPERATIVE = '(把|将|给|帮我|帮忙|麻烦|替我|请|去)'

// 被动 / 询问状态的写法，不应视为控制指令
const PASSIVE = new RegExp(`(被|已|是否|有没有|有没有人|谁).{0,6}(${VERBS})`)

// 明确的 how-to / 规则询问。用于放过「报损需要什么流程」这类问法——
// 刻意**不含**情态词（能否/可以/需要/应该），它们同样出现在写请求里。
// 注意：宽泛的「什么/哪些」在此是安全的，因为祈使前缀的判定优先于本例外（见下方逻辑）。
const ADVISORY = new RegExp(
  '怎么|如何|怎样|为什么|' +
  '什么|哪些|' +
  '多久|多长|期限|有效期|' +
  '规定|制度|标准|规范|依据|流程|手续|审批|' +
  '是否必须|需要几个|要不要|能不能|可以不可以',
)

const HIGH_CONFIDENCE: RegExp[] = [
  // A. 祈使前缀 + 控制动词：把李清妍的资质改到明年 / 帮我把门禁撤销
  new RegExp(`${IMPERATIVE}[^。？！]{0,24}(?:${VERBS})`),
  // B. 控制动词 + 完成标记：这瓶丙酮报损掉（无前缀也能识别）
  new RegExp(`(?:${VERBS})(掉|了|成|完)`),
  // C. 控制动词 + 受控对象：删除王景尧的违规记录 / 撤销王景尧权限
  new RegExp(`(?:${VERBS})[^。？！]{0,12}(?:${OBJECTS})`),
  // D. 句首就是控制动词：导出 3 号楼名单、删除违规记录
  new RegExp(`^\\s*(?:${IMPERATIVE})?(?:${VERBS})`),
  // E. 直接执行写语句
  /(执行|运行|跑一下|直接给我跑)\s*(UPDATE|DELETE|INSERT|DROP|ALTER|TRUNCATE)/i,
  /\b(UPDATE|DELETE|INSERT|DROP|ALTER|TRUNCATE)\s+[A-Za-z_]+\s+SET\b/i,
  // F. 远程操作门禁：现在远程把 3 号间的门打开
  /远程[^。？！]{0,20}(门|开|关|锁|解锁|闸)/,
]

const IMPERATIVE_WITH_VERB = new RegExp(`${IMPERATIVE}[^。？！]{0,24}(?:${VERBS})`)

/**
 * 命中高置信控制指令时返回拒绝话术；否则返回 null 交给后端。
 * 判定顺序：控制意图优先 → 被动/状态询问例外 → how-to 且无祈使前缀例外。
 */
export function detectControlIntent(question: string): string | null {
  const q = question.trim()
  if (!q) return null

  if (!HIGH_CONFIDENCE.some((re) => re.test(q))) return null

  // 例外 1：被动/询问写法——「王景尧的授权被撤销了吗」是在问状态，不是在改数据
  if (PASSIVE.test(q)) return null

  // 例外 2：明确的 how-to / 规则询问，且没有祈使前缀
  if (!IMPERATIVE_WITH_VERB.test(q) && ADVISORY.test(q)) return null

  return CONTROL_REFUSAL
}

// 剧毒品 / 易制爆精确库存只允许区间化输出（红线 4）
// 与后端 inventory_tools.to_interval 口径一致：q<5 少量；[5,50) 步长5；[50,500) 步长50；≥500 步长500。
// 下界取 max(lo, step) 保证不为 0——否则 q=6 会输出「约 0–5」，反而把精确值暴露在区间边界上。
export function toInterval(qty: number, unit: string): string {
  if (qty <= 0) return `无库存（0 ${unit}）`
  if (qty < 5) return `少量（不足 5 ${unit}）`
  const step = qty < 50 ? 5 : qty < 500 ? 50 : 500
  const lo = Math.max(Math.floor(qty / step) * step, step)
  return `约 ${lo}–${lo + step} ${unit}`
}

/** 需区间化处理的危险类别，与后端 SENSITIVE_CLASSES 一致 */
export const SENSITIVE_CLASSES = ['剧毒品', '易制爆']

export function isSensitive(hazardClass: string | null | undefined): boolean {
  return SENSITIVE_CLASSES.includes(hazardClass ?? '')
}

