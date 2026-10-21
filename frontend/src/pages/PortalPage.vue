<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, auth } from '@/services/auth'
import type { AvailableLab, Notification, Page, PersonalSummary } from '@/services/portal'
import ApplicationsPanel from '@/components/portal/ApplicationsPanel.vue'
const route = useRoute()
const section = computed(() => route.path.split('/')[2] ?? '')
const data = ref<PersonalSummary | null>(null), labs = ref<AvailableLab[]>([]), messages=ref<Notification[]>([])
const error=ref(''), loading=ref(true), busy=ref(false), selectedLab=ref('')
const check=ref<{allowed:boolean;issues:string[];checkedAt:string;hardwareStatus:string}|null>(null)
const validPermits=computed(()=>data.value?.authorizations.filter(a=>a.effectiveStatus==='有效').length??0)
async function load(){
  loading.value=true;error.value=''
  try{const [d,l]=await Promise.all([api<PersonalSummary>('/api/me/summary'),api<AvailableLab[]>('/api/labs/available')]);data.value=d;labs.value=l
    if(section.value==='notifications')messages.value=(await api<Page<Notification>>('/api/me/notifications?page_size=100')).items
  }catch(e){error.value=(e as Error).message}finally{loading.value=false}
}
async function mark(id:number){try{await api(`/api/me/notifications/${id}/read`,{method:'POST'});await load()}catch(e){error.value=(e as Error).message}}
async function checkAccess(){busy.value=true;error.value='';try{check.value=await api(`/api/me/access-check?lab_id=${encodeURIComponent(selectedLab.value)}`)}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
function labName(id:string){return labs.value.find(l=>l.labId===id)?.labName??id}
onMounted(load)
</script>
<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between gap-4"><div><h1 class="text-3xl">{{ route.meta.title }}</h1><p class="text-ink-3 mt-2">{{ section ? '查看与你有关的实验室事项' : `${auth.user?.displayName}，欢迎回来。` }}</p></div><button class="btn-default" :disabled="loading" @click="load">刷新</button></div>
    <p v-if="error" role="alert" class="p-4 border border-err/30 bg-err-soft text-err">{{ error }} <button class="underline ml-2" @click="load">重试</button></p>
    <p v-if="loading" role="status" class="text-ink-3 py-8">正在读取个人记录…</p>
    <template v-else-if="data">
      <template v-if="!section">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <RouterLink v-for="card in [{label:'当前有效许可',value:validPermits,to:'/portal/permits'},{label:'我的资质',value:data.qualifications.length,to:'/portal/qualifications'},{label:'处理中申请',value:data.pendingApplications,to:'/portal/requests'},{label:'未读消息',value:data.unreadNotifications,to:'/portal/notifications'}]" :key="card.label" :to="card.to" class="panel p-5 hover:border-ink-3"><p class="text-ink-2 text-sm">{{ card.label }}</p><p class="text-3xl mt-3 font-serif">{{ card.value }}</p></RouterLink>
        </div>
        <section class="panel p-6 flex flex-wrap items-center justify-between gap-5"><div><h2 class="text-xl">准备开始下一次实验</h2><p class="mt-2 text-ink-2">先核对资质与许可，再办理实验室准入申请。</p></div><RouterLink to="/portal/requests?new=1" class="btn-primary">申请实验室许可</RouterLink></section>
        <section class="panel p-6"><h2 class="text-xl mb-4">需要留意的事项</h2><p v-if="!data.qualifications.some(q=>q.effectiveStatus!=='有效') && !data.authorizations.some(a=>a.effectiveStatus!=='有效')" class="text-ink-2">当前没有失效的资质或许可。进入实验室前请再次核对准入条件。</p><p v-for="q in data.qualifications.filter(q=>q.effectiveStatus!=='有效')" :key="q.id" class="text-warn py-1">{{ q.certType }}：{{ q.effectiveStatus }}，请联系管理员更新资质。</p><p v-for="a in data.authorizations.filter(a=>a.effectiveStatus!=='有效')" :key="a.id" class="text-warn py-1">{{ labName(a.labId) }}：{{ a.effectiveStatus }}</p></section>
      </template>
      <section v-else-if="section==='profile'" class="panel p-6"><h2 class="text-xl mb-5">人员档案</h2><dl class="grid sm:grid-cols-2 gap-6"><div v-for="[label,value] in [['姓名',data.profile.name],['工号 / 学号',data.profile.empNo],['院系 / 课题组',data.profile.dept],['人员身份',data.profile.role],['登录账号',auth.user?.username],['系统角色',auth.user?.role==='admin'?'管理员':'普通用户']]" :key="label"><dt class="text-ink-3 text-xs">{{ label }}</dt><dd class="mt-1">{{ value }}</dd></div></dl><p class="mt-8 text-sm text-ink-3">身份信息需要更正时，请联系管理员核对人员档案。</p></section>
      <section v-else-if="section==='qualifications'" class="space-y-4"><article v-for="q in data.qualifications" :key="q.id" class="panel p-6"><div class="flex justify-between gap-4"><h2 class="text-lg">{{ q.certType }}</h2><span :class="q.effectiveStatus==='有效'?'text-ok':'text-err'">{{ q.effectiveStatus }}</span></div><p class="text-ink-2 mt-2">{{ q.certNo }} · {{ q.issueDate }} 至 {{ q.expireDate }}</p></article><p v-if="!data.qualifications.length" class="panel p-8 text-ink-3">暂无资质记录，请联系管理员核对档案。</p></section>
      <section v-else-if="section==='permits'" class="space-y-4"><article v-for="a in data.authorizations" :key="a.id" class="panel p-6"><div class="flex justify-between gap-4"><h2 class="text-lg">{{ labName(a.labId) }}</h2><span :class="a.effectiveStatus==='有效'?'text-ok':'text-warn'">{{ a.effectiveStatus }}</span></div><p class="text-ink-2 mt-2">{{ a.authFrom }} 至 {{ a.authTo }} · 授权人：{{ a.grantor }}</p><p v-for="issue in a.issues" :key="issue" class="text-warn mt-1">{{ issue }}</p><div class="mt-4 flex flex-wrap items-center gap-4"><span class="text-xs text-ink-3">{{ a.hardwareStatus }}</span><RouterLink :to="`/portal/requests?new=1&amp;lab=${a.labId}&amp;kind=renew`" class="btn-default">申请续期</RouterLink></div></article><p v-if="!data.authorizations.length" class="panel p-8">尚无实验室许可，可前往许可申请办理。</p></section>
      <ApplicationsPanel v-else-if="section==='requests'" :labs="labs" />
      <section v-else-if="section==='records'" class="space-y-6"><div class="panel p-6"><h2 class="text-xl mb-4">设备借用</h2><p v-if="!data.equipmentLoans.length" class="text-ink-3">暂无借用记录</p><div v-for="l in data.equipmentLoans" :key="l.id" class="py-3 border-b border-line last:border-0"><p>{{ data.equipment.find(e=>e.equipId===l.equipId)?.equipName??l.equipId }} <span class="ml-3 text-ink-2">{{ l.returnTime?'已归还':l.dueTime.slice(0,10)<data.serverTime.slice(0,10)?'已逾期':'借用中' }}</span></p><p class="text-ink-3 text-sm">借出 {{ l.borrowTime }}，应还 {{ l.dueTime }}</p></div></div><div class="panel p-6"><h2 class="text-xl mb-4">通行记录</h2><p v-if="!data.accessEvents.length" class="text-ink-3">暂无通行记录</p><div v-for="e in [...data.accessEvents].sort((a,b)=>b.eventTime.localeCompare(a.eventTime)).slice(0,50)" :key="e.id" class="py-2 border-b border-line last:border-0 flex flex-wrap gap-4"><span>{{ e.eventTime }}</span><span>{{ labName(e.labId) }}</span><span>{{ e.direction }} · {{ e.authResult }}</span></div><p class="mt-3 text-xs text-ink-3">展示最近 50 条本人通行记录</p></div></section>
      <section v-else-if="section==='notifications'" class="space-y-3"><p v-if="!messages.length" class="panel p-8">暂无消息</p><article v-for="m in messages" :key="m.id" class="panel p-5" :class="m.is_read?'opacity-70':''"><div class="flex items-start justify-between gap-3"><h2 class="font-medium">{{ m.title }}</h2><button v-if="!m.is_read" class="btn-ghost" @click="mark(m.id)">标记已读</button><span v-else class="text-xs text-ink-3">已读</span></div><p class="text-ink-2 mt-2">{{ m.body }}</p><p class="text-xs text-ink-3 mt-2">{{ m.created_at }}</p><RouterLink v-if="m.application_id" :to="`/portal/requests?id=${m.application_id}`" class="inline-block mt-2 underline text-sm">查看申请</RouterLink></article></section>
      <section v-else-if="section==='assistant'" class="panel p-6"><h2 class="text-xl mb-2">我能进入这间实验室吗？</h2><p class="text-ink-2 mb-5">根据本人当前资质和许可检查准入条件。</p><form class="flex flex-wrap gap-3" @submit.prevent="checkAccess"><select v-model="selectedLab" class="input max-w-md" aria-label="选择实验室" required><option value="">选择实验室</option><option v-for="l in labs" :key="l.labId" :value="l.labId">{{ l.labName }}</option></select><button class="btn-primary !h-9" :disabled="busy">检查准入条件</button></form><div v-if="check" class="mt-6 border-t border-line pt-5"><p class="font-medium" :class="check.allowed?'text-ok':'text-warn'">{{ check.allowed?'当前系统准入条件满足':'当前尚不满足准入条件' }}</p><p v-for="issue in check.issues" :key="issue" class="mt-2">{{ issue }}</p><p class="text-xs text-ink-3 mt-4">核对于 {{ check.checkedAt }} · {{ check.hardwareStatus }}</p></div><div class="mt-8 text-sm text-ink-2 space-y-2"><p>需要新许可或续期：前往“许可申请”。</p><p>资质已过期或缺失：联系管理员核对并更新资质。</p><p>实际进入还需遵守现场安全要求，本页不会操作门禁设备。</p></div></section>
      <section v-if="section==='permits' && data.permitHistory.length" class="panel p-6"><h2 class="text-xl mb-4">历史登记记录</h2><div v-for="h in data.permitHistory" :key="h.id" class="py-3 border-b border-line last:border-0"><p>{{ labName(h.lab_id) }} · {{ h.status }}</p><p class="text-sm text-ink-3">{{ h.start_date }} 至 {{ h.end_date }} · 登记来源 {{ h.source_ref }}</p></div><p class="text-xs text-ink-3 mt-4">历史登记用于追踪，当前能否准入以最新许可与资质核对结果为准。</p></section>
      <p class="text-xs text-ink-3">数据读取于 {{ data.serverTime }}<span v-if="data.updatedAt">，业务数据更新于 {{ data.updatedAt }}</span></p>
    </template>
  </div>
</template>
