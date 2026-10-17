<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Send, Square, RefreshCw, Copy, Trash2, AlertTriangle, ShieldAlert, PanelRight } from 'lucide-vue-next'
import type { ChatMessage, ChatSession } from '@/types'
import MessageContent from '@/components/chat/MessageContent.vue'
import { useUiStore } from '@/stores/ui'
import { copyText } from '@/utils/format'

const props = defineProps<{
  session: ChatSession | null
  busy: boolean
  streamingText: string
  agents: { id: string; name: string }[]
  contextOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'send', text: string): void
  (e: 'stop'): void
  (e: 'regenerate', messageId: string): void
  (e: 'clear'): void
  (e: 'agent', id: string): void
  (e: 'toggle-context'): void
}>()

const ui = useUiStore()
const input = ref('')
// 运行模式由构建变量决定：模拟模式的回答是预设内容，后端模式的回答来自真实服务，界面必须区分
const isBackend = import.meta.env.VITE_API_MODE === 'backend'
const scroller = ref<HTMLElement | null>(null)

// 资质异常 / 授权异常 / 台账差异 / 缺见证人 单独高亮置顶（开发 Plan M6-2）
const ALERT_RULES = [
  { re: /(资质过期|已过期|证书过期|资质闸：未通过)/, tone: 'danger' as const, text: '发现资质过期' },
  { re: /(无授权|已撤销|授权失效)/, tone: 'danger' as const, text: '发现授权异常' },
  { re: /(账物不符|存在账物不符|盘亏|盘盈|差异.*超出)/, tone: 'warning' as const, text: '台账与流水不一致' },
  { re: /(缺少见证人|无见证人|缺少见证)/, tone: 'warning' as const, text: '领用记录缺少见证人' },
]

const alerts = computed(() => {
  if (!props.session) return []
  const text = props.session.messages.map((m) => m.content).join('\n') + props.streamingText
  return ALERT_RULES.filter((r) => r.re.test(text)).map((r) => ({ tone: r.tone, text: r.text }))
})

const messages = computed<ChatMessage[]>(() => props.session?.messages ?? [])

async function scrollToBottom() {
  await nextTick()
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight })
}

watch(() => [messages.value.length, props.streamingText], scrollToBottom)

function submit() {
  const text = input.value.trim()
  if (!text || props.busy) return
  emit('send', text)
  input.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}

async function copyMessage(m: ChatMessage) {
  const ok = await copyText(m.content)
  ui.toast(ok ? '已复制回答' : '复制失败，请手动选择文本', ok ? 'success' : 'error')
}

const promptExamples = [
  '剧毒化学品领用需要几个人在场？',
  '上周进过 3 号间的人里，有谁的资质是过期的？',
  '台账上 3 号柜的丙酮还剩 8 瓶，但领用记录显示领了 12 瓶——对得上吗？',
  '丙酮泄漏怎么处置？',
]
</script>

<template>
  <div class="flex h-full min-w-0 flex-col bg-surface">
    <!-- 会话头：窄屏下折行，避免控件溢出 -->
    <header class="flex min-h-14 shrink-0 flex-wrap items-center gap-2 border-b border-line px-4 py-2">
      <h2 class="min-w-0 truncate text-[14px] font-semibold text-ink">
        {{ session?.title ?? 'AI 对话' }}
      </h2>
      <span
        v-if="isBackend"
        class="inline-flex h-5 shrink-0 items-center rounded border border-ok/20 bg-ok-soft px-1.5 text-[11px] font-medium text-ok"
        title="已连接后端服务，回答来自真实运行"
      >已连接后端服务</span>
      <span v-else class="mock-tag shrink-0" title="模拟模式：未连接真实模型，回答为预设内容">模拟模式 · 未连接真实模型</span>

      <div class="ml-auto flex items-center gap-2">
        <label class="sr-only" for="agent-select">选择 Agent</label>
        <select
          id="agent-select"
          class="input h-8 max-w-[9rem] text-[12px]"
          :value="session?.agentId"
          @change="emit('agent', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
        </select>
        <button
          type="button"
          class="btn-ghost h-8 w-8 p-0"
          :aria-pressed="contextOpen"
          :aria-label="contextOpen ? '隐藏检索上下文' : '显示检索上下文'"
          title="检索上下文"
          @click="emit('toggle-context')"
        >
          <PanelRight class="size-4" />
        </button>
        <button
          type="button"
          class="btn-ghost h-8 w-8 p-0"
          aria-label="清空当前会话"
          title="清空会话"
          :disabled="!session?.messages.length || busy"
          @click="emit('clear')"
        >
          <Trash2 class="size-4" />
        </button>
      </div>
    </header>

    <!-- 高亮告警区 -->
    <div v-if="alerts.length" class="shrink-0 space-y-1.5 border-b border-line bg-page px-4 py-2" aria-live="polite">
      <div
        v-for="a in alerts"
        :key="a.text"
        :class="[
          'flex items-center gap-1.5 rounded-[var(--radius-control)] border px-2.5 py-1.5 text-[12px] font-medium',
          a.tone === 'danger' ? 'border-err/20 bg-err-soft text-err' : 'border-warn/20 bg-warn-soft text-warn',
        ]"
      >
        <ShieldAlert v-if="a.tone === 'danger'" class="size-3.5 shrink-0" aria-hidden="true" />
        <AlertTriangle v-else class="size-3.5 shrink-0" aria-hidden="true" />
        {{ a.text }}
      </div>
    </div>

    <!-- 消息区 -->
    <div ref="scroller" class="flex-1 overflow-y-auto px-4 py-5">
      <div v-if="!session || !messages.length" class="mx-auto max-w-2xl py-8">
        <h3 class="text-[16px] font-semibold text-ink">向实验室治理助手提问</h3>
        <p class="mt-1 text-[13px] text-ink-2">
          本系统只读：可查资质、授权、通行记录、台账与规程，不能修改任何数据。
        </p>
        <ul class="mt-4 grid gap-2 sm:grid-cols-2">
          <li v-for="p in promptExamples" :key="p">
            <button
              type="button"
              class="w-full rounded-[var(--radius-panel)] border border-line px-3 py-2.5 text-left text-[13px] text-ink hover:border-brand hover:bg-brand-soft"
              @click="input = p"
            >{{ p }}</button>
          </li>
        </ul>
      </div>

      <ul v-else class="mx-auto max-w-3xl space-y-5">
        <li v-for="m in messages" :key="m.id" class="flex flex-col gap-2">
          <div v-if="m.role === 'user'" class="flex justify-end">
            <div class="max-w-[85%] rounded-[var(--radius-panel)] bg-brand-soft px-3.5 py-2.5">
              <p class="whitespace-pre-wrap break-words text-[14px] leading-[1.7] text-ink">{{ m.content }}</p>
            </div>
          </div>

          <div v-else class="flex flex-col gap-2">
            <div
              :class="[
                'rounded-[var(--radius-panel)] border px-3.5 py-3',
                m.refused ? 'border-warn/30 bg-warn-soft' : 'border-line bg-surface',
              ]"
            >
              <MessageContent :text="m.content" />
            </div>
            <div class="flex items-center gap-1.5 text-[12px] text-ink-3">
              <span>{{ m.createdAt }}</span>
              <span v-if="m.refused" class="text-warn">· 控制类请求已拒绝（只读系统）</span>
              <span v-else-if="m.sources?.length" class="text-ink-3">· 引用 {{ m.sources.length }} 条来源</span>
              <span class="ml-auto flex items-center gap-1">
                <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="copyMessage(m)">
                  <Copy class="size-3.5" aria-hidden="true" />复制
                </button>
                <button
                  type="button"
                  class="btn-ghost h-7 px-2 text-[12px]"
                  :disabled="busy"
                  @click="emit('regenerate', m.id)"
                >
                  <RefreshCw class="size-3.5" aria-hidden="true" />重新生成
                </button>
              </span>
            </div>
          </div>
        </li>

        <li v-if="busy" class="flex flex-col gap-2">
          <div class="rounded-[var(--radius-panel)] border border-line px-3.5 py-3">
            <p v-if="!streamingText" class="flex items-center gap-2 text-[13px] text-ink-2">
              <span class="size-1.5 animate-pulse rounded-full bg-brand" aria-hidden="true" />
              正在思考…（模拟，未连接真实模型）
            </p>
            <MessageContent v-else :text="streamingText" plain />
          </div>
        </li>
      </ul>
    </div>

    <!-- 输入区 -->
    <div class="shrink-0 border-t border-line px-4 py-3">
      <form class="mx-auto max-w-3xl" @submit.prevent="submit">
        <label class="sr-only" for="chat-input">输入你的问题</label>
        <textarea
          id="chat-input"
          v-model="input"
          rows="2"
          class="textarea resize-none"
          placeholder="例：上周进过 3 号间的人里，有谁资质过期？（Enter 发送，Shift + Enter 换行）"
          @keydown="onKeydown"
        />
        <div class="mt-2 flex items-center gap-2">
          <p class="text-[12px] text-ink-3">只读系统 · 修改资质 / 台账 / 授权 / 导名单 / 开门一律拒绝</p>
          <div class="ml-auto flex gap-2">
            <button v-if="busy" type="button" class="btn-default" @click="emit('stop')">
              <Square class="size-3.5" aria-hidden="true" />停止生成
            </button>
            <button type="submit" class="btn-primary" :disabled="busy || !input.trim()">
              <Send class="size-3.5" aria-hidden="true" />发送
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>
