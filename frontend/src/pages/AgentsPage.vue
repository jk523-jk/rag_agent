<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { LayoutGrid, Table2, Plus, Copy, Power, PowerOff, Trash2, Pencil, MoreHorizontal, Bot, BookOpen, FlaskConical, Workflow } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import AgentForm from '@/components/forms/AgentForm.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { newId, plainClone } from '@/utils/format'
import type { Agent } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const view = ref<'card' | 'table'>('card')
const keyword = ref('')
const statusFilter = ref<'all' | 'enabled' | 'disabled'>('all')
const typeFilter = ref<'all' | Agent['icon']>('all')
const formOpen = ref(false)
const editing = ref<Agent | null>(null)
const confirmDelete = ref<Agent | null>(null)
const menuId = ref<string | null>(null)

const TYPE_LABEL: Record<Agent['icon'], string> = {
  shield: '准入', book: '规程', flask: '台账', workflow: '编排',
}
const TYPE_ICON = { shield: Bot, book: BookOpen, flask: FlaskConical, workflow: Workflow }

const rows = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return workspace.state.agents.filter((a) => {
    if (statusFilter.value !== 'all' && a.status !== statusFilter.value) return false
    if (typeFilter.value !== 'all' && a.icon !== typeFilter.value) return false
    if (!q) return true
    return a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q)
  })
})

const columns: Column[] = [
  { key: 'name', label: '名称', sortable: false },
  { key: 'model', label: '模型' },
  { key: 'tools', label: '工具', align: 'right' },
  { key: 'knowledge', label: '知识库' },
  { key: 'status', label: '状态' },
  { key: 'lastRunAt', label: '最近运行' },
  { key: 'actions', label: '', align: 'right' },
]

function kbNames(a: Agent) {
  return a.knowledgeIds.map((id) => workspace.findKb(id)?.name ?? id).join('、') || '—'
}

function openCreate() {
  editing.value = null
  formOpen.value = true
}

function openEdit(a: Agent) {
  menuId.value = null
  editing.value = a
  formOpen.value = true
}

// 支持从工作台 / 顶部快捷按钮跳转：/agents?create=1
watch(() => route.query.create, (v) => {
  if (v) {
    openCreate()
    router.replace({ path: '/agents' })
  }
}, { immediate: true })

function duplicate(a: Agent) {
  menuId.value = null
  const copy: Agent = { ...plainClone(a), id: newId('agt'), name: `${a.name}（副本）`, status: 'disabled', runCount: 0, lastRunAt: '—' }
  workspace.upsertAgent(copy)
  ui.toast(`已复制为「${copy.name}」，默认停用`)
}

function toggleStatus(a: Agent) {
  menuId.value = null
  const next = a.status === 'enabled' ? 'disabled' : 'enabled'
  workspace.upsertAgent({ ...a, status: next })
  ui.toast(next === 'enabled' ? `已启用「${a.name}」` : `已停用「${a.name}」`)
}

function doDelete() {
  if (!confirmDelete.value) return
  const name = confirmDelete.value.name
  workspace.removeAgent(confirmDelete.value.id)
  confirmDelete.value = null
  ui.toast(`已删除「${name}」`)
}
</script>

<template>
  <PageHeader title="Agent 管理" description="创建、配置和管理 AI 智能体。">
    <template #actions>
      <div role="group" aria-label="视图切换" class="inline-flex rounded-[var(--radius-control)] border border-line p-0.5">
        <button type="button" :aria-pressed="view === 'card'" :class="['h-7 px-2 rounded-[4px]', view === 'card' ? 'bg-brand-soft text-brand' : 'text-ink-2']" aria-label="卡片视图" @click="view = 'card'">
          <LayoutGrid class="size-4" />
        </button>
        <button type="button" :aria-pressed="view === 'table'" :class="['h-7 px-2 rounded-[4px]', view === 'table' ? 'bg-brand-soft text-brand' : 'text-ink-2']" aria-label="表格视图" @click="view = 'table'">
          <Table2 class="size-4" />
        </button>
      </div>
      <button type="button" class="btn-primary" @click="openCreate"><Plus class="size-4" aria-hidden="true" />新建 Agent</button>
    </template>
    <template #filters>
      <SearchInput v-model="keyword" label="搜索 Agent" placeholder="搜索名称或描述" />
      <label class="sr-only" for="agent-status-filter">状态筛选</label>
      <select id="agent-status-filter" v-model="statusFilter" class="input w-auto">
        <option value="all">全部状态</option>
        <option value="enabled">启用中</option>
        <option value="disabled">已停用</option>
      </select>
      <label class="sr-only" for="agent-type-filter">类型筛选</label>
      <select id="agent-type-filter" v-model="typeFilter" class="input w-auto">
        <option value="all">全部类型</option>
        <option v-for="(label, key) in TYPE_LABEL" :key="key" :value="key">{{ label }}</option>
      </select>
    </template>
  </PageHeader>

  <EmptyState v-if="!workspace.state.agents.length" title="还没有 Agent" description="创建第一个 Agent，把它绑定到知识库并配置可用工具。">
    <template #action>
      <button type="button" class="btn-primary" @click="openCreate">新建 Agent</button>
    </template>
  </EmptyState>

  <EmptyState v-else-if="!rows.length" title="没有符合条件的 Agent" description="调整搜索词或筛选条件试试。" />

  <!-- 卡片视图 -->
  <ul v-else-if="view === 'card'" class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
    <li v-for="a in rows" :key="a.id" class="panel flex flex-col p-4">
      <div class="flex items-start gap-3">
        <span class="grid size-9 shrink-0 place-items-center rounded-[var(--radius-control)] bg-brand-soft text-brand">
          <component :is="TYPE_ICON[a.icon]" class="size-4" aria-hidden="true" />
        </span>
        <div class="min-w-0 flex-1">
          <RouterLink :to="`/agents/${a.id}`" class="block truncate text-[14px] font-semibold text-ink hover:text-brand">{{ a.name }}</RouterLink>
          <p class="mt-0.5 line-clamp-2 text-[12px] text-ink-2">{{ a.description }}</p>
        </div>
        <div class="relative">
          <button type="button" class="btn-ghost h-7 w-7 p-0" :aria-label="`${a.name} 的更多操作`" aria-haspopup="menu" :aria-expanded="menuId === a.id" @click="menuId = menuId === a.id ? null : a.id">
            <MoreHorizontal class="size-4" />
          </button>
          <ul v-if="menuId === a.id" role="menu" class="absolute right-0 top-8 z-20 w-36 panel py-1 shadow-lg text-[13px]">
            <li><button role="menuitem" type="button" class="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-page" @click="openEdit(a)"><Pencil class="size-3.5" />编辑</button></li>
            <li><button role="menuitem" type="button" class="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-page" @click="duplicate(a)"><Copy class="size-3.5" />复制</button></li>
            <li><button role="menuitem" type="button" class="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-page" @click="toggleStatus(a)"><component :is="a.status === 'enabled' ? PowerOff : Power" class="size-3.5" />{{ a.status === 'enabled' ? '停用' : '启用' }}</button></li>
            <li><button role="menuitem" type="button" class="flex w-full items-center gap-2 px-3 py-1.5 text-err hover:bg-err-soft" @click="menuId = null; confirmDelete = a"><Trash2 class="size-3.5" />删除</button></li>
          </ul>
        </div>
      </div>

      <dl class="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-[12px]">
        <div><dt class="text-ink-3">使用模型</dt><dd class="text-ink">{{ a.model }}</dd></div>
        <div><dt class="text-ink-3">工具数量</dt><dd class="text-ink tabular-nums">{{ a.tools.length }}</dd></div>
        <div class="col-span-2"><dt class="text-ink-3">关联知识库</dt><dd class="truncate text-ink">{{ kbNames(a) }}</dd></div>
        <div><dt class="text-ink-3">最近运行</dt><dd class="text-ink tabular-nums">{{ a.lastRunAt }}</dd></div>
      </dl>

      <div class="mt-auto flex items-center justify-between border-t border-line pt-3">
        <StatusBadge :status="a.status === 'enabled' ? 'success' : 'disabled'" :label="a.status === 'enabled' ? '启用中' : '已停用'" />
        <RouterLink :to="`/agents/${a.id}`" class="text-[13px] text-brand hover:underline">查看详情</RouterLink>
      </div>
    </li>
  </ul>

  <!-- 表格视图 -->
  <DataTable v-else :columns="columns" :rows="rows" caption="Agent 列表" @row="(r) => router.push(`/agents/${r.id}`)">
    <template #name="{ row }">
      <span class="font-medium text-ink">{{ row.name }}</span>
    </template>
    <template #tools="{ row }">{{ row.tools.length }}</template>
    <template #knowledge="{ row }">{{ kbNames(row) }}</template>
    <template #status="{ row }">
      <StatusBadge :status="row.status === 'enabled' ? 'success' : 'disabled'" :label="row.status === 'enabled' ? '启用中' : '已停用'" />
    </template>
    <template #actions="{ row }">
      <span class="inline-flex gap-1" @click.stop>
        <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="openEdit(row)">编辑</button>
        <button type="button" class="btn-ghost h-7 px-2 text-[12px] text-err" @click="confirmDelete = row">删除</button>
      </span>
    </template>
  </DataTable>

  <AgentForm v-model:open="formOpen" :agent="editing" />

  <ConfirmDialog
    :open="!!confirmDelete"
    title="删除该 Agent？"
    :description="confirmDelete ? `「${confirmDelete.name}」及其配置将被删除，已有会话不受影响。` : ''"
    confirm-text="删除"
    danger
    @update:open="confirmDelete = null"
    @confirm="doDelete"
  />
</template>
