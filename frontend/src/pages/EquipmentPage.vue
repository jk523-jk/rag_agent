<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Plus, Microscope, Pencil, Trash2, AlertTriangle, CalendarClock } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatCard from '@/components/common/StatCard.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import EquipmentForm from '@/components/forms/EquipmentForm.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { todayIso } from '@/utils/clock'
import type { Equipment, EquipCategory, EquipStatus, Status } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const keyword = ref('')
const labFilter = ref('all')
const statusFilter = ref<'all' | EquipStatus>('all')
const categoryFilter = ref<'all' | EquipCategory>('all')
const formOpen = ref(false)
const editing = ref<Equipment | null>(null)
const confirmDelete = ref<Equipment | null>(null)

const EQUIP_CATEGORIES: EquipCategory[] = ['分析仪器', '合成设备', '检测仪器', '储存设施', '其他']
const EQUIP_STATUSES: EquipStatus[] = ['在用', '维修中', '停用', '报废']

const STATUS_TONE: Record<EquipStatus, Status> = {
  在用: 'success',
  维修中: 'warning',
  停用: 'disabled',
  报废: 'failed',
}

/** 校准剩余天数。储存设施无校准要求时为 null。 */
function calibrateDaysLeft(e: Equipment): number | null {
  if (!e.calibrateDue) return null
  const due = Date.parse(`${e.calibrateDue}T00:00:00`)
  const today = Date.parse(`${todayIso}T00:00:00`)
  return Math.round((due - today) / 86400000)
}

function isCalibrationExpired(e: Equipment): boolean {
  const d = calibrateDaysLeft(e)
  return d !== null && d < 0
}

function isCalibrationDueSoon(e: Equipment): boolean {
  const d = calibrateDaysLeft(e)
  return d !== null && d >= 0 && d <= 30
}

/** 校准状态文案。无校准要求不误报为过期，与后端 _calibrate_text 口径一致。 */
function calibrateText(e: Equipment): string {
  const d = calibrateDaysLeft(e)
  if (d === null) return '无校准要求'
  if (d < 0) return `已过期 ${Math.abs(d)} 天`
  if (d <= 30) return `${d} 天后到期`
  return `有效期至 ${e.calibrateDue}`
}

/** 当前持有记录（未归还） */
function holder(e: Equipment) {
  return workspace.currentLoan(e.equipId)
}

function holderText(e: Equipment): string {
  const loan = holder(e)
  if (!loan) return '未借出'
  const p = workspace.findPerson(loan.personId)
  return p ? `${p.name}（${p.empNo}）` : loan.personId
}

/** 借出且已过应还时间 */
function isLoanOverdue(e: Equipment): boolean {
  const loan = holder(e)
  if (!loan) return false
  return loan.dueTime < `${todayIso} 23:59`
}

function keeperText(e: Equipment): string {
  if (!e.keeperId) return '未登记'
  const p = workspace.findPerson(e.keeperId)
  return p ? `${p.name}（${p.empNo}）` : e.keeperId
}

const rows = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return workspace.state.equipment.filter((e) => {
    if (labFilter.value !== 'all' && e.labId !== labFilter.value) return false
    if (statusFilter.value !== 'all' && e.status !== statusFilter.value) return false
    if (categoryFilter.value !== 'all' && e.category !== categoryFilter.value) return false
    if (!q) return true
    return (
      e.equipName.toLowerCase().includes(q) ||
      e.equipId.toLowerCase().includes(q) ||
      e.modelNo.toLowerCase().includes(q)
    )
  })
})

const expiredCount = computed(() => workspace.state.equipment.filter(isCalibrationExpired).length)
const dueSoonCount = computed(() => workspace.state.equipment.filter(isCalibrationDueSoon).length)
const borrowedCount = computed(
  () => workspace.state.equipment.filter((e) => workspace.currentLoan(e.equipId)).length,
)
const overdueCount = computed(() => workspace.state.equipment.filter(isLoanOverdue).length)

const columns: Column[] = [
  { key: 'equipId', label: '设备编号' },
  { key: 'equipName', label: '设备名称' },
  { key: 'category', label: '类别' },
  { key: 'labId', label: '所在实验室' },
  { key: 'keeper', label: '保管人' },
  { key: 'status', label: '状态' },
  { key: 'calibrate', label: '校准' },
  { key: 'loan', label: '借还' },
  { key: 'actions', label: '', align: 'right' },
]

// 支持从工作台 / 顶部快捷按钮跳转：/equipment?create=1
watch(() => route.query.create, (v) => {
  if (v) {
    editing.value = null
    formOpen.value = true
    router.replace({ path: '/equipment' })
  }
}, { immediate: true })

function openCreate() {
  editing.value = null
  formOpen.value = true
}

function openEdit(e: Equipment) {
  editing.value = e
  formOpen.value = true
}

function doDelete() {
  if (!confirmDelete.value) return
  const name = confirmDelete.value.equipName
  const id = confirmDelete.value.id
  // 级联：设备移除时其借还记录一并移除，避免留下指向不存在设备的孤儿记录
  workspace.state.equipment = workspace.state.equipment.filter((e) => e.id !== id)
  workspace.state.equipmentLoans = workspace.state.equipmentLoans.filter(
    (l) => l.equipId !== confirmDelete.value!.equipId,
  )
  confirmDelete.value = null
  ui.toast(`已移除设备「${name}」及其借还记录`)
}

const openLoans = computed(() =>
  workspace.state.equipmentLoans
    .filter((l) => l.returnTime === null)
    .sort((a, b) => a.dueTime.localeCompare(b.dueTime)),
)
</script>

<template>
  <PageHeader title="设备管理" description="管理实验室设备台账、启用状态与校准有效期，查看借出与逾期情况。">
    <template #actions>
      <button type="button" class="btn-primary" @click="openCreate">
        <Plus class="size-4" aria-hidden="true" />新增设备
      </button>
    </template>
    <template #filters>
      <SearchInput v-model="keyword" label="搜索设备" placeholder="搜索名称、编号或型号" />
      <label class="sr-only" for="equip-lab">实验室筛选</label>
      <select id="equip-lab" v-model="labFilter" class="input w-auto">
        <option value="all">全部实验室</option>
        <option v-for="l in workspace.state.labs" :key="l.labId" :value="l.labId">{{ l.labId }} {{ l.labName }}</option>
      </select>
      <label class="sr-only" for="equip-status">状态筛选</label>
      <select id="equip-status" v-model="statusFilter" class="input w-auto">
        <option value="all">全部状态</option>
        <option v-for="s in EQUIP_STATUSES" :key="s" :value="s">{{ s }}</option>
      </select>
      <label class="sr-only" for="equip-category">类别筛选</label>
      <select id="equip-category" v-model="categoryFilter" class="input w-auto">
        <option value="all">全部类别</option>
        <option v-for="c in EQUIP_CATEGORIES" :key="c" :value="c">{{ c }}</option>
      </select>
    </template>
  </PageHeader>

  <p class="mb-4 text-[12px] text-ink-3">以下为演示数据（模拟），不代表真实资产台账。</p>

  <section aria-label="设备概览" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <StatCard label="设备总数" :value="String(workspace.state.equipment.length)" hint="含储存设施" />
    <StatCard
      label="校准已过期"
      :value="String(expiredCount)"
      :delta="expiredCount ? '按规定不得用于出具数据' : '无'"
      :delta-tone="expiredCount ? 'down' : 'flat'"
    />
    <StatCard label="30 天内到期" :value="String(dueSoonCount)" hint="预警窗口内" />
    <StatCard
      label="借出 / 其中逾期"
      :value="`${borrowedCount} / ${overdueCount}`"
      :delta="overdueCount ? '需催还' : '无逾期'"
      :delta-tone="overdueCount ? 'down' : 'flat'"
    />
  </section>

  <!-- 校准与逾期告警：不能只靠颜色区分，同时给出文字与图标 -->
  <section
    v-if="expiredCount || overdueCount"
    class="mt-4 panel border-warn/30 bg-warn-soft p-4"
    aria-label="设备告警"
  >
    <h2 class="flex items-center gap-1.5 text-[13px] font-medium text-warn">
      <AlertTriangle class="size-4" aria-hidden="true" />需处理的设备
    </h2>
    <ul class="mt-2 space-y-1 text-[12px] text-warn">
      <li v-if="expiredCount">
        校准已过期 {{ expiredCount }} 台：
        {{ workspace.state.equipment.filter(isCalibrationExpired).map((e) => e.equipId).join('、') }}
        ——按规定不得用于出具数据，请安排送检。
      </li>
      <li v-if="overdueCount">
        借出逾期 {{ overdueCount }} 台：
        {{ workspace.state.equipment.filter(isLoanOverdue).map((e) => e.equipId).join('、') }}
        ——请催还并核对设备状态。
      </li>
    </ul>
  </section>

  <EmptyState v-if="!workspace.state.equipment.length" title="还没有设备" description="新增第一台设备，或从后端同步设备台账。">
    <template #action><button type="button" class="btn-primary" @click="openCreate">新增设备</button></template>
  </EmptyState>
  <EmptyState v-else-if="!rows.length" title="没有符合条件的设备" description="调整搜索词或筛选条件试试。" />

  <div v-else class="mt-6">
    <DataTable :columns="columns" :rows="rows" caption="设备台账列表" @row="(r) => router.push(`/equipment/${r.id}`)">
      <template #equipId="{ row }"><span class="font-mono text-[12px] text-ink-2">{{ row.equipId }}</span></template>
      <template #equipName="{ row }">
        <span class="flex flex-col">
          <span class="font-medium text-ink">{{ row.equipName }}</span>
          <span v-if="row.modelNo" class="text-[12px] text-ink-3">{{ row.modelNo }}</span>
        </span>
      </template>
      <template #keeper="{ row }">{{ keeperText(row) }}</template>
      <template #status="{ row }"><StatusBadge :status="STATUS_TONE[row.status as EquipStatus]" :label="row.status" /></template>
      <template #calibrate="{ row }">
        <span
          class="inline-flex items-center gap-1"
          :class="isCalibrationExpired(row) ? 'text-err' : isCalibrationDueSoon(row) ? 'text-warn' : 'text-ink-2'"
        >
          <AlertTriangle v-if="isCalibrationExpired(row)" class="size-3.5" aria-hidden="true" />
          <CalendarClock v-else-if="isCalibrationDueSoon(row)" class="size-3.5" aria-hidden="true" />
          {{ calibrateText(row) }}
        </span>
      </template>
      <template #loan="{ row }">
        <span v-if="!holder(row)" class="text-ink-3">未借出</span>
        <span v-else class="inline-flex flex-col">
          <span :class="isLoanOverdue(row) ? 'text-err' : 'text-ink'">{{ holderText(row) }}</span>
          <span v-if="isLoanOverdue(row)" class="text-[12px] text-err">逾期未还</span>
          <span v-else class="text-[12px] text-ink-3">借用中</span>
        </span>
      </template>
      <template #actions="{ row }">
        <span class="inline-flex gap-1" @click.stop>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="openEdit(row)"><Pencil class="size-3.5" aria-hidden="true" />编辑</button>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px] text-err" @click="confirmDelete = row"><Trash2 class="size-3.5" aria-hidden="true" />移除</button>
        </span>
      </template>
    </DataTable>
  </div>

  <!-- 借出台账 -->
  <section v-if="openLoans.length" class="panel mt-6" aria-labelledby="loans-title">
    <div class="flex items-center gap-2 border-b border-line px-4 py-3">
      <h2 id="loans-title" class="text-[15px] font-semibold text-ink">当前借出（{{ openLoans.length }}）</h2>
      <RouterLink to="/access" class="ml-auto text-[13px] text-brand hover:underline">查看全部出入记录</RouterLink>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full min-w-[720px] text-[13px]">
        <caption class="sr-only">尚未归还的设备借出记录</caption>
        <thead class="bg-page text-ink-2">
          <tr>
            <th scope="col" class="h-9 px-4 text-left font-medium">设备</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">借用人</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">借出时间</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">应还时间</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">状态</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">批准人</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in openLoans" :key="l.id" class="border-t border-line">
            <td class="px-4 py-2.5">
              <span class="block font-medium text-ink">{{ workspace.findEquipment(l.equipId)?.equipName ?? l.equipId }}</span>
              <span class="font-mono text-[12px] text-ink-3">{{ l.equipId }}</span>
            </td>
            <td class="px-4 py-2.5 text-ink">
              {{ workspace.findPerson(l.personId)?.name ?? l.personId }}
              <span class="text-[12px] text-ink-3">{{ workspace.findPerson(l.personId)?.empNo }}</span>
            </td>
            <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ l.borrowTime }}</td>
            <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ l.dueTime }}</td>
            <td class="px-4 py-2.5">
              <StatusBadge :status="l.status === '逾期' ? 'failed' : 'running'" :label="l.status" />
            </td>
            <td class="px-4 py-2.5 text-ink-2">{{ l.approver }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <EquipmentForm v-model:open="formOpen" :equipment="editing" />

  <ConfirmDialog
    :open="!!confirmDelete"
    title="移除该设备？"
    :description="confirmDelete ? `「${confirmDelete.equipName}」（${confirmDelete.equipId}）及其借还记录将被移除。演示环境下的本地操作，后端资产台账不受影响。` : ''"
    confirm-text="移除"
    danger
    @update:open="confirmDelete = null"
    @confirm="doDelete"
  />

  <p class="mt-6 flex items-center gap-2 text-[12px] text-ink-3">
    <Microscope class="size-3.5" aria-hidden="true" />
    设备校准是否过期一律以校准有效期为准——台账中存在状态仍为「在用」但校准已过期的记录。
  </p>
</template>
