<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/services/auth'
import type { AvailableLab } from '@/services/portal'
import ApplicationsPanel from '@/components/portal/ApplicationsPanel.vue'
import { useWorkspaceStore } from '@/stores/workspace'
const workspace=useWorkspaceStore()
const labs=ref<AvailableLab[]>([]),error=ref(''),ready=ref(false)
onMounted(async()=>{try{labs.value=await api('/api/labs/available');ready.value=true}catch(e){error.value=(e as Error).message}})
</script>
<template><div class="space-y-6"><div><h1 class="text-3xl">许可审批</h1><p class="text-ink-3 mt-2">处理负责范围内的申请，跟进授权登记结果。</p></div><p v-if="error" role="alert" class="text-err">{{ error }}</p><ApplicationsPanel v-if="ready" :labs="labs" admin @changed="workspace.hydrate" /></div></template>
