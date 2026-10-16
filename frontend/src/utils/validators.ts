import type { Agent } from '@/types'

// 表单字段的选项与校验规则。校验失败返回字段 -> 错误文案，空对象表示通过。
export const MODEL_OPTIONS = ['qwen-plus', 'qwen-max', 'qwen-turbo'] as const

export const TOOL_OPTIONS = [
  { id: 'search_policy', desc: '检索规程、制度与 SDS 摘要' },
  { id: 'query_records', desc: '结构化查询门禁流水与台账（只读）' },
  { id: 'check_lab_access', desc: '逐人判定资质 / 授权 / 双人三闸' },
  { id: 'get_person_qualification', desc: '查询某人全部资质' },
  { id: 'query_inventory', desc: '查询台账结存（剧毒品区间化）' },
  { id: 'reconcile_inventory', desc: '台账与领用交叉校验' },
] as const

export type AgentDraft = Pick<
  Agent,
  'name' | 'description' | 'systemPrompt' | 'model' | 'temperature' | 'maxTokens' | 'knowledgeIds' | 'tools' | 'status'
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

// 知识库表单校验（分块与检索参数的合理范围）
export interface KbDraft {
  name: string
  description: string
  chunkSize: number
  chunkOverlap: number
  topK: number
  scoreThreshold: number
}

export function validateKb(d: KbDraft, existingNames: string[], selfName?: string): FieldErrors<KbDraft> {
  const e: FieldErrors<KbDraft> = {}
  const name = d.name.trim()
  if (!name) e.name = '请填写知识库名称'
  else if (name.length > 40) e.name = '名称不能超过 40 个字符'
  else if (name !== selfName && existingNames.includes(name)) e.name = '已存在同名知识库'

  if (!Number.isInteger(d.chunkSize) || d.chunkSize < 100 || d.chunkSize > 2000) {
    e.chunkSize = '分块大小需为 100–2000 的整数'
  }
  if (!Number.isInteger(d.chunkOverlap) || d.chunkOverlap < 0 || d.chunkOverlap >= d.chunkSize) {
    e.chunkOverlap = '重叠长度需小于分块大小'
  }
  if (!Number.isInteger(d.topK) || d.topK < 1 || d.topK > 20) e.topK = 'Top-K 需为 1–20 的整数'
  if (!Number.isFinite(d.scoreThreshold) || d.scoreThreshold < 0 || d.scoreThreshold > 1) {
    e.scoreThreshold = '相似度阈值需在 0–1 之间'
  }
  return e
}
