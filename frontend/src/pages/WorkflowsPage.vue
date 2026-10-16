<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Plus, Copy, Play, Trash2 } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { newId, plainClone } from '@/utils/format'
import type { Workflow } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const keyword = ref('')
const statusFilter = ref<'all' | Workflow['status']>('all')
const confirmDelete = ref<Workflow | null>(null)
const running = ref<string | null>(null)

const rows = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return workspace.state.workflows.filter((w) => {
    if (statusFilter.value !== 'all' && w.status !== statusFilter.value) return false
    if (!q) return true
    return w.name.toLowerCase().includes(q) || w.description.toLowerCase().includes(q)
  })
})

const columns: Column[] = [
  { key: 'name', label: '工作流名称' },
  { key: 'nodes', label: '节点数', align: 'right' },
  { key: 'status', label: '状态' },
  { key: 'createdAt', label: '创建时间' },
  { key: 'lastRunAt', label: '最近运行' },
  { key: 'actions', label: '', align: 'right' },
]

function create() {
  const wf: Workflow = {
    id: newId('wf'), name: '未命名工作流', description: '（未填写描述）',
    nodes: [{ id: 'n-start', type: 'start', label: '开始', x: 40, y: 140, config: {} }],
    edges: [], status: 'draft', createdAt: '2026-10-15 10:00', lastRunAt: null,
  }
  workspace.upsertWorkflow(wf)
  ui.toast('已创建工作流草稿')
  router.push(`/workflows/${wf.id}`)
}

watch(() => route.query.create, (v) => {
  if (v) {
    create()
    router.replace({ path: '/workflows' })
  }
}, { immediate: true })

function duplicate(w: Workflow) {
  const copy: Workflow = {
    ...plainClone(w), id: newId('wf'), name: `${w.name}（副本）`,
    status: 'draft', createdAt: '2026-10-15 10:00', lastRunAt: null,
  }
  workspace.upsertWorkflow(copy)
  ui.toast(`已复制为「${copy.name}」`)
}

function run(w: Workflow) {
  running.value = w.id
  window.setTimeout(() => {
    running.value = null
    router.push(`/workflows/${w.id}?run=1`)
  }, 400)
}

function doDelete() {
  if (!confirmDelete.value) return
  const name = confirmDelete.value.name
  workspace.removeWorkflow(confirmDelete.value.id)
  confirmDelete.value = null
  ui.toast(`已删除「${name}」`)
}
</script>

<template>
  <PageHeader title="工作流" description="用节点方式编排准入判定与台账核查流程（模拟执行）。">
    <template #actions>
      <button type="button" class="btn-primary" @click="create"><Plus class="size-4" aria-hidden="true" />新建工作流</button>
    </template>
    <template #filters>
      <SearchInput v-model="keyword" label="搜索工作流" placeholder="搜索名称或描述" />
      <label class="sr-only" for="wf-status">状态筛选</label>
      <select id="wf-status" v-model="statusFilter" class="input w-auto">
        <option value="all">全部状态</option>
        <option value="published">已发布</option>
        <option value="draft">草稿</option>
      </select>
    </template>
  </PageHeader>

  <EmptyState v-if="!workspace.state.workflows.length" title="还没有工作流" description="创建一个工作流，把准入判定与台账核查串成可复用流程。">
    <template #action><button type="button" class="btn-primary" @click="create">新建工作流</button></template>
  </EmptyState>

  <EmptyState v-else-if="!rows.length" title="没有符合条件的工作流" description="调整搜索词或筛选条件试试。" />

  <DataTable v-else :columns="columns" :rows="rows" caption="工作流列表" @row="(r) => router.push(`/workflows/${r.id}`)">
    <template #name="{ row }">
      <span class="block font-medium text-ink">{{ row.name }}</span>
      <span class="block text-[12px] text-ink-3">{{ row.description }}</span>
    </template>
    <template #nodes="{ row }">{{ row.nodes.length }}</template>
    <template #status="{ row }">
      <StatusBadge :status="row.status === 'published' ? 'success' : 'pending'" :label="row.status === 'published' ? '已发布' : '草稿'" />
    </template>
    <template #lastRunAt="{ row }">{{ row.lastRunAt ?? '—' }}</template>
    <template #actions="{ row }">
      <span class="inline-flex gap-1" @click.stop>
        <button type="button" class="btn-ghost h-7 px-2 text-[12px]" :disabled="running === row.id" @click="run(row)">
          <Play class="size-3.5" aria-hidden="true" />{{ running === row.id ? '运行中' : '运行' }}
        </button>
        <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="duplicate(row)"><Copy class="size-3.5" aria-hidden="true" />复制</button>
        <button type="button" class="btn-ghost h-7 px-2 text-[12px] text-err" @click="confirmDelete = row"><Trash2 class="size-3.5" aria-hidden="true" />删除</button>
      </span>
    </template>
  </DataTable>

  <p class="sr-only"><RouterLink to="/workflows/wf-access">打开示例工作流</RouterLink></p>

  <ConfirmDialog
    :open="!!confirmDelete"
    title="删除该工作流？"
    :description="confirmDelete ? `「${confirmDelete.name}」及其节点配置将被删除。` : ''"
    confirm-text="删除"
    danger
    @update:open="confirmDelete = null"
    @confirm="doDelete"
  />
</template>
