<script setup lang="ts">
// 墨迹分隔线：用一条起伏的手绘曲线替代 1px 实线，
// 末端收锋、中段略重，模拟毛笔落纸的浓淡变化。
withDefaults(defineProps<{ tone?: 'light' | 'medium' | 'strong' }>(), { tone: 'medium' })
</script>

<template>
  <div class="ink-divider" aria-hidden="true">
    <svg viewBox="0 0 600 14" preserveAspectRatio="none" class="h-3 w-full">
      <path
        d="M2 8.2 C 74 3.4, 148 11.1, 224 7.4 S 372 2.6, 446 6.8 S 552 10.4, 598 5.2"
        fill="none"
        stroke="#1a1a1a"
        :stroke-opacity="tone === 'light' ? 0.14 : tone === 'medium' ? 0.28 : 0.46"
        :stroke-width="tone === 'strong' ? 1.9 : 1.35"
        stroke-linecap="round"
      />
      <path
        d="M18 10.6 C 120 7.2, 214 12.4, 320 9.1 S 486 6.4, 588 9.6"
        fill="none"
        stroke="#1a1a1a"
        :stroke-opacity="tone === 'light' ? 0.05 : 0.1"
        stroke-width="3.2"
        stroke-linecap="round"
      />
    </svg>
  </div>
</template>
