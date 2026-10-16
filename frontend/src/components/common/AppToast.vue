<script setup lang="ts">
import { CircleCheck, CircleX, Info, X } from 'lucide-vue-next'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>

<template>
  <div class="fixed bottom-4 right-4 z-50 flex w-[min(360px,calc(100vw-32px))] flex-col gap-2" aria-live="polite">
    <div
      v-for="t in ui.toasts"
      :key="t.id"
      role="status"
      :class="[
        'panel flex items-start gap-2.5 px-3.5 py-3 shadow-lg text-[13px]',
        t.tone === 'error' ? 'border-err/30' : t.tone === 'success' ? 'border-ok/30' : 'border-info/30',
      ]"
    >
      <CircleCheck v-if="t.tone === 'success'" class="mt-0.5 size-4 shrink-0 text-ok" aria-hidden="true" />
      <CircleX v-else-if="t.tone === 'error'" class="mt-0.5 size-4 shrink-0 text-err" aria-hidden="true" />
      <Info v-else class="mt-0.5 size-4 shrink-0 text-info" aria-hidden="true" />
      <p class="min-w-0 flex-1 text-ink whitespace-pre-line break-words">{{ t.text }}</p>
      <button type="button" class="btn-ghost h-6 w-6 p-0 shrink-0" aria-label="关闭提示" @click="ui.dismiss(t.id)">
        <X class="size-3.5" />
      </button>
    </div>
  </div>
</template>
