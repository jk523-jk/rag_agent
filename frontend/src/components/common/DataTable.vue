<script setup lang="ts" generic="T extends { id: string }">
export interface Column {
  key: string
  label: string
  align?: 'left' | 'right'
  width?: string
  sortable?: boolean
}

defineProps<{ columns: Column[]; rows: T[]; caption: string; sortKey?: string; sortAsc?: boolean }>()
defineEmits<{ (e: 'sort', key: string): void; (e: 'row', row: T): void }>()
</script>

<template>
  <!-- 长表格在自身区域横向滚动，不撑破页面 -->
  <div class="panel overflow-x-auto">
    <table class="w-full min-w-[640px] border-collapse text-[13px]">
      <caption class="sr-only">{{ caption }}</caption>
      <thead class="bg-page text-ink-2">
        <tr>
          <th
            v-for="c in columns"
            :key="c.key"
            scope="col"
            :style="{ width: c.width }"
            :class="['h-9 whitespace-nowrap border-b border-line px-3 font-medium', c.align === 'right' ? 'text-right' : 'text-left']"
            :aria-sort="sortKey === c.key ? (sortAsc ? 'ascending' : 'descending') : undefined"
          >
            <button
              v-if="c.sortable"
              type="button"
              class="inline-flex items-center gap-1 hover:text-ink"
              @click="$emit('sort', c.key)"
            >
              {{ c.label }}
              <span aria-hidden="true" class="text-[11px]">{{ sortKey === c.key ? (sortAsc ? '↑' : '↓') : '↕' }}</span>
            </button>
            <template v-else>{{ c.label }}</template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="r in rows"
          :key="r.id"
          class="cursor-pointer border-b border-line last:border-0 hover:bg-page/60 focus-visible:bg-page/60"
          tabindex="0"
          @click="$emit('row', r)"
          @keydown.enter="$emit('row', r)"
        >
          <td
            v-for="c in columns"
            :key="c.key"
            :class="['px-3 py-2.5 align-middle text-ink', c.align === 'right' ? 'text-right tabular-nums' : 'text-left']"
          >
            <slot :name="c.key" :row="r">{{ (r as unknown as Record<string, unknown>)[c.key] }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
