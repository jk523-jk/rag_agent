import { defineStore } from 'pinia'
import { reactive, ref, watch, computed } from 'vue'
import type {
  AccessEvent, Agent, AppSettings, Equipment, EquipmentLoan, EvalCase, EvalTask,
  HazardItem, HazmatUse, Lab, LabAuthorization, LogEntry, Person, Qualification,
} from '@/types'
import {
  accessEvents as seedAccess, authorizations as seedAuths, equipment as seedEquipment,
  equipmentLoans as seedLoans, hazmatUses as seedUses, inventory as seedInventory,
  labs as seedLabs, persons as seedPersons, qualifications as seedQualifications,
} from '@/mocks/labData'
import {
  agents as seedAgents, evalCases as seedCases, evalTasks as seedTasks,
  logs as seedLogs,
} from '@/mocks/data'
import { loadState, saveState, removeState } from '@/utils/storage'
import { USE_BACKEND } from '@/utils/clock'
import {
  createAgentApi, deleteAgentApi, fetchOverview, listAgents, setAgentStatusApi, updateAgentApi,
  type AgentPayload,
} from '@/services/dataApi'

// v2.0：删除了工作流字段、Agent 改为后端配置，旧存档不再兼容，直接换 key 丢弃
const KEY = 'nexus-workspace-v2'

interface WorkspaceState {
  agents: Agent[]
  evalCases: EvalCase[]
  evalTasks: EvalTask[]
  logs: LogEntry[]
  // 实验室领域（对齐后端 lab_hazmat 库表）
  labs: Lab[]
  persons: Person[]
  qualifications: Qualification[]
  authorizations: LabAuthorization[]
  accessEvents: AccessEvent[]
  inventory: HazardItem[]
  hazmatUses: HazmatUse[]
  equipment: Equipment[]
  equipmentLoans: EquipmentLoan[]
  settings: AppSettings
}

export const DEFAULT_SETTINGS: AppSettings = {
  version: 1,
  workspaceName: '实验室智能管理agent',
  model: { name: 'qwen-plus', temperature: 0, maxTokens: 2048, timeoutSec: 60 },
  appearance: { theme: 'light', density: 'comfortable' },
}

function seed(): WorkspaceState {
  return structuredClone({
    agents: seedAgents,
    evalCases: seedCases,
    evalTasks: seedTasks,
    logs: seedLogs,
    labs: seedLabs,
    persons: seedPersons,
    qualifications: seedQualifications,
    authorizations: seedAuths,
    accessEvents: seedAccess,
    inventory: seedInventory,
    hazmatUses: seedUses,
    equipment: seedEquipment,
    equipmentLoans: seedLoans,
    settings: DEFAULT_SETTINGS,
  })
}

// 结构校验：数据损坏或旧版本不兼容时回退为演示数据。
// ⚠ 新增顶层数组必须加进这个列表，否则旧存档会通过校验却缺字段，页面读取时才崩。
const ARRAY_KEYS = [
  'agents', 'evalCases', 'evalTasks', 'logs',
  'labs', 'persons', 'qualifications', 'authorizations', 'accessEvents',
  'inventory', 'hazmatUses', 'equipment', 'equipmentLoans',
] as const

function isWorkspaceState(v: unknown): v is WorkspaceState {
  if (!v || typeof v !== 'object') return false
  const o = v as Record<string, unknown>
  return ARRAY_KEYS.every((k) => Array.isArray(o[k])) && !!o.settings
}

/** 实验室领域的 9 个数据集——切到真实数据时整组替换、整组清空 */
const LAB_KEYS = [
  'labs', 'persons', 'qualifications', 'authorizations', 'accessEvents',
  'inventory', 'hazmatUses', 'equipment', 'equipmentLoans',
] as const

export type DataSource = 'mock' | 'loading' | 'mysql' | 'error'

export const useWorkspaceStore = defineStore('workspace', () => {
  const initial = loadState(KEY, seed(), isWorkspaceState)
  if (USE_BACKEND) {
    // 真实数据模式下先清空演示数据：宁可短时间显示空表，
    // 也不能让演示数据冒充真实数据（这是此前最容易误导人的地方）。
    for (const k of LAB_KEYS) initial[k] = [] as never
    // Agent 配置也由后端提供（配置存在服务端，不是浏览器）
    initial.agents = []
  }
  const state = reactive<WorkspaceState>(initial)
  watch(state, (s) => saveState(KEY, s), { deep: true })

  // 数据来源标记，页面可据此显示「演示数据 / 实时数据库」徽标
  const dataSource = ref<DataSource>(USE_BACKEND ? 'loading' : 'mock')
  const dataError = ref('')
  const serverTime = ref('')

  /** 从后端拉取真实领域数据，整组替换 store 中的实验室数据 */
  async function hydrate() {
    if (!USE_BACKEND) return
    dataSource.value = 'loading'
    try {
      const [d, agentList] = await Promise.all([fetchOverview(), listAgents()])
      state.labs = d.labs
      state.persons = d.persons
      state.qualifications = d.qualifications
      state.authorizations = d.authorizations
      state.accessEvents = d.accessEvents
      state.inventory = d.inventory
      state.hazmatUses = d.hazmatUses
      state.equipment = d.equipment
      state.equipmentLoans = d.equipmentLoans
      state.agents = agentList
      serverTime.value = d.serverTime
      dataError.value = ''
      dataSource.value = 'mysql'
    } catch (e) {
      dataSource.value = 'error'
      dataError.value = e instanceof Error ? e.message : String(e)
    }
  }

  if (USE_BACKEND) void hydrate()

  const enabledAgents = computed(() => state.agents.filter((a) => a.status === 'enabled'))

  function findAgent(id: string) {
    return state.agents.find((a) => a.id === id)
  }
  function findLab(labId: string) {
    return state.labs.find((l) => l.labId === labId)
  }
  function findPerson(id: string) {
    return state.persons.find((p) => p.id === id)
  }
  function findEquipment(id: string) {
    return state.equipment.find((e) => e.id === id || e.equipId === id)
  }

  function upsertAgent(agent: Agent) {
    const i = state.agents.findIndex((a) => a.id === agent.id)
    if (i >= 0) state.agents[i] = agent
    else state.agents.push(agent)
  }
  function removeAgent(id: string) {
    state.agents = state.agents.filter((a) => a.id !== id)
  }

  // ---------------- Agent 配置：写穿到后端 ----------------
  //
  // mock 模式写本地（演示用）；backend 模式一律走后端，成功后用返回值覆盖本地，
  // 避免"界面显示成功、后端其实没保存"的两套真相。

  function agentPayload(a: Agent): AgentPayload {
    return {
      name: a.name,
      description: a.description,
      icon: a.icon,
      model: a.model,
      temperature: a.temperature,
      maxTokens: a.maxTokens,
      systemPrompt: a.systemPrompt,
      tools: [...a.tools],
      status: a.status,
    }
  }

  /** 新建或更新 Agent。isNew 由调用方决定（表单里有 props.agent 即为编辑） */
  async function saveAgent(agent: Agent, isNew: boolean): Promise<Agent> {
    if (!USE_BACKEND) {
      upsertAgent(agent)
      return agent
    }
    const saved = isNew
      ? await createAgentApi(agentPayload(agent))
      : await updateAgentApi(agent.id, agentPayload(agent))
    const i = state.agents.findIndex((x) => x.id === saved.id)
    if (i >= 0) state.agents[i] = saved
    else state.agents.push(saved)
    return saved
  }

  /** 启用 / 停用。停用后后端会拒绝该 Agent 的问答请求（403） */
  async function toggleAgent(id: string): Promise<Agent | null> {
    const current = state.agents.find((a) => a.id === id)
    if (!current) return null
    const next = current.status === 'enabled' ? 'disabled' : 'enabled'
    if (!USE_BACKEND) {
      current.status = next
      return current
    }
    const saved = await setAgentStatusApi(id, next)
    Object.assign(current, saved)
    return current
  }

  /** 删除。内置 Agent 后端会拒绝（400），这里把错误原样抛给调用方提示 */
  async function deleteAgentById(id: string): Promise<void> {
    if (USE_BACKEND) await deleteAgentApi(id)
    removeAgent(id)
  }

  // ---------------- 实验室领域：查询辅助 ----------------

  /** 某人的资质（按人员 id），已按有效期去重取最新 */
  function qualificationsOf(personId: string) {
    return state.qualifications.filter((q) => q.personId === personId)
  }
  /** 某人的实验室授权 */
  function authorizationsOf(personId: string) {
    return state.authorizations.filter((a) => a.personId === personId)
  }
  /** 某人的通行记录，按时间倒序 */
  function accessEventsOf(personId: string) {
    return state.accessEvents
      .filter((e) => e.personId === personId)
      .sort((a, b) => b.eventTime.localeCompare(a.eventTime))
  }
  /** 某台设备的借还记录，按借出时间倒序 */
  function loansOfEquipment(equipId: string) {
    return state.equipmentLoans
      .filter((l) => l.equipId === equipId)
      .sort((a, b) => b.borrowTime.localeCompare(a.borrowTime))
  }
  /** 设备的当前持有记录（未归还），无则返回 null */
  function currentLoan(equipId: string) {
    return state.equipmentLoans.find((l) => l.equipId === equipId && l.returnTime === null) ?? null
  }
  /** 药剂台账的领用记录 */
  function usesOfItem(itemId: string) {
    return state.hazmatUses.filter((u) => u.itemId === itemId)
  }

  function addLog(entry: LogEntry) {
    state.logs.unshift(entry)
    if (state.logs.length > 200) state.logs.length = 200
  }

  function addEvalTask(task: EvalTask) {
    state.evalTasks.unshift(task)
  }

  function updateSettings(patch: Partial<AppSettings>) {
    Object.assign(state.settings, patch)
  }

  function resetDemo() {
    removeState(KEY)
    const fresh = seed()
    Object.assign(state, fresh)
  }

  return {
    state,
    dataSource,
    dataError,
    serverTime,
    hydrate,
    enabledAgents,
    findAgent,
    findLab,
    findPerson,
    findEquipment,
    upsertAgent,
    removeAgent,
    saveAgent,
    toggleAgent,
    deleteAgentById,
    qualificationsOf,
    authorizationsOf,
    accessEventsOf,
    loansOfEquipment,
    currentLoan,
    usesOfItem,
    addLog,
    addEvalTask,
    updateSettings,
    resetDemo,
  }
})
