<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  confirmText?: string
  danger?: boolean
}>(), { confirmText: '确认', danger: false })

const emit = defineEmits<{ (e: 'update:open', v: boolean): void; (e: 'confirm'): void }>()
const cancelBtn = ref<HTMLButtonElement | null>(null)

// 打开时焦点落在“取消”上，避免误触危险操作
watch(() => props.open, async (v) => {
  if (v) {
    await nextTick()
    cancelBtn.value?.focus()
  }
})

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('update:open', false)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown="onKey">
      <div class="absolute inset-0 bg-ink/30" aria-hidden="true" @click="emit('update:open', false)" />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        :aria-describedby="description ? 'confirm-desc' : undefined"
        class="relative w-full max-w-md rounded-[var(--radius-modal)] bg-surface p-5 shadow-lg"
      >
        <h2 id="confirm-title" class="text-[16px] font-semibold text-ink">{{ title }}</h2>
        <p v-if="description" id="confirm-desc" class="mt-2 text-[13px] text-ink-2">{{ description }}</p>
        <div class="mt-5 flex justify-end gap-2">
          <button ref="cancelBtn" type="button" class="btn-default" @click="emit('update:open', false)">取消</button>
          <button
            type="button"
            :class="danger ? 'btn-danger border-err bg-err text-white hover:bg-err/90 hover:text-white' : 'btn-primary'"
            @click="emit('confirm')"
          >{{ confirmText }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
