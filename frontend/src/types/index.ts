export type Status = 'success' | 'running' | 'failed' | 'idle' | 'warning' | 'pending' | 'disabled'

// ==================== AI 应用 ====================

export interface Agent {
  id: string
  name: string
  description: string
  icon: 'shield' | 'book' | 'flask' | 'workflow'
  model: string
  temperature: number
  maxTokens: number
  systemPrompt: string
  tools: string[]
  status: 'enabled' | 'disabled'
  lastRunAt: string
  runCount: number
}

export interface ChatSource {
  docName: string
  chapter: string
  text: string
  similarity: number
  rerank: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  sources?: ChatSource[]
  refused?: boolean
}

export interface ChatSession {
  id: string
  title: string
  agentId: string
  updatedAt: string
  messages: ChatMessage[]
}

export interface WorkflowNode {
  id: string
  type: 'start' | 'llm' | 'retriever' | 'tool' | 'condition' | 'output'
  label: string
  x: number
  y: number
  config: Record<string, string>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  label?: string
}

export interface Workflow {
  id: string
  name: string
  description: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  status: 'draft' | 'published'
  createdAt: string
  lastRunAt: string | null
}

export interface RunStep {
  nodeId: string
  label: string
  status: Status
  durationMs: number
  input: string
  output: string
  error?: string
}

export interface LogEntry {
  id: string
  taskType: 'chat' | 'access' | 'equipment' | 'workflow' | 'evaluation'
  target: string
  startedAt: string
  durationMs: number
  status: 'success' | 'failed' | 'running'
  tokens: number
  steps: RunStep[]
  error?: string
  isMock: true
}

export interface EvalCase {
  id: string
  question: string
  expect: string
  expectDocs: string[]
  tags: string[]
  expectRefuse: boolean
}

export interface EvalTask {
  id: string
  name: string
  target: string
  caseCount: number
  progress: number
  status: 'success' | 'running' | 'failed' | 'pending'
  recall: number | null
  relevance: number | null
  faithfulness: number | null
  failures: { caseId: string; reason: string }[]
  isMock: true
}

// ==================== 实验室领域（对齐后端 lab_hazmat 库表）====================

/** 危险类别，对应 hazmat_inventory.hazard_class */
export type HazardClass = '易燃液体' | '腐蚀品' | '氧化剂' | '剧毒品' | '易制爆' | '一般化学品'

/** 计量单位，对应 hazmat_inventory.unit */
export type Unit = '瓶' | '克' | '毫升'

/** 人员身份，对应 persons.role */
export type PersonRole = '教师' | '博士生' | '硕士生' | '本科生' | '外协'

/** 资质类型，对应 qualifications.cert_type */
export type CertType = '安全考试合格证' | '危化品操作证' | '特种作业证' | '导师授权书'

/** 资质状态，对应 qualifications.status */
export type CertStatus = '有效' | '已过期' | '已注销'

/** 授权状态，对应 lab_authorizations.status */
export type AuthStatus = '有效' | '已撤销' | '已过期'

/** 通行方向，对应 access_events.direction */
export type Direction = '进' | '出'

/** 验证方式，对应 access_events.auth_type */
export type AuthType = '人脸' | '工卡' | '密码' | '人工放行'

/** 验证结果，对应 access_events.auth_result */
export type AuthResult = '通过' | '拒绝' | '超时'

/** 准入判定结论，与后端 access_tools 的四值严格一致 */
export type AccessVerdict = '资质过期' | '无授权' | '需双人同行' | '准予进入'

/** 设备状态，对应 equipment.status */
export type EquipStatus = '在用' | '维修中' | '停用' | '报废'

/** 设备类别，对应 equipment.category */
export type EquipCategory = '分析仪器' | '合成设备' | '检测仪器' | '储存设施' | '其他'

/** 借还状态，对应 equipment_loans.status */
export type LoanStatus = '借用中' | '已归还' | '逾期'

export interface Lab {
  labId: string
  labName: string
  hazmatClass: string
  /** 是否要求双人准入，剧毒品间为 true */
  needsDouble: boolean
  mgrName: string
}

export interface Person {
  id: string
  name: string
  empNo: string
  dept: string
  role: PersonRole
}

export interface Qualification {
  id: string
  personId: string
  certType: CertType
  certNo: string
  issueDate: string
  /** 判定准入资格的关键字段；status 可能未及时更新，一律以本字段为准 */
  expireDate: string
  status: CertStatus
}

export interface LabAuthorization {
  id: string
  personId: string
  labId: string
  authFrom: string
  authTo: string
  grantor: string
  status: AuthStatus
}

export interface AccessEvent {
  id: string
  personId: string
  labId: string
  eventTime: string
  direction: Direction
  authType: AuthType
  authResult: AuthResult
  /** 同行人数，剧毒品间要求双人准入时用于核查；null 表示未登记 */
  companionNo: number | null
}

export interface HazardItem {
  id: string
  chemName: string
  casNo: string
  hazardClass: HazardClass
  labId: string
  cabinetNo: string
  /** 内部精确值；对外展示必须按 isSensitive 判断是否区间化 */
  quantity: number
  unit: Unit
  updatedAt: string
}

export interface HazmatUse {
  id: string
  itemId: string
  personId: string
  useTime: string
  quantity: number
  /** 见证人；剧毒品与易制爆必须非空 */
  witnessId: string | null
  purpose: string
}

export interface Equipment {
  id: string
  equipId: string
  equipName: string
  category: EquipCategory
  modelNo: string
  labId: string
  keeperId: string | null
  status: EquipStatus
  /** 校准有效期；储存设施无校准要求，为 null */
  calibrateDue: string | null
  purchaseDate: string
  remark: string
}

export interface EquipmentLoan {
  id: string
  equipId: string
  personId: string
  borrowTime: string
  dueTime: string
  /** null 表示尚未归还 */
  returnTime: string | null
  purpose: string
  approver: string
  status: LoanStatus
}

/** 三闸判定结果，逐条理由与后端 check_lab_access 输出结构一致 */
export interface AccessDecision {
  verdict: AccessVerdict
  reasons: string[]
  /** 命中的闸位标签，用于 UI 高亮 */
  failedGate: '资质闸' | '授权闸' | '双人闸' | null
}

// ==================== 设置 ====================

export interface AppSettings {
  version: number
  workspaceName: string
  model: { name: string; temperature: number; maxTokens: number; timeoutSec: number }
  appearance: { theme: 'light'; density: 'comfortable' | 'compact' }
}
