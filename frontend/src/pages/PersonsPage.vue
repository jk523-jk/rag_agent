<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Users, AlertTriangle, ShieldCheck } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatCard from '@/components/common/StatCard.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { todayIso } from '@/utils/clock'
import type { Person, PersonRole, Status } from '@/types'

const workspace = useWorkspaceStore()
const router = useRouter()

const keyword = ref('')
const roleFilter = ref<'all' | PersonRole>('all')
const certFilter = ref<'all' | 'expired' | 'ok'>('all')

const PERSON_ROLES: PersonRole[] = ['教师', '博士生', '硕士生', '本科生', '外协']

/** 资质闸唯一认可的证书类型 */
const CERT_GATE_TYPE = '安全考试合格证'

/** 取该人安全考试合格证中有效期最新的一条（换证/复审会产生多条） */
function gateCert(p: Person) {
  const matched = workspace.qualificationsOf(p.id).filter((q) => q.certType === CERT_GATE_TYPE)
  if (!matched.length) return null
  return matched.reduce((a, b) => (b.expireDate > a.expireDate ? b : a))
}

/** 资质是否有效：一律以有效期为准，不看 status 字段 */
function certOk(p: Person): boolean {
  const c = gateCert(p)
  return !!c && c.expireDate >= todayIso
}

function certText(p: Person): string {
  const c = gateCert(p)
  if (!c) return '未登记'
  return c.expireDate
}

/** 状态字段与有效期不一致的情况（库里真实存在） */
function certStatusConflict(p: Person): boolean {
  const c = gateCert(p)
  return !!c && c.status === '有效' && c.expireDate < todayIso
}

const authorizedLabIds = (p: Person) =>
  workspace.authorizationsOf(p.id).filter((a) => a.status === '有效').map((a) => a.labId)

const rows = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return workspace.state.persons.filter((p) => {
    if (roleFilter.value !== 'all' && p.role !== roleFilter.value) return false
    if (certFilter.value === 'expired' && certOk(p)) return false
    if (certFilter.value === 'ok' && !certOk(p)) return false
    if (!q) return true
    // 姓名与工号都可搜——重名人员必须靠工号区分
    return p.name.toLowerCase().includes(q) || p.empNo.toLowerCase().includes(q)
  })
})

/** 重名检测：同名人员必须用工号区分，页面需显式提示 */
const duplicateNames = computed(() => {
  const counts = new Map<string, number>()
  for (const p of workspace.state.persons) counts.set(p.name, (counts.get(p.name) ?? 0) + 1)
  return new Set([...counts.entries()].filter(([, n]) => n > 1).map(([name]) => name))
})

const expiredCount = computed(() => workspace.state.persons.filter((p) => !certOk(p)).length)

function tone(p: Person): Status {
  return certOk(p) ? 'success' : 'failed'
}

const columns: Column[] = [
  { key: 'name', label: '姓名' },
  { key: 'empNo', label: '工号' },
  { key: 'role', label: '身份' },
  { key: 'dept', label: '所属院系 / 课题组' },
  { key: 'cert', label: '安全考试合格证' },
  { key: 'labs', label: '有效授权实验室' },
  { key: 'actions', label: '', align: 'right' },
]
</script>

<template>
  <PageHeader title="人员管理" description="管理实验室人员台账、准入资质与实验室授权。资质是否有效以有效期为准。">
    <template #filters>
      <SearchInput v-model="keyword" label="搜索人员" placeholder="搜索姓名或工号" />
      <label class="sr-only" for="person-role">身份筛选</label>
      <select id="person-role" v-model="roleFilter" class="input w-auto">
        <option value="all">全部身份</option>
        <option v-for="r in PERSON_ROLES" :key="r" :value="r">{{ r }}</option>
      </select>
      <label class="sr-only" for="person-cert">资质筛选</label>
      <select id="person-cert" v-model="certFilter" class="input w-auto">
        <option value="all">全部资质状态</option>
        <option value="ok">资质有效</option>
        <option value="expired">资质异常</option>
      </select>
    </template>
  </PageHeader>


  <section aria-label="人员概览" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <StatCard label="人员总数" :value="String(workspace.state.persons.length)" hint="含教师与学生" />
    <StatCard
      label="资质异常"
      :value="String(expiredCount)"
      :delta="expiredCount ? '不得进入危化品实验室' : '全部有效'"
      :delta-tone="expiredCount ? 'down' : 'flat'"
    />
    <StatCard label="授权记录" :value="String(workspace.state.authorizations.length)" hint="含已撤销" />
    <StatCard
      label="重名人员"
      :value="String(duplicateNames.size)"
      :delta="duplicateNames.size ? '须以工号区分' : '无重名'"
      :delta-tone="duplicateNames.size ? 'down' : 'flat'"
    />
  </section>

  <!-- 重名提示：不同的人可以有相同的名字，页面必须显式说明用哪个字段区分 -->
  <section v-if="duplicateNames.size" class="mt-4 panel border-warn/30 bg-warn-soft p-4" aria-label="重名提示">
    <h2 class="flex items-center gap-1.5 text-[13px] font-medium text-warn">
      <AlertTriangle class="size-4" aria-hidden="true" />存在重名人员
    </h2>
    <p class="mt-2 text-[12px] text-warn">
      姓名「{{ [...duplicateNames].join('、') }}」对应多人。名录与准入判定中一律
      <strong class="font-medium">以工号区分</strong>，处理前请先核对工号，避免误判到他人。
    </p>
  </section>

  <EmptyState v-if="!workspace.state.persons.length" title="还没有人员" description="人员数据来自后端人员表。" />
  <EmptyState v-else-if="!rows.length" title="没有符合条件的人员" description="调整搜索词或筛选条件试试。" />

  <div v-else class="mt-6">
    <DataTable :columns="columns" :rows="rows" caption="人员列表" @row="(r) => router.push(`/persons/${r.id}`)">
      <template #name="{ row }">
        <span class="flex items-center gap-2">
          <span class="font-medium text-ink">{{ row.name }}</span>
          <span v-if="duplicateNames.has(row.name)" class="mock-tag" title="存在同名人员，请以工号区分">重名</span>
        </span>
      </template>
      <template #empNo="{ row }"><span class="font-mono text-[12px] text-ink-2">{{ row.empNo }}</span></template>
      <template #cert="{ row }">
        <span class="inline-flex items-center gap-1.5">
          <StatusBadge :status="tone(row)" :label="certOk(row) ? '有效' : '已过期'" />
          <span class="tabular-nums text-[12px] text-ink-3">{{ certText(row) }}</span>
          <!-- 状态字段与有效期不一致时单独提示，避免用户以为系统读错 -->
          <span
            v-if="certStatusConflict(row)"
            class="mock-tag"
            title="证书状态仍登记为有效，但有效期已届满；判定一律以有效期为准"
          >状态未更新</span>
        </span>
      </template>
      <template #labs="{ row }">
        <span v-if="authorizedLabIds(row).length" class="text-ink-2">{{ authorizedLabIds(row).join('、') }}</span>
        <span v-else class="text-ink-3">无有效授权</span>
      </template>
      <template #actions="{ row }">
        <span class="inline-flex gap-1" @click.stop>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="router.push(`/persons/${row.id}`)">详情</button>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="router.push({ path: '/permits', query: { person: row.empNo } })">判定准入</button>
        </span>
      </template>
    </DataTable>

    <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
      <ShieldCheck class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      资质状态字段可能未及时更新（台账中存在「状态有效但已过期」的记录），
      因此判定一律以<strong class="font-medium">有效期</strong>为准。当天到期算有效。
    </p>
  </div>

  <p class="mt-6 flex items-center gap-2 text-[12px] text-ink-3">
    <Users class="size-3.5" aria-hidden="true" />
    人员资质与授权明细见各人详情页；准入结论请到
    <RouterLink to="/permits" class="text-brand hover:underline">许可管理</RouterLink> 用三闸判定器核查。
  </p>
</template>
