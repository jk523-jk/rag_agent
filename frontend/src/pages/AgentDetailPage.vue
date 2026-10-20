<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { ArrowLeft, Pencil, Play, Copy, Trash2 } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import CodeBlock from '@/components/common/CodeBlock.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import AgentForm from '@/components/forms/AgentForm.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { copyText } from '@/utils/format'
import { USE_BACKEND } from '@/utils/clock'
import { streamChatFromBackend } from '@/services/chatApi'
import { answerFor } from '@/services/chatEngine'

const route = useRoute()
const router = useRouter()
const workspace = useWorkspaceStore()
const ui = useUiStore()

/** Agent 可查询的只读数据域，用于替代原「知识库绑定」展示 */
const DATA_SOURCES = [
  '人员 · 资质 · 实验室授权',
  '门禁通行记录',
  '危化品台账 · 领用记录',
  '设备台账 · 借还记录 · 校准',
  '安全规程 · 危化品管理制度 · SDS 摘要',
]

const agent = computed(() => workspace.findAgent(String(route.params.id)))
const formOpen = ref(false)
const confirmDelete = ref(false)

// 测试运行：backend 模式是**真实调用**该 Agent（会查库、会花 token）；mock 模式走本地剧本
const testInput = ref('')
const testOutput = ref('')
const testElapsed = ref<number | null>(null)
const testing = ref(false)
let controller: AbortController | null = null

const runs = computed(() => workspace.state.logs.filter((l) => l.target === agent.value?.name).slice(0, 5))

async function runTest() {
  const q = testInput.value.trim()
  if (!q || !agent.value) return
  testing.value = true
  testOutput.value = ''
  testElapsed.value = null

  if (!USE_BACKEND) {
    window.setTimeout(() => {
      testOutput.value = answerFor(q).text
      testing.value = false
    }, 700)
    return
  }

  const started = performance.now()
  controller = new AbortController()
  try {
    await streamChatFromBackend(
      q,
      `test-${agent.value.id}-${Date.now()}`,
      agent.value.id,
      {
        onDelta: (delta) => { testOutput.value += delta },
        onReplace: (text) => { testOutput.value = text },
      },
      controller.signal,
    )
    testElapsed.value = Math.round(performance.now() - started)
  } catch (e) {
    testOutput.value = `调用失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    testing.value = false
  }
}

async function copyId() {
  const ok = await copyText(agent.value?.id ?? '')
  ui.toast(ok ? '已复制 Agent ID' : '复制失败', ok ? 'success' : 'error')
}

async function doDelete() {
  if (!agent.value) return
  const name = agent.value.name
  const id = agent.value.id
  confirmDelete.value = false
  try {
    await workspace.deleteAgentById(id)
    ui.toast(`已删除「${name}」`)
    router.push('/agents')
  } catch (e) {
    ui.toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}
</script>

<template>
  <div v-if="agent">
    <PageHeader :title="agent.name" :description="agent.description">
      <template #actions>
        <button type="button" class="btn-ghost" @click="copyId"><Copy class="size-4" aria-hidden="true" />复制 ID</button>
        <button type="button" class="btn-default" @click="formOpen = true"><Pencil class="size-4" aria-hidden="true" />编辑</button>
        <RouterLink :to="`/chat`" class="btn-primary"><Play class="size-4" aria-hidden="true" />去对话测试</RouterLink>
        <button type="button" class="btn-danger" @click="confirmDelete = true"><Trash2 class="size-4" aria-hidden="true" />删除</button>
      </template>
    </PageHeader>

    <RouterLink to="/agents" class="mb-4 inline-flex items-center gap-1 text-[13px] text-ink-2 hover:text-ink">
      <ArrowLeft class="size-3.5" aria-hidden="true" />返回 Agent 列表
    </RouterLink>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <!-- 基础信息与模型配置 -->
      <section class="panel p-4" aria-labelledby="basic-title">
        <h2 id="basic-title" class="mb-3 text-[15px] font-semibold text-ink">基础信息</h2>
        <dl class="space-y-2.5 text-[13px]">
          <div class="flex items-center justify-between gap-3"><dt class="text-ink-2">状态</dt><dd><StatusBadge :status="agent.status === 'enabled' ? 'success' : 'disabled'" :label="agent.status === 'enabled' ? '启用中' : '已停用'" /></dd></div>
          <div class="flex items-center justify-between gap-3"><dt class="text-ink-2">Agent ID</dt><dd class="font-mono text-[12px] text-ink">{{ agent.id }}</dd></div>
          <div class="flex items-center justify-between gap-3"><dt class="text-ink-2">使用模型</dt><dd class="text-ink">{{ agent.model }}</dd></div>
          <div class="flex items-center justify-between gap-3"><dt class="text-ink-2">温度</dt><dd class="tabular-nums text-ink">{{ agent.temperature }}</dd></div>
          <div class="flex items-center justify-between gap-3"><dt class="text-ink-2">最大输出 Token</dt><dd class="tabular-nums text-ink">{{ agent.maxTokens }}</dd></div>
          <div class="flex items-center justify-between gap-3"><dt class="text-ink-2">累计运行</dt><dd class="tabular-nums text-ink">{{ agent.runCount }} 次</dd></div>
          <div class="flex items-center justify-between gap-3"><dt class="text-ink-2">最近运行</dt><dd class="tabular-nums text-ink">{{ agent.lastRunAt }}</dd></div>
        </dl>
      </section>

      <!-- 系统提示词 -->
      <section class="panel p-4 xl:col-span-2" aria-labelledby="prompt-title">
        <h2 id="prompt-title" class="mb-3 text-[15px] font-semibold text-ink">系统提示词</h2>
        <CodeBlock :code="agent.systemPrompt" lang="text" />
      </section>

      <!-- 工具权限 -->
      <section class="panel p-4" aria-labelledby="tools-title">
        <h2 id="tools-title" class="mb-3 text-[15px] font-semibold text-ink">工具权限（{{ agent.tools.length }}）</h2>
        <p v-if="!agent.tools.length" class="text-[12px] text-ink-3">未授予任何工具。</p>
        <ul v-else class="flex flex-wrap gap-1.5">
          <li v-for="t in agent.tools" :key="t" class="rounded border border-line bg-page px-2 py-0.5 font-mono text-[12px] text-ink">{{ t }}</li>
        </ul>
        <p class="mt-3 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
          本系统只读：不存在任何写入类工具，控制类请求会被拒绝。
        </p>
      </section>

      <!-- 数据来源 -->
      <section class="panel p-4" aria-labelledby="kb-title">
        <h2 id="kb-title" class="mb-3 text-[15px] font-semibold text-ink">数据来源</h2>
        <p class="text-[12px] text-ink-3">
          本 Agent 通过上方工具查询后端只读数据：人员资质与授权、危化品台账与领用、
          设备台账与借还记录、安全规程与 SDS 语料。不绑定知识库，语料检索由
          <code class="font-mono">search_policy</code> 工具完成。
        </p>
        <ul class="mt-3 flex flex-wrap gap-1.5">
          <li v-for="src in DATA_SOURCES" :key="src" class="rounded border border-line bg-page px-2 py-0.5 text-[12px] text-ink-2">{{ src }}</li>
        </ul>
      </section>

      <!-- 测试运行 -->
      <section class="panel p-4" aria-labelledby="test-title">
        <h2 id="test-title" class="mb-1 text-[15px] font-semibold text-ink">测试运行</h2>
        <p class="mb-3 text-[12px] text-ink-3">
          {{ USE_BACKEND ? '真实调用该 Agent（会查库、消耗 token）。' : '模拟运行，不会调用真实模型。' }}
        </p>
        <form @submit.prevent="runTest">
          <label class="sr-only" for="test-input">测试问题</label>
          <textarea id="test-input" v-model="testInput" rows="2" class="textarea" placeholder="例：王景尧现在能不能进 LAB-3？" />
          <button type="submit" class="btn-primary mt-2 w-full" :disabled="testing || !testInput.trim()">
            <Play class="size-3.5" aria-hidden="true" />{{ testing ? '运行中…' : '运行测试' }}
          </button>
        </form>
        <div v-if="testOutput" class="mt-3">
          <p class="label">
            输出{{ USE_BACKEND ? '' : '（模拟）' }}
            <span v-if="testElapsed !== null" class="ml-1 text-ink-3">· 耗时 {{ testElapsed }}ms</span>
          </p>
          <pre class="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-[var(--radius-control)] border border-line bg-page p-3 text-[12px] leading-relaxed text-ink">{{ testOutput }}</pre>
        </div>
      </section>
    </div>

    <!-- 最近运行记录 -->
    <section class="panel mt-4" aria-labelledby="runs-title">
      <div class="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 id="runs-title" class="text-[15px] font-semibold text-ink">最近运行记录</h2>
        <RouterLink to="/logs" class="text-[13px] text-brand hover:underline">全部日志</RouterLink>
      </div>
      <EmptyState v-if="!runs.length" title="暂无运行记录" description="在上方测试运行，或到 AI 对话页向该 Agent 提问。" />
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[560px] text-[13px]">
          <caption class="sr-only">该 Agent 的最近运行记录</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">任务 ID</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">开始时间</th>
              <th scope="col" class="h-9 px-4 text-right font-medium">耗时</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">状态</th>
              <th scope="col" class="h-9 px-4 text-right font-medium">Token（模拟）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in runs" :key="r.id" class="border-t border-line">
              <td class="px-4 py-2.5 font-mono text-[12px] text-ink">{{ r.id }}</td>
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ r.startedAt }}</td>
              <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ (r.durationMs / 1000).toFixed(1) }} s</td>
              <td class="px-4 py-2.5"><StatusBadge :status="r.status" /></td>
              <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ r.tokens.toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <AgentForm v-model:open="formOpen" :agent="agent" />
    <ConfirmDialog
      :open="confirmDelete"
      title="删除该 Agent？"
      :description="`「${agent.name}」及其配置将被删除。`"
      confirm-text="删除"
      danger
      @update:open="confirmDelete = false"
      @confirm="doDelete"
    />
  </div>

  <EmptyState v-else title="Agent 不存在" description="它可能已被删除，或链接有误。">
    <template #action><RouterLink to="/agents" class="btn-primary">返回 Agent 列表</RouterLink></template>
  </EmptyState>
</template>
