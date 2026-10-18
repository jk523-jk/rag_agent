<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ShieldCheck, Play, DoorOpen, GitBranch } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatCard from '@/components/common/StatCard.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { judge, verdictTone } from '@/utils/accessDecision'
import { todayIso } from '@/utils/clock'
import type { AccessDecision, AuthStatus, Status } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()
const route = useRoute()

const tab = ref<'judge' | 'grants'>('judge')

// ---------------- 三闸判定器 ----------------

/** 人员用「工号」作为选项值：姓名可能重名，工号唯一 */
const personKey = ref('')
const labId = ref('')
const atDate = ref(todayIso)
const decision = ref<AccessDecision | null>(null)
const judgeError = ref('')

// 支持从人员页跳转：/permits?person=<工号>
watch(() => route.query.person, (v) => {
  if (typeof v === 'string' && v) {
    personKey.value = v
    tab.value = 'judge'
  }
}, { immediate: true })

const selectedPerson = computed(() => workspace.state.persons.find((p) => p.empNo === personKey.value) ?? null)
const selectedLab = computed(() => workspace.state.labs.find((l) => l.labId === labId.value) ?? null)

function runJudge() {
  judgeError.value = ''
  decision.value = null
  const p = selectedPerson.value
  const l = selectedLab.value
  if (!p) {
    judgeError.value = '请选择人员。'
    return
  }
  if (!l) {
    judgeError.value = '请选择实验室。'
    return
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(atDate.value)) {
    judgeError.value = '判定日期格式为 YYYY-MM-DD。'
    return
  }
  decision.value = judge({
    personName: p.name,
    empNo: p.empNo,
    role: p.role,
    lab: l,
    atDate: atDate.value,
    qualifications: workspace.qualificationsOf(p.id),
    authorizations: workspace.authorizationsOf(p.id),
    accessEvents: workspace.state.accessEvents,
  })
  ui.toast('已完成三闸判定（演示）')
}

// ---------------- 授权台账 ----------------

const keyword = ref('')
const statusFilter = ref<'all' | AuthStatus>('all')

const AUTH_TONE: Record<AuthStatus, Status> = {
  有效: 'success', 已撤销: 'failed', 已过期: 'disabled',
}

interface GrantRow {
  id: string
  personId: string
  personName: string
  empNo: string
  labId: string
  labName: string
  authFrom: string
  authTo: string
  grantor: string
  status: AuthStatus
  needsDouble: boolean
}

const grants = computed<GrantRow[]>(() =>
  workspace.state.authorizations.map((a) => {
    const p = workspace.findPerson(a.personId)
    const l = workspace.findLab(a.labId)
    return {
      id: a.id,
      personId: a.personId,
      personName: p?.name ?? a.personId,
      empNo: p?.empNo ?? '',
      labId: a.labId,
      labName: l?.labName ?? '',
      authFrom: a.authFrom,
      authTo: a.authTo,
      grantor: a.grantor,
      status: a.status,
      needsDouble: l?.needsDouble ?? false,
    }
  }),
)

const filteredGrants = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return grants.value.filter((g) => {
    if (statusFilter.value !== 'all' && g.status !== statusFilter.value) return false
    if (!q) return true
    return (
      g.personName.toLowerCase().includes(q) ||
      g.empNo.toLowerCase().includes(q) ||
      g.labId.toLowerCase().includes(q) ||
      g.labName.toLowerCase().includes(q)
    )
  })
})

const activeCount = computed(() => grants.value.filter((g) => g.status === '有效').length)
const revokedCount = computed(() => grants.value.filter((g) => g.status === '已撤销').length)
const doubleLabCount = computed(() => workspace.state.labs.filter((l) => l.needsDouble).length)

const columns: Column[] = [
  { key: 'personName', label: '人员' },
  { key: 'empNo', label: '工号' },
  { key: 'lab', label: '实验室' },
  { key: 'authFrom', label: '授权生效' },
  { key: 'authTo', label: '授权失效' },
  { key: 'grantor', label: '授权人' },
  { key: 'status', label: '状态' },
  { key: 'actions', label: '', align: 'right' },
]

function judgeFor(row: GrantRow) {
  personKey.value = row.empNo
  labId.value = row.labId
  tab.value = 'judge'
  decision.value = null
  judgeError.value = ''
}
</script>

<template>
  <PageHeader title="许可管理" description="查看实验室准入授权台账，并用三闸判定器核查指定人员能否进入指定实验室。">
    <template #actions>
      <div role="group" aria-label="视图切换" class="inline-flex rounded-[var(--radius-control)] border border-line p-0.5">
        <button type="button" :aria-pressed="tab === 'judge'" :class="['h-7 px-3 rounded-[4px] text-[12px]', tab === 'judge' ? 'bg-brand-soft text-brand font-medium' : 'text-ink-2']" @click="tab = 'judge'">准入判定</button>
        <button type="button" :aria-pressed="tab === 'grants'" :class="['h-7 px-3 rounded-[4px] text-[12px]', tab === 'grants' ? 'bg-brand-soft text-brand font-medium' : 'text-ink-2']" @click="tab = 'grants'">授权台账</button>
      </div>
    </template>
  </PageHeader>

  <p class="mb-4 text-[12px] text-ink-3">以下为演示数据（模拟）。判定逻辑与后端 check_lab_access 三闸口径一致。</p>

  <section aria-label="许可概览" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <StatCard label="授权记录" :value="String(grants.length)" hint="含已撤销与已过期" />
    <StatCard label="有效授权" :value="String(activeCount)" hint="状态为有效" />
    <StatCard
      label="已撤销"
      :value="String(revokedCount)"
      :delta="revokedCount ? '授权闸将拦截' : '无'"
      :delta-tone="revokedCount ? 'down' : 'flat'"
    />
    <StatCard label="要求双人准入" :value="String(doubleLabCount)" hint="剧毒品间等场所" />
  </section>

  <!-- ============ 三闸判定器 ============ -->
  <div v-if="tab === 'judge'" class="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
    <section class="panel p-4" aria-labelledby="judge-form-title">
      <h2 id="judge-form-title" class="mb-3 text-[15px] font-semibold text-ink">判定条件</h2>
      <div class="space-y-4">
        <div>
          <label class="label" for="j-person">人员（按工号）<span class="text-err">*</span></label>
          <select id="j-person" v-model="personKey" class="input">
            <option value="">请选择人员</option>
            <option v-for="p in workspace.state.persons" :key="p.id" :value="p.empNo">
              {{ p.name }}（{{ p.empNo }}）· {{ p.role }}
            </option>
          </select>
          <!-- 重名人员必须显式提示，避免误判到他人 -->
          <p v-if="selectedPerson" class="mt-1 text-[12px] text-ink-3">
            已选：{{ selectedPerson.name }} · {{ selectedPerson.dept }}
            <span v-if="workspace.state.persons.filter((x) => x.name === selectedPerson!.name).length > 1" class="text-warn">
              （存在同名人员，已按工号 {{ selectedPerson.empNo }} 锁定）
            </span>
          </p>
        </div>

        <div>
          <label class="label" for="j-lab">实验室 <span class="text-err">*</span></label>
          <select id="j-lab" v-model="labId" class="input">
            <option value="">请选择实验室</option>
            <option v-for="l in workspace.state.labs" :key="l.labId" :value="l.labId">
              {{ l.labId }} {{ l.labName }}{{ l.needsDouble ? '（要求双人）' : '' }}
            </option>
          </select>
        </div>

        <div>
          <label class="label" for="j-date">判定日期 <span class="text-err">*</span></label>
          <input id="j-date" v-model="atDate" type="date" class="input tabular-nums" />
          <p class="mt-1 text-[12px] text-ink-3">当天到期算有效。双人闸按该日期核查通行记录。</p>
        </div>

        <button type="button" class="btn-primary w-full" @click="runJudge">
          <Play class="size-4" aria-hidden="true" />执行三闸判定
        </button>
        <p v-if="judgeError" class="text-[12px] text-err" role="alert">{{ judgeError }}</p>
      </div>

      <div class="mt-4 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
        <p class="flex items-center gap-1.5 font-medium"><GitBranch class="size-3.5" aria-hidden="true" />闸位顺序固定</p>
        <p class="mt-1">资质闸 → 授权闸 → 双人闸。任一闸未通过即停止，不再评估后续闸位——这样能防住「只看了授权、忘了资质」这类常见失误。</p>
      </div>
    </section>

    <div class="space-y-4">
      <EmptyState v-if="!decision" title="尚未执行判定" description="在左侧选择人员、实验室与日期，然后点击「执行三闸判定」。" />

      <template v-else>
        <section
          :class="['panel p-4', decision.verdict === '准予进入' ? 'border-ok/30 bg-ok-soft' : decision.verdict === '需双人同行' ? 'border-warn/30 bg-warn-soft' : 'border-err/30 bg-err-soft']"
          aria-labelledby="verdict-title"
        >
          <div class="flex flex-wrap items-center gap-2">
            <h2 id="verdict-title" class="text-[15px] font-semibold text-ink">判定结论</h2>
            <StatusBadge :status="verdictTone(decision.verdict)" :label="decision.verdict" />
            <span v-if="decision.failedGate" class="text-[12px] text-ink-2">未通过：{{ decision.failedGate }}</span>
          </div>
          <p class="mt-2 text-[13px] text-ink-2">
            {{ selectedPerson?.name }}（{{ selectedPerson?.empNo }}）于 {{ atDate }} 进入
            {{ selectedLab?.labId }} {{ selectedLab?.labName }}
          </p>
        </section>

        <section class="panel p-4" aria-labelledby="reasons-title">
          <h2 id="reasons-title" class="mb-3 text-[15px] font-semibold text-ink">逐闸依据</h2>
          <ol class="space-y-2">
            <li v-for="(r, i) in decision.reasons" :key="i" class="rounded-[var(--radius-control)] border border-line p-3 text-[13px]">
              <span class="mr-2 tabular-nums text-ink-3">{{ i + 1 }}</span>
              <span :class="r.includes('未通过') ? 'text-err' : r.includes('通过') ? 'text-ink' : 'text-ink-2'">{{ r }}</span>
            </li>
          </ol>
        </section>

        <section class="panel p-4" aria-labelledby="next-title">
          <h2 id="next-title" class="mb-2 text-[15px] font-semibold text-ink">后续处置</h2>
          <p class="text-[13px] text-ink-2">
            <template v-if="decision.verdict === '准予进入'">三闸全部通过，按规程可正常进入。</template>
            <template v-else-if="decision.verdict === '资质过期'">
              资质过期的，不得进入危化品实验室；已进入的应立即停止作业，并由实验室负责人登记处置。
            </template>
            <template v-else-if="decision.verdict === '无授权'">
              需先由导师或实验室负责人授予该实验室的准入授权，授权后仍需通过资质闸。
            </template>
            <template v-else>
              剧毒品间要求双人准入，需与同行人一同进入。查不到当日通行记录时按从严原则判定。
            </template>
          </p>
          <p class="mt-3 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
            本系统只读：不能改资质、改授权、改门禁权限或远程开门。上述处置请走实验室安全负责人人工审批。
          </p>
        </section>
      </template>
    </div>
  </div>

  <!-- ============ 授权台账 ============ -->
  <div v-else class="mt-6">
    <div class="mb-4 flex flex-wrap gap-2">
      <SearchInput v-model="keyword" label="搜索授权" placeholder="搜索人员、工号或实验室" />
      <label class="sr-only" for="grant-status">状态筛选</label>
      <select id="grant-status" v-model="statusFilter" class="input w-auto">
        <option value="all">全部状态</option>
        <option value="有效">有效</option>
        <option value="已撤销">已撤销</option>
        <option value="已过期">已过期</option>
      </select>
    </div>

    <EmptyState v-if="!filteredGrants.length" title="没有符合条件的授权记录" description="调整搜索词或筛选条件试试。" />

    <DataTable v-else :columns="columns" :rows="filteredGrants" caption="实验室准入授权台账">
      <template #personName="{ row }">
        <span class="font-medium text-ink">{{ row.personName }}</span>
      </template>
      <template #empNo="{ row }"><span class="font-mono text-[12px] text-ink-2">{{ row.empNo }}</span></template>
      <template #lab="{ row }">
        <span class="block text-ink">{{ row.labId }}</span>
        <span class="text-[12px] text-ink-3">{{ row.labName }}{{ row.needsDouble ? ' · 要求双人' : '' }}</span>
      </template>
      <template #authFrom="{ row }"><span class="tabular-nums text-ink-2">{{ row.authFrom }}</span></template>
      <template #authTo="{ row }">
        <span class="tabular-nums" :class="row.authTo < todayIso ? 'text-err' : 'text-ink-2'">{{ row.authTo }}</span>
      </template>
      <template #status="{ row }"><StatusBadge :status="AUTH_TONE[row.status as AuthStatus]" :label="row.status" /></template>
      <template #actions="{ row }">
        <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="judgeFor(row as GrantRow)">判定准入</button>
      </template>
    </DataTable>

    <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
      <ShieldCheck class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      授权可用需同时满足状态为「有效」且判定日期落在生效与失效之间。
      授权被撤销后，即使资质仍有效也无法进入对应实验室。
    </p>
  </div>

  <p class="mt-6 flex items-center gap-2 text-[12px] text-ink-3">
    <DoorOpen class="size-3.5" aria-hidden="true" />
    出入流水与设备借还见
    <RouterLink to="/access" class="text-brand hover:underline">出入管理</RouterLink>；
    人员资质明细见
    <RouterLink to="/persons" class="text-brand hover:underline">人员管理</RouterLink>。
  </p>
</template>
