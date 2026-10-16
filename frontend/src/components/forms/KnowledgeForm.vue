<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { KnowledgeBase } from '@/types'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { newId } from '@/utils/format'
import { validateKb, type FieldErrors, type KbDraft } from '@/utils/validators'
import AppDrawer from '@/components/common/AppDrawer.vue'

const props = defineProps<{ open: boolean; kb: KnowledgeBase | null }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void; (e: 'saved', kb: KnowledgeBase): void }>()

const workspace = useWorkspaceStore()
const ui = useUiStore()

const form = reactive<KbDraft & { embedModel: KnowledgeBase['embedModel']; hybrid: boolean; rerank: boolean }>({
  name: '', description: '', chunkSize: 800, chunkOverlap: 100, topK: 4, scoreThreshold: 0.3,
  embedModel: 'text-embedding-v3', hybrid: true, rerank: true,
})
const errors = ref<FieldErrors<KbDraft>>({})

watch(() => props.open, (v) => {
  if (!v) return
  errors.value = {}
  const k = props.kb
  Object.assign(form, k
    ? { name: k.name, description: k.description, chunkSize: k.chunkSize, chunkOverlap: k.chunkOverlap,
        topK: k.topK, scoreThreshold: k.scoreThreshold, embedModel: k.embedModel, hybrid: k.hybrid, rerank: k.rerank }
    : { name: '', description: '', chunkSize: 800, chunkOverlap: 100, topK: 4, scoreThreshold: 0.3,
        embedModel: 'text-embedding-v3', hybrid: true, rerank: true })
})

const title = computed(() => (props.kb ? '编辑知识库' : '新建知识库'))

function submit() {
  errors.value = validateKb(form, workspace.state.knowledgeBases.map((k) => k.name), props.kb?.name)
  if (Object.keys(errors.value).length) {
    ui.toast('请修正表单中标红的字段', 'error')
    return
  }
  const kb: KnowledgeBase = {
    id: props.kb?.id ?? newId('kb'),
    name: form.name.trim(),
    description: form.description.trim(),
    docCount: props.kb?.docCount ?? 0,
    chunkCount: props.kb?.chunkCount ?? 0,
    embedModel: form.embedModel,
    dimension: form.embedModel === 'bge-m3' ? 1024 : 1024,
    chunkSize: Number(form.chunkSize),
    chunkOverlap: Number(form.chunkOverlap),
    topK: Number(form.topK),
    scoreThreshold: Number(form.scoreThreshold),
    hybrid: form.hybrid,
    rerank: form.rerank,
    indexStatus: props.kb?.indexStatus ?? 'ready',
    updatedAt: props.kb?.updatedAt ?? '2026-10-15 10:00',
  }
  workspace.upsertKb(kb)
  emit('saved', kb)
  emit('update:open', false)
  ui.toast(props.kb ? '知识库已更新' : '知识库已创建')
}
</script>

<template>
  <AppDrawer :open="open" :title="title" width="lg" @update:open="emit('update:open', $event)">
    <form id="kb-form" class="space-y-4" novalidate @submit.prevent="submit">
      <div>
        <label class="label" for="kb-name">知识库名称 <span class="text-err">*</span></label>
        <input id="kb-name" v-model="form.name" class="input" maxlength="40" :aria-invalid="!!errors.name" aria-describedby="kb-name-err" />
        <p v-if="errors.name" id="kb-name-err" class="mt-1 text-[12px] text-err">{{ errors.name }}</p>
      </div>

      <div>
        <label class="label" for="kb-desc">描述</label>
        <textarea id="kb-desc" v-model="form.description" class="textarea" rows="2" maxlength="200" />
      </div>

      <fieldset class="rounded-[var(--radius-panel)] border border-line p-4">
        <legend class="px-1 text-[12px] text-ink-2">切分与向量化</legend>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label class="label" for="kb-chunk">分块大小（token）</label>
            <input id="kb-chunk" v-model.number="form.chunkSize" type="number" min="100" max="2000" step="50" class="input tabular-nums" :aria-invalid="!!errors.chunkSize" />
            <p v-if="errors.chunkSize" class="mt-1 text-[12px] text-err">{{ errors.chunkSize }}</p>
          </div>
          <div>
            <label class="label" for="kb-overlap">分块重叠（token）</label>
            <input id="kb-overlap" v-model.number="form.chunkOverlap" type="number" min="0" max="1999" step="10" class="input tabular-nums" :aria-invalid="!!errors.chunkOverlap" />
            <p v-if="errors.chunkOverlap" class="mt-1 text-[12px] text-err">{{ errors.chunkOverlap }}</p>
          </div>
          <div>
            <label class="label" for="kb-embed">Embedding 模型</label>
            <select id="kb-embed" v-model="form.embedModel" class="input">
              <option value="text-embedding-v3">text-embedding-v3（1024 维）</option>
              <option value="bge-m3">bge-m3（1024 维）</option>
            </select>
          </div>
        </div>
        <p class="mt-3 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
          SDS 语料必须按小节切分（理化特性 / 危害 / 储存 / 应急处置），不能使用固定长度硬切。
        </p>
      </fieldset>

      <fieldset class="rounded-[var(--radius-panel)] border border-line p-4">
        <legend class="px-1 text-[12px] text-ink-2">检索配置</legend>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label class="label" for="kb-topk">检索 Top-K</label>
            <input id="kb-topk" v-model.number="form.topK" type="number" min="1" max="20" class="input tabular-nums" :aria-invalid="!!errors.topK" />
            <p v-if="errors.topK" class="mt-1 text-[12px] text-err">{{ errors.topK }}</p>
          </div>
          <div>
            <label class="label" for="kb-threshold">相似度阈值（0–1）</label>
            <input id="kb-threshold" v-model.number="form.scoreThreshold" type="number" min="0" max="1" step="0.05" class="input tabular-nums" :aria-invalid="!!errors.scoreThreshold" />
            <p v-if="errors.scoreThreshold" class="mt-1 text-[12px] text-err">{{ errors.scoreThreshold }}</p>
            <p class="mt-1 text-[12px] text-ink-3">低于阈值一律返回空，严禁编造条款。</p>
          </div>
        </div>
        <div class="mt-3 space-y-2">
          <label class="flex items-center gap-2 text-[13px] text-ink"><input v-model="form.hybrid" type="checkbox" class="accent-[#4F46E5]" />启用混合检索（BM25 + 向量）</label>
          <label class="flex items-center gap-2 text-[13px] text-ink"><input v-model="form.rerank" type="checkbox" class="accent-[#4F46E5]" />启用重排序</label>
        </div>
      </fieldset>
    </form>

    <template #footer>
      <button type="button" class="btn-default" @click="emit('update:open', false)">取消</button>
      <button type="submit" form="kb-form" class="btn-primary">保存</button>
    </template>
  </AppDrawer>
</template>
