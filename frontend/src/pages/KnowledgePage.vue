<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Plus, Trash2, Pencil, Database } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import KnowledgeForm from '@/components/forms/KnowledgeForm.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import type { KnowledgeBase } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const keyword = ref('')
const statusFilter = ref<'all' | KnowledgeBase['indexStatus']>('all')
const formOpen = ref(false)
const editing = ref<KnowledgeBase | null>(null)
const confirmDelete = ref<KnowledgeBase | null>(null)

const STATUS_MAP: Record<KnowledgeBase['indexStatus'], { tone: 'success' | 'running' | 'failed'; label: string }> = {
  ready: { tone: 'success', label: '索引就绪' },
  indexing: { tone: 'running', label: '索引中' },
  failed: { tone: 'failed', label: '索引失败' },
}

const rows = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return workspace.state.knowledgeBases.filter((k) => {
    if (statusFilter.value !== 'all' && k.indexStatus !== statusFilter.value) return false
    if (!q) return true
    return k.name.toLowerCase().includes(q) || k.description.toLowerCase().includes(q)
  })
})

watch(() => route.query.create, (v) => {
  if (v) {
    editing.value = null
    formOpen.value = true
    router.replace({ path: '/knowledge' })
  }
}, { immediate: true })

function doDelete() {
  if (!confirmDelete.value) return
  const name = confirmDelete.value.name
  workspace.removeKb(confirmDelete.value.id)
  confirmDelete.value = null
  ui.toast(`已删除知识库「${name}」及其文档元数据`)
}
</script>

<template>
  <PageHeader title="知识库" description="管理 RAG 语料、切分参数与索引状态。">
    <template #actions>
      <button type="button" class="btn-primary" @click="editing = null; formOpen = true">
        <Plus class="size-4" aria-hidden="true" />新建知识库
      </button>
    </template>
    <template #filters>
      <SearchInput v-model="keyword" label="搜索知识库" placeholder="搜索名称或描述" />
      <label class="sr-only" for="kb-status-filter">索引状态筛选</label>
      <select id="kb-status-filter" v-model="statusFilter" class="input w-auto">
        <option value="all">全部索引状态</option>
        <option value="ready">索引就绪</option>
        <option value="indexing">索引中</option>
        <option value="failed">索引失败</option>
      </select>
    </template>
  </PageHeader>

  <EmptyState v-if="!workspace.state.knowledgeBases.length" title="还没有知识库" description="创建第一个知识库，上传规程、制度与 SDS 语料。">
    <template #action><button type="button" class="btn-primary" @click="editing = null; formOpen = true">创建知识库</button></template>
  </EmptyState>

  <EmptyState v-else-if="!rows.length" title="没有符合条件的知识库" description="调整搜索词或筛选条件试试。" />

  <ul v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
    <li v-for="k in rows" :key="k.id" class="panel flex flex-col p-4">
      <div class="flex items-start gap-3">
        <span class="grid size-9 shrink-0 place-items-center rounded-[var(--radius-control)] bg-brand-soft text-brand">
          <Database class="size-4" aria-hidden="true" />
        </span>
        <div class="min-w-0 flex-1">
          <RouterLink :to="`/knowledge/${k.id}`" class="block truncate text-[14px] font-semibold text-ink hover:text-brand">{{ k.name }}</RouterLink>
          <p class="mt-0.5 line-clamp-2 text-[12px] text-ink-2">{{ k.description || '（无描述）' }}</p>
        </div>
        <StatusBadge :status="STATUS_MAP[k.indexStatus].tone" :label="STATUS_MAP[k.indexStatus].label" />
      </div>

      <dl class="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-[12px]">
        <div><dt class="text-ink-3">文档数量</dt><dd class="tabular-nums text-ink">{{ workspace.state.documents.filter((d) => d.kbId === k.id).length }}</dd></div>
        <div><dt class="text-ink-3">分块数量</dt><dd class="tabular-nums text-ink">{{ k.chunkCount }}</dd></div>
        <div><dt class="text-ink-3">向量维度</dt><dd class="tabular-nums text-ink">{{ k.dimension }}</dd></div>
        <div><dt class="text-ink-3">Top-K / 阈值</dt><dd class="tabular-nums text-ink">{{ k.topK }} / {{ k.scoreThreshold }}</dd></div>
        <div class="col-span-2"><dt class="text-ink-3">Embedding 模型</dt><dd class="truncate text-ink">{{ k.embedModel }}</dd></div>
      </dl>

      <p class="mt-3 text-[12px] text-ink-3">最近更新 {{ k.updatedAt }}</p>

      <div class="mt-auto flex items-center gap-1 border-t border-line pt-3">
        <RouterLink :to="`/knowledge/${k.id}`" class="text-[13px] text-brand hover:underline">查看详情</RouterLink>
        <span class="ml-auto flex gap-1">
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="editing = k; formOpen = true"><Pencil class="size-3.5" aria-hidden="true" />编辑</button>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px] text-err" @click="confirmDelete = k"><Trash2 class="size-3.5" aria-hidden="true" />删除</button>
        </span>
      </div>
    </li>
  </ul>

  <KnowledgeForm v-model:open="formOpen" :kb="editing" />
  <ConfirmDialog
    :open="!!confirmDelete"
    title="删除该知识库？"
    :description="confirmDelete ? `「${confirmDelete.name}」及其文档元数据将被删除，绑定该库的 Agent 会失去语料来源。` : ''"
    confirm-text="删除"
    danger
    @update:open="confirmDelete = null"
    @confirm="doDelete"
  />
</template>
