<script setup lang="ts">
import { todayIso } from '@/utils/clock'
import { auth } from '@/services/auth'
import { computed, defineAsyncComponent, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import StatCard from '@/components/common/StatCard.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InkDivider from '@/components/common/InkDivider.vue'
import PageSection from '@/components/common/PageSection.vue'
import FadeInOnScroll from '@/components/common/FadeInOnScroll.vue'
import QuoteBlock from '@/components/common/QuoteBlock.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { LogEntry } from '@/types'

const workspace = useWorkspaceStore()
const router = useRouter()
const range = ref<7 | 30>(7)

const TrendChart = defineAsyncComponent(() => import('@/components/common/TrendChart.vue'))

const trend = computed(() => {
  const end = new Date(`${todayIso}T12:00:00`)
  return Array.from({ length: range.value }, (_, index) => {
    const day = new Date(end)
    day.setDate(end.getDate() - range.value + index + 1)
    const iso = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
    return {
      date: `${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`,
      value: workspace.state.logs.filter((log) => log.taskType === 'chat' && log.startedAt.startsWith(iso)).length,
    }
  })
})
const hasData = computed(() => trend.value.some((p) => p.value > 0))

const recentLogs = computed(() => [...workspace.state.logs].sort((a, b) => b.startedAt.localeCompare(a.startedAt)))
const recentTasks = computed(() => recentLogs.value.slice(0, 5))
const recentActivities = computed(() => recentLogs.value.slice(0, 5).map((log) => ({
  id: log.id,
  text: `${log.target} · ${log.status === 'success' ? '已完成' : log.status === 'running' ? '运行中' : '执行失败'}`,
  at: log.startedAt,
})))

// ---------------- 实验室指标（对齐后端判定口径）----------------


/** 资质闸唯一认可的证书类型 */
const CERT_GATE_TYPE = '安全考试合格证'

const equipmentCount = computed(() => workspace.state.equipment.length)
const inUseCount = computed(() => workspace.state.equipment.filter((e) => e.status === '在用').length)

/** 校准是否过期：以有效期为准，不看状态字段 */
const calibExpiredCount = computed(
  () => workspace.state.equipment.filter((e) => !!e.calibrateDue && e.calibrateDue < todayIso).length,
)

/** 资质异常人数：安全考试合格证已过期或未登记 */
const certExpiredCount = computed(
  () =>
    workspace.state.persons.filter((p) => {
      const matched = workspace
        .qualificationsOf(p.id)
        .filter((q) => q.certType === CERT_GATE_TYPE)
      if (!matched.length) return true
      const latest = matched.reduce((a, b) => (b.expireDate > a.expireDate ? b : a))
      return latest.expireDate < todayIso || latest.issueDate > todayIso || latest.status !== '有效'
    }).length,
)

const openLoanCount = computed(
  () => workspace.state.equipment.filter((e) => workspace.currentLoan(e.equipId)).length,
)

const overdueCount = computed(
  () =>
    workspace.state.equipmentLoans.filter(
      (l) => l.returnTime === null && l.dueTime < `${todayIso} 23:59`,
    ).length,
)

function taskTarget(log: LogEntry) {
  const agent = workspace.state.agents.find((a) => a.name === log.target)
  return agent ? `/agents/${agent.id}` : '/logs'
}

function openLog(log: LogEntry) {
  router.push({ path: '/logs', query: { id: log.id } })
}
</script>

<template>
  <PageHeader title="工作台" description="查看 AI 应用、实验室设备与人员的整体状态。">
    <template #actions>
      <RouterLink to="/applications" class="btn-primary">处理许可申请</RouterLink>
      <RouterLink v-if="auth.user?.systemAdmin" to="/chat" class="btn-default">去 AI 对话</RouterLink>
      <RouterLink v-if="workspace.dataSource === 'mock'" to="/equipment?create=1" class="btn-primary">新增设备</RouterLink>
    </template>
  </PageHeader>

  <p v-if="workspace.dataSource !== 'mock'" class="mb-4 flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
    <template v-if="workspace.dataSource === 'mysql'">
      <span class="rounded-full bg-ok-soft px-2 py-0.5 text-[11px] font-medium text-ok">数据已更新</span>
      数据读取于 {{ workspace.serverTime }}
    </template>
    <template v-else-if="workspace.dataSource === 'loading'">
      <span class="rounded-full bg-info-soft px-2 py-0.5 text-[11px] font-medium text-info">加载中</span>
      正在从后端读取数据…
    </template>
    <template v-else-if="workspace.dataSource === 'error'">
      <span class="rounded-full bg-err-soft px-2 py-0.5 text-[11px] font-medium text-err">连接失败</span>
      {{ workspace.dataError }}——页面为空不代表库里没有数据
    </template>
  </p>

  <InkDivider class="mt-5" />

  <!-- 核心指标 -->
  <FadeInOnScroll>
    <section aria-label="核心指标" class="mt-[var(--space-ma-2)] grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <StatCard label="设备总数" :value="String(equipmentCount)" :delta="`在用 ${inUseCount}`" deltaTone="flat" />
    <StatCard
      label="校准过期"
      :value="String(calibExpiredCount)"
      :delta="calibExpiredCount ? '不得用于出具数据' : '无'"
      :deltaTone="calibExpiredCount ? 'down' : 'flat'"
    />
    <StatCard
      label="人员资质异常"
      :value="String(certExpiredCount)"
      :delta="certExpiredCount ? '资质闸将拦截' : '全部有效'"
      :deltaTone="certExpiredCount ? 'down' : 'flat'"
    />
    <StatCard
      label="借出未还"
      :value="String(openLoanCount)"
      :delta="overdueCount ? `其中 ${overdueCount} 台逾期` : '无逾期'"
      :deltaTone="overdueCount ? 'down' : 'flat'"
      />
    </section>
  </FadeInOnScroll>

  <FadeInOnScroll :delay="80">
  <div class="mt-[var(--space-ma-3)] grid grid-cols-1 gap-4 xl:grid-cols-3">
    <!-- 使用趋势 -->
    <section class="panel p-4 xl:col-span-2" aria-labelledby="trend-title">
      <div class="mb-3 flex items-center justify-between gap-2">
        <div>
          <h2 id="trend-title" class="text-[15px] font-semibold text-ink">对话趋势</h2>
          <p class="text-[12px] text-ink-3">基于运行日志 · 按日统计</p>
        </div>
        <div role="group" aria-label="时间范围" class="inline-flex rounded-[var(--radius-control)] border border-line p-0.5">
          <button
            v-for="r in [7, 30] as const"
            :key="r"
            type="button"
            :aria-pressed="range === r"
            :class="[
              'h-7 px-3 rounded-[4px] text-[12px]',
              range === r ? 'bg-brand-soft text-brand font-medium' : 'text-ink-2 hover:text-ink',
            ]"
            @click="range = r"
          >近 {{ r }} 天</button>
        </div>
      </div>
      <div v-if="hasData" class="h-64">
        <TrendChart :data="trend" :days="range" />
      </div>
      <EmptyState v-else title="暂无对话数据" description="该时间范围内没有对话记录。发起一次对话后，趋势会在这里显示。">
        <template #action>
          <RouterLink to="/chat" class="btn-primary">去 AI 对话</RouterLink>
        </template>
      </EmptyState>
    </section>

    <!-- 最近活动 -->
    <section class="panel p-4" aria-labelledby="activity-title">
      <h2 id="activity-title" class="mb-3 text-[15px] font-semibold text-ink">最近活动</h2>
      <ul class="divide-y divide-line">
        <li v-if="!recentActivities.length" class="py-4 text-[12px] text-ink-3">暂无最近活动。任务运行后，最新记录会显示在这里。</li>
        <li v-for="a in recentActivities" :key="a.id">
          <RouterLink :to="{ path: '/logs', query: { id: a.id } }" class="flex flex-col gap-0.5 py-2.5 hover:text-brand">
            <span class="text-[13px] text-ink">{{ a.text }}</span>
            <span class="text-[12px] text-ink-3">{{ a.at }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
  </FadeInOnScroll>

  <!-- 最近任务 -->
  <FadeInOnScroll :delay="120">
  <section class="panel mt-[var(--space-ma-3)]" aria-labelledby="tasks-title">
    <div class="flex items-center justify-between border-b border-line px-4 py-3">
      <h2 id="tasks-title" class="text-[15px] font-semibold text-ink">最近任务</h2>
      <RouterLink to="/logs" class="text-[13px] text-brand hover:underline">查看全部日志</RouterLink>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full min-w-[640px] text-[13px]">
        <caption class="sr-only">最近 5 条任务</caption>
        <thead class="bg-page text-ink-2">
          <tr>
            <th scope="col" class="h-9 px-4 text-left font-medium">任务</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">执行 Agent</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">开始时间</th>
            <th scope="col" class="h-9 px-4 text-right font-medium">耗时</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">状态</th>
            <th scope="col" class="h-9 px-4 text-right font-medium"><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in recentTasks" :key="t.id" class="border-t border-line">
            <td class="px-4 py-2.5 font-mono text-[12px] text-ink">{{ t.id }}</td>
            <td class="px-4 py-2.5 text-ink">
              <RouterLink :to="taskTarget(t)" class="hover:text-brand">{{ t.target }}</RouterLink>
            </td>
            <td class="px-4 py-2.5 text-ink-2 tabular-nums">{{ t.startedAt }}</td>
            <td class="px-4 py-2.5 text-right text-ink-2 tabular-nums">{{ (t.durationMs / 1000).toFixed(1) }} s</td>
            <td class="px-4 py-2.5">
              <StatusBadge :status="t.status === 'success' ? 'success' : t.status === 'running' ? 'running' : 'failed'" />
            </td>
            <td class="px-4 py-2.5 text-right">
              <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="openLog(t)">查看详情</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
  </FadeInOnScroll>

  <PageSection :ma="3">
    <InkDivider tone="light" class="mb-8" />
    <div class="flex justify-end">
      <QuoteBlock
        vertical
        text="先有记录，再有判断；没有依据的结论，一律不作数。"
        source="实验室智能管理agent · 设计原则"
      />
    </div>
  </PageSection>

</template>
