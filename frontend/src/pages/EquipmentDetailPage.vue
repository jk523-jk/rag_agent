<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { ArrowLeft, AlertTriangle, CalendarClock, Wrench } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import EquipmentForm from '@/components/forms/EquipmentForm.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { todayIso } from '@/utils/clock'
import type { EquipStatus, LoanStatus, Status } from '@/types'

const route = useRoute()
const workspace = useWorkspaceStore()
const ui = useUiStore()

const equipment = computed(() => workspace.findEquipment(String(route.params.id)))
const tab = ref<'info' | 'loans'>('info')
const formOpen = ref(false)
const confirmDelete = ref(false)

const STATUS_TONE: Record<EquipStatus, Status> = {
  在用: 'success', 维修中: 'warning', 停用: 'disabled', 报废: 'failed',
}
const LOAN_TONE: Record<LoanStatus, Status> = {
  借用中: 'running', 已归还: 'success', 逾期: 'failed',
}

const loans = computed(() => (equipment.value ? workspace.loansOfEquipment(equipment.value.equipId) : []))

function calibrateDaysLeft(): number | null {
  const e = equipment.value
  if (!e?.calibrateDue) return null
  const due = Date.parse(`${e.calibrateDue}T00:00:00`)
  const today = Date.parse(`${todayIso}T00:00:00`)
  return Math.round((due - today) / 86400000)
}

const isExpired = computed(() => {
  const d = calibrateDaysLeft()
  return d !== null && d < 0
})
const isDueSoon = computed(() => {
  const d = calibrateDaysLeft()
  return d !== null && d >= 0 && d <= 30
})

const calibrateText = computed(() => {
  const d = calibrateDaysLeft()
  if (d === null) return '无校准要求'
  if (d < 0) return `已过期 ${Math.abs(d)} 天（有效期至 ${equipment.value?.calibrateDue}）`
  if (d <= 30) return `${d} 天后到期（有效期至 ${equipment.value?.calibrateDue}）`
  return `有效期至 ${equipment.value?.calibrateDue}`
})

function personLabel(id: string | null) {
  if (!id) return '未登记'
  const p = workspace.findPerson(id)
  return p ? `${p.name}（${p.empNo}）` : id
}

const currentLoan = computed(() => (equipment.value ? workspace.currentLoan(equipment.value.equipId) : null))

function isLoanOverdue(loan: { dueTime: string; returnTime: string | null }): boolean {
  return loan.returnTime === null && loan.dueTime < `${todayIso} 23:59`
}

const hasOpenLoan = computed(() => loans.value.some((l) => l.returnTime === null))

function doDelete() {
  if (workspace.dataSource !== 'mock' || !equipment.value) return
  const { id, equipId, equipName } = equipment.value
  workspace.state.equipment = workspace.state.equipment.filter((e) => e.id !== id)
  workspace.state.equipmentLoans = workspace.state.equipmentLoans.filter((l) => l.equipId !== equipId)
  confirmDelete.value = false
  ui.toast(`已移除「${equipName}」及其借还记录`)
}
</script>

<template>
  <div v-if="equipment">
    <PageHeader :title="`${equipment.equipId} ${equipment.equipName}`" :description="`${equipment.category}${equipment.modelNo ? ' · ' + equipment.modelNo : ''} · ${equipment.labId}`">
      <template #actions>
        <button v-if="workspace.dataSource === 'mock'" type="button" class="btn-default" @click="formOpen = true">编辑设备</button>
        <button v-if="workspace.dataSource === 'mock'" type="button" class="btn-danger" @click="confirmDelete = true">移除</button>
      </template>
    </PageHeader>

    <RouterLink to="/equipment" class="mb-4 inline-flex items-center gap-1 text-[13px] text-ink-2 hover:text-ink">
      <ArrowLeft class="size-3.5" aria-hidden="true" />返回设备列表
    </RouterLink>

    <!-- 告警区：不能只靠颜色区分，同时给出图标与文字 -->
    <section v-if="isExpired || (currentLoan && isLoanOverdue(currentLoan))" class="panel mb-4 border-warn/30 bg-warn-soft p-4" aria-label="设备告警">
      <h2 class="flex items-center gap-1.5 text-[13px] font-medium text-warn">
        <AlertTriangle class="size-4" aria-hidden="true" />需处理
      </h2>
      <ul class="mt-2 space-y-1 text-[12px] text-warn">
        <li v-if="isExpired">校准已过期（{{ calibrateText }}）——按规定不得用于出具数据，请安排送检。</li>
        <li v-if="currentLoan && isLoanOverdue(currentLoan)">
          借出已逾期未还，持有人 {{ personLabel(currentLoan.personId) }}，应还 {{ currentLoan.dueTime }}——请催还。
        </li>
      </ul>
    </section>

    <div class="mb-4 border-b border-line" role="tablist" aria-label="设备详情">
      <button
        v-for="t in [
          { key: 'info', label: '设备信息' },
          { key: 'loans', label: `借还记录（${loans.length}）` },
        ]"
        :key="t.key"
        role="tab"
        type="button"
        :aria-selected="tab === t.key"
        :class="[
          '-mb-px h-9 border-b-2 px-3 text-[13px]',
          tab === t.key ? 'border-brand font-medium text-brand' : 'border-transparent text-ink-2 hover:text-ink',
        ]"
        @click="tab = t.key as typeof tab"
      >{{ t.label }}</button>
    </div>

    <!-- 设备信息 -->
    <section v-if="tab === 'info'" class="panel p-4" aria-label="设备信息">
      <h2 class="mb-3 text-[15px] font-semibold text-ink">台账信息</h2>
      <dl class="grid grid-cols-1 gap-x-8 gap-y-3 text-[13px] sm:grid-cols-2">
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">设备编号</dt><dd class="font-mono text-ink">{{ equipment.equipId }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">设备名称</dt><dd class="text-ink">{{ equipment.equipName }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">设备类别</dt><dd class="text-ink">{{ equipment.category }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">规格型号</dt><dd class="text-ink">{{ equipment.modelNo || '—' }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">所在实验室</dt><dd class="text-ink">{{ equipment.labId }} {{ workspace.findLab(equipment.labId)?.labName }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">保管人</dt><dd class="text-ink">{{ personLabel(equipment.keeperId) }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">设备状态</dt><dd><StatusBadge :status="STATUS_TONE[equipment.status]" :label="equipment.status" /></dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2">
          <dt class="text-ink-2">校准有效期</dt>
          <dd :class="isExpired ? 'text-err' : isDueSoon ? 'text-warn' : 'text-ink'">{{ calibrateText }}</dd>
        </div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">购置日期</dt><dd class="tabular-nums text-ink">{{ equipment.purchaseDate || '—' }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2">
          <dt class="text-ink-2">当前借还</dt>
          <dd>
            <span v-if="!currentLoan" class="text-ink-3">未借出</span>
            <span v-else :class="isLoanOverdue(currentLoan) ? 'text-err' : 'text-ink'">
              {{ personLabel(currentLoan.personId) }}{{ isLoanOverdue(currentLoan) ? '（逾期未还）' : '（借用中）' }}
            </span>
          </dd>
        </div>
      </dl>
      <p v-if="equipment.remark" class="mt-4 rounded-[var(--radius-control)] bg-page px-3 py-2 text-[12px] text-ink-2">
        备注：{{ equipment.remark }}
      </p>
      <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
        <Wrench class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        校准是否过期一律以校准有效期为准，不以设备状态判定——台账中存在状态仍为
        「在用」但校准已过期的记录。校准过期的设备按规定不得用于出具数据。
      </p>
    </section>

    <!-- 借还记录 -->
    <section v-else aria-label="借还记录">
      <EmptyState v-if="!loans.length" title="暂无借还记录" description="该设备还没有借出与归还记录。" />
      <div v-else class="panel overflow-x-auto">
        <table class="w-full min-w-[720px] text-[13px]">
          <caption class="sr-only">设备借还记录</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">借用人</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">借出时间</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">应还时间</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">实际归还</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">状态</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">用途</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">批准人</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in loans" :key="l.id" class="border-t border-line">
              <td class="px-4 py-2.5 text-ink">{{ personLabel(l.personId) }}</td>
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ l.borrowTime }}</td>
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ l.dueTime }}</td>
              <td class="px-4 py-2.5 tabular-nums" :class="isLoanOverdue(l) ? 'text-err' : 'text-ink-2'">
                {{ l.returnTime ?? '未归还' }}
              </td>
              <td class="px-4 py-2.5"><StatusBadge :status="LOAN_TONE[l.status]" :label="l.status" /></td>
              <td class="px-4 py-2.5 text-ink-2">{{ l.purpose || '—' }}</td>
              <td class="px-4 py-2.5 text-ink-2">{{ l.approver || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="hasOpenLoan" class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-warn-soft px-3 py-2 text-[12px] text-warn">
        <CalendarClock class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        该设备仍有未归还的借用记录。归还登记属控制类操作，本系统只读，需走设备管理部门线下流程。
      </p>
    </section>

    <EquipmentForm v-if="workspace.dataSource === 'mock'" v-model:open="formOpen" :equipment="equipment" />

    <ConfirmDialog
      :open="workspace.dataSource === 'mock' && confirmDelete"
      title="移除该设备？"
      :description="`「${equipment.equipName}」（${equipment.equipId}）及其 ${loans.length} 条借还记录将被移除。仅影响浏览器演示数据。`"
      confirm-text="移除"
      danger
      @update:open="confirmDelete = false"
      @confirm="doDelete"
    />
  </div>

  <EmptyState v-else title="设备不存在" description="它可能已被移除，或链接有误。">
    <template #action><RouterLink to="/equipment" class="btn-primary">返回设备列表</RouterLink></template>
  </EmptyState>
</template>
