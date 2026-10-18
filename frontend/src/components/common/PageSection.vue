<script setup lang="ts">
// 版块容器：纵向留白统一走 Ma 刻度（16 / 32 / 64 / 96），
// 标题用宋体、正文用黑体，形成纸与墨的对比。
withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    /** 纵向间距：1=32px  2=64px  3=96px */
    ma?: 1 | 2 | 3
  }>(),
  { ma: 2 },
)

const MA_CLASS: Record<number, string> = {
  1: 'mt-[var(--space-ma-2)]',
  2: 'mt-[var(--space-ma-3)]',
  3: 'mt-[var(--space-ma-4)]',
}
</script>

<template>
  <section :class="MA_CLASS[ma]">
    <header v-if="title" class="mb-4">
      <h2 class="text-[16px] font-medium tracking-wide text-ink">{{ title }}</h2>
      <p v-if="subtitle" class="mt-1 text-[12px] text-ink-3">{{ subtitle }}</p>
    </header>
    <slot />
  </section>
</template>
