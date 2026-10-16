import { defineStore } from 'pinia'
import { reactive, watch, computed } from 'vue'
import type {
  Agent, AppSettings, Chunk, EvalCase, EvalTask, KbDocument, KnowledgeBase, LogEntry, Workflow,
} from '@/types'
import { agents as seedAgents, chunks as seedChunks, documents as seedDocs, evalCases as seedCases, evalTasks as seedTasks,
  knowledgeBases as seedKbs, logs as seedLogs, workflows as seedWorkflows } from '@/mocks/data'
import { loadState, saveState, removeState } from '@/utils/storage'

const KEY = 'nexus-workspace'

interface WorkspaceState {
  agents: Agent[]
  knowledgeBases: KnowledgeBase[]
  documents: KbDocument[]
  chunks: Chunk[]
  workflows: Workflow[]
  evalCases: EvalCase[]
  evalTasks: EvalTask[]
  logs: LogEntry[]
  settings: AppSettings
}

export const DEFAULT_SETTINGS: AppSettings = {
  version: 1,
  workspaceName: '危化品准入工作区',
  model: { name: 'qwen-plus', temperature: 0, maxTokens: 2048, timeoutSec: 60 },
  embedding: { model: 'text-embedding-v3', dimension: 1024 },
  retrieval: { topK: 4, scoreThreshold: 0.3, hybrid: true, rerank: true },
  appearance: { theme: 'light', density: 'comfortable' },
}

function seed(): WorkspaceState {
  return structuredClone({
    agents: seedAgents,
    knowledgeBases: seedKbs,
    documents: seedDocs,
    chunks: seedChunks,
    workflows: seedWorkflows,
    evalCases: seedCases,
    evalTasks: seedTasks,
    logs: seedLogs,
    settings: DEFAULT_SETTINGS,
  })
}

// 结构校验：数据损坏或旧版本不兼容时回退为演示数据
function isWorkspaceState(v: unknown): v is WorkspaceState {
  if (!v || typeof v !== 'object') return false
  const o = v as Record<string, unknown>
  return ['agents', 'knowledgeBases', 'documents', 'chunks', 'workflows', 'evalCases', 'evalTasks', 'logs']
    .every((k) => Array.isArray(o[k])) && !!o.settings
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const state = reactive<WorkspaceState>(loadState(KEY, seed(), isWorkspaceState))
  watch(state, (s) => saveState(KEY, s), { deep: true })

  const enabledAgents = computed(() => state.agents.filter((a) => a.status === 'enabled'))

  function findAgent(id: string) {
    return state.agents.find((a) => a.id === id)
  }
  function findKb(id: string) {
    return state.knowledgeBases.find((k) => k.id === id)
  }
  function findWorkflow(id: string) {
    return state.workflows.find((w) => w.id === id)
  }

  function upsertAgent(agent: Agent) {
    const i = state.agents.findIndex((a) => a.id === agent.id)
    if (i >= 0) state.agents[i] = agent
    else state.agents.push(agent)
  }
  function removeAgent(id: string) {
    state.agents = state.agents.filter((a) => a.id !== id)
  }

  function upsertKb(kb: KnowledgeBase) {
    const i = state.knowledgeBases.findIndex((k) => k.id === kb.id)
    if (i >= 0) state.knowledgeBases[i] = kb
    else state.knowledgeBases.push(kb)
  }
  function removeKb(id: string) {
    state.knowledgeBases = state.knowledgeBases.filter((k) => k.id !== id)
    state.documents = state.documents.filter((d) => d.kbId !== id)
    state.chunks = state.chunks.filter((c) => !state.documents.some((d) => d.id === c.docId))
  }

  function upsertWorkflow(wf: Workflow) {
    const i = state.workflows.findIndex((w) => w.id === wf.id)
    if (i >= 0) state.workflows[i] = wf
    else state.workflows.push(wf)
  }
  function removeWorkflow(id: string) {
    state.workflows = state.workflows.filter((w) => w.id !== id)
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
    findKb,
    findWorkflow,
    upsertAgent,
    removeAgent,
    upsertKb,
    removeKb,
    upsertWorkflow,
    removeWorkflow,
    addLog,
    addEvalTask,
    updateSettings,
    resetDemo,
  }
})
