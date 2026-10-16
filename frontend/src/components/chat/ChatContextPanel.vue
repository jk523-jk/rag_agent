<script setup lang="ts">
import { computed } from 'vue'
import { FileText, Info } from 'lucide-vue-next'
import type { ChatSource } from '@/types'

const props = defineProps<{ sources: ChatSource[]; question: string; strategy: string }>()

// 分数分属不同算法，不得当作统一概率横向比较；这里只做同一次检索内的相对排序展示
const ranked = computed(() => [...props.sources].sort((a, b) => b.rerank - a.rerank))
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="border-b border-line px-4 py-3">
      <h2 class="text-[14px] font-semibold text-ink">检索上下文</h2>
      <p class="mt-0.5 text-[12px] text-ink-3">模拟检索结果，非真实向量库返回</p>
    </header>

    <div class="flex-1 space-y-4 overflow-y-auto p-4">
      <section>
        <h3 class="label">本次查询</h3>
        <p class="rounded-[var(--radius-control)] border border-line bg-page px-3 py-2 text-[13px] text-ink break-words">
          {{ question || '（尚未提问）' }}
        </p>
      </section>

      <section>
        <h3 class="label">检索策略</h3>
        <p class="text-[13px] text-ink">{{ strategy }}</p>
      </section>

      <section>
        <h3 class="label">召回文档（{{ ranked.length }}）</h3>
        <p v-if="!ranked.length" class="text-[12px] text-ink-3">
          本次回答未使用检索（例如控制类指令被拒绝，或问题未命中规程）。
        </p>
        <ul class="space-y-2">
          <li v-for="(s, i) in ranked" :key="i" class="rounded-[var(--radius-control)] border border-line p-3">
            <div class="flex items-center gap-1.5">
              <FileText class="size-3.5 shrink-0 text-ink-3" aria-hidden="true" />
              <span class="truncate text-[13px] font-medium text-ink">{{ s.docName }}</span>
              <span class="ml-auto shrink-0 text-[12px] text-ink-3">{{ s.chapter }}</span>
            </div>
            <p class="mt-1.5 line-clamp-3 text-[12px] leading-relaxed text-ink-2">{{ s.text }}</p>
            <dl class="mt-2 grid grid-cols-2 gap-2 text-[12px]">
              <div class="flex items-center justify-between gap-2">
                <dt class="text-ink-3">相似度</dt>
                <dd class="tabular-nums text-ink">{{ s.similarity.toFixed(2) }}</dd>
              </div>
              <div class="flex items-center justify-between gap-2">
                <dt class="text-ink-3">重排序</dt>
                <dd class="tabular-nums text-ink">{{ s.rerank.toFixed(2) }}</dd>
              </div>
            </dl>
          </li>
        </ul>
      </section>

      <section v-if="ranked.length">
        <h3 class="label">最终引用来源</h3>
        <ul class="space-y-1">
          <li v-for="(s, i) in ranked" :key="i" class="text-[12px] text-ink-2">
            [{{ i + 1 }}] 《{{ s.docName }}》{{ s.chapter }}
          </li>
        </ul>
      </section>

      <p class="flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
        <Info class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        分数来自不同相似度算法，仅可在本次结果内做相对排序比较，不能跨算法直接比较。
      </p>
    </div>
  </div>
</template>
