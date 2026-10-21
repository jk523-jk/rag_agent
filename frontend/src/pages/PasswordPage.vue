<script setup lang="ts">
import { ref } from 'vue'
import { api, auth, clearPrivateStorage } from '@/services/auth'
const oldPassword=ref(''), newPassword=ref(''), confirm=ref(''), error=ref(''), busy=ref(false)
async function save(){
  error.value=''
  if(newPassword.value!==confirm.value){error.value='两次输入的新密码不一致';return}
  busy.value=true
  try{await api('/api/auth/change-password',{method:'POST',body:JSON.stringify({oldPassword:oldPassword.value,newPassword:newPassword.value})});clearPrivateStorage();window.location.replace('/login?passwordChanged=1')}
  catch(e){error.value=(e as Error).message}finally{busy.value=false}
}
</script>
<template>
  <section class="panel max-w-lg mx-auto p-7">
    <h1 class="text-2xl mb-2">{{ auth.user?.mustChangePassword ? '首次登录，设置你的密码' : '修改密码' }}</h1>
    <p class="text-ink-3 mb-6">密码至少 10 个字符。修改后需要重新登录。</p>
    <form class="space-y-4" @submit.prevent="save">
      <label class="block"><span class="label">原密码 / 临时密码</span><input v-model="oldPassword" class="input" type="password" autocomplete="current-password" required maxlength="128"></label>
      <label class="block"><span class="label">新密码</span><input v-model="newPassword" class="input" type="password" autocomplete="new-password" required minlength="10" maxlength="128"></label>
      <label class="block"><span class="label">确认新密码</span><input v-model="confirm" class="input" type="password" autocomplete="new-password" required minlength="10" maxlength="128"></label>
      <p v-if="error" role="alert" class="text-err">{{ error }}</p><button class="btn-primary" :disabled="busy">{{ busy?'保存中…':'保存并重新登录' }}</button>
    </form>
  </section>
</template>
