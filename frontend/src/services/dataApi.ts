// 真实后端数据接口（只读）。契约见 backend/app/api/data.py。
//
// 仅在 VITE_API_MODE=backend 时由 workspace store 调用；
// mock 模式下前端完全不发数据请求，全部读 @/mocks/labData。
import type {
  AccessEvent, Agent, Equipment, EquipmentLoan, HazardItem, HazmatUse,
  Lab, LabAuthorization, Person, Qualification,
} from '@/types'

export interface DataOverview {
  labs: Lab[]
  persons: Person[]
  qualifications: Qualification[]
  authorizations: LabAuthorization[]
  accessEvents: AccessEvent[]
  inventory: HazardItem[]
  hazmatUses: HazmatUse[]
  equipment: Equipment[]
  equipmentLoans: EquipmentLoan[]
  serverTime: string
  source: string
}

/** 后端未启动 / 数据库不可达时抛出的错误，带上可读原因供页面提示 */
export class DataApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'DataApiError'
    this.status = status
  }
}

async function getJson<T>(url: string): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch {
    throw new DataApiError('无法连接后端服务，请确认 8000 端口已启动')
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = (await resp.json()) as { detail?: string }
      if (body?.detail) detail = body.detail
    } catch {
      /* 非 JSON 响应，保留状态码 */
    }
    throw new DataApiError(detail, resp.status)
  }
  return (await resp.json()) as T
}

/** 控制台首屏所需的全部领域数据，一次往返取回 */
export function fetchOverview(): Promise<DataOverview> {
  return getJson<DataOverview>('/api/data/overview')
}

/** 单资源接口，供局部刷新使用 */
export const dataApi = {
  labs: () => getJson<Lab[]>('/api/data/labs'),
  persons: () => getJson<Person[]>('/api/data/persons'),
  qualifications: () => getJson<Qualification[]>('/api/data/qualifications'),
  authorizations: () => getJson<LabAuthorization[]>('/api/data/authorizations'),
  accessEvents: () => getJson<AccessEvent[]>('/api/data/access-events'),
  inventory: () => getJson<HazardItem[]>('/api/data/inventory'),
  hazmatUses: () => getJson<HazmatUse[]>('/api/data/hazmat-uses'),
  equipment: () => getJson<Equipment[]>('/api/data/equipment'),
  equipmentLoans: () => getJson<EquipmentLoan[]>('/api/data/equipment-loans'),
}

// ==================== Agent 配置（可写：平台配置，不碰实验数据） ====================

/** 后端返回的 Agent DTO（camelCase，与 @/types 基本对齐） */
interface AgentDto {
  id: string
  name: string
  description: string
  icon: string
  model: string
  temperature: number
  maxTokens: number
  tools: string[]
  status: string
  isBuiltin?: boolean
  updatedAt?: string
  systemPrompt?: string
}

/** 提交给后端的字段（不含 id / 统计字段） */
export interface AgentPayload {
  name: string
  description: string
  icon: string
  model: string
  temperature: number
  maxTokens: number
  systemPrompt: string
  tools: string[]
  status: string
}

function toAgent(dto: AgentDto): Agent {
  return {
    id: dto.id,
    name: dto.name,
    description: dto.description ?? '',
    icon: (dto.icon as Agent['icon']) ?? 'shield',
    model: dto.model,
    temperature: dto.temperature,
    maxTokens: dto.maxTokens,
    systemPrompt: dto.systemPrompt ?? '',
    tools: dto.tools ?? [],
    status: dto.status === 'disabled' ? 'disabled' : 'enabled',
    // 后端暂不统计运行次数与最近运行时间：留占位，不伪造数字
    lastRunAt: dto.updatedAt ?? '—',
    runCount: 0,
  }
}

async function sendJson<T>(method: string, url: string, body?: unknown): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new DataApiError('无法连接后端服务，请确认 8000 端口已启动')
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const data = (await resp.json()) as { detail?: unknown }
      if (typeof data?.detail === 'string') detail = data.detail
      else if (data?.detail && typeof data.detail === 'object') {
        const errs = (data.detail as { errors?: Record<string, string> }).errors
        if (errs) detail = Object.values(errs).join('；')
      }
    } catch {
      /* 非 JSON，保留状态码 */
    }
    throw new DataApiError(detail, resp.status)
  }
  return (await resp.json()) as T
}

export async function listAgents(): Promise<Agent[]> {
  const data = await getJson<{ agents: AgentDto[] }>('/api/agents')
  return (data.agents ?? []).map(toAgent)
}

export async function fetchAgent(id: string): Promise<Agent> {
  return toAgent(await getJson<AgentDto>(`/api/agents/${encodeURIComponent(id)}`))
}

export async function createAgentApi(payload: AgentPayload): Promise<Agent> {
  return toAgent(await sendJson<AgentDto>('POST', '/api/agents', payload))
}

export async function updateAgentApi(id: string, payload: AgentPayload): Promise<Agent> {
  return toAgent(await sendJson<AgentDto>('PUT', `/api/agents/${encodeURIComponent(id)}`, payload))
}

export async function setAgentStatusApi(id: string, status: 'enabled' | 'disabled'): Promise<Agent> {
  return toAgent(
    await sendJson<AgentDto>('POST', `/api/agents/${encodeURIComponent(id)}/status`, { status }),
  )
}

export async function deleteAgentApi(id: string): Promise<void> {
  await sendJson<{ deleted: string }>('DELETE', `/api/agents/${encodeURIComponent(id)}`)
}
