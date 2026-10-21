<script setup lang="ts">
import { computed, ref } from 'vue'

interface TrendPoint {
  date: string
  value: number
}

// 轻量 SVG 折线面积图：只服务于 7/30 天对话趋势这一个场景，不引入图表库
const props = defineProps<{ data: TrendPoint[]; days: number }>()

const W = 640
const H = 256
const PAD = { l: 44, r: 12, t: 12, b: 28 }
const plotW = W - PAD.l - PAD.r
const plotH = H - PAD.t - PAD.b

const yMax = computed(() => {
  const peak = Math.max(0, ...props.data.map((p) => p.value))
  return Math.max(50, Math.ceil(peak / 50) * 50)
})

const xAt = (i: number) => PAD.l + (props.data.length > 1 ? (i * plotW) / (props.data.length - 1) : plotW / 2)
const yAt = (v: number) => PAD.t + plotH * (1 - v / yMax.value)

const linePath = computed(() =>
  props.data.map((p, i) => `${i === 0 ? 'M' : 'L'}${xAt(i).toFixed(1)},${yAt(p.value).toFixed(1)}`).join(' '),
)
const areaPath = computed(() => {
  if (!props.data.length) return ''
  const base = PAD.t + plotH
  return `${linePath.value} L${xAt(props.data.length - 1).toFixed(1)},${base} L${xAt(0).toFixed(1)},${base} Z`
})

const ticks = computed(() => [0, 1, 2, 3, 4].map((k) => (yMax.value * k) / 4))
// 标签最多显示 7 个，避免 30 天时挤在一起
const labelEvery = computed(() => Math.max(1, Math.ceil(props.data.length / 7)))

const hovered = ref<number | null>(null)
const hoverPoint = computed(() => (hovered.value === null ? null : props.data[hovered.value]))

function onMove(e: PointerEvent) {
  const svg = e.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  const svgX = ((e.clientX - rect.left) / rect.width) * W
  const ratio = (svgX - PAD.l) / plotW
  const idx = Math.round(ratio * (props.data.length - 1))
  hovered.value = props.data.length ? Math.min(props.data.length - 1, Math.max(0, idx)) : null
}
</script>

<template>
  <div class="relative">
    <svg
      :viewBox="`0 0 ${W} ${H}`"
      class="h-64 w-full"
      role="img"
      :aria-label="`近 ${days} 天对话数趋势`"
      @pointermove="onMove"
      @pointerleave="hovered = null"
    >
      <g class="text-[11px]" fill="#8a857c">
        <g v-for="t in ticks" :key="t">
          <line :x1="PAD.l" :x2="W - PAD.r" :y1="yAt(t)" :y2="yAt(t)" stroke="#d9d2c5" />
          <text :x="PAD.l - 8" :y="yAt(t) + 4" text-anchor="end">{{ Math.round(t) }}</text>
        </g>
        <text
          v-for="(p, i) in data"
          v-show="i % labelEvery === 0 || i === data.length - 1"
          :key="p.date"
          :x="xAt(i)"
          :y="H - 8"
          text-anchor="middle"
        >{{ p.date }}</text>
      </g>

      <path :d="areaPath" fill="rgba(79,70,229,0.08)" />
      <path :d="linePath" fill="none" stroke="#2f2c28" stroke-width="2" stroke-linejoin="round" />

      <template v-if="hovered !== null">
        <line :x1="xAt(hovered)" :x2="xAt(hovered)" :y1="PAD.t" :y2="PAD.t + plotH" stroke="#8a857c" stroke-dasharray="3 3" />
        <circle :cx="xAt(hovered)" :cy="yAt(data[hovered].value)" r="4" fill="#2f2c28" stroke="#f5f0e8" stroke-width="2" />
      </template>
    </svg>

    <div
      v-if="hoverPoint"
      class="pointer-events-none absolute top-2 -translate-x-1/2 rounded-[var(--radius-control)] border border-line bg-surface px-2 py-1 text-[12px] shadow-lg"
      :style="{ left: `${(xAt(hovered!) / W) * 100}%` }"
    >
      <span class="text-ink-2">{{ hoverPoint.date }}</span>
      <span class="ml-2 font-medium tabular-nums text-ink">{{ hoverPoint.value }} 次对话</span>
    </div>

    <!-- 屏幕阅读器与键盘用户的等价数据 -->
    <table class="sr-only">
      <caption>近 {{ days }} 天对话数</caption>
      <thead>
        <tr><th scope="col">日期</th><th scope="col">对话数</th></tr>
      </thead>
      <tbody>
        <tr v-for="p in data" :key="p.date"><td>{{ p.date }}</td><td>{{ p.value }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
