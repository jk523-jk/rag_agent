<script setup lang="ts">
import { RouterLink } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
</script>

<template>
  <PageHeader title="页面不存在" description="你访问的地址没有对应的页面。" />
  <EmptyState title="404 · 找不到该页面" description="链接可能已失效，或该功能尚未开放。">
    <template #action>
      <RouterLink to="/dashboard" class="btn-primary">返回工作台</RouterLink>
      <RouterLink to="/chat" class="btn-default">去 AI 对话</RouterLink>
    </template>
  </EmptyState>
</template>
