<script setup lang="ts">
defineProps<{ message: string }>()
defineEmits<{ (e: 'retry'): void }>()
</script>

<template>
  <div class="panel flex flex-col items-start gap-3 border-err/30 bg-err-soft p-4" role="alert">
    <p class="text-[13px] text-err">{{ message }}</p>
    <button type="button" class="btn-danger" @click="$emit('retry')">重试</button>
  </div>
</template>
