<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { FlaskConical, Scale, AlertTriangle, Info } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatCard from '@/components/common/StatCard.vue'
import AppDrawer from '@/components/common/AppDrawer.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { isSensitive, toInterval } from '@/utils/guard'
import type { HazardClass, HazardItem, Status } from '@/types'

const workspace = useWorkspaceStore()

const keyword = ref('')
const labFilter = ref('all')
const classFilter = ref<'all' | HazardClass>('all')
const detail = ref<HazardItem | null>(null)

const HAZARD_CLASSES: HazardClass[] = ['易燃液体', '腐蚀品', '氧化剂', '剧毒品', '易制爆', '一般化学品']

const CLASS_TONE: Record<HazardClass, Status> = {
  剧毒品: 'failed',
  易制爆: 'warning',
  易燃液体: 'warning',
  腐蚀品: 'pending',
  氧化剂: 'running',
  一般化学品: 'idle',
}

/** 结存展示：剧毒品与易制爆一律区间化，不显示精确值（红线） */
function qtyText(item: HazardItem): string {
  if (isSensitive(item.hazardClass)) return toInterval(item.quantity, item.unit)
  return `${item.quantity} ${item.unit}`
}

/** 某条台账的领用合计 */
function usedTotal(item: HazardItem): number {
  return workspace.usesOfItem(item.id).reduce((sum, u) => sum + u.quantity, 0)
}

/**
 * 账物校验：与后端 reconcile_inventory 同口径——
 * 无期初结存时按周转校验，领用超过结存即为不符信号，阈值 max(1, 结存 × 5%)。
 */
function isAnomaly(item: HazardItem): boolean {
  const used = usedTotal(item)
  if (!used) return false
  const threshold = Math.max(1, item.quantity * 0.05)
  return Math.abs(used - item.quantity) > threshold
}

const rows = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return workspace.state.inventory.filter((i) => {
    if (labFilter.value !== 'all' && i.labId !== labFilter.value) return false
    if (classFilter.value !== 'all' && i.hazardClass !== classFilter.value) return false
    if (!q) return true
    return i.chemName.toLowerCase().includes(q) || i.casNo.toLowerCase().includes(q)
  })
})

const sensitiveCount = computed(() => workspace.state.inventory.filter((i) => isSensitive(i.hazardClass)).length)
const anomalyCount = computed(() => workspace.state.inventory.filter(isAnomaly).length)

/** 缺见证人的领用记录数：剧毒品与易制爆要求双人领用 */
const noWitnessCount = computed(
  () => workspace.state.hazmatUses.filter((u) => u.witnessId === null).length,
)

const columns: Column[] = [
  { key: 'chemName', label: '化学品' },
  { key: 'casNo', label: 'CAS 号' },
  { key: 'hazardClass', label: '危险类别' },
  { key: 'lab', label: '所在实验室' },
  { key: 'cabinetNo', label: '存放柜' },
  { key: 'quantity', label: '结存', align: 'right' },
  { key: 'updatedAt', label: '数据截至' },
  { key: 'actions', label: '', align: 'right' },
]

const detailUses = computed(() => (detail.value ? workspace.usesOfItem(detail.value.id) : []))
const detailUsed = computed(() => detailUses.value.reduce((s, u) => s + u.quantity, 0))

function personName(id: string | null) {
  if (!id) return '—'
  const p = workspace.findPerson(id)
  return p ? `${p.name}（${p.empNo}）` : id
}
</script>

<template>
  <PageHeader title="药剂管理" description="查看危化品台账结存、存放位置与领用记录。剧毒品与易制爆的精确数量不予展示。">
    <template #filters>
      <SearchInput v-model="keyword" label="搜索化学品" placeholder="搜索名称或 CAS 号" />
      <label class="sr-only" for="reagent-lab">实验室筛选</label>
      <select id="reagent-lab" v-model="labFilter" class="input w-auto">
        <option value="all">全部实验室</option>
        <option v-for="l in workspace.state.labs" :key="l.labId" :value="l.labId">{{ l.labId }} {{ l.labName }}</option>
      </select>
      <label class="sr-only" for="reagent-class">危险类别筛选</label>
      <select id="reagent-class" v-model="classFilter" class="input w-auto">
        <option value="all">全部危险类别</option>
        <option v-for="c in HAZARD_CLASSES" :key="c" :value="c">{{ c }}</option>
      </select>
    </template>
  </PageHeader>

  <p class="mb-4 text-[12px] text-ink-3">以下为演示数据（模拟），不代表真实台账。</p>

  <section aria-label="台账概览" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <StatCard label="台账条目" :value="String(workspace.state.inventory.length)" hint="全部实验室" />
    <StatCard label="剧毒 / 易制爆" :value="String(sensitiveCount)" hint="精确数量区间化展示" />
    <StatCard
      label="账物差异待核实"
      :value="String(anomalyCount)"
      :delta="anomalyCount ? '需核对领用与结存' : '未发现异常'"
      :delta-tone="anomalyCount ? 'down' : 'flat'"
    />
    <StatCard
      label="缺见证人领用"
      :value="String(noWitnessCount)"
      :delta="noWitnessCount ? '剧毒品与易制爆要求双人' : '记录完整'"
      :delta-tone="noWitnessCount ? 'down' : 'flat'"
    />
  </section>

  <EmptyState v-if="!workspace.state.inventory.length" title="还没有台账条目" description="台账数据来自后端危化品台账表。" />
  <EmptyState v-else-if="!rows.length" title="没有符合条件的条目" description="调整搜索词或筛选条件试试。" />

  <div v-else class="mt-6">
    <DataTable :columns="columns" :rows="rows" caption="危化品台账列表" @row="(r) => (detail = r)">
      <template #chemName="{ row }">
        <span class="flex items-center gap-2">
          <span class="font-medium text-ink">{{ row.chemName }}</span>
          <StatusBadge v-if="isAnomaly(row)" status="failed" label="账物差异" />
        </span>
      </template>
      <template #casNo="{ row }"><span class="font-mono text-[12px] text-ink-2">{{ row.casNo }}</span></template>
      <template #hazardClass="{ row }"><StatusBadge :status="CLASS_TONE[row.hazardClass as HazardClass]" :label="row.hazardClass" /></template>
      <template #lab="{ row }">
        <span class="text-ink-2">{{ row.labId }}</span>
      </template>
      <template #quantity="{ row }">
        <span :class="isSensitive(row.hazardClass) ? 'text-warn' : 'text-ink'">{{ qtyText(row) }}</span>
      </template>
      <template #actions="{ row }">
        <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click.stop="detail = row">领用记录</button>
      </template>
    </DataTable>

    <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
      <Info class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      剧毒品与易制爆的结存按区间展示（不足 5 为「少量」，其后按 5 / 50 / 500 分段），
      精确数量请联系实验室安全负责人核对实物。系统只读，不能修改台账。
    </p>
  </div>

  <AppDrawer :open="!!detail" :title="detail ? `${detail.chemName} · 领用记录` : ''" width="lg" @update:open="detail = null">
    <div v-if="detail" class="space-y-5">
      <section>
        <h3 class="label">台账信息</h3>
        <dl class="grid grid-cols-1 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-2">
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">化学品</dt><dd class="text-ink">{{ detail.chemName }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">CAS 号</dt><dd class="font-mono text-ink">{{ detail.casNo }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">危险类别</dt><dd><StatusBadge :status="CLASS_TONE[detail.hazardClass]" :label="detail.hazardClass" /></dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">所在实验室</dt><dd class="text-ink">{{ detail.labId }} {{ workspace.findLab(detail.labId)?.labName }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2"><dt class="text-ink-2">存放柜</dt><dd class="text-ink">{{ detail.cabinetNo }}</dd></div>
          <div class="flex items-center justify-between gap-2 border-b border-line pb-2">
            <dt class="text-ink-2">结存</dt>
            <dd :class="isSensitive(detail.hazardClass) ? 'text-warn' : 'text-ink'">{{ qtyText(detail) }}</dd>
          </div>
        </dl>
      </section>

      <section>
        <h3 class="mb-2 flex items-center gap-1.5 text-[12px] text-ink-2">
          <Scale class="size-3.5" aria-hidden="true" />账物校验（近 30 天）
        </h3>
        <div :class="['rounded-[var(--radius-control)] border p-3 text-[13px]', isAnomaly(detail) ? 'border-err/30 bg-err-soft' : 'border-line']">
          <p v-if="isSensitive(detail.hazardClass)" class="text-warn">
            该化学品属 {{ detail.hazardClass }}，结存与领用合计均按区间处理，不提供精确差值。
          </p>
          <template v-else>
            <p class="text-ink">台账结存 {{ detail.quantity }} {{ detail.unit }}，领用合计 {{ detailUsed }} {{ detail.unit }}（{{ detailUses.length }} 笔）</p>
            <p class="mt-1 flex items-center gap-1.5" :class="isAnomaly(detail) ? 'text-err' : 'text-ink-2'">
              <AlertTriangle v-if="isAnomaly(detail)" class="size-3.5" aria-hidden="true" />
              {{ isAnomaly(detail)
                ? `存在账物不符，需核实（合理损耗阈值 ±${Math.max(1, detail.quantity * 0.05).toFixed(2)} ${detail.unit}）`
                : '在合理损耗范围内，暂未发现异常' }}
            </p>
          </template>
        </div>
      </section>

      <section>
        <h3 class="label">领用明细</h3>
        <ul v-if="detailUses.length" class="space-y-2">
          <li v-for="u in detailUses" :key="u.id" class="rounded-[var(--radius-control)] border border-line p-3 text-[12px]">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-ink">{{ personName(u.personId) }}</span>
              <span class="tabular-nums text-ink-3">{{ u.useTime }}</span>
              <span class="ml-auto tabular-nums text-ink">
                {{ isSensitive(detail.hazardClass) ? toInterval(u.quantity, detail.unit) : `${u.quantity} ${detail.unit}` }}
              </span>
            </div>
            <p class="mt-1 text-ink-2">用途：{{ u.purpose }}</p>
            <p class="mt-0.5" :class="u.witnessId ? 'text-ink-3' : 'text-warn'">
              见证人：{{ u.witnessId ? personName(u.witnessId) : '未登记（剧毒品与易制爆要求双人领用）' }}
            </p>
          </li>
        </ul>
        <p v-else class="text-[12px] text-ink-3">该条目没有领用记录。</p>
      </section>

      <p class="rounded-[var(--radius-control)] bg-warn-soft px-3 py-2 text-[12px] text-warn">
        本页为演示数据。系统只读，不能修改台账、报损或核销；相关操作请走实验室安全负责人人工审批。
      </p>
    </div>
  </AppDrawer>

  <p class="mt-6 flex items-center gap-2 text-[12px] text-ink-3">
    <FlaskConical class="size-3.5" aria-hidden="true" />
    需要按化学品排查账物差异时，可到
    <RouterLink to="/chat" class="text-brand hover:underline">AI 对话</RouterLink>
    提问，或查看
    <RouterLink to="/access" class="text-brand hover:underline">出入管理</RouterLink>。
  </p>
</template>
