<script setup lang="ts">
import { X } from 'lucide-vue-next'

withDefaults(defineProps<{ open: boolean; title: string; width?: 'md' | 'lg' | 'xl' }>(), { width: 'md' })
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50" @keydown.esc="emit('update:open', false)">
      <div class="absolute inset-0 bg-ink/30" aria-hidden="true" @click="emit('update:open', false)" />
      <aside
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        :class="[
          'absolute inset-y-0 right-0 flex w-full flex-col bg-surface shadow-lg',
          width === 'xl' ? 'md:w-[720px]' : width === 'lg' ? 'md:w-[560px]' : 'md:w-[440px]',
        ]"
      >
        <header class="flex h-14 items-center gap-2 border-b border-line px-5">
          <h2 class="truncate text-[15px] font-semibold text-ink">{{ title }}</h2>
          <button type="button" class="btn-ghost ml-auto h-8 w-8 p-0" aria-label="关闭" @click="emit('update:open', false)">
            <X class="size-4" />
          </button>
        </header>
        <div class="flex-1 overflow-y-auto p-5">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="flex justify-end gap-2 border-t border-line px-5 py-3">
          <slot name="footer" />
        </footer>
      </aside>
    </div>
  </Teleport>
</template>
