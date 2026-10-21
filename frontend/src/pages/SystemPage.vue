<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, auth } from '@/services/auth'
const state=ref<Record<string,unknown>|null>(null),error=ref('')
onMounted(async()=>{try{state.value=await api('/api/health')}catch(e){error.value=(e as Error).message}})
</script>
<template><div class="space-y-6"><h1 class="text-3xl">系统设置</h1><section class="panel p-6"><h2 class="text-xl mb-4">当前运行状态</h2><p v-if="error" role="alert" class="text-err">{{ error }}</p><p v-if="state">业务服务：{{ state.status==='ok'?'可用':'尚未就绪' }}</p><p class="mt-2 text-ink-2">当前账号：{{ auth.user?.username }}；权限：系统管理员</p><p class="mt-4 text-sm text-ink-3">连接和会话策略由服务端配置维护。业务记录保存在服务端，退出登录后清理浏览器中的个人缓存。</p></section><section class="panel p-6"><h2 class="text-xl mb-4">管理入口</h2><div class="flex gap-3 flex-wrap"><RouterLink to="/users" class="btn-default">账号与权限</RouterLink><RouterLink to="/audit" class="btn-default">操作审计</RouterLink><RouterLink to="/change-password" class="btn-default">修改本人密码</RouterLink></div></section></div></template>
