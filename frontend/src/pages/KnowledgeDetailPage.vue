<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { ArrowLeft, Upload, Trash2, RefreshCw, FileText, X } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import KnowledgeForm from '@/components/forms/KnowledgeForm.vue'
import DocumentChunkViewer from '@/components/knowledge/DocumentChunkViewer.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { newId } from '@/utils/format'
import type { KbDocument } from '@/types'

const route = useRoute()
const workspace = useWorkspaceStore()
const ui = useUiStore()

const kb = computed(() => workspace.findKb(String(route.params.id)))
const docs = computed(() => workspace.state.documents.filter((d) => d.kbId === kb.value?.id))

const tab = ref<'docs' | 'chunks' | 'config' | 'history'>('docs')
const formOpen = ref(false)
const confirmDeleteDoc = ref<KbDocument | null>(null)
const selectedDocId = ref<string | null>(null)
const uploading = ref(false)
const processingId = ref<string | null>(null)
const progress = ref(0)
const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
let timer: number | null = null

const ALLOWED = ['.md', '.txt', '.pdf', '.docx', '.xlsx']
const MAX_MB = 20

// 选中文档时分块只看该文档，否则展示全部
const docChunks = computed(() => {
  const list = workspace.state.chunks
  return selectedDocId.value ? list.filter((c) => c.docId === selectedDocId.value) : list
})

const history = computed(() =>
  docs.value.map((d) => ({ id: d.id, name: d.name, at: d.uploadedAt, status: d.status, chunks: d.chunkCount })),
)

watch(tab, (t) => {
  if (t !== 'chunks') selectedDocId.value = null
})

onUnmounted(() => {
  if (timer !== null) window.clearInterval(timer)
})

function pickFile() {
  fileInput.value?.click()
}

function validFile(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!ALLOWED.includes(ext)) return `不支持的文件格式 ${ext}，仅支持 ${ALLOWED.join(' / ')}`
  if (file.size > MAX_MB * 1024 * 1024) return `文件超过 ${MAX_MB} MB 上限`
  if (!file.size) return '文件为空'
  return null
}

// 模拟处理流程：上传 → 解析 → 切分 → 向量化 → 索引完成
const STAGES = ['上传完成', '文档解析', '文本切分', '向量化', '索引完成']

function startProcessing(doc: KbDocument) {
  processingId.value = doc.id
  progress.value = 0
  if (timer !== null) window.clearInterval(timer)
  timer = window.setInterval(() => {
    progress.value = Math.min(100, progress.value + 8)
    if (progress.value >= 100) {
      if (timer !== null) window.clearInterval(timer)
      timer = null
      const i = workspace.state.documents.findIndex((d) => d.id === doc.id)
      if (i >= 0) workspace.state.documents[i] = { ...workspace.state.documents[i], status: 'ready' }
      processingId.value = null
      ui.toast(`「${doc.name}」模拟处理完成`)
    }
  }, 160)
}

function addDocument(file: File) {
  const err = validFile(file)
  if (err) {
    ui.toast(err, 'error')
    return
  }
  if (!kb.value) return
  uploading.value = true
  const doc: KbDocument = {
    id: newId('doc'),
    kbId: kb.value.id,
    name: file.name,
    type: (file.name.slice(file.name.lastIndexOf('.') + 1) as KbDocument['type']) ?? 'md',
    sizeKb: Math.max(1, Math.round(file.size / 1024)),
    uploadedAt: '2026-10-15 10:00',
    status: 'processing',
    chunkCount: 0,
    isMock: true,
  }
  window.setTimeout(() => {
    workspace.state.documents.push(doc)
    uploading.value = false
    ui.toast(`已添加「${doc.name}」，开始模拟处理`)
    startProcessing(doc)
  }, 500)
}

function onFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files?.length) addDocument(files[0])
  ;(e.target as HTMLInputElement).value = ''
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) addDocument(file)
}

function cancelProcessing() {
  if (timer !== null) window.clearInterval(timer)
  timer = null
  if (processingId.value) {
    const i = workspace.state.documents.findIndex((d) => d.id === processingId.value)
    if (i >= 0) workspace.state.documents[i] = { ...workspace.state.documents[i], status: 'cancelled' }
  }
  processingId.value = null
  progress.value = 0
  ui.toast('已取消模拟处理任务', 'info')
}

function doDeleteDoc() {
  if (!confirmDeleteDoc.value) return
  const name = confirmDeleteDoc.value.name
  workspace.state.documents = workspace.state.documents.filter((d) => d.id !== confirmDeleteDoc.value!.id)
  confirmDeleteDoc.value = null
  ui.toast(`已删除文档「${name}」`)
}

function openChunks(doc: KbDocument) {
  selectedDocId.value = doc.id
  tab.value = 'chunks'
}

const FILE_ICON = FileText
</script>

<template>
  <div v-if="kb">
    <PageHeader :title="kb.name" :description="kb.description || '（无描述）'">
      <template #actions>
        <button type="button" class="btn-default" @click="formOpen = true">编辑配置</button>
        <button type="button" class="btn-primary" @click="pickFile"><Upload class="size-4" aria-hidden="true" />上传文档</button>
      </template>
    </PageHeader>

    <RouterLink to="/knowledge" class="mb-4 inline-flex items-center gap-1 text-[13px] text-ink-2 hover:text-ink">
      <ArrowLeft class="size-3.5" aria-hidden="true" />返回知识库列表
    </RouterLink>

    <!-- Tabs -->
    <div class="mb-4 border-b border-line" role="tablist" aria-label="知识库详情">
      <button
        v-for="t in [
          { key: 'docs', label: `文档（${docs.length}）` },
          { key: 'chunks', label: '分块' },
          { key: 'config', label: '索引配置' },
          { key: 'history', label: '处理记录' },
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

    <!-- 文档 -->
    <section v-if="tab === 'docs'" aria-label="文档列表">
      <div
        :class="[
          'mb-4 flex flex-col items-center justify-center gap-2 rounded-[var(--radius-panel)] border border-dashed px-6 py-8 text-center',
          dragOver ? 'border-brand bg-brand-soft' : 'border-line bg-surface',
        ]"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="onDrop"
      >
        <p class="text-[13px] text-ink">拖拽文件到此处，或
          <button type="button" class="text-brand hover:underline" @click="pickFile">选择文件</button>
        </p>
        <p class="text-[12px] text-ink-3">支持 {{ ALLOWED.join(' / ') }}，单个文件不超过 {{ MAX_MB }} MB。当前阶段不解析真实文件内容，仅演示处理流程。</p>
        <input ref="fileInput" type="file" class="sr-only" :accept="ALLOWED.join(',')" aria-label="选择要上传的文档" @change="onFileChange" />
      </div>

      <div v-if="uploading" class="panel mb-4 p-4">
        <p class="text-[13px] text-ink-2">正在上传（模拟）…</p>
        <div class="mt-2 h-1.5 overflow-hidden rounded bg-page"><div class="h-full w-1/3 animate-pulse bg-brand" /></div>
      </div>

      <EmptyState v-if="!docs.length" title="还没有文档" description="上传规程、制度或 SDS 文件，开始模拟处理流程。" />

      <div v-else class="panel overflow-x-auto">
        <table class="w-full min-w-[720px] text-[13px]">
          <caption class="sr-only">知识库文档列表</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">文件名称</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">类型</th>
              <th scope="col" class="h-9 px-4 text-right font-medium">大小</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">上传时间</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">处理状态</th>
              <th scope="col" class="h-9 px-4 text-right font-medium">分块数</th>
              <th scope="col" class="h-9 px-4 text-right font-medium"><span class="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in docs" :key="d.id" class="border-t border-line">
              <td class="px-4 py-2.5">
                <span class="flex items-center gap-2 text-ink"><component :is="FILE_ICON" class="size-3.5 text-ink-3" aria-hidden="true" />{{ d.name }}</span>
              </td>
              <td class="px-4 py-2.5 uppercase text-ink-2">{{ d.type }}</td>
              <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ d.sizeKb }} KB</td>
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ d.uploadedAt }}</td>
              <td class="px-4 py-2.5">
                <div class="flex flex-col gap-1.5">
                  <StatusBadge
                    :status="d.status === 'ready' ? 'success' : d.status === 'processing' ? 'running' : d.status === 'cancelled' ? 'pending' : 'failed'"
                    :label="d.status === 'ready' ? '就绪' : d.status === 'processing' ? '处理中' : d.status === 'cancelled' ? '已取消' : '失败'"
                  />
                  <div v-if="processingId === d.id" class="w-32">
                    <div class="h-1 overflow-hidden rounded bg-page"><div class="h-full bg-brand transition-all" :style="{ width: `${progress}%` }" /></div>
                    <p class="mt-1 text-[11px] text-ink-3">
                      {{ STAGES[Math.min(STAGES.length - 1, Math.floor(progress / 20))] }} · {{ progress }}%（模拟）
                    </p>
                  </div>
                </div>
              </td>
              <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ d.chunkCount || '—' }}</td>
              <td class="px-4 py-2.5 text-right">
                <span class="inline-flex gap-1">
                  <button v-if="processingId === d.id" type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="cancelProcessing">
                    <X class="size-3.5" aria-hidden="true" />取消
                  </button>
                  <button v-else-if="d.status !== 'ready'" type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="startProcessing(d)">
                    <RefreshCw class="size-3.5" aria-hidden="true" />重试
                  </button>
                  <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="openChunks(d)">查看分块</button>
                  <button type="button" class="btn-ghost h-7 px-2 text-[12px] text-err" @click="confirmDeleteDoc = d">
                    <Trash2 class="size-3.5" aria-hidden="true" /><span class="sr-only">删除 {{ d.name }}</span>
                  </button>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 分块 -->
    <section v-else-if="tab === 'chunks'" aria-label="分块查看器">
      <div v-if="selectedDocId" class="mb-3 flex items-center gap-2 text-[13px]">
        <span class="text-ink-2">当前筛选文档：</span>
        <span class="text-ink">{{ docs.find((d) => d.id === selectedDocId)?.name }}</span>
        <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="selectedDocId = null">清除筛选</button>
      </div>
      <p class="mb-3 text-[12px] text-ink-3">分块文本为演示数据，SDS 小节隔离校验结果显示在列表上方。</p>
      <DocumentChunkViewer :chunks="docChunks" />
    </section>

    <!-- 索引配置 -->
    <section v-else-if="tab === 'config'" class="panel p-4" aria-label="索引配置">
      <h2 class="mb-3 text-[15px] font-semibold text-ink">索引与检索参数</h2>
      <dl class="grid grid-cols-1 gap-x-8 gap-y-3 text-[13px] sm:grid-cols-2">
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">分块大小</dt><dd class="tabular-nums text-ink">{{ kb.chunkSize }} token</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">分块重叠</dt><dd class="tabular-nums text-ink">{{ kb.chunkOverlap }} token</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">Embedding 模型</dt><dd class="text-ink">{{ kb.embedModel }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">向量维度</dt><dd class="tabular-nums text-ink">{{ kb.dimension }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">检索 Top-K</dt><dd class="tabular-nums text-ink">{{ kb.topK }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">相似度阈值</dt><dd class="tabular-nums text-ink">{{ kb.scoreThreshold }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">混合检索</dt><dd class="text-ink">{{ kb.hybrid ? '已启用' : '未启用' }}</dd></div>
        <div class="flex items-center justify-between gap-3 border-b border-line pb-2"><dt class="text-ink-2">重排序</dt><dd class="text-ink">{{ kb.rerank ? '已启用' : '未启用' }}</dd></div>
      </dl>
      <button type="button" class="btn-default mt-4" @click="formOpen = true">修改配置</button>
    </section>

    <!-- 处理记录 -->
    <section v-else aria-label="处理记录">
      <EmptyState v-if="!history.length" title="暂无处理记录" description="上传文档后会在这里显示模拟处理记录。" />
      <div v-else class="panel overflow-x-auto">
        <table class="w-full min-w-[560px] text-[13px]">
          <caption class="sr-only">文档处理记录</caption>
          <thead class="bg-page text-ink-2">
            <tr>
              <th scope="col" class="h-9 px-4 text-left font-medium">文档</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">时间</th>
              <th scope="col" class="h-9 px-4 text-left font-medium">结果</th>
              <th scope="col" class="h-9 px-4 text-right font-medium">分块数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.id" class="border-t border-line">
              <td class="px-4 py-2.5 text-ink">{{ h.name }}</td>
              <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ h.at }}</td>
              <td class="px-4 py-2.5"><StatusBadge :status="h.status === 'ready' ? 'success' : h.status === 'failed' ? 'failed' : 'pending'" /></td>
              <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ h.chunks || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <KnowledgeForm v-model:open="formOpen" :kb="kb" />
    <ConfirmDialog
      :open="!!confirmDeleteDoc"
      title="删除该文档？"
      :description="confirmDeleteDoc ? `「${confirmDeleteDoc.name}」及其分块元数据将被删除。` : ''"
      confirm-text="删除"
      danger
      @update:open="confirmDeleteDoc = null"
      @confirm="doDeleteDoc"
    />
  </div>

  <EmptyState v-else title="知识库不存在" description="它可能已被删除，或链接有误。">
    <template #action><RouterLink to="/knowledge" class="btn-primary">返回知识库列表</RouterLink></template>
  </EmptyState>
</template>
