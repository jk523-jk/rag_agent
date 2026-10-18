<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { ArrowLeft, ShieldCheck, DoorOpen, LogIn, LogOut } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { todayIso } from '@/utils/clock'
import type { AuthResult, AuthStatus, CertStatus, Status } from '@/types'

const route = useRoute()
const workspace = useWorkspaceStore()

const person = computed(() => workspace.findPerson(String(route.params.id)))
const tab = ref<'quals' | 'auths' | 'access'>('quals')

const CERT_GATE_TYPE = '安全考试合格证'

const CERT_TONE: Record<CertStatus, Status> = {
  有效: 'success', 已过期: 'failed', 已注销: 'disabled',
}
const AUTH_TONE: Record<AuthStatus, Status> = {
  有效: 'success', 已撤销: 'failed', 已过期: 'disabled',
}
const RESULT_TONE: Record<AuthResult, Status> = {
  通过: 'success', 拒绝: 'failed', 超时: 'warning',
}

const qualifications = computed(() => (person.value ? workspace.qualificationsOf(person.value.id) : []))
const authorizations = computed(() => (person.value ? workspace.authorizationsOf(person.value.id) : []))
const events = computed(() => (person.value ? workspace.accessEventsOf(person.value.id) : []))

/** 资质是否有效：以有效期为准，不看 status（二者可能不一致） */
function qualEffective(expireDate: string): boolean {
  return expireDate >= todayIso
}

/** 资质闸只看安全考试合格证，取有效期最新一条 */
const gateCert = computed(() => {
  const matched = qualifications.value.filter((q) => q.certType === CERT_GATE_TYPE)
  if (!matched.length) return null
  return matched.reduce((a, b) => (b.expireDate > a.expireDate ? b : a))
})

const gateOk = computed(() => !!gateCert.value && qualEffective(gateCert.value.expireDate))

/** 状态字段写着有效但有效期已过——库里真实存在的样本，必须显式提示 */
const statusConflict = computed(() => !!gateCert.value && gateCert.value.status === '有效' && !gateOk.value)

const activeAuths = computed(() => authorizations.value.filter((a) => a.status === '有效'))

function labName(labId: string) {
  return workspace.findLab(labId)?.labName ?? ''
}
</script>

<template>
  <div v-if="person">
    <PageHeader :title="person.name" :description="`${person.empNo} · ${person.role} · ${person.dept}`">
      <template #actions>
        <RouterLink :to="{ path: '/permits', query: { person: person.empNo } }" class="btn-primary">
          <ShieldCheck class="size-4" aria-hidden="true" />准入判定
        </RouterLink>
      </template>
    </PageHeader>

    <RouterLink to="/persons" class="mb-4 inline-flex items-center gap-1 text-[13px] text-ink-2 hover:text-ink">
      <ArrowLeft class="size-3.5" aria-hidden="true" />返回人员列表
    </RouterLink>

    <!-- 资质闸结论 -->
    <section
      :class="['panel mb-4 p-4', gateOk ? '' : 'border-err/30 bg-err-soft']"
      aria-label="资质闸结论"
    >
      <h2 class="flex items-center gap-2 text-[13px] font-medium" :class="gateOk ? 'text-ink' : 'text-err'">
        <ShieldCheck class="size-4" aria-hidden="true" />资质闸：{{ gateOk ? '通过' : '未通过' }}
      </h2>
      <p class="mt-1.5 text-[12px]" :class="gateOk ? 'text-ink-2' : 'text-err'">
        <template v-if="gateCert">
          {{ CERT_GATE_TYPE }} {{ gateCert.certNo }}，有效期至 {{ gateCert.expireDate }}，状态 {{ gateCert.status }}。
        </template>
        <template v-else>未登记{{ CERT_GATE_TYPE }}，无法进入危化品实验室。</template>
      </p>
      <p v-if="statusConflict" class="mt-1.5 text-[12px] text-warn">
        注意：该证书状态仍登记为「有效」，但有效期已于 {{ gateCert?.expireDate }} 届满。
        判定以有效期为准确认，状态字段未及时更新。
      </p>
    </section>

    <div class="mb-4 border-b border-line" role="tablist" aria-label="人员详情">
      <button
        v-for="t in [
          { key: 'quals', label: `资质（${qualifications.length}）` },
          { key: 'auths', label: `实验室授权（${authorizations.length}）` },
          { key: 'access', label: `通行记录（${events.length}）` },
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

    <!-- 资质 -->
    <section v-if="tab === 'quals'" aria-label="资质台账">
      <EmptyState v-if="!qualifications.length" title="暂无资质记录" description="该人员没有登记任何资质证书。" />
      <div v-else class="panel overflow-x-auto">
        <table class="w-full min-w-[640px] text-[13px]">
          <caption class="sr-only">人员资质台账</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">资质类型</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">证书编号</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">发证日期</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">有效期至</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">登记状态</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">实际有效性</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="q in qualifications" :key="q.id" class="border-t border-line">
              <td class="px-4 py-2.5">
                <span class="flex items-center gap-2">
                  <span class="text-ink">{{ q.certType }}</span>
                  <span v-if="q.certType === CERT_GATE_TYPE" class="mock-tag" title="准入资质闸仅校验此证书">闸位依据</span>
                </span>
              </td>
              <td class="px-4 py-2.5 font-mono text-[12px] text-ink-2">{{ q.certNo }}</td>
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ q.issueDate }}</td>
              <td class="px-4 py-2.5 tabular-nums" :class="qualEffective(q.expireDate) ? 'text-ink-2' : 'text-err'">{{ q.expireDate }}</td>
              <td class="px-4 py-2.5"><StatusBadge :status="CERT_TONE[q.status]" :label="q.status" /></td>
              <td class="px-4 py-2.5">
                <!-- 实际有效性独立成列：状态字段与有效期可能不一致 -->
                <StatusBadge
                  :status="qualEffective(q.expireDate) ? 'success' : 'failed'"
                  :label="qualEffective(q.expireDate) ? '有效' : '已过期'"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-3 text-[12px] text-ink-3">
        同一资质类型可能因换证或复审存在多条记录，判定时取有效期最新的一条。
      </p>
    </section>

    <!-- 授权 -->
    <section v-else-if="tab === 'auths'" aria-label="实验室授权">
      <EmptyState v-if="!authorizations.length" title="暂无授权记录" description="该人员没有被授予任何实验室准入授权。" />
      <div v-else class="panel overflow-x-auto">
        <table class="w-full min-w-[720px] text-[13px]">
          <caption class="sr-only">实验室准入授权</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">实验室</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">授权生效</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">授权失效</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">授权人</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">状态</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">双人要求</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in authorizations" :key="a.id" class="border-t border-line">
              <td class="px-4 py-2.5">
                <span class="block text-ink">{{ a.labId }}</span>
                <span class="text-[12px] text-ink-3">{{ labName(a.labId) }}</span>
              </td>
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ a.authFrom }}</td>
              <td class="px-4 py-2.5 tabular-nums" :class="a.authTo >= todayIso ? 'text-ink-2' : 'text-err'">{{ a.authTo }}</td>
              <td class="px-4 py-2.5 text-ink-2">{{ a.grantor }}</td>
              <td class="px-4 py-2.5"><StatusBadge :status="AUTH_TONE[a.status]" :label="a.status" /></td>
              <td class="px-4 py-2.5 text-ink-2">
                {{ workspace.findLab(a.labId)?.needsDouble ? '要求双人准入' : '无' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-3 text-[12px] text-ink-3">
        授权是否可用需同时满足：状态为「有效」，且判定日期落在授权生效与失效之间。
        当前有效授权 {{ activeAuths.length }} 条。
      </p>
    </section>

    <!-- 通行记录 -->
    <section v-else aria-label="通行记录">
      <EmptyState v-if="!events.length" title="暂无通行记录" description="该人员没有门禁通行记录。" />
      <div v-else class="panel overflow-x-auto">
        <table class="w-full min-w-[720px] text-[13px]">
          <caption class="sr-only">门禁通行记录</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">时间</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">实验室</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">方向</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">验证方式</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">结果</th>
              <th scope="col" class="h-9 px-4 text-right font-medium">同行人数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in events" :key="e.id" class="border-t border-line">
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ e.eventTime }}</td>
              <td class="px-4 py-2.5">
                <span class="block text-ink">{{ e.labId }}</span>
                <span class="text-[12px] text-ink-3">{{ labName(e.labId) }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="inline-flex items-center gap-1 text-ink-2">
                  <LogIn v-if="e.direction === '进'" class="size-3.5" aria-hidden="true" />
                  <LogOut v-else class="size-3.5" aria-hidden="true" />
                  {{ e.direction }}
                </span>
              </td>
              <td class="px-4 py-2.5 text-ink-2">{{ e.authType }}</td>
              <td class="px-4 py-2.5"><StatusBadge :status="RESULT_TONE[e.authResult]" :label="e.authResult" /></td>
              <td class="px-4 py-2.5 text-right">
                <span v-if="e.companionNo === null" class="text-ink-3">未登记</span>
                <span
                  v-else
                  :class="workspace.findLab(e.labId)?.needsDouble && e.direction === '进' && e.companionNo < 1 ? 'text-err' : 'text-ink-2'"
                >
                  {{ e.companionNo }}
                  <span v-if="workspace.findLab(e.labId)?.needsDouble && e.direction === '进' && e.companionNo < 1" class="text-[12px]">
                    （违反双人准入）
                  </span>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
        <DoorOpen class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        剧毒品间要求双人准入，同行人数为 0 的「进 + 通过」记录即违反该要求。
        系统只读，不能修改门禁权限或远程开门。
      </p>
    </section>
  </div>

  <EmptyState v-else title="人员不存在" description="他/她可能已从名录移除，或链接有误。">
    <template #action><RouterLink to="/persons" class="btn-primary">返回人员列表</RouterLink></template>
  </EmptyState>
</template>
