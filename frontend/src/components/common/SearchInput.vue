<script setup lang="ts">
import { Search } from 'lucide-vue-next'

withDefaults(defineProps<{ modelValue: string; placeholder?: string; label: string }>(), { placeholder: '搜索' })
defineEmits<{ (e: 'update:modelValue', v: string): void }>()
</script>

<template>
  <div class="relative w-full sm:w-72">
    <label class="sr-only" :for="label">{{ label }}</label>
    <Search class="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
    <input
      :id="label"
      :value="modelValue"
      type="search"
      class="input pl-8"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </div>
</template>
