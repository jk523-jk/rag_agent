<script setup lang="ts">
defineProps<{ label?: string; rows?: number }>()
</script>

<template>
  <div class="panel p-4 space-y-3" role="status" :aria-label="label ?? '加载中'">
    <p class="text-[12px] text-ink-2">{{ label ?? '加载中…' }}</p>
    <div v-for="i in rows ?? 3" :key="i" class="h-4 rounded bg-page animate-pulse" />
  </div>
</template>
