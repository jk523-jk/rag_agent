<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Play, RefreshCw } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppDrawer from '@/components/common/AppDrawer.vue'
import StatCard from '@/components/common/StatCard.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useUiStore } from '@/stores/ui'
import {
  fetchWorkflowRun, listWorkflowRuns, listWorkflowTemplates, runWorkflowApi,
} from '@/services/dataApi'
import type {
  InspectionFinding, InspectionRun, InspectionRunSummary, WorkflowTemplate,
} from '@/types'
const ui = useUiStore()

const templates = ref<WorkflowTemplate[]>([])
const runs = ref<InspectionRunSummary[]>([])
const current = ref<InspectionRun | null>(null)
const selectedId = ref<string>('')
const running = ref(false)
const loadingRuns = ref(false)
const detail = ref<InspectionFinding | null>(null)
const severityFilter = ref<'all' | 'high' | 'medium' | 'low'>('all')
const paramValues = ref<Record<string, unknown>>({})

const selected = computed(() => templates.value.find((t) => t.id === selectedId.value) ?? null)

const SEV_LABEL: Record<string, string> = { high: '高', medium: '中', low: '低' }
const SEV_TONE: Record<string, 'failed' | 'warning' | 'idle'> = {
  high: 'failed', medium: 'warning', low: 'idle',
}
const CHECK_STATUS_TONE: Record<string, 'success' | 'failed' | 'pending'> = {
  ok: 'success', error: 'failed', skipped: 'pending',
}

const filteredFindings = computed(() => {
  const list = current.value?.findings ?? []
  const base = severityFilter.value === 'all' ? list : list.filter((f) => f.severity === severityFilter.value)
  return base.map((f) => ({ ...f, id: f.key }))
})

const runRows = computed(() => runs.value.map((r) => ({ ...r, id: r.run_id })))

const findingColumns: Column[] = [
  { key: 'severity', label: '严重度' },
  { key: 'title', label: '结论' },
  { key: 'subjectLabel', label: '主体' },
  { key: 'owner', label: '责任人' },
  { key: 'daysOpen', label: '持续', align: 'right' },
]

const runColumns: Column[] = [
  { key: 'started_at', label: '开始时间' },
  { key: 'workflow_name', label: '模板' },
  { key: 'status', label: '状态' },
  { key: 'total', label: '异常数', align: 'right' },
  { key: 'duration_ms', label: '耗时', align: 'right' },
]

async function loadTemplates() {
  try {
    templates.value = await listWorkflowTemplates()
    if (!selectedId.value && templates.value.length) {
      selectedId.value = templates.value[0].id
    }
  } catch (e) {
    ui.toast(e instanceof Error ? e.message : '加载巡检模板失败', 'error')
  }
}

async function loadRuns() {
  loadingRuns.value = true
  try {
    runs.value = await listWorkflowRuns(undefined, 20)
  } catch {
    runs.value = []
  } finally {
    loadingRuns.value = false
  }
}

function initParams() {
  paramValues.value = {}
  for (const p of selected.value?.params ?? []) {
    if (p.default !== undefined) paramValues.value[p.name] = p.default
    else if (p.type === 'boolean') paramValues.value[p.name] = false
  }
}

async function runNow() {
  if (!selected.value || running.value) return
  running.value = true
  current.value = null
  try {
    const report = await runWorkflowApi(selected.value.id, { ...paramValues.value })
    current.value = report
    severityFilter.value = 'all'
    await loadRuns()
    if (report.status === 'partial') {
      ui.toast(`巡检不完整：${report.incompleteReason || '部分检查失败'}`, 'error')
    } else {
      ui.toast(`巡检完成，发现 ${report.counts.total} 项异常`, report.counts.total ? 'success' : 'success')
    }
  } catch (e) {
    ui.toast(e instanceof Error ? e.message : '巡检运行失败', 'error')
  } finally {
    running.value = false
  }
}

async function openRun(runId: string) {
  try {
    current.value = await fetchWorkflowRun(runId)
    severityFilter.value = 'all'
  } catch (e) {
    ui.toast(e instanceof Error ? e.message : '加载运行记录失败', 'error')
  }
}

function openFinding(f: InspectionFinding) {
  detail.value = f
}

function onTemplateChange() {
  initParams()
}

onMounted(async () => {
  await loadTemplates()
  initParams()
  await loadRuns()
})
</script>

<template>
  <PageHeader title="风险巡检" description="按固定流程批量交叉校验人/料/机/双人闸，输出带责任人的风险清单。">
    <template #actions>
      <button type="button" class="btn-default" :disabled="loadingRuns" @click="loadRuns">
        <RefreshCw class="size-4" aria-hidden="true" />刷新历史
      </button>
      <button type="button" class="btn-primary" :disabled="!selected || running" @click="runNow">
        <Play class="size-4" aria-hidden="true" />{{ running ? '巡检中…' : '立即运行' }}
      </button>
    </template>
  </PageHeader>

  <!-- 模板选择 -->
  <section class="mb-4 grid gap-3 md:grid-cols-3">
    <button
      v-for="t in templates"
      :key="t.id"
      type="button"
      :class="[
        'rounded-[var(--radius-card)] border p-4 text-left transition',
        selectedId === t.id ? 'border-brand bg-brand-soft' : 'border-line bg-panel hover:border-ink-3',
      ]"
      @click="selectedId = t.id; onTemplateChange()"
    >
      <div class="flex items-center justify-between">
        <span class="text-[14px] font-medium text-ink">{{ t.name }}</span>
        <span class="text-[11px] text-ink-3">{{ t.checks.length }} 项检查</span>
      </div>
      <p class="mt-1 text-[12px] text-ink-2">{{ t.description }}</p>
      <p class="mt-2 text-[11px] text-ink-3">窗口 {{ t.windowDays }} 天</p>
    </button>
  </section>

  <!-- 参数 -->
  <section v-if="selected && selected.params.length" class="mb-4 flex flex-wrap items-end gap-3 rounded-[var(--radius-card)] border border-line bg-panel p-3">
    <div v-for="p in selected.params" :key="p.name" class="flex flex-col gap-1">
      <label class="text-[12px] text-ink-2">{{ p.label }}</label>
      <select
        v-if="p.type === 'select'"
        v-model="paramValues[p.name]"
        class="h-8 rounded-[var(--radius-control)] border border-line bg-page px-2 text-[12.5px]"
      >
        <option :value="undefined">全部</option>
        <option v-for="opt in p.options" :key="opt" :value="opt">{{ opt }}</option>
      </select>
      <input
        v-else-if="p.type === 'number'"
        v-model.number="paramValues[p.name]"
        type="number"
        class="h-8 w-28 rounded-[var(--radius-control)] border border-line bg-page px-2 text-[12.5px]"
      >
      <label v-else class="flex h-8 items-center gap-2 text-[12.5px]">
        <input v-model="paramValues[p.name]" type="checkbox"> 启用
      </label>
    </div>
  </section>

  <!-- 结果区 -->
  <section v-if="current" class="mb-6">
    <!-- partial 红色横幅：与「未发现异常」视觉完全不同 -->
    <div
      v-if="current.status === 'partial'"
      class="mb-3 rounded-[var(--radius-control)] border border-err/40 bg-err-soft px-3 py-2 text-[13px] text-err"
    >
      ⚠ 本次巡检不完整：{{ current.incompleteReason || '部分检查失败' }}。以下仅为已完成检查的结果，<strong>不代表无风险</strong>。
    </div>
    <div
      v-else-if="current.counts.total === 0"
      class="mb-3 rounded-[var(--radius-control)] border border-ok/40 bg-ok-soft px-3 py-2 text-[13px] text-ok"
    >
      ✓ 本次巡检完成，未发现异常（快照 {{ current.asOf }}）。
    </div>
    <div v-else class="mb-3 rounded-[var(--radius-control)] border border-line bg-panel px-3 py-2 text-[13px] text-ink-2">
      本次巡检完成，共 {{ current.counts.total }} 项异常（快照 {{ current.asOf }}，耗时 {{ (current.durationMs / 1000).toFixed(1) }} s）。
    </div>

    <!-- 统计卡 -->
    <div class="mb-3 grid grid-cols-3 gap-3">
      <button type="button" class="text-left" @click="severityFilter = severityFilter === 'high' ? 'all' : 'high'">
        <StatCard label="高" :value="String(current.counts.high)" :hint="severityFilter === 'high' ? '已筛选 · 点击取消' : '点击筛选'" />
      </button>
      <button type="button" class="text-left" @click="severityFilter = severityFilter === 'medium' ? 'all' : 'medium'">
        <StatCard label="中" :value="String(current.counts.medium)" :hint="severityFilter === 'medium' ? '已筛选 · 点击取消' : '点击筛选'" />
      </button>
      <button type="button" class="text-left" @click="severityFilter = severityFilter === 'low' ? 'all' : 'low'">
        <StatCard label="低" :value="String(current.counts.low)" :hint="severityFilter === 'low' ? '已筛选 · 点击取消' : '点击筛选'" />
      </button>
    </div>

    <!-- 检查项明细 -->
    <div class="mb-3 rounded-[var(--radius-card)] border border-line bg-panel">
      <div
        v-for="c in current.checks"
        :key="c.id"
        class="flex items-center gap-3 border-b border-line px-3 py-2 text-[12.5px] last:border-0"
      >
        <StatusBadge :status="CHECK_STATUS_TONE[c.status] ?? 'idle'" :label="c.status === 'ok' ? '正常' : c.status === 'error' ? '失败' : '跳过'" />
        <span class="flex-1 text-ink">{{ c.label }}</span>
        <span class="text-ink-3">{{ c.count }} 条 · {{ c.durationMs }} ms</span>
        <span v-if="c.error" class="max-w-[40%] truncate text-err" :title="c.error">{{ c.error }}</span>
      </div>
    </div>

    <!-- Findings 表 -->
    <DataTable
      v-if="filteredFindings.length"
      :columns="findingColumns"
      :rows="filteredFindings"
      caption="风险清单"
      @row="openFinding"
    >
      <template #cell-severity="{ row }">
        <StatusBadge :status="SEV_TONE[row.severity]" :label="SEV_LABEL[row.severity]" />
      </template>
      <template #cell-title="{ row }">
        <button type="button" class="text-left text-ink hover:text-brand" @click.stop="openFinding(row)">{{ row.title }}</button>
      </template>
      <template #cell-owner="{ row }">
        <span>{{ row.owner || '—' }}</span>
        <span v-if="row.ownerHint" class="ml-1 text-[11px] text-ink-3">（{{ row.ownerHint }}）</span>
      </template>
      <template #cell-daysOpen="{ row }">
        <span class="tabular-nums">{{ row.daysOpen }} 天</span>
      </template>
    </DataTable>
    <EmptyState v-else title="当前筛选下没有异常" description="切换严重度筛选，或查看上方检查项明细确认巡检完整性。" />
  </section>

  <!-- 空态：从未运行 -->
  <EmptyState
    v-else
    title="尚未运行巡检"
    description="选择上方模板后点击「立即运行」，或从下方历史记录查看过往结果。"
  />

  <!-- 运行历史 -->
  <section class="mt-8">
    <h2 class="mb-2 text-[15px] font-medium text-ink">运行历史</h2>
    <DataTable
      v-if="runs.length"
      :columns="runColumns"
      :rows="runRows"
      caption="运行历史"
      @row="(r) => openRun(r.run_id)"
    >
      <template #cell-status="{ row }">
        <StatusBadge
          :status="row.status === 'success' ? 'success' : row.status === 'partial' ? 'warning' : 'failed'"
          :label="row.status === 'success' ? '完成' : row.status === 'partial' ? '不完整' : '失败'"
        />
      </template>
      <template #cell-total="{ row }"><span class="tabular-nums">{{ row.counts.total }}</span></template>
      <template #cell-duration_ms="{ row }"><span class="tabular-nums">{{ (row.duration_ms / 1000).toFixed(1) }} s</span></template>
    </DataTable>
    <EmptyState v-else title="暂无运行记录" description="运行一次巡检后会出现在这里。" />
  </section>

  <!-- Finding 详情抽屉 -->
  <AppDrawer :open="!!detail" :title="detail?.title ?? ''" width="lg" @update:open="detail = null">
    <div v-if="detail" class="space-y-5">
      <section>
        <h3 class="label mb-2">判定</h3>
        <div class="flex items-center gap-2">
          <StatusBadge :status="SEV_TONE[detail.severity]" :label="SEV_LABEL[detail.severity]" />
          <span class="text-[12px] text-ink-3">持续 {{ detail.daysOpen }} 天 · 首次发现 {{ detail.firstSeen || '—' }}</span>
        </div>
      </section>
      <section>
        <h3 class="label mb-2">证据</h3>
        <dl class="space-y-1.5">
          <div v-for="(ev, i) in detail.evidence" :key="i" class="flex gap-2 text-[13px]">
            <dt class="w-32 shrink-0 text-ink-3">{{ ev.label }}</dt>
            <dd class="text-ink-2">{{ ev.value }}</dd>
          </div>
        </dl>
      </section>
      <section>
        <h3 class="label mb-2">责任</h3>
        <p class="text-[13px] text-ink-2">{{ detail.owner || '未登记' }}<span v-if="detail.ownerHint" class="text-ink-3">（{{ detail.ownerHint }}）</span></p>
      </section>
      <section>
        <h3 class="label mb-2">建议下一步</h3>
        <p class="text-[13px] leading-relaxed text-ink-2">{{ detail.suggest }}</p>
      </section>
      <section v-if="detail.links.length">
        <h3 class="label mb-2">相关页面</h3>
        <div class="flex flex-wrap gap-2">
          <RouterLink v-for="l in detail.links" :key="l.to" :to="l.to" class="btn-default h-8 px-3 text-[12.5px]">{{ l.label }}</RouterLink>
        </div>
      </section>
    </div>
  </AppDrawer>
</template>
