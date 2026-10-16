import { defineStore } from 'pinia'
import { reactive, watch } from 'vue'
import { loadState, saveState } from '@/utils/storage'

const KEY = 'nexus-ui'

export type ToastTone = 'success' | 'error' | 'info'
export interface Toast {
  id: number
  tone: ToastTone
  text: string
}

interface UiState {
  sidebarCollapsed: boolean
}

let seq = 0

export const useUiStore = defineStore('ui', () => {
  const prefs = reactive<UiState>(loadState(KEY, { sidebarCollapsed: false }))
  watch(prefs, (p) => saveState(KEY, p), { deep: true })

  const toasts = reactive<Toast[]>([])

  function toast(text: string, tone: ToastTone = 'success') {
    const id = ++seq
    toasts.push({ id, tone, text })
    window.setTimeout(() => dismiss(id), tone === 'error' ? 5000 : 3000)
  }

  function dismiss(id: number) {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }

  function toggleSidebar() {
    prefs.sidebarCollapsed = !prefs.sidebarCollapsed
  }

  return { prefs, toasts, toast, dismiss, toggleSidebar }
})
