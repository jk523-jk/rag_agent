<script setup lang="ts">
import { ref } from 'vue'
import { Copy, Check } from 'lucide-vue-next'

const props = defineProps<{ code: string; lang?: string }>()
const copied = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1500)
  } catch {
    copied.value = false
  }
}
</script>

<template>
  <div class="overflow-hidden rounded-[var(--radius-panel)] border border-line bg-page">
    <div class="flex h-8 items-center justify-between border-b border-line px-3 text-[12px] text-ink-2">
      <span>{{ lang ?? 'text' }}</span>
      <button type="button" class="inline-flex items-center gap-1 hover:text-ink" :aria-label="copied ? '已复制代码' : '复制代码'" @click="copy">
        <Check v-if="copied" class="size-3.5" aria-hidden="true" />
        <Copy v-else class="size-3.5" aria-hidden="true" />
        {{ copied ? '已复制' : '复制' }}
      </button>
    </div>
    <pre class="overflow-x-auto whitespace-pre p-3 font-mono text-[12px] leading-relaxed text-ink"><code>{{ code }}</code></pre>
  </div>
</template>
