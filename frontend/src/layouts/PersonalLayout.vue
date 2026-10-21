<script setup lang="ts">
import { ref } from 'vue'
import { auth, logout } from '@/services/auth'
import { LogOut, ShieldCheck } from 'lucide-vue-next'
const error = ref('')
async function exit() { try { await logout() } catch(e) { error.value=(e as Error).message } }
const links = [ ['/portal','我的首页'],['/portal/profile','我的资料'],['/portal/qualifications','我的资质'],['/portal/permits','我的许可'],['/portal/requests','许可申请'],['/portal/records','我的记录'],['/portal/notifications','消息中心'],['/portal/assistant','安全查询'] ]
</script>
<template>
  <div class="min-h-screen">
    <header class="border-b border-line bg-surface">
      <div class="max-w-6xl mx-auto px-5 py-4 flex gap-4 items-center flex-wrap">
        <RouterLink to="/portal" class="flex items-center gap-2 font-medium"><ShieldCheck class="size-6" />实验室智能管理</RouterLink>
        <div class="ml-auto flex gap-3 items-center text-sm flex-wrap">
          <span>{{ auth.user?.displayName }} <span class="text-ink-3">{{ auth.user?.role === 'admin' ? '管理员' : '普通用户' }}</span></span>
          <RouterLink v-if="auth.user?.role === 'admin' && !auth.user.mustChangePassword" to="/dashboard" class="btn-default">管理工作台</RouterLink>
          <RouterLink to="/change-password" class="text-ink-2">修改密码</RouterLink>
          <button class="btn-ghost" @click="exit"><LogOut class="size-4" />退出</button>
        </div>
      </div>
      <nav v-if="!auth.user?.mustChangePassword" class="max-w-6xl mx-auto px-5 flex gap-6 overflow-x-auto" aria-label="个人导航">
        <RouterLink v-for="[to,label] in links" :key="to" :to="to!" class="shrink-0 py-3 text-sm border-b-2 border-transparent text-ink-2" exact-active-class="!border-brand !text-ink font-medium">{{ label }}</RouterLink>
      </nav>
    </header>
    <p v-if="error" role="alert" class="text-err max-w-6xl mx-auto px-5">{{ error }}</p>
    <main class="max-w-6xl mx-auto px-5 py-8"><RouterView :key="$route.path" /></main>
  </div>
</template>
