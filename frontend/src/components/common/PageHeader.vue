<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <header class="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
    <div class="min-w-0">
      <h1 class="font-[var(--font-serif)] text-[26px] font-medium leading-tight tracking-wide text-ink">{{ title }}</h1>
      <p v-if="description" class="mt-1.5 text-[12.5px] text-ink-2">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
      <slot name="actions" />
    </div>
  </header>
  <div v-if="$slots.filters" class="mb-4 flex flex-wrap items-center gap-2">
    <slot name="filters" />
  </div>
</template>
