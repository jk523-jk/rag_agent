<script setup lang="ts">
// 引言块：可选竖排（日式短册/挂轴），右侧留一枚朱印位置但不使用彩色，
// 保持纯灰阶——用边框与墨色浓淡制造层次。
withDefaults(
  defineProps<{
    text: string
    source?: string
    vertical?: boolean
  }>(),
  { vertical: false, source: '' },
)
</script>

<template>
  <figure class="flex gap-4" :class="vertical ? 'items-start' : 'flex-col'">
    <blockquote
      class="border-l border-line pl-4 font-[var(--font-serif)] text-ink"
      :class="vertical
        ? 'border-l-0 border-r border-line pl-0 pr-4 text-[15px] leading-[2] [writing-mode:vertical-rl] [text-orientation:upright] max-h-56'
        : 'text-[15px] leading-[1.9]'"
    >
      {{ text }}
    </blockquote>
    <figcaption v-if="source" class="text-[12px] text-ink-3" :class="vertical ? 'mt-1' : ''">
      — {{ source }}
    </figcaption>
  </figure>
</template>
