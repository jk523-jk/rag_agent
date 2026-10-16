import { defineStore } from 'pinia'
import { reactive, watch, computed } from 'vue'
import type { ChatMessage, ChatSession } from '@/types'
import { loadState, saveState } from '@/utils/storage'

const KEY = 'nexus-chat'

interface ChatState {
  sessions: ChatSession[]
  activeId: string | null
}

const newId = (p: string) => `${p}-${Math.random().toString(36).slice(2, 9)}`
const now = () => {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function makeSession(agentId: string, title = '新会话'): ChatSession {
  return { id: newId('sess'), title, agentId, updatedAt: now(), messages: [] }
}

function isChatState(v: unknown): v is ChatState {
  if (!v || typeof v !== 'object') return false
  const o = v as ChatState
  return Array.isArray(o.sessions)
}

export const useChatStore = defineStore('chat', () => {
  const state = reactive<ChatState>(loadState(KEY, { sessions: [], activeId: null }, isChatState))
  watch(state, (s) => saveState(KEY, s), { deep: true })

  const active = computed(() => state.sessions.find((s) => s.id === state.activeId) ?? null)

  function create(agentId: string) {
    const s = makeSession(agentId)
    state.sessions.unshift(s)
    state.activeId = s.id
    return s
  }

  function select(id: string) {
    state.activeId = id
  }

  function rename(id: string, title: string) {
    const s = state.sessions.find((x) => x.id === id)
    if (s) s.title = title.trim().slice(0, 40) || '未命名会话'
  }

  function remove(id: string) {
    state.sessions = state.sessions.filter((s) => s.id !== id)
    if (state.activeId === id) state.activeId = state.sessions[0]?.id ?? null
  }

  function appendMessage(sessionId: string, msg: Omit<ChatMessage, 'id' | 'createdAt'>) {
    const s = state.sessions.find((x) => x.id === sessionId)
    if (!s) return null
    const m: ChatMessage = { ...msg, id: newId('msg'), createdAt: now() }
    s.messages.push(m)
    s.updatedAt = m.createdAt
    if (s.messages.length === 1 && msg.role === 'user') {
      s.title = msg.content.slice(0, 18)
    }
    return m
  }

  function updateMessage(sessionId: string, messageId: string, patch: Partial<ChatMessage>) {
    const m = state.sessions.find((x) => x.id === sessionId)?.messages.find((x) => x.id === messageId)
    if (m) Object.assign(m, patch)
  }

  function clear(sessionId: string) {
    const s = state.sessions.find((x) => x.id === sessionId)
    if (s) {
      s.messages = []
      s.updatedAt = now()
    }
  }

  function truncateAfter(sessionId: string, messageId: string) {
    const s = state.sessions.find((x) => x.id === sessionId)
    if (!s) return
    const i = s.messages.findIndex((m) => m.id === messageId)
    if (i >= 0) s.messages = s.messages.slice(0, i)
  }

  return { state, active, create, select, rename, remove, appendMessage, updateMessage, clear, truncateAfter }
})
