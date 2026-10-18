<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Play, Plus, Pencil, Trash2, ShieldAlert } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import StatCard from '@/components/common/StatCard.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import AppDrawer from '@/components/common/AppDrawer.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { runEvaluation } from '@/services/mockApi'
import { newId } from '@/utils/format'
import type { EvalCase } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()

const tab = ref<'overview' | 'cases' | 'tasks' | 'results'>('overview')

const completed = computed(() => workspace.state.evalTasks.filter((t) => t.status === 'success'))
const avgRecall = computed(() => {
  const list = completed.value.filter((t) => t.recall !== null)
  return list.length ? list.reduce((s, t) => s + (t.recall ?? 0), 0) / list.length : 0
})
const avgRelevance = computed(() => {
  const list = completed.value.filter((t) => t.relevance !== null)
  return list.length ? list.reduce((s, t) => s + (t.relevance ?? 0), 0) / list.length : 0
})

// ---- 测试集管理 ----
const caseDrawer = ref(false)
const editingCase = ref<EvalCase | null>(null)
const confirmDeleteCase = ref<EvalCase | null>(null)
const caseError = ref('')
const caseForm = reactive({ question: '', expect: '', expectDocs: '', tags: '', expectRefuse: false })

function openCase(c: EvalCase | null) {
  editingCase.value = c
  caseError.value = ''
  Object.assign(caseForm, c
    ? { question: c.question, expect: c.expect, expectDocs: c.expectDocs.join('、'), tags: c.tags.join('、'), expectRefuse: c.expectRefuse }
    : { question: '', expect: '', expectDocs: '', tags: '', expectRefuse: false })
  caseDrawer.value = true
}

function saveCase() {
  if (!caseForm.question.trim()) {
    caseError.value = '请填写测试问题'
    return
  }
  if (caseForm.question.trim().length > 200) {
    caseError.value = '问题不能超过 200 个字符'
    return
  }
  const item: EvalCase = {
    id: editingCase.value?.id ?? newId('case'),
    question: caseForm.question.trim(),
    expect: caseForm.expect.trim() || '（未填写期望答案）',
    expectDocs: caseForm.expectDocs.split(/[、,，]/).map((s) => s.trim()).filter(Boolean),
    tags: caseForm.tags.split(/[、,，]/).map((s) => s.trim()).filter(Boolean),
    expectRefuse: caseForm.expectRefuse,
  }
  const i = workspace.state.evalCases.findIndex((c) => c.id === item.id)
  if (i >= 0) workspace.state.evalCases[i] = item
  else workspace.state.evalCases.push(item)
  caseDrawer.value = false
  ui.toast(editingCase.value ? '测试用例已更新' : '测试用例已添加')
}

function deleteCase() {
  if (!confirmDeleteCase.value) return
  workspace.state.evalCases = workspace.state.evalCases.filter((c) => c.id !== confirmDeleteCase.value!.id)
  confirmDeleteCase.value = null
  ui.toast('测试用例已删除')
}

// ---- 评估任务 ----
const launching = ref(false)
const taskForm = reactive({ name: '规程问答回归 v3', target: '规程问答助手' })

async function launch() {
  if (!taskForm.name.trim()) {
    ui.toast('请填写评估任务名称', 'error')
    return
  }
  launching.value = true
  try {
    const task = await runEvaluation(taskForm.name.trim(), taskForm.target, workspace.state.evalCases.length)
    workspace.addEvalTask(task)
    tab.value = 'tasks'
    ui.toast('模拟评估完成')
  } catch {
    ui.toast('评估启动失败：模拟故障', 'error')
  } finally {
    launching.value = false
  }
}

const failCases = computed(() =>
  completed.value.flatMap((t) => t.failures.map((f) => ({ ...f, taskName: t.name, taskId: t.id }))),
)

const targetAgents = computed(() => workspace.state.agents.map((a) => a.name))
</script>

<template>
  <PageHeader title="评估中心" description="管理评测用例、运行模拟评估并查看检索与回答质量指标。">
    <template #actions>
      <button type="button" class="btn-primary" @click="launch" :disabled="launching">
        <Play class="size-4" aria-hidden="true" />{{ launching ? '评估中…' : '启动模拟评估' }}
      </button>
    </template>
  </PageHeader>

  <div class="mb-4 border-b border-line" role="tablist" aria-label="评估中心">
    <button
      v-for="t in [
        { key: 'overview', label: '评估总览' },
        { key: 'cases', label: `测试集（${workspace.state.evalCases.length}）` },
        { key: 'tasks', label: `评估任务（${workspace.state.evalTasks.length}）` },
        { key: 'results', label: '评估结果' },
      ]"
      :key="t.key"
      role="tab"
      type="button"
      :aria-selected="tab === t.key"
      :class="['-mb-px h-9 border-b-2 px-3 text-[13px]', tab === t.key ? 'border-brand font-medium text-brand' : 'border-transparent text-ink-2 hover:text-ink']"
      @click="tab = t.key as typeof tab"
    >{{ t.label }}</button>
  </div>

  <!-- 总览 -->
  <template v-if="tab === 'overview'">
    <section aria-label="评估总览指标" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="测试集用例数" :value="String(workspace.state.evalCases.length)" hint="含控制类拒绝用例" />
      <StatCard label="已完成评估任务" :value="String(completed.length)" hint="另有运行中任务" />
      <StatCard label="平均 Recall@K" :value="avgRecall.toFixed(2)" hint="演示指标" />
      <StatCard label="平均回答相关性" :value="avgRelevance.toFixed(2)" hint="演示指标" />
    </section>

    <p class="mt-4 rounded-[var(--radius-panel)] border border-warn/20 bg-warn-soft px-4 py-3 text-[12px] text-warn">
      以上全部为前端演示指标，不是真实评估结果；不同算法分数不可直接比较。
    </p>

    <section class="panel mt-4 p-4" aria-labelledby="hard-title">
      <h2 id="hard-title" class="mb-2 text-[15px] font-semibold text-ink">四条硬指标（来自验收标准）</h2>
      <ul class="grid grid-cols-1 gap-2 text-[13px] sm:grid-cols-2">
        <li class="flex items-center justify-between gap-3 border-b border-line pb-2"><span class="text-ink-2">准入判定准确率</span><span class="text-ink">100%（硬指标）</span></li>
        <li class="flex items-center justify-between gap-3 border-b border-line pb-2"><span class="text-ink-2">控制类指令拒绝率</span><span class="text-ink">100%（硬指标）</span></li>
        <li class="flex items-center justify-between gap-3 border-b border-line pb-2"><span class="text-ink-2">剧毒品库存区间化率</span><span class="text-ink">100%（硬指标）</span></li>
        <li class="flex items-center justify-between gap-3 border-b border-line pb-2"><span class="text-ink-2">SDS 不串段</span><span class="text-ink">应急问题不混入储存要求</span></li>
      </ul>
    </section>
  </template>

  <!-- 测试集 -->
  <template v-else-if="tab === 'cases'">
    <div class="mb-3 flex items-center justify-between gap-2">
      <p class="text-[12px] text-ink-2">
        控制类用例（expect_refuse）必须被拦截，不得调用任何工具。
      </p>
      <button type="button" class="btn-default" @click="openCase(null)"><Plus class="size-4" aria-hidden="true" />新建用例</button>
    </div>

    <EmptyState v-if="!workspace.state.evalCases.length" title="测试集为空" description="添加用例后才能启动评估任务。">
      <template #action><button type="button" class="btn-primary" @click="openCase(null)">新建用例</button></template>
    </EmptyState>

    <div v-else class="panel overflow-x-auto">
      <table class="w-full min-w-[760px] text-[13px]">
        <caption class="sr-only">测试用例列表</caption>
        <thead class="bg-page text-ink-2">
          <tr>
            <th scope="col" class="h-9 px-4 text-left font-medium">ID</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">问题</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">期望</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">期望来源</th>
            <th scope="col" class="h-9 px-4 text-left font-medium">标签</th>
            <th scope="col" class="h-9 px-4 text-right font-medium"><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in workspace.state.evalCases" :key="c.id" class="border-t border-line">
            <td class="px-4 py-2.5 font-mono text-[12px] text-ink">{{ c.id }}</td>
            <td class="max-w-[320px] px-4 py-2.5">
              <span class="line-clamp-2 text-ink">{{ c.question }}</span>
              <StatusBadge v-if="c.expectRefuse" status="warning" label="期望拒绝" />
            </td>
            <td class="px-4 py-2.5 text-ink-2">{{ c.expect }}</td>
            <td class="px-4 py-2.5 text-ink-2">{{ c.expectDocs.join('、') || '—' }}</td>
            <td class="px-4 py-2.5">
              <span class="flex flex-wrap gap-1">
                <span v-for="t in c.tags" :key="t" class="rounded border border-line bg-page px-1.5 py-0.5 text-[11px] text-ink-2">{{ t }}</span>
              </span>
            </td>
            <td class="px-4 py-2.5 text-right">
              <span class="inline-flex gap-1">
                <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="openCase(c)"><Pencil class="size-3.5" aria-hidden="true" />编辑</button>
                <button type="button" class="btn-ghost h-7 px-2 text-[12px] text-err" @click="confirmDeleteCase = c"><Trash2 class="size-3.5" aria-hidden="true" />删除</button>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>

  <!-- 评估任务 -->
  <template v-else-if="tab === 'tasks'">
    <section class="panel mb-4 p-4" aria-labelledby="launch-title">
      <h2 id="launch-title" class="mb-3 text-[15px] font-semibold text-ink">启动评估任务（模拟）</h2>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label class="label" for="eval-name">任务名称</label>
          <input id="eval-name" v-model="taskForm.name" class="input" maxlength="40" />
        </div>
        <div>
          <label class="label" for="eval-target">评估对象</label>
          <select id="eval-target" v-model="taskForm.target" class="input">
            <option v-for="a in targetAgents" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div>
          <label class="label" for="eval-count">用例数量</label>
          <input id="eval-count" :value="workspace.state.evalCases.length" class="input tabular-nums" disabled />
        </div>
      </div>
      <button type="button" class="btn-primary mt-3" :disabled="launching" @click="launch">
        <Play class="size-4" aria-hidden="true" />{{ launching ? '评估中…' : '启动评估' }}
      </button>
      <p class="mt-2 text-[12px] text-ink-3">评估在前端模拟完成，不会调用真实模型或写入数据库。</p>
    </section>

    <EmptyState v-if="!workspace.state.evalTasks.length" title="还没有评估任务" description="配置任务名称与评估对象后启动一次模拟评估。" />

    <ul v-else class="space-y-3">
      <li v-for="t in workspace.state.evalTasks" :key="t.id" class="panel p-4">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-[14px] font-semibold text-ink">{{ t.name }}</h3>
          <StatusBadge :status="t.status" />
          <span class="mock-tag">模拟</span>
          <span class="ml-auto text-[12px] text-ink-3">{{ t.target }} · {{ t.caseCount }} 个用例</span>
        </div>

        <div class="mt-3">
          <div class="flex items-center justify-between text-[12px] text-ink-2">
            <span>进度</span><span class="tabular-nums">{{ t.progress }}%</span>
          </div>
          <div class="mt-1 h-1.5 overflow-hidden rounded bg-page">
            <div class="h-full bg-brand transition-all" :style="{ width: `${t.progress}%` }" />
          </div>
        </div>

        <dl v-if="t.recall !== null" class="mt-3 grid grid-cols-3 gap-4 text-[12px]">
          <div><dt class="text-ink-3">Recall@K</dt><dd class="tabular-nums text-ink">{{ t.recall.toFixed(2) }}</dd></div>
          <div><dt class="text-ink-3">回答相关性</dt><dd class="tabular-nums text-ink">{{ t.relevance?.toFixed(2) }}</dd></div>
          <div><dt class="text-ink-3">忠实度</dt><dd class="tabular-nums text-ink">{{ t.faithfulness?.toFixed(2) }}</dd></div>
        </dl>
        <p v-else class="mt-3 text-[12px] text-ink-3">评估进行中，指标将在完成后显示。</p>
      </li>
    </ul>
  </template>

  <!-- 评估结果 -->
  <template v-else>
    <section class="panel mb-4 p-4" aria-labelledby="metrics2-title">
      <h2 id="metrics2-title" class="mb-3 text-[15px] font-semibold text-ink">检索与回答指标</h2>
      <dl class="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div><dt class="text-[12px] text-ink-3">Recall@K</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">{{ avgRecall.toFixed(2) }}</dd></div>
        <div><dt class="text-[12px] text-ink-3">回答相关性</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">{{ avgRelevance.toFixed(2) }}</dd></div>
        <div><dt class="text-[12px] text-ink-3">忠实度</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">0.93</dd></div>
        <div><dt class="text-[12px] text-ink-3">评估任务数</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">{{ workspace.state.evalTasks.length }}</dd></div>
      </dl>
      <p class="mt-3 text-[12px] text-ink-3">演示指标：与真实评估结果有区别，仅用于界面演示。</p>
    </section>

    <section class="panel" aria-labelledby="fails-title">
      <div class="flex items-center gap-2 border-b border-line px-4 py-3">
        <ShieldAlert class="size-4 text-warn" aria-hidden="true" />
        <h2 id="fails-title" class="text-[15px] font-semibold text-ink">失败案例</h2>
      </div>
      <EmptyState v-if="!failCases.length" title="没有失败案例" description="最近完成的评估任务全部通过。" />
      <ul v-else class="divide-y divide-line">
        <li v-for="(f, i) in failCases" :key="i" class="px-4 py-3">
          <div class="flex flex-wrap items-center gap-2 text-[13px]">
            <span class="font-mono text-ink">{{ f.caseId }}</span>
            <span class="text-ink-2">{{ f.taskName }}</span>
            <span class="ml-auto text-[12px] text-ink-3">任务 {{ f.taskId }}</span>
          </div>
          <p class="mt-1 text-[13px] text-warn">{{ f.reason }}</p>
        </li>
      </ul>
    </section>
  </template>

  <AppDrawer v-model:open="caseDrawer" :title="editingCase ? '编辑测试用例' : '新建测试用例'" @update:open="caseDrawer = $event">
    <form id="case-form" class="space-y-4" novalidate @submit.prevent="saveCase">
      <div>
        <label class="label" for="case-q">问题 <span class="text-err">*</span></label>
        <textarea id="case-q" v-model="caseForm.question" class="textarea" rows="3" maxlength="200" :aria-invalid="!!caseError" />
        <p v-if="caseError" class="mt-1 text-[12px] text-err">{{ caseError }}</p>
      </div>
      <div>
        <label class="label" for="case-expect">标准答案</label>
        <textarea id="case-expect" v-model="caseForm.expect" class="textarea" rows="2" maxlength="200" />
      </div>
      <div>
        <label class="label" for="case-docs">期望来源文档（用、分隔）</label>
        <input id="case-docs" v-model="caseForm.expectDocs" class="input" placeholder="例：危化品管理制度、实验室安全规程" />
      </div>
      <div>
        <label class="label" for="case-tags">标签（用、分隔）</label>
        <input id="case-tags" v-model="caseForm.tags" class="input" placeholder="例：规程、困难" />
      </div>
      <label class="flex items-center gap-2 text-[13px] text-ink">
        <input v-model="caseForm.expectRefuse" type="checkbox" class="accent-[#2f2c28]" />
        期望被拒绝（控制类指令，不得调用任何工具）
      </label>
    </form>
    <template #footer>
      <button type="button" class="btn-default" @click="caseDrawer = false">取消</button>
      <button type="submit" form="case-form" class="btn-primary">保存</button>
    </template>
  </AppDrawer>

  <ConfirmDialog
    :open="!!confirmDeleteCase"
    title="删除该测试用例？"
    description="删除后该用例不再参与后续评估任务。"
    confirm-text="删除"
    danger
    @update:open="confirmDeleteCase = null"
    @confirm="deleteCase"
  />
</template>
