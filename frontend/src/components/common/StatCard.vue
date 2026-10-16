<script setup lang="ts">
defineProps<{ label: string; value: string; delta?: string; deltaTone?: 'up' | 'down' | 'flat'; hint?: string }>()
</script>

<template>
  <div class="panel p-4 flex flex-col gap-2">
    <div class="flex items-center justify-between gap-2">
      <span class="text-[13px] text-ink-2">{{ label }}</span>
      <span class="mock-tag">模拟</span>
    </div>
    <div class="text-[28px] font-semibold leading-none text-ink tabular-nums">{{ value }}</div>
    <div class="flex items-center gap-2 text-[12px]">
      <span
        v-if="delta"
        :class="deltaTone === 'down' ? 'text-err' : deltaTone === 'up' ? 'text-ok' : 'text-ink-2'"
      >{{ delta }}</span>
      <span v-if="hint" class="text-ink-3">{{ hint }}</span>
    </div>
  </div>
</template>
