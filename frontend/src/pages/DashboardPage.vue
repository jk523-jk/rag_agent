<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import StatCard from '@/components/common/StatCard.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { chatTrend } from '@/mocks/trend'
import type { LogEntry } from '@/types'

const workspace = useWorkspaceStore()
const router = useRouter()
const range = ref<7 | 30>(7)

const TrendChart = defineAsyncComponent(() => import('@/components/common/TrendChart.vue'))

const trend = computed(() => chatTrend[range.value])
const hasData = computed(() => trend.value.some((p) => p.value > 0))

const recentTasks = computed(() => workspace.state.logs.slice(0, 5))

// 最近活动：演示用固定条目，点击进入对应页面
const activities = [
  { text: '知识库「重点试剂 SDS 摘要」新增文档 过氧化氢_SDS.md', at: '2026-10-14 16:50', to: '/knowledge/kb-sds' },
  { text: 'Agent「准入判定助手」完成一次三闸判定', at: '2026-10-15 09:42', to: '/logs' },
  { text: '工作流「准入复核流程」运行失败（模拟超时）', at: '2026-10-14 16:58', to: '/workflows/wf-access' },
  { text: '检索实验室执行混合检索（模拟）', at: '2026-10-14 17:30', to: '/retrieval' },
]

function taskTarget(log: LogEntry) {
  const agent = workspace.state.agents.find((a) => a.name === log.target)
  return agent ? `/agents/${agent.id}` : '/logs'
}

function openLog(log: LogEntry) {
  router.push({ path: '/logs', query: { id: log.id } })
}
</script>

<template>
  <PageHeader title="工作台" description="查看 AI 应用、知识库和任务运行的整体状态。">
    <template #actions>
      <RouterLink to="/agents?create=1" class="btn-default">新建 Agent</RouterLink>
      <RouterLink to="/knowledge?create=1" class="btn-primary">新建知识库</RouterLink>
    </template>
  </PageHeader>

  <p class="mb-4 text-[12px] text-ink-3">
    以下为演示数据（模拟），不代表真实生产运行情况。
  </p>

  <!-- 核心指标 -->
  <section aria-label="核心指标" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <StatCard label="Agent 总数" :value="String(workspace.state.agents.length)" delta="较上周 +1" deltaTone="up" />
    <StatCard label="知识库总数" :value="String(workspace.state.knowledgeBases.length)" delta="较上周 +0" deltaTone="flat" />
    <StatCard label="今日对话数" value="1,284" delta="较昨日 +6.2%" deltaTone="up" />
    <StatCard label="任务成功率" value="98.6%" delta="较上周 −0.4%" deltaTone="down" />
  </section>

  <div class="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
    <!-- 使用趋势 -->
    <section class="panel p-4 xl:col-span-2" aria-labelledby="trend-title">
      <div class="mb-3 flex items-center justify-between gap-2">
        <div>
          <h2 id="trend-title" class="text-[15px] font-semibold text-ink">对话趋势</h2>
          <p class="text-[12px] text-ink-3">模拟数据 · 按日统计</p>
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
        <li v-for="a in activities" :key="a.text">
          <RouterLink :to="a.to" class="flex flex-col gap-0.5 py-2.5 hover:text-brand">
            <span class="text-[13px] text-ink">{{ a.text }}</span>
            <span class="text-[12px] text-ink-3">{{ a.at }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>

  <!-- 最近任务 -->
  <section class="panel mt-6" aria-labelledby="tasks-title">
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

</template>
