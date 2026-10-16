<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Play, Save, ArrowLeft, X, Plus } from 'lucide-vue-next'
import { VueFlow, useVueFlow, type Node, type Edge } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { runWorkflow } from '@/services/mockApi'
import { newId } from '@/utils/format'
import type { RunStep, Workflow, WorkflowNode } from '@/types'

const route = useRoute()
const workspace = useWorkspaceStore()
const ui = useUiStore()

const wf = computed(() => workspace.findWorkflow(String(route.params.id)))

const NODE_TYPES: { type: WorkflowNode['type']; label: string; hint: string }[] = [
  { type: 'start', label: '开始', hint: '流程入口，定义输入' },
  { type: 'llm', label: '大模型', hint: '生成或改写文本' },
  { type: 'retriever', label: '知识检索', hint: '从知识库召回片段' },
  { type: 'tool', label: '工具调用', hint: '只读工具，如准入判定' },
  { type: 'condition', label: '条件判断', hint: '按结论分支' },
  { type: 'output', label: '输出', hint: '汇总为最终答复' },
]

// 画布数据用 shallowRef：Vue Flow 的 Node/Edge 是深泛型类型，ref 的深层解包会拖垮类型推导
const nodes = shallowRef<Node[]>([])
const edges = shallowRef<Edge[]>([])
const selectedId = ref<string | null>(null)
const steps = ref<RunStep[] | null>(null)
const running = ref(false)
const failNext = ref(false)
const { fitView } = useVueFlow()

const NODE_COLOR: Record<WorkflowNode['type'], string> = {
  start: '#64748B', llm: '#4F46E5', retriever: '#0369A1', tool: '#15803D', condition: '#B45309', output: '#0F172A',
}

function toFlow(w: Workflow) {
  nodes.value = w.nodes.map((n) => ({
    id: n.id,
    position: { x: n.x, y: n.y },
    data: { label: n.label, type: n.type, config: { ...n.config } },
    style: { borderColor: NODE_COLOR[n.type], borderWidth: '1px', borderRadius: '8px', fontSize: '12px', padding: '8px 12px', background: '#FFFFFF', color: '#0F172A', width: 'auto' },
  }))
  edges.value = w.edges.map((e) => ({ id: e.id, source: e.source, target: e.target, label: e.label, animated: false, style: { stroke: '#E2E8F0' } }))
}

watch(wf, (w) => {
  if (w) {
    toFlow(w)
    window.setTimeout(() => fitView({ padding: 0.2 }), 80)
  }
}, { immediate: true })

const selected = computed<WorkflowNode | null>(() => {
  const w = wf.value
  if (!w || !selectedId.value) return null
  const n = w.nodes.find((x) => x.id === selectedId.value)
  return n ?? null
})

// 选中节点的类型标签（选中为空时返回空串，避免模板里出现非空断言）
const selectedTypeLabel = computed(() => {
  const t = selected.value?.type
  return t ? NODE_TYPES.find((x) => x.type === t)?.label ?? t : ''
})

function addNode(type: WorkflowNode['type']) {
  const w = wf.value
  if (!w) return
  const label = NODE_TYPES.find((t) => t.type === type)!.label
  const node: WorkflowNode = {
    id: newId('n'), type, label, config: {},
    x: 80 + (w.nodes.length % 6) * 200, y: 60 + Math.floor(w.nodes.length / 6) * 120,
  }
  w.nodes.push(node)
  nodes.value.push({
    id: node.id, position: { x: node.x, y: node.y },
    data: { label: node.label, type, config: {} },
    style: { borderColor: NODE_COLOR[type], borderWidth: '1px', borderRadius: '8px', fontSize: '12px', padding: '8px 12px', background: '#FFFFFF', color: '#0F172A' },
  })
  selectedId.value = node.id
  ui.toast(`已添加「${label}」节点`)
}

function removeSelected() {
  const w = wf.value
  if (!w || !selectedId.value) return
  w.nodes = w.nodes.filter((n) => n.id !== selectedId.value)
  w.edges = w.edges.filter((e) => e.source !== selectedId.value && e.target !== selectedId.value)
  nodes.value = nodes.value.filter((n) => n.id !== selectedId.value)
  edges.value = edges.value.filter((e) => e.source !== selectedId.value && e.target !== selectedId.value)
  selectedId.value = null
  ui.toast('已删除节点')
}

function updateConfig(key: string, value: string) {
  const w = wf.value
  if (!w || !selectedId.value) return
  const n = w.nodes.find((x) => x.id === selectedId.value)
  if (!n) return
  n.config = { ...n.config, [key]: value }
  const flow = nodes.value.find((x) => x.id === selectedId.value)
  if (flow) flow.data.config = { ...n.config }
}

function renameSelected(value: string) {
  const w = wf.value
  if (!w || !selectedId.value) return
  const n = w.nodes.find((x) => x.id === selectedId.value)
  if (!n) return
  n.label = value || '未命名节点'
  const flow = nodes.value.find((x) => x.id === selectedId.value)
  if (flow) flow.data.label = n.label
}

function onConnect(params: { source: string; target: string }) {
  const w = wf.value
  if (!w) return
  const edge = { id: newId('e'), source: params.source, target: params.target }
  w.edges.push(edge)
  edges.value.push({ ...edge, style: { stroke: '#E2E8F0' } })
}

// 画布拖动后同步回 store，保存时位置不会丢
function onNodeDragStop(p: { node: Node }) {
  const w = wf.value
  const n = w?.nodes.find((x) => x.id === p.node.id)
  if (n) {
    n.x = Math.round(p.node.position.x)
    n.y = Math.round(p.node.position.y)
  }
}

function save() {
  if (!wf.value) return
  wf.value.status = 'published'
  ui.toast('工作流已保存并发布')
}

async function run() {
  if (!wf.value || running.value) return
  running.value = true
  steps.value = null
  try {
    const failing = failNext.value ? wf.value.nodes.find((n) => n.type === 'tool')?.id : undefined
    const res = await runWorkflow(wf.value, { failAt: failing })
    steps.value = res.steps
    wf.value.lastRunAt = '2026-10-15 10:00'
    workspace.addLog({
      id: res.logId, taskType: 'workflow', target: wf.value.name, startedAt: '2026-10-15 10:00',
      durationMs: res.steps.reduce((s, x) => s + x.durationMs, 0),
      status: res.steps.some((s) => s.status === 'failed') ? 'failed' : 'success',
      tokens: 1180, steps: res.steps, linkedChunks: [], isMock: true,
      error: res.steps.find((s) => s.error)?.error,
    })
    ui.toast(res.steps.some((s) => s.status === 'failed') ? '模拟运行结束：存在失败节点' : '模拟运行完成', res.steps.some((s) => s.status === 'failed') ? 'error' : 'success')
  } catch {
    ui.toast('模拟运行失败，请重试', 'error')
  } finally {
    running.value = false
    failNext.value = false
  }
}

const stepOf = (id: string) => steps.value?.find((s) => s.nodeId === id)

watch(() => route.query.run, (v) => {
  if (v) run()
}, { immediate: true })
</script>

<template>
  <div v-if="wf">
    <PageHeader :title="wf.name" :description="wf.description">
      <template #actions>
        <label class="flex items-center gap-2 text-[12px] text-ink-2">
          <input v-model="failNext" type="checkbox" class="accent-[#4F46E5]" />下次运行模拟失败
        </label>
        <button type="button" class="btn-default" @click="save"><Save class="size-4" aria-hidden="true" />保存并发布</button>
        <button type="button" class="btn-primary" :disabled="running" @click="run">
          <Play class="size-4" aria-hidden="true" />{{ running ? '运行中…' : '运行' }}
        </button>
      </template>
    </PageHeader>

    <RouterLink to="/workflows" class="mb-4 inline-flex items-center gap-1 text-[13px] text-ink-2 hover:text-ink">
      <ArrowLeft class="size-3.5" aria-hidden="true" />返回工作流列表
    </RouterLink>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-[200px_minmax(0,1fr)_300px]">
      <!-- 节点面板 -->
      <section class="panel p-3" aria-labelledby="palette-title">
        <h2 id="palette-title" class="mb-2 px-1 text-[13px] font-semibold text-ink">节点组件</h2>
        <ul class="space-y-1.5">
          <li v-for="t in NODE_TYPES" :key="t.type">
            <button
              type="button"
              class="w-full rounded-[var(--radius-control)] border border-line px-3 py-2 text-left hover:border-brand hover:bg-brand-soft"
              @click="addNode(t.type)"
            >
              <span class="flex items-center gap-1.5 text-[13px] text-ink">
                <span class="size-2 rounded-full" :style="{ background: NODE_COLOR[t.type] }" aria-hidden="true" />
                {{ t.label }}
              </span>
              <span class="block text-[12px] text-ink-3">{{ t.hint }}</span>
            </button>
          </li>
        </ul>
      </section>

      <!-- 画布 -->
      <section class="panel overflow-hidden" aria-label="工作流画布">
        <div class="h-[520px]">
          <VueFlow
            v-model:nodes="nodes"
            v-model:edges="edges"
            :default-viewport="{ zoom: 0.85 }"
            :min-zoom="0.3"
            :max-zoom="1.6"
            fit-view-on-init
            @node-click="(p) => (selectedId = p.node.id)"
            @node-drag-stop="onNodeDragStop"
            @connect="onConnect"
          >
            <Background :gap="16" :size="1" pattern-color="#E2E8F0" />
            <template #node-default="{ data }">
              <div class="min-w-[150px]">
                <span class="block font-medium text-ink">{{ data.label }}</span>
                <span class="mt-0.5 block text-[11px] text-ink-3">{{ data.type }}</span>
                <StatusBadge v-if="stepOf(selectedId ?? '')" :status="'running'" label="运行中" />
              </div>
            </template>
          </VueFlow>
        </div>
        <p class="border-t border-line px-4 py-2 text-[12px] text-ink-3">
          节点可拖动；从节点边缘拖出连线可建立依赖。画布操作：滚轮缩放，拖拽空白处平移。
        </p>
      </section>

      <!-- 配置面板 -->
      <section class="panel p-4" aria-labelledby="config-title">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 id="config-title" class="text-[13px] font-semibold text-ink">节点配置</h2>
          <button v-if="selected" type="button" class="btn-ghost h-7 px-2 text-[12px] text-err" @click="removeSelected">
            <X class="size-3.5" aria-hidden="true" />删除节点
          </button>
        </div>

        <p v-if="!selected" class="text-[12px] text-ink-3">在画布上选择一个节点以编辑其参数。</p>
        <div v-else class="space-y-3">
          <div>
            <label class="label" for="node-label">节点名称</label>
            <input id="node-label" :value="selected.label" class="input" @input="renameSelected(($event.target as HTMLInputElement).value)" />
          </div>
          <div>
            <span class="label">节点类型</span>
            <p class="text-[13px] text-ink">{{ selectedTypeLabel }}</p>
          </div>

          <div v-for="(v, k) in selected.config" :key="k">
            <label class="label" :for="`cfg-${k}`">{{ k }}</label>
            <input :id="`cfg-${k}`" :value="v" class="input" @input="updateConfig(String(k), ($event.target as HTMLInputElement).value)" />
          </div>

          <div class="border-t border-line pt-3">
            <label class="label" for="cfg-new-key">新增参数</label>
            <div class="flex gap-2">
              <input id="cfg-new-key" class="input" placeholder="参数名" @keydown.enter="updateConfig(($event.target as HTMLInputElement).value, ''); ($event.target as HTMLInputElement).value = ''" />
              <button type="button" class="btn-default" aria-label="添加参数" @click="(($event.target as HTMLElement).previousElementSibling as HTMLInputElement)?.focus()">
                <Plus class="size-4" aria-hidden="true" />
              </button>
            </div>
            <p class="mt-1 text-[12px] text-ink-3">输入参数名后按 Enter 添加。</p>
          </div>
        </div>
      </section>
    </div>

    <!-- 执行日志 -->
    <section class="panel mt-4" aria-labelledby="runlog-title">
      <div class="flex items-center gap-2 border-b border-line px-4 py-3">
        <h2 id="runlog-title" class="text-[15px] font-semibold text-ink">执行日志</h2>
        <span class="mock-tag">模拟执行</span>
        <span v-if="running" class="text-[12px] text-ink-2">正在按节点顺序执行…</span>
      </div>

      <EmptyState v-if="!steps && !running" title="尚未运行" description="点击右上角“运行”，按节点顺序模拟执行并查看每步输入输出。" />
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[720px] text-[13px]">
          <caption class="sr-only">节点执行明细</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">节点</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">状态</th>
              <th scope="col" class="h-9 px-4 text-right font-medium">耗时</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">输入</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">输出 / 错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in steps ?? []" :key="s.nodeId" class="border-t border-line align-top">
              <td class="px-4 py-2.5 text-ink">{{ s.label }}</td>
              <td class="px-4 py-2.5"><StatusBadge :status="s.status" /></td>
              <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ s.durationMs }} ms</td>
              <td class="max-w-[220px] px-4 py-2.5 text-ink-2">{{ s.input }}</td>
              <td class="max-w-[260px] px-4 py-2.5">
                <span v-if="s.error" class="text-err">{{ s.error }}</span>
                <span v-else class="text-ink-2">{{ s.output }}</span>
              </td>
            </tr>
            <tr v-if="running" class="border-t border-line">
              <td colspan="5" class="px-4 py-3 text-[12px] text-ink-2">执行中…</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>

  <EmptyState v-else title="工作流不存在" description="它可能已被删除，或链接有误。">
    <template #action><RouterLink to="/workflows" class="btn-primary">返回工作流列表</RouterLink></template>
  </EmptyState>
</template>

<style scoped>
:deep(.vue-flow__edge-path) {
  stroke-width: 1.5;
}
</style>
