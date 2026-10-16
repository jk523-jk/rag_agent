<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { DoorOpen, LogIn, LogOut, Info, AlertTriangle } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatCard from '@/components/common/StatCard.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { DEMO_TODAY } from '@/mocks/labData'
import type { AuthResult, AuthType, Direction, LoanStatus, Status } from '@/types'

const workspace = useWorkspaceStore()

const tab = ref<'persons' | 'equipment'>('persons')

// ---------------- 人员门禁 ----------------

const keyword = ref('')
const labFilter = ref('all')
const resultFilter = ref<'all' | AuthResult>('all')

const RESULT_TONE: Record<AuthResult, Status> = {
  通过: 'success', 拒绝: 'failed', 超时: 'warning',
}
const LOAN_TONE: Record<LoanStatus, Status> = {
  借用中: 'running', 已归还: 'success', 逾期: 'failed',
}

interface AccessRow {
  id: string
  personName: string
  empNo: string
  labId: string
  labName: string
  eventTime: string
  direction: Direction
  authType: AuthType
  authResult: AuthResult
  companionNo: number | null
  needsDouble: boolean
}

const accessRows = computed<AccessRow[]>(() =>
  workspace.state.accessEvents
    .map((e) => {
      const p = workspace.findPerson(e.personId)
      const l = workspace.findLab(e.labId)
      return {
        id: e.id,
        personName: p?.name ?? e.personId,
        empNo: p?.empNo ?? '',
        labId: e.labId,
        labName: l?.labName ?? '',
        eventTime: e.eventTime,
        direction: e.direction,
        authType: e.authType,
        authResult: e.authResult,
        companionNo: e.companionNo,
        needsDouble: l?.needsDouble ?? false,
      }
    })
    .sort((a, b) => b.eventTime.localeCompare(a.eventTime)),
)

/** 违反双人准入：要求双人的实验室 + 进方向 + 通过 + 同行人数不足 1 */
function violatesDouble(r: AccessRow): boolean {
  return r.needsDouble && r.direction === '进' && r.authResult === '通过' && (r.companionNo ?? 0) < 1
}

const filteredAccess = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return accessRows.value.filter((r) => {
    if (labFilter.value !== 'all' && r.labId !== labFilter.value) return false
    if (resultFilter.value !== 'all' && r.authResult !== resultFilter.value) return false
    if (!q) return true
    return r.personName.toLowerCase().includes(q) || r.empNo.toLowerCase().includes(q)
  })
})

// ---------------- 设备借还 ----------------

const loanKeyword = ref('')
const loanStatusFilter = ref<'all' | LoanStatus>('all')

interface LoanRow {
  id: string
  equipId: string
  equipName: string
  personName: string
  empNo: string
  borrowTime: string
  dueTime: string
  returnTime: string | null
  purpose: string
  approver: string
  status: LoanStatus
}

const loanRows = computed<LoanRow[]>(() =>
  workspace.state.equipmentLoans
    .map((l) => {
      const e = workspace.findEquipment(l.equipId)
      const p = workspace.findPerson(l.personId)
      return {
        id: l.id,
        equipId: l.equipId,
        equipName: e?.equipName ?? l.equipId,
        personName: p?.name ?? l.personId,
        empNo: p?.empNo ?? '',
        borrowTime: l.borrowTime,
        dueTime: l.dueTime,
        returnTime: l.returnTime,
        purpose: l.purpose,
        approver: l.approver,
        status: l.status,
      }
    })
    .sort((a, b) => b.borrowTime.localeCompare(a.borrowTime)),
)

function isOverdue(r: LoanRow): boolean {
  return r.returnTime === null && r.dueTime < `${DEMO_TODAY} 23:59`
}

const filteredLoans = computed(() => {
  const q = loanKeyword.value.trim().toLowerCase()
  return loanRows.value.filter((r) => {
    if (loanStatusFilter.value !== 'all' && r.status !== loanStatusFilter.value) return false
    if (!q) return true
    return (
      r.equipName.toLowerCase().includes(q) ||
      r.equipId.toLowerCase().includes(q) ||
      r.personName.toLowerCase().includes(q) ||
      r.empNo.toLowerCase().includes(q)
    )
  })
})

// ---------------- 概览 ----------------

const denyCount = computed(() => accessRows.value.filter((r) => r.authResult === '拒绝').length)
const violateCount = computed(() => accessRows.value.filter(violatesDouble).length)
const overdueLoanCount = computed(() => loanRows.value.filter(isOverdue).length)

const accessColumns: Column[] = [
  { key: 'eventTime', label: '时间' },
  { key: 'person', label: '人员' },
  { key: 'lab', label: '实验室' },
  { key: 'direction', label: '方向' },
  { key: 'authType', label: '验证方式' },
  { key: 'authResult', label: '结果' },
  { key: 'companionNo', label: '同行人数', align: 'right' },
]

const loanColumns: Column[] = [
  { key: 'equip', label: '设备' },
  { key: 'person', label: '借用人' },
  { key: 'borrowTime', label: '借出时间' },
  { key: 'dueTime', label: '应还时间' },
  { key: 'returnTime', label: '实际归还' },
  { key: 'status', label: '状态' },
  { key: 'approver', label: '批准人' },
]
</script>

<template>
  <PageHeader title="出入管理" description="查看人员门禁通行记录与设备借还流水，识别违规进入与逾期未还。">
    <template #actions>
      <div role="group" aria-label="记录类型" class="inline-flex rounded-[var(--radius-control)] border border-line p-0.5">
        <button type="button" :aria-pressed="tab === 'persons'" :class="['h-7 px-3 rounded-[4px] text-[12px]', tab === 'persons' ? 'bg-brand-soft text-brand font-medium' : 'text-ink-2']" @click="tab = 'persons'">
          人员门禁
        </button>
        <button type="button" :aria-pressed="tab === 'equipment'" :class="['h-7 px-3 rounded-[4px] text-[12px]', tab === 'equipment' ? 'bg-brand-soft text-brand font-medium' : 'text-ink-2']" @click="tab = 'equipment'">
          设备借还
        </button>
      </div>
    </template>
  </PageHeader>

  <p class="mb-4 text-[12px] text-ink-3">以下为演示数据（模拟），不代表真实门禁与借还流水。</p>

  <section aria-label="出入概览" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <StatCard label="通行记录" :value="String(accessRows.length)" hint="全部实验室" />
    <StatCard
      label="验证被拒"
      :value="String(denyCount)"
      :delta="denyCount ? '资质或授权未通过' : '无'"
      :delta-tone="denyCount ? 'down' : 'flat'"
    />
    <StatCard
      label="违反双人准入"
      :value="String(violateCount)"
      :delta="violateCount ? '剧毒品间单人进入' : '无'"
      :delta-tone="violateCount ? 'down' : 'flat'"
    />
    <StatCard
      label="借出逾期未还"
      :value="String(overdueLoanCount)"
      :delta="overdueLoanCount ? '需催还' : '无'"
      :delta-tone="overdueLoanCount ? 'down' : 'flat'"
    />
  </section>

  <!-- ============ 人员门禁 ============ -->
  <div v-if="tab === 'persons'" class="mt-6">
    <div class="mb-4 flex flex-wrap gap-2">
      <SearchInput v-model="keyword" label="搜索通行记录" placeholder="搜索姓名或工号" />
      <label class="sr-only" for="access-lab">实验室筛选</label>
      <select id="access-lab" v-model="labFilter" class="input w-auto">
        <option value="all">全部实验室</option>
        <option v-for="l in workspace.state.labs" :key="l.labId" :value="l.labId">{{ l.labId }} {{ l.labName }}</option>
      </select>
      <label class="sr-only" for="access-result">验证结果筛选</label>
      <select id="access-result" v-model="resultFilter" class="input w-auto">
        <option value="all">全部结果</option>
        <option value="通过">通过</option>
        <option value="拒绝">拒绝</option>
        <option value="超时">超时</option>
      </select>
    </div>

    <!-- 违规告警：同时给出图标与文字，不只靠颜色 -->
    <section v-if="violateCount" class="panel mb-4 border-err/30 bg-err-soft p-4" aria-label="双人准入违规">
      <h2 class="flex items-center gap-1.5 text-[13px] font-medium text-err">
        <AlertTriangle class="size-4" aria-hidden="true" />违反双人准入（{{ violateCount }} 条）
      </h2>
      <ul class="mt-2 space-y-1 text-[12px] text-err">
        <li v-for="r in accessRows.filter(violatesDouble)" :key="r.id">
          {{ r.eventTime }} · {{ r.personName }}（{{ r.empNo }}）进入 {{ r.labId }} {{ r.labName }}，
          同行人数 {{ r.companionNo }}——该实验室要求双人准入，应停止作业并核实。
        </li>
      </ul>
    </section>

    <EmptyState v-if="!filteredAccess.length" title="没有符合条件的通行记录" description="调整搜索词或筛选条件试试。" />

    <DataTable v-else :columns="accessColumns" :rows="filteredAccess" caption="人员门禁通行记录">
      <template #eventTime="{ row }"><span class="tabular-nums text-ink-2">{{ row.eventTime }}</span></template>
      <template #person="{ row }">
        <span class="font-medium text-ink">{{ row.personName }}</span>
        <span class="ml-1 font-mono text-[12px] text-ink-3">{{ row.empNo }}</span>
      </template>
      <template #lab="{ row }">
        <span class="block text-ink">{{ row.labId }}</span>
        <span class="text-[12px] text-ink-3">{{ row.labName }}{{ row.needsDouble ? ' · 要求双人' : '' }}</span>
      </template>
      <template #direction="{ row }">
        <span class="inline-flex items-center gap-1 text-ink-2">
          <LogIn v-if="row.direction === '进'" class="size-3.5" aria-hidden="true" />
          <LogOut v-else class="size-3.5" aria-hidden="true" />
          {{ row.direction }}
        </span>
      </template>
      <template #authResult="{ row }"><StatusBadge :status="RESULT_TONE[row.authResult as AuthResult]" :label="row.authResult" /></template>
      <template #companionNo="{ row }">
        <span v-if="row.companionNo === null" class="text-ink-3">未登记</span>
        <span v-else :class="violatesDouble(row) ? 'text-err' : 'text-ink-2'">
          {{ row.companionNo }}<span v-if="violatesDouble(row)" class="text-[12px]">（违规）</span>
        </span>
      </template>
    </DataTable>

    <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
      <Info class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      双人闸只认当天「进 + 通过」的记录，取最大同行人数。拒绝与超时记录不作为双人同行的证据。
      本系统只读，不能修改门禁权限或远程开门。
    </p>
  </div>

  <!-- ============ 设备借还 ============ -->
  <div v-else class="mt-6">
    <div class="mb-4 flex flex-wrap gap-2">
      <SearchInput v-model="loanKeyword" label="搜索借还记录" placeholder="搜索设备或借用人" />
      <label class="sr-only" for="loan-status">借还状态筛选</label>
      <select id="loan-status" v-model="loanStatusFilter" class="input w-auto">
        <option value="all">全部状态</option>
        <option value="借用中">借用中</option>
        <option value="已归还">已归还</option>
        <option value="逾期">逾期</option>
      </select>
    </div>

    <section v-if="overdueLoanCount" class="panel mb-4 border-warn/30 bg-warn-soft p-4" aria-label="逾期未还">
      <h2 class="flex items-center gap-1.5 text-[13px] font-medium text-warn">
        <AlertTriangle class="size-4" aria-hidden="true" />借出逾期未还（{{ overdueLoanCount }} 条）
      </h2>
      <ul class="mt-2 space-y-1 text-[12px] text-warn">
        <li v-for="r in loanRows.filter(isOverdue)" :key="r.id">
          {{ r.equipName }}（{{ r.equipId }}）· 借用人 {{ r.personName }}（{{ r.empNo }}）·
          应还 {{ r.dueTime }}——请催还并核对设备状态。
        </li>
      </ul>
    </section>

    <EmptyState v-if="!filteredLoans.length" title="没有符合条件的借还记录" description="调整搜索词或筛选条件试试。" />

    <DataTable v-else :columns="loanColumns" :rows="filteredLoans" caption="设备借还记录">
      <template #equip="{ row }">
        <span class="block font-medium text-ink">{{ row.equipName }}</span>
        <span class="font-mono text-[12px] text-ink-3">{{ row.equipId }}</span>
      </template>
      <template #person="{ row }">
        <span class="text-ink">{{ row.personName }}</span>
        <span class="ml-1 font-mono text-[12px] text-ink-3">{{ row.empNo }}</span>
      </template>
      <template #borrowTime="{ row }"><span class="tabular-nums text-ink-2">{{ row.borrowTime }}</span></template>
      <template #dueTime="{ row }"><span class="tabular-nums text-ink-2">{{ row.dueTime }}</span></template>
      <template #returnTime="{ row }">
        <span class="tabular-nums" :class="isOverdue(row as LoanRow) ? 'text-err' : 'text-ink-2'">
          {{ row.returnTime ?? '未归还' }}
        </span>
      </template>
      <template #status="{ row }"><StatusBadge :status="LOAN_TONE[row.status as LoanStatus]" :label="row.status" /></template>
      <template #approver="{ row }"><span class="text-ink-2">{{ row.approver || '—' }}</span></template>
    </DataTable>

    <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
      <Info class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      借还与归还登记属控制类操作，本系统只读。设备可用性判定见
      <RouterLink to="/equipment" class="mx-0.5 text-brand hover:underline">设备管理</RouterLink>。
    </p>
  </div>

  <p class="mt-6 flex items-center gap-2 text-[12px] text-ink-3">
    <DoorOpen class="size-3.5" aria-hidden="true" />
    准入结论请到
    <RouterLink to="/permits" class="text-brand hover:underline">许可管理</RouterLink> 执行三闸判定核查。
  </p>
</template>
