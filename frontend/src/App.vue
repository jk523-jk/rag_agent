<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue'
import PersonalLayout from '@/layouts/PersonalLayout.vue'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <RouterView v-if="route.meta.public" />
  <PersonalLayout v-else-if="route.meta.personal" />
  <AppLayout v-else />
</template>
