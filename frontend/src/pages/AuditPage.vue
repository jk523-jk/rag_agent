<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/services/auth'
import type { Page } from '@/services/portal'
interface Audit {id:number;actor_id:string;action:string;target:string;detail:string;created_at:string}
const rows=ref<Audit[]>([]),page=ref(1),total=ref(0),error=ref('')
async function load(){try{const r=await api<Page<Audit>>(`/api/admin/audit-events?page=${page.value}`);rows.value=r.items;total.value=r.total}catch(e){error.value=(e as Error).message}}
onMounted(load)
</script>
<template><div class="space-y-5"><h1 class="text-3xl">操作审计</h1><p class="text-ink-3">追踪登录、审批、授权和权限变更。</p><p v-if="error" role="alert" class="text-err">{{ error }}</p><section class="panel overflow-x-auto"><table class="w-full text-sm text-left"><thead><tr class="border-b border-line"><th class="p-3">时间</th><th class="p-3">操作人</th><th class="p-3">动作</th><th class="p-3">对象</th><th class="p-3">详情</th></tr></thead><tbody><tr v-for="r in rows" :key="r.id" class="border-b border-line"><td class="p-3 whitespace-nowrap">{{ r.created_at }}</td><td class="p-3">{{ r.actor_id }}</td><td class="p-3 whitespace-nowrap">{{ r.action }}</td><td class="p-3">{{ r.target }}</td><td class="p-3 max-w-sm break-all">{{ r.detail }}</td></tr></tbody></table><p v-if="!rows.length" class="p-8 text-ink-3">暂无审计记录</p></section><div class="flex items-center justify-between"><span class="text-ink-3 text-sm">共 {{ total }} 条，第 {{ page }} 页</span><div class="flex gap-2"><button class="btn-default" :disabled="page===1" @click="page--;load()">上一页</button><button class="btn-default" :disabled="page*50>=total" @click="page++;load()">下一页</button></div></div></div></template>
