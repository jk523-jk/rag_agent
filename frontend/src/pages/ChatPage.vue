<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { PanelLeft, X } from 'lucide-vue-next'
import ChatSessionList from '@/components/chat/ChatSessionList.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import ChatContextPanel from '@/components/chat/ChatContextPanel.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useChatStore } from '@/stores/chat'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { streamAnswer, type SimAnswer } from '@/services/chatEngine'
import { streamChatFromBackend } from '@/services/chatApi'

const useBackend = import.meta.env.VITE_API_MODE === 'backend'

const chat = useChatStore()
const workspace = useWorkspaceStore()
const ui = useUiStore()

const busy = ref(false)
const streamingText = ref('')
const contextOpen = ref(true)
const listOpen = ref(false)
const confirmClear = ref(false)
const confirmRemoveId = ref<string | null>(null)
let controller: AbortController | null = null

const agents = computed(() => workspace.state.agents.map((a) => ({ id: a.id, name: a.name })))
const session = computed(() => chat.active)

const lastQuestion = computed(() => {
  const msgs = session.value?.messages ?? []
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') return msgs[i].content
  }
  return ''
})

const lastSources = computed(() => {
  const msgs = session.value?.messages ?? []
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant' && msgs[i].sources?.length) return msgs[i].sources!
  }
  return []
})

const strategy = computed(() =>
  workspace.state.settings.retrieval.hybrid
    ? `混合检索（BM25 + 向量）· Top-K ${workspace.state.settings.retrieval.topK} · 阈值 ${workspace.state.settings.retrieval.scoreThreshold}`
    : `向量检索 · Top-K ${workspace.state.settings.retrieval.topK} · 阈值 ${workspace.state.settings.retrieval.scoreThreshold}`,
)

onMounted(() => {
  if (!chat.state.sessions.length) {
    chat.create(workspace.enabledAgents[0]?.id ?? workspace.state.agents[0].id)
  } else if (!chat.state.activeId) {
    chat.select(chat.state.sessions[0].id)
  }
})

function runStream(question: string, replaceMessageId?: string) {
  const s = session.value
  if (!s) return
  busy.value = true
  streamingText.value = ''
  controller = new AbortController()
  const signal = controller.signal
  const onDelta = (delta: string) => { streamingText.value += delta }

  // 后端模式走真实 SSE；模拟模式走本地引擎。两者都能被“停止生成”中断并保留已输出内容
  const request: Promise<SimAnswer & { aborted: boolean }> = useBackend
    ? streamChatFromBackend(question, s.id, onDelta, signal)
        .then(() => ({ text: streamingText.value, sources: [], refused: false, aborted: false }))
        .catch((err: unknown) => {
          if (signal.aborted) return { text: streamingText.value, sources: [], refused: false, aborted: true }
          throw err
        })
    : streamAnswer(question, onDelta, signal)

  request
    .then((res) => {
      const finalText = streamingText.value || res.text
      if (replaceMessageId) {
        chat.updateMessage(s.id, replaceMessageId, { content: finalText, sources: res.sources })
      } else {
        chat.appendMessage(s.id, { role: 'assistant', content: finalText, sources: res.sources, refused: res.refused })
      }
      if (res.aborted) ui.toast('已停止生成（保留已输出的内容）', 'info')
    })
    .catch((err: unknown) => {
      const reason = err instanceof Error ? err.message : '未知错误'
      chat.appendMessage(s.id, { role: 'assistant', content: `请求失败：${reason}\n\n可以稍后重试，或换个问法。` })
      ui.toast('请求失败', 'error')
    })
    .finally(() => {
      busy.value = false
      streamingText.value = ''
      controller = null
    })
}

function send(text: string) {
  const s = session.value
  if (!s) return
  chat.appendMessage(s.id, { role: 'user', content: text })
  runStream(text)
}

function regenerate(messageId: string) {
  const s = session.value
  if (!s || busy.value) return
  const i = s.messages.findIndex((m) => m.id === messageId)
  const question = [...s.messages.slice(0, i)].reverse().find((m) => m.role === 'user')?.content
  if (!question) return
  chat.truncateAfter(s.id, messageId)
  chat.appendMessage(s.id, { role: 'user', content: question })
  runStream(question)
}

function stop() {
  controller?.abort()
}

function doClear() {
  if (session.value) chat.clear(session.value.id)
  confirmClear.value = false
  ui.toast('已清空当前会话')
}

function doRemove() {
  if (confirmRemoveId.value) chat.remove(confirmRemoveId.value)
  confirmRemoveId.value = null
  ui.toast('已删除会话')
}

function changeAgent(id: string) {
  const s = session.value
  if (s) s.agentId = id
}
</script>

<template>
  <div class="lg:-mx-7 lg:-my-6">
    <div class="flex h-[calc(100vh-3.5rem)]">
      <!-- 会话列表：桌面常驻，移动端抽屉 -->
      <aside class="hidden w-64 shrink-0 border-r border-line bg-surface lg:block">
        <ChatSessionList
          :sessions="chat.state.sessions"
          :active-id="chat.state.activeId"
          @create="chat.create(workspace.enabledAgents[0]?.id ?? workspace.state.agents[0].id)"
          @select="chat.select"
          @rename="chat.rename"
          @remove="confirmRemoveId = $event"
        />
      </aside>

      <!-- 主聊天区 -->
      <div class="relative flex min-w-0 flex-1 flex-col">
        <div class="flex h-9 shrink-0 items-center gap-2 border-b border-line bg-surface px-3 lg:hidden">
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" aria-label="打开会话列表" @click="listOpen = true">
            <PanelLeft class="size-3.5" aria-hidden="true" />会话
          </button>
          <span class="truncate text-[12px] text-ink-2">{{ session?.title }}</span>
        </div>
        <ChatPanel
          class="flex-1"
          :session="session"
          :busy="busy"
          :streaming-text="streamingText"
          :agents="agents"
          :context-open="contextOpen"
          @send="send"
          @stop="stop"
          @regenerate="regenerate"
          @clear="confirmClear = true"
          @agent="changeAgent"
          @toggle-context="contextOpen = !contextOpen"
        />

        <!-- 移动端：上下文以覆盖层展示 -->
        <div v-if="contextOpen && lastSources.length" class="border-t border-line bg-surface lg:hidden">
          <button
            type="button"
            class="flex w-full items-center justify-between px-4 py-2 text-[12px] text-ink-2"
            @click="contextOpen = false"
          >
            <span>检索上下文（{{ lastSources.length }}）</span>
            <X class="size-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>

      <!-- 上下文面板：桌面端显示 -->
      <aside
        v-if="contextOpen"
        class="hidden w-[340px] shrink-0 border-l border-line bg-surface xl:block"
        aria-label="检索上下文"
      >
        <ChatContextPanel :sources="lastSources" :question="lastQuestion" :strategy="strategy" />
      </aside>
    </div>

    <!-- 移动端会话抽屉 -->
    <Teleport to="body">
      <div v-if="listOpen" class="fixed inset-0 z-50 lg:hidden">
        <div class="absolute inset-0 bg-ink/30" aria-hidden="true" @click="listOpen = false" />
        <div class="absolute inset-y-0 left-0 w-[280px] bg-surface shadow-lg">
          <div class="flex h-12 items-center justify-between border-b border-line px-3">
            <h2 class="text-[14px] font-semibold text-ink">会话</h2>
            <button type="button" class="btn-ghost h-8 w-8 p-0" aria-label="关闭会话列表" @click="listOpen = false">
              <X class="size-4" />
            </button>
          </div>
          <div class="h-[calc(100%-3rem)]">
            <ChatSessionList
              :sessions="chat.state.sessions"
              :active-id="chat.state.activeId"
              @create="chat.create(workspace.enabledAgents[0]?.id ?? workspace.state.agents[0].id); listOpen = false"
              @select="(id: string) => { chat.select(id); listOpen = false }"
              @rename="chat.rename"
              @remove="confirmRemoveId = $event"
            />
          </div>
        </div>
      </div>
    </Teleport>

    <ConfirmDialog
      v-model:open="confirmClear"
      title="清空当前会话？"
      description="将删除本会话的全部消息记录，此操作不可撤销。"
      confirm-text="清空"
      danger
      @confirm="doClear"
    />
    <ConfirmDialog
      :open="confirmRemoveId !== null"
      title="删除该会话？"
      description="会话及其消息记录将被永久删除。"
      confirm-text="删除"
      danger
      @update:open="confirmRemoveId = null"
      @confirm="doRemove"
    />
  </div>
</template>
