import type { Agent, EquipCategory, EquipStatus, Equipment } from '@/types'

// 表单字段的选项与校验规则。校验失败返回字段 -> 错误文案，空对象表示通过。
export const MODEL_OPTIONS = ['qwen-plus', 'qwen-max', 'qwen-turbo'] as const

export const TOOL_OPTIONS = [
  { id: 'search_policy', desc: '检索规程、制度与 SDS 摘要' },
  { id: 'query_records', desc: '结构化查询门禁流水与台账（只读）' },
  { id: 'check_lab_access', desc: '逐人判定资质 / 授权 / 双人三闸' },
  { id: 'get_person_qualification', desc: '查询某人全部资质' },
  { id: 'query_inventory', desc: '查询台账结存（剧毒品区间化）' },
  { id: 'reconcile_inventory', desc: '台账与领用交叉校验' },
  { id: 'query_equipment', desc: '查询设备台账、状态与校准有效期' },
  { id: 'check_equipment_loan', desc: '查询设备借还状态与逾期情况' },
  { id: 'list_calibration_due', desc: '列出校准已过期或即将到期的设备' },
] as const

export type AgentDraft = Pick<
  Agent,
  'name' | 'description' | 'systemPrompt' | 'model' | 'temperature' | 'maxTokens' | 'tools' | 'status'
>

export type FieldErrors<T> = Partial<Record<keyof T, string>>

export function validateAgent(d: AgentDraft): FieldErrors<AgentDraft> {
  const e: FieldErrors<AgentDraft> = {}
  const name = d.name.trim()
  if (!name) e.name = '请填写 Agent 名称'
  else if (name.length < 2 || name.length > 40) e.name = '名称长度需在 2–40 个字符之间'

  if (d.description.length > 200) e.description = '描述不能超过 200 个字符'

  const prompt = d.systemPrompt.trim()
  if (!prompt) e.systemPrompt = '系统提示词不能为空'
  else if (prompt.length < 10) e.systemPrompt = '系统提示词至少 10 个字符，请写清角色与边界'
  else if (d.systemPrompt.length > 2000) e.systemPrompt = '系统提示词不能超过 2000 个字符'

  if (!Number.isFinite(d.temperature) || d.temperature < 0 || d.temperature > 1) {
    e.temperature = '温度需在 0–1 之间'
  }
  if (!Number.isInteger(d.maxTokens) || d.maxTokens < 128 || d.maxTokens > 8192) {
    e.maxTokens = '最大输出 Token 需为 128–8192 的整数'
  }
  if (d.tools.length === 0) e.tools = '至少选择一个工具'
  return e
}

// ==================== 设备表单 ====================

export const EQUIP_CATEGORY_OPTIONS: EquipCategory[] = ['分析仪器', '合成设备', '检测仪器', '储存设施', '其他']
export const EQUIP_STATUS_OPTIONS: EquipStatus[] = ['在用', '维修中', '停用', '报废']

export type EquipmentDraft = Pick<
  Equipment,
  'equipId' | 'equipName' | 'category' | 'modelNo' | 'labId' | 'keeperId' | 'status' | 'calibrateDue' | 'purchaseDate' | 'remark'
>

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export function validateEquipment(
  d: EquipmentDraft,
  existingIds: string[],
  selfId?: string,
): FieldErrors<EquipmentDraft> {
  const e: FieldErrors<EquipmentDraft> = {}

  const equipId = d.equipId.trim()
  if (!equipId) e.equipId = '请填写设备编号'
  else if (!/^EQ-\d{4}$/.test(equipId)) e.equipId = '设备编号格式为 EQ-0001（EQ- 加四位数字）'
  else if (equipId !== selfId && existingIds.includes(equipId)) e.equipId = '已存在同编号设备'

  const name = d.equipName.trim()
  if (!name) e.equipName = '请填写设备名称'
  else if (name.length > 64) e.equipName = '设备名称不能超过 64 个字符'

  if (d.modelNo.length > 64) e.modelNo = '规格型号不能超过 64 个字符'
  if (!d.labId) e.labId = '请选择所在实验室'

  // 储存设施（试剂柜、通风橱）无校准要求，可不填；其余类别建议登记校准有效期
  if (d.calibrateDue && !DATE_RE.test(d.calibrateDue)) {
    e.calibrateDue = '校准有效期格式为 YYYY-MM-DD'
  }
  if (d.purchaseDate && !DATE_RE.test(d.purchaseDate)) {
    e.purchaseDate = '购置日期格式为 YYYY-MM-DD'
  }
  if (d.calibrateDue && d.purchaseDate && d.calibrateDue < d.purchaseDate) {
    e.calibrateDue = '校准有效期不能早于购置日期'
  }
  if (d.remark.length > 200) e.remark = '备注不能超过 200 个字符'
  return e
}
