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
import { answerFor } from '@/services/chatEngine'

const route = useRoute()
const router = useRouter()
const workspace = useWorkspaceStore()
const ui = useUiStore()

const agent = computed(() => workspace.findAgent(String(route.params.id)))
const formOpen = ref(false)
const confirmDelete = ref(false)

// 测试运行：直接跑模拟回答引擎，明确标注是模拟结果
const testInput = ref('')
const testOutput = ref('')
const testing = ref(false)

const runs = computed(() => workspace.state.logs.filter((l) => l.target === agent.value?.name).slice(0, 5))

function runTest() {
  const q = testInput.value.trim()
  if (!q) return
  testing.value = true
  window.setTimeout(() => {
    testOutput.value = answerFor(q).text
    testing.value = false
  }, 700)
}

async function copyId() {
  const ok = await copyText(agent.value?.id ?? '')
  ui.toast(ok ? '已复制 Agent ID' : '复制失败', ok ? 'success' : 'error')
}

function doDelete() {
  if (!agent.value) return
  const name = agent.value.name
  workspace.removeAgent(agent.value.id)
  confirmDelete.value = false
  ui.toast(`已删除「${name}」`)
  router.push('/agents')
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

      <!-- 知识库绑定 -->
      <section class="panel p-4" aria-labelledby="kb-title">
        <h2 id="kb-title" class="mb-3 text-[15px] font-semibold text-ink">知识库绑定（{{ agent.knowledgeIds.length }}）</h2>
        <p v-if="!agent.knowledgeIds.length" class="text-[12px] text-ink-3">未绑定知识库，规程类问题将回答“未找到相关规定”。</p>
        <ul v-else class="space-y-1.5">
          <li v-for="id in agent.knowledgeIds" :key="id">
            <RouterLink :to="`/knowledge/${id}`" class="flex items-center justify-between rounded-[var(--radius-control)] border border-line px-3 py-2 text-[13px] text-ink hover:border-brand hover:bg-brand-soft">
              <span>{{ workspace.findKb(id)?.name ?? id }}</span>
              <span class="text-[12px] text-ink-3">{{ workspace.findKb(id)?.chunkCount ?? 0 }} chunk</span>
            </RouterLink>
          </li>
        </ul>
      </section>

      <!-- 测试运行 -->
      <section class="panel p-4" aria-labelledby="test-title">
        <h2 id="test-title" class="mb-1 text-[15px] font-semibold text-ink">测试运行</h2>
        <p class="mb-3 text-[12px] text-ink-3">模拟运行，不会调用真实模型。</p>
        <form @submit.prevent="runTest">
          <label class="sr-only" for="test-input">测试问题</label>
          <textarea id="test-input" v-model="testInput" rows="2" class="textarea" placeholder="例：王某现在能不能进 LAB-3？" />
          <button type="submit" class="btn-primary mt-2 w-full" :disabled="testing || !testInput.trim()">
            <Play class="size-3.5" aria-hidden="true" />{{ testing ? '运行中…' : '运行测试' }}
          </button>
        </form>
        <div v-if="testOutput" class="mt-3">
          <p class="label">输出（模拟）</p>
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
