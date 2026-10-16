<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import CodeBlock from '@/components/common/CodeBlock.vue'

const props = defineProps<{ text: string; plain?: boolean }>()

// 把回答切成“普通段落 / 代码块”两类：代码块走 CodeBlock 以提供复制按钮，其余走 Markdown 渲染
type Part = { kind: 'md'; html: string } | { kind: 'code'; lang: string; code: string }

const parts = computed<Part[]>(() => {
  if (props.plain) return []
  const out: Part[] = []
  const re = /```(\w*)\n([\s\S]*?)```/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(props.text)) !== null) {
    if (m.index > last) out.push({ kind: 'md', html: renderMd(props.text.slice(last, m.index)) })
    out.push({ kind: 'code', lang: m[1] || 'text', code: m[2].replace(/\n$/, '') })
    last = m.index + m[0].length
  }
  if (last < props.text.length) out.push({ kind: 'md', html: renderMd(props.text.slice(last)) })
  return out
})

function renderMd(src: string): string {
  const html = marked.parse(src, { async: false, breaks: true }) as string
  return DOMPurify.sanitize(html)
}
</script>

<template>
  <!-- 流式输出中使用纯文本，结束后再渲染 Markdown，避免半截语法闪烁 -->
  <div v-if="plain" class="whitespace-pre-wrap break-words text-[14px] leading-[1.7] text-ink">{{ text }}</div>
  <div v-else class="space-y-3 break-words text-[14px] leading-[1.7] text-ink">
    <template v-for="(p, i) in parts" :key="i">
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div v-if="p.kind === 'md'" class="chat-md" v-html="p.html" />
      <CodeBlock v-else :code="p.code" :lang="p.lang" />
    </template>
  </div>
</template>

<style scoped>
.chat-md :deep(p) {
  margin: 0.25rem 0;
}
.chat-md :deep(ol),
.chat-md :deep(ul) {
  padding-left: 1.25rem;
  margin: 0.25rem 0;
  list-style: revert;
}
.chat-md :deep(code) {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--color-page);
  border: 1px solid var(--color-line);
  border-radius: 4px;
  padding: 0 4px;
}
.chat-md :deep(strong) {
  font-weight: 600;
}
</style>
