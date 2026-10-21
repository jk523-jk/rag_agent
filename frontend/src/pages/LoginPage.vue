<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ShieldCheck, ArrowRight } from 'lucide-vue-next'
import { auth, login } from '@/services/auth'
const router = useRouter()
const username = ref(''), password = ref(''), error = ref(''), busy = ref(false)
async function submit() {
  busy.value = true; error.value = ''
  try {
    await login(username.value.trim(), password.value)
    password.value = ''
    await router.replace(auth.user?.mustChangePassword ? '/change-password' : auth.user?.role === 'admin' ? '/dashboard' : '/portal')
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>
<template>
  <main class="login-shell">
    <section class="login-intro">
      <ShieldCheck class="size-10 mb-8" :stroke-width="1.2" />
      <h1>每一次进入，<br>都有安全的依据。</h1>
      <p>实验室智能管理</p><div class="login-rule" />
      <p class="text-ink-2 max-w-sm">查阅个人资质，办理实验室许可，跟进每一步审批。</p>
    </section>
    <section class="panel p-7 sm:p-10 w-full max-w-md">
      <h2 class="text-2xl mb-2">登录工作空间</h2><p class="text-ink-3 mb-8">使用管理员分配的账号登录</p>
      <form class="space-y-5" @submit.prevent="submit">
        <label class="block"><span class="label">账号</span><input v-model="username" class="input" autocomplete="username" required maxlength="64" placeholder="工号、学号或登录账号"></label>
        <label class="block"><span class="label">密码</span><input v-model="password" type="password" class="input" autocomplete="current-password" required maxlength="128" placeholder="输入密码"></label>
        <p v-if="error" role="alert" class="text-err text-sm">{{ error }}</p>
        <button class="btn-primary w-full !h-10" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}<ArrowRight class="size-4" /></button>
      </form>
      <p class="mt-6 text-xs text-ink-3">忘记密码或尚未分配账号，请联系实验室管理员。</p>
    </section>
  </main>
</template>
<style scoped>
.login-shell { min-height:100vh; display:grid; grid-template-columns:1fr 1fr; align-items:center; gap:8vw; max-width:1200px; margin:auto; padding:64px 48px; }
.login-intro h1 { font-size:clamp(32px,4vw,52px); line-height:1.5; margin-bottom:24px; }
.login-rule { width:72px; border-top:2px solid var(--color-ink); margin:28px 0; }
@media(max-width:767px){.login-shell{grid-template-columns:1fr;gap:32px;padding:36px 20px}.login-intro h1{font-size:30px}.login-intro>svg,.login-rule{display:none}}
</style>
