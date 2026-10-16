import { defineStore } from 'pinia'
import { reactive, watch, computed } from 'vue'
import type {
  AccessEvent, Agent, AppSettings, Equipment, EquipmentLoan, EvalCase, EvalTask,
  HazardItem, HazmatUse, Lab, LabAuthorization, LogEntry, Person, Qualification, Workflow,
} from '@/types'
import {
  accessEvents as seedAccess, authorizations as seedAuths, equipment as seedEquipment,
  equipmentLoans as seedLoans, hazmatUses as seedUses, inventory as seedInventory,
  labs as seedLabs, persons as seedPersons, qualifications as seedQualifications,
} from '@/mocks/labData'
import {
  agents as seedAgents, evalCases as seedCases, evalTasks as seedTasks,
  logs as seedLogs, workflows as seedWorkflows,
} from '@/mocks/data'
import { loadState, saveState, removeState } from '@/utils/storage'

const KEY = 'nexus-workspace'

interface WorkspaceState {
  agents: Agent[]
  workflows: Workflow[]
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
  workspaceName: '危化品准入工作区',
  model: { name: 'qwen-plus', temperature: 0, maxTokens: 2048, timeoutSec: 60 },
  appearance: { theme: 'light', density: 'comfortable' },
}

function seed(): WorkspaceState {
  return structuredClone({
    agents: seedAgents,
    workflows: seedWorkflows,
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
  'agents', 'workflows', 'evalCases', 'evalTasks', 'logs',
  'labs', 'persons', 'qualifications', 'authorizations', 'accessEvents',
  'inventory', 'hazmatUses', 'equipment', 'equipmentLoans',
] as const

function isWorkspaceState(v: unknown): v is WorkspaceState {
  if (!v || typeof v !== 'object') return false
  const o = v as Record<string, unknown>
  return ARRAY_KEYS.every((k) => Array.isArray(o[k])) && !!o.settings
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const state = reactive<WorkspaceState>(loadState(KEY, seed(), isWorkspaceState))
  watch(state, (s) => saveState(KEY, s), { deep: true })

  const enabledAgents = computed(() => state.agents.filter((a) => a.status === 'enabled'))

  function findAgent(id: string) {
    return state.agents.find((a) => a.id === id)
  }
  function findWorkflow(id: string) {
    return state.workflows.find((w) => w.id === id)
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

  function upsertWorkflow(wf: Workflow) {
    const i = state.workflows.findIndex((w) => w.id === wf.id)
    if (i >= 0) state.workflows[i] = wf
    else state.workflows.push(wf)
  }
  function removeWorkflow(id: string) {
    state.workflows = state.workflows.filter((w) => w.id !== id)
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
    enabledAgents,
    findAgent,
    findWorkflow,
    findLab,
    findPerson,
    findEquipment,
    upsertAgent,
    removeAgent,
    upsertWorkflow,
    removeWorkflow,
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
