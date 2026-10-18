<script setup lang="ts">
// 滚动入场：像笔锋落下，轻微上移 + 淡入，400ms ease-out。
// 只做一次（进入视口后断开观察），避免来回滚动时反复闪动。
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ delay?: number; as?: string }>(), {
  delay: 0,
  as: 'div',
})

const el = ref<HTMLElement | null>(null)
const shown = ref(false)
let observer: IntersectionObserver | null = null

onMounted(() => {
  if (typeof IntersectionObserver === 'undefined') {
    shown.value = true
    return
  }
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          window.setTimeout(() => { shown.value = true }, props.delay)
          observer?.disconnect()
          observer = null
        }
      }
    },
    { threshold: 0.08, rootMargin: '0px 0px -40px 0px' },
  )
  if (el.value) observer.observe(el.value)
})

onBeforeUnmount(() => { observer?.disconnect() })
</script>

<template>
  <component
    :is="as"
    ref="el"
    class="transition-all duration-[400ms] ease-out motion-reduce:transition-none"
    :class="shown ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'"
  >
    <slot />
  </component>
</template>
