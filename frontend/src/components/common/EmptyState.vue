<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <div class="panel flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
    <p class="text-[14px] font-medium text-ink">{{ title }}</p>
    <p v-if="description" class="max-w-md text-[13px] text-ink-2">{{ description }}</p>
    <div v-if="$slots.action" class="mt-2 flex gap-2"><slot name="action" /></div>
  </div>
</template>
