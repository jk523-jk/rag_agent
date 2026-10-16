<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Copy, Search } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppDrawer from '@/components/common/AppDrawer.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { copyText, downloadText, fmtDuration } from '@/utils/format'
import type { LogEntry } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const keyword = ref('')
const typeFilter = ref<'all' | LogEntry['taskType']>('all')
const statusFilter = ref<'all' | LogEntry['status']>('all')
const rangeFilter = ref<'all' | 'today' | '7d'>('all')
const sortKey = ref('startedAt')
const sortAsc = ref(false)
const page = ref(1)
const pageSize = 10
const detail = ref<LogEntry | null>(null)

const TYPE_LABEL: Record<LogEntry['taskType'], string> = {
  chat: '对话', retrieval: '检索', workflow: '工作流', evaluation: '评估',
}

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  let list = workspace.state.logs.filter((l) => {
    if (typeFilter.value !== 'all' && l.taskType !== typeFilter.value) return false
    if (statusFilter.value !== 'all' && l.status !== statusFilter.value) return false
    if (rangeFilter.value === 'today' && !l.startedAt.startsWith('2026-10-15')) return false
    if (rangeFilter.value === '7d' && l.startedAt < '2026-10-09') return false
    if (!q) return true
    return l.id.toLowerCase().includes(q) || l.target.toLowerCase().includes(q)
  })
  const dir = sortAsc.value ? 1 : -1
  list = [...list].sort((a, b) => {
    if (sortKey.value === 'durationMs') return (a.durationMs - b.durationMs) * dir
    if (sortKey.value === 'status') return a.status.localeCompare(b.status) * dir
    return a.startedAt.localeCompare(b.startedAt) * dir
  })
  return list
})

const paged = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize)))

watch([keyword, typeFilter, statusFilter, rangeFilter], () => { page.value = 1 })

const columns: Column[] = [
  { key: 'id', label: '任务 ID', sortable: true },
  { key: 'taskType', label: '任务类型' },
  { key: 'target', label: 'Agent / 工作流' },
  { key: 'startedAt', label: '开始时间', sortable: true },
  { key: 'durationMs', label: '耗时', align: 'right', sortable: true },
  { key: 'status', label: '状态', sortable: true },
  { key: 'actions', label: '', align: 'right' },
]

function onSort(key: string) {
  if (sortKey.value === key) sortAsc.value = !sortAsc.value
  else {
    sortKey.value = key
    sortAsc.value = false
  }
}

function exportRows() {
  if (!filtered.value.length) {
    ui.toast('当前没有可导出的记录', 'error')
    return
  }
  downloadText(`execution-logs-2026-10-15.json`, JSON.stringify({ isMock: true, rows: filtered.value }, null, 2))
  ui.toast(`已导出 ${filtered.value.length} 条记录（含模拟标记）`)
}

async function copyId(id: string) {
  const ok = await copyText(id)
  ui.toast(ok ? '已复制任务 ID' : '复制失败', ok ? 'success' : 'error')
}

async function copyError() {
  if (!detail.value?.error) return
  const ok = await copyText(detail.value.error)
  ui.toast(ok ? '已复制错误信息' : '复制失败', ok ? 'success' : 'error')
}

// 支持从工作台跳转：/logs?id=xxx 直接打开详情
watch(() => route.query.id, (id) => {
  if (!id) return
  const found = workspace.state.logs.find((l) => l.id === id)
  if (found) detail.value = found
  router.replace({ path: '/logs' })
}, { immediate: true })
</script>

<template>
  <PageHeader title="运行日志" description="查看对话、检索、工作流与评估任务的执行记录。">
    <template #actions>
      <button type="button" class="btn-default" @click="exportRows"><Download class="size-4" aria-hidden="true" />导出当前记录</button>
    </template>
    <template #filters>
      <div class="relative w-full sm:w-64">
        <label class="sr-only" for="log-search">搜索任务 ID 或名称</label>
        <Search class="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
        <input id="log-search" v-model="keyword" type="search" class="input pl-8" placeholder="搜索任务 ID / 名称…" />
      </div>
      <label class="sr-only" for="log-type">任务类型</label>
      <select id="log-type" v-model="typeFilter" class="input w-auto">
        <option value="all">全部类型</option>
        <option v-for="(label, key) in TYPE_LABEL" :key="key" :value="key">{{ label }}</option>
      </select>
      <label class="sr-only" for="log-status">状态</label>
      <select id="log-status" v-model="statusFilter" class="input w-auto">
        <option value="all">全部状态</option>
        <option value="success">成功</option>
        <option value="running">运行中</option>
        <option value="failed">失败</option>
      </select>
      <label class="sr-only" for="log-range">时间范围</label>
      <select id="log-range" v-model="rangeFilter" class="input w-auto">
        <option value="all">全部时间</option>
        <option value="today">今天</option>
        <option value="7d">近 7 天</option>
      </select>
    </template>
  </PageHeader>

  <EmptyState v-if="!workspace.state.logs.length" title="还没有执行记录" description="在对话、检索或工作流页面执行任务后，记录会出现在这里。" />
  <EmptyState v-else-if="!filtered.length" title="没有符合条件的记录" description="调整搜索词或筛选条件试试。" />

  <template v-else>
    <DataTable
      :columns="columns"
      :rows="paged"
      caption="运行日志列表"
      :sort-key="sortKey"
      :sort-asc="sortAsc"
      @sort="onSort"
      @row="(r) => (detail = r)"
    >
      <template #id="{ row }"><span class="font-mono text-[12px] text-ink">{{ row.id }}</span></template>
      <template #taskType="{ row }">{{ TYPE_LABEL[row.taskType as LogEntry['taskType']] }}</template>
      <template #durationMs="{ row }">{{ fmtDuration(row.durationMs) }}</template>
      <template #status="{ row }"><StatusBadge :status="row.status" /></template>
      <template #actions="{ row }">
        <span class="inline-flex gap-1" @click.stop>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" aria-label="复制任务 ID" @click="copyId(row.id)"><Copy class="size-3.5" aria-hidden="true" /></button>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="detail = row">详情</button>
        </span>
      </template>
    </DataTable>

    <div class="mt-3 flex items-center gap-2 text-[12px] text-ink-2">
      <span>共 {{ filtered.length }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
      <span class="ml-auto flex gap-2">
        <button type="button" class="btn-default h-7 px-2 text-[12px]" :disabled="page <= 1" @click="page--">上一页</button>
        <button type="button" class="btn-default h-7 px-2 text-[12px]" :disabled="page >= totalPages" @click="page++">下一页</button>
      </span>
    </div>
  </template>

  <AppDrawer :open="!!detail" :title="detail ? `任务详情 · ${detail.id}` : ''" width="lg" @update:open="detail = null">
    <div v-if="detail" class="space-y-5">
      <section>
        <h3 class="label">基础信息</h3>
        <dl class="grid grid-cols-1 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-2">
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">任务类型</dt><dd class="text-ink">{{ TYPE_LABEL[detail.taskType] }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">执行对象</dt><dd class="truncate text-ink">{{ detail.target }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">开始时间</dt><dd class="tabular-nums text-ink">{{ detail.startedAt }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">耗时</dt><dd class="tabular-nums text-ink">{{ fmtDuration(detail.durationMs) }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">状态</dt><dd><StatusBadge :status="detail.status" /></dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">Token 消耗（模拟）</dt><dd class="tabular-nums text-ink">{{ detail.tokens.toLocaleString() }}</dd></div>
        </dl>
        <p class="mt-2 flex gap-2">
          <button type="button" class="btn-default h-7 px-2 text-[12px]" @click="copyId(detail.id)"><Copy class="size-3.5" aria-hidden="true" />复制任务 ID</button>
        </p>
      </section>

      <section>
        <h3 class="label">执行步骤</h3>
        <ul v-if="detail.steps.length" class="space-y-2">
          <li v-for="s in detail.steps" :key="s.nodeId" class="rounded-[var(--radius-control)] border border-line p-3">
            <div class="flex items-center gap-2 text-[12px]">
              <span class="font-medium text-ink">{{ s.label }}</span>
              <StatusBadge :status="s.status" />
              <span class="ml-auto tabular-nums text-ink-3">{{ s.durationMs }} ms</span>
            </div>
            <dl class="mt-2 space-y-1 text-[12px]">
              <div class="flex gap-2"><dt class="w-12 shrink-0 text-ink-3">输入</dt><dd class="text-ink-2">{{ s.input }}</dd></div>
              <div class="flex gap-2"><dt class="w-12 shrink-0 text-ink-3">输出</dt><dd :class="s.error ? 'text-err' : 'text-ink-2'">{{ s.error || s.output || '—' }}</dd></div>
            </dl>
          </li>
        </ul>
        <p v-else class="text-[12px] text-ink-3">该任务没有可展示的节点级步骤。</p>
      </section>

      <section v-if="detail.error">
        <h3 class="label">错误信息</h3>
        <p class="rounded-[var(--radius-control)] border border-err/30 bg-err-soft px-3 py-2 text-[12px] text-err">{{ detail.error }}</p>
        <button type="button" class="btn-default mt-2 h-7 px-2 text-[12px]" @click="copyError"><Copy class="size-3.5" aria-hidden="true" />复制错误信息</button>
      </section>

      <section v-if="detail.linkedChunks.length">
        <h3 class="label">关联的检索结果</h3>
        <ul class="flex flex-wrap gap-1.5">
          <li v-for="c in detail.linkedChunks" :key="c" class="rounded border border-line bg-page px-2 py-0.5 font-mono text-[12px] text-ink-2">{{ c }}</li>
        </ul>
      </section>

      <p class="rounded-[var(--radius-control)] bg-warn-soft px-3 py-2 text-[12px] text-warn">
        本记录为模拟数据，Token 消耗与耗时均为演示值。
      </p>
    </div>
  </AppDrawer>
</template>
