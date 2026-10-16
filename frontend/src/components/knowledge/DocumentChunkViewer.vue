<script setup lang="ts">
import { computed, ref } from 'vue'
import { Copy, Check } from 'lucide-vue-next'
import type { Chunk } from '@/types'
import { copyText } from '@/utils/format'
import { checkSdsSectionIsolation } from '@/utils/sdsCheck'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{ chunks: Chunk[] }>()
const ui = useUiStore()
const issues = computed(() => checkSdsSectionIsolation(props.chunks))
const sdsCount = computed(() => props.chunks.filter((c) => c.meta.kind === 'sds').length)

const keyword = ref('')
const expanded = ref<Set<string>>(new Set())
const copiedId = ref<string | null>(null)

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return props.chunks
  return props.chunks.filter((c) => c.text.toLowerCase().includes(q) || c.section.toLowerCase().includes(q))
})

function toggle(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

async function copy(chunk: Chunk) {
  const ok = await copyText(chunk.text)
  if (ok) {
    copiedId.value = chunk.id
    window.setTimeout(() => (copiedId.value = null), 1500)
  } else {
    ui.toast('复制失败，请手动选择文本', 'error')
  }
}
</script>

<template>
  <div class="space-y-3">
    <!-- 切分校验结果：SDS 串段属于红线问题，必须醒目展示而不是藏在数据里 -->
    <div
      v-if="issues.length"
      role="alert"
      class="rounded-[var(--radius-panel)] border border-err/30 bg-err-soft p-3 text-[13px] text-err"
    >
      <p class="font-medium">SDS 小节隔离校验发现 {{ issues.length }} 处问题，请人工核对后再用于回答</p>
      <ul class="mt-1 list-disc space-y-0.5 pl-5 text-[12px]">
        <li v-for="i in issues" :key="i.chunkId">{{ i.chunkId }}：{{ i.message }}</li>
      </ul>
    </div>
    <p v-else-if="sdsCount" class="text-[12px] text-ok">
      SDS 小节隔离校验通过：{{ sdsCount }} 个 SDS 分块，应急处置未混入储存措辞（演示校验，非切分正确性证明）。
    </p>

    <div class="flex flex-wrap items-center gap-2">
      <label class="sr-only" for="chunk-search">搜索分块</label>
      <input id="chunk-search" v-model="keyword" type="search" class="input sm:w-72" placeholder="搜索分块内容或小节…" />
      <span class="text-[12px] text-ink-3">共 {{ filtered.length }} / {{ chunks.length }} 个分块</span>
    </div>

    <p v-if="!filtered.length" class="panel px-4 py-8 text-center text-[13px] text-ink-2">
      {{ chunks.length ? '没有匹配的分块' : '该文档暂无分块，先完成一次模拟处理流程。' }}
    </p>

    <ul v-else class="space-y-2">
      <li v-for="c in filtered" :key="c.id" class="panel p-3.5">
        <div class="flex flex-wrap items-center gap-2 text-[12px]">
          <span class="font-mono text-ink">{{ c.id }}</span>
          <span class="text-ink-3">·</span>
          <span class="text-ink-2">{{ c.docName }}</span>
          <span class="rounded border border-line bg-page px-1.5 py-0.5 text-ink-2">{{ c.section }}</span>
          <span class="text-ink-3">{{ c.tokens }} token</span>
          <span class="text-ink-3">{{ c.position }}</span>
          <button
            type="button"
            class="btn-ghost ml-auto h-7 px-2 text-[12px]"
            :aria-label="copiedId === c.id ? '已复制分块' : '复制分块文本'"
            @click="copy(c)"
          >
            <Check v-if="copiedId === c.id" class="size-3.5" aria-hidden="true" />
            <Copy v-else class="size-3.5" aria-hidden="true" />
            {{ copiedId === c.id ? '已复制' : '复制片段' }}
          </button>
        </div>

        <p
          :class="['mt-2 text-[13px] leading-relaxed text-ink', expanded.has(c.id) ? '' : 'line-clamp-3']"
        >{{ c.text }}</p>

        <div class="mt-2 flex items-center gap-3">
          <button type="button" class="text-[12px] text-brand hover:underline" :aria-expanded="expanded.has(c.id)" @click="toggle(c.id)">
            {{ expanded.has(c.id) ? '收起' : '展开原文' }}
          </button>
        </div>

        <dl class="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-2 text-[12px]">
          <div v-for="(v, k) in c.meta" :key="k" class="flex gap-1">
            <dt class="text-ink-3">{{ k }}:</dt>
            <dd class="font-mono text-ink-2">{{ v }}</dd>
          </div>
        </dl>
      </li>
    </ul>
  </div>
</template>
