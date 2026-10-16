<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, CircleX, Loader, Clock, AlertTriangle, CircleSlash, Pause } from 'lucide-vue-next'

// 状态不只靠颜色区分：每种状态同时有图标与文字（设计规范 §九）
type Tone = 'success' | 'running' | 'failed' | 'pending' | 'warning' | 'idle' | 'disabled'
const props = defineProps<{ status: Tone; label?: string }>()

const MAP: Record<Tone, { text: string; cls: string; icon: unknown }> = {
  success: { text: '成功', cls: 'bg-ok-soft text-ok border-ok/20', icon: CircleCheck },
  running: { text: '运行中', cls: 'bg-info-soft text-info border-info/20', icon: Loader },
  failed: { text: '失败', cls: 'bg-err-soft text-err border-err/20', icon: CircleX },
  pending: { text: '等待中', cls: 'bg-page text-ink-2 border-line', icon: Clock },
  warning: { text: '需关注', cls: 'bg-warn-soft text-warn border-warn/20', icon: AlertTriangle },
  idle: { text: '空闲', cls: 'bg-page text-ink-2 border-line', icon: Pause },
  disabled: { text: '已停用', cls: 'bg-page text-ink-3 border-line', icon: CircleSlash },
}
const meta = computed(() => MAP[props.status])
</script>

<template>
  <span :class="['inline-flex h-5 items-center gap-1 rounded border px-1.5 text-[12px] font-medium whitespace-nowrap', meta.cls]">
    <component :is="meta.icon" class="size-3" :class="{ 'animate-spin': status === 'running' }" aria-hidden="true" />
    {{ label ?? meta.text }}
  </span>
</template>
