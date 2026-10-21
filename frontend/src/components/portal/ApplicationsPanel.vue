<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, auth } from '@/services/auth'
import type { Application, AvailableLab, Page } from '@/services/portal'
const props=defineProps<{labs:AvailableLab[];admin?:boolean}>()
const emit=defineEmits<{changed:[]}>()
const route=useRoute()
const rows=ref<Application[]>([]),total=ref(0),page=ref(1),status=ref(''),error=ref(''),success=ref(''),busy=ref(false),loading=ref(false)
const selected=ref<Application|null>(null),editing=ref(false),note=ref(''),reference=ref('')
const form=reactive({labId:'',kind:'新申请',purpose:'',startDate:new Date().toLocaleDateString('en-CA'),endDate:''})
const prefix=computed(()=>props.admin?'/api/admin/permit-applications':'/api/me/permit-applications')
const editable=computed(()=>selected.value&&['草稿','待补充'].includes(selected.value.status)&&!props.admin)
const canReview=computed(()=>props.admin&&selected.value?.status==='待审批'&&selected.value.user_id!==auth.user?.id)
function labName(id:string){return props.labs.find(l=>l.labId===id)?.labName??id}
async function load(){loading.value=true;try{const result=await api<Page<Application>>(`${prefix.value}?page=${page.value}&status=${encodeURIComponent(status.value)}`);rows.value=result.items;total.value=result.total}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
async function open(id:string){error.value='';success.value='';editing.value=false;note.value='';reference.value='';try{selected.value=await api<Application>(`${prefix.value}/${encodeURIComponent(id)}`)}catch(e){error.value=(e as Error).message}}
function newForm(){selected.value=null;editing.value=true;success.value='';error.value='';Object.assign(form,{labId:typeof route.query.lab==='string'?route.query.lab:'',kind:route.query.kind==='renew'?'续期':'新申请',purpose:'',startDate:new Date().toLocaleDateString('en-CA'),endDate:''})}
function edit(){if(!selected.value)return;Object.assign(form,{labId:selected.value.lab_id,kind:selected.value.kind,purpose:selected.value.purpose,startDate:selected.value.start_date,endDate:selected.value.end_date});editing.value=true}
async function run(task:()=>Promise<void>){busy.value=true;error.value='';success.value='';try{await task();await load();emit('changed')}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
async function save(){await run(async()=>{selected.value=await api<Application>(`/api/me/permit-applications${selected.value?'/'+selected.value.id:''}`,{method:selected.value?'PATCH':'POST',body:JSON.stringify({...form,version:selected.value?.version??1})});editing.value=false;success.value='申请已保存。核对信息后点击提交申请。'})}
async function action(kind:string,extra:Record<string,unknown>={}){if(!selected.value)return;const row=selected.value;await run(async()=>{selected.value=await api<Application>(`${prefix.value}/${row.id}/${kind}`,{method:'POST',body:JSON.stringify({version:row.version,...extra})});success.value='操作已完成'})}
async function upload(event:Event){const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file||!selected.value)return;const id=selected.value.id;if(file.size>2_000_000){error.value='文件大小需在 2 MB 以内';input.value='';return}await run(async()=>{const buffer=new Uint8Array(await file.arrayBuffer());let binary='';for(const byte of buffer)binary+=String.fromCharCode(byte);await api(`/api/me/permit-applications/${id}/attachments`,{method:'POST',body:JSON.stringify({name:file.name,content:btoa(binary)})});selected.value=await api<Application>(`${prefix.value}/${id}`);success.value='材料已上传'});input.value=''}
watch(status,()=>{page.value=1;void load()})
onMounted(async()=>{await load();if(route.query.new&&!props.admin)newForm();else if(typeof route.query.id==='string')await open(route.query.id)})
</script>
<template>
  <div class="space-y-4">
    <div class="flex flex-wrap justify-between gap-3 items-center"><div class="flex gap-2 items-center"><label for="application-status" class="text-sm text-ink-2">状态</label><select id="application-status" v-model="status" class="input !w-40"><option value="">全部状态</option><option v-for="s in ['草稿','待审批','待补充','已通过','已驳回','已撤回','已失效']" :key="s">{{ s }}</option></select></div><button v-if="!admin" class="btn-primary" @click="newForm">新建许可申请</button><button v-else class="btn-default" :disabled="loading" @click="load">刷新队列</button></div>
    <p v-if="error" role="alert" class="text-err bg-err-soft p-3">{{ error }}</p><p v-if="success" role="status" class="text-ok bg-ok-soft p-3">{{ success }}</p>
    <div class="grid gap-5" :class="selected||editing?'lg:grid-cols-[minmax(250px,0.8fr)_minmax(0,1.4fr)]':''">
      <section class="panel overflow-hidden self-start">
        <p v-if="loading" class="p-5 text-ink-3">正在读取申请…</p><p v-else-if="!rows.length" class="p-8 text-ink-3">暂无符合条件的申请</p>
        <button v-for="r in rows" :key="r.id" class="w-full text-left p-4 border-b border-line hover:bg-page last:border-0" :class="selected?.id===r.id?'bg-brand-soft':''" @click="open(r.id)"><div class="flex flex-wrap items-center justify-between gap-2"><span class="font-medium">{{ labName(r.lab_id) }}</span><span class="text-xs px-2 py-1 bg-page rounded">{{ r.status==='已通过'?`${r.status} · ${r.execution_status}`:r.status }}</span></div><p class="text-xs text-ink-3 mt-2">{{ r.id }}<span v-if="admin"> · {{ r.applicant_name }}</span></p><p class="text-sm text-ink-2 mt-1">{{ r.kind }} · {{ r.start_date }} 至 {{ r.end_date }}</p></button>
        <div class="p-3 flex items-center justify-between text-xs text-ink-3"><span>共 {{ total }} 单，第 {{ page }} 页</span><div class="flex gap-2"><button class="btn-ghost" :disabled="page===1||loading" @click="page--;load()">上一页</button><button class="btn-ghost" :disabled="page*20>=total||loading" @click="page++;load()">下一页</button></div></div>
      </section>
      <section v-if="editing" class="panel p-6 self-start">
        <h2 class="text-xl mb-5">{{ selected?'编辑申请':'新建许可申请' }}</h2>
        <form class="space-y-4" @submit.prevent="save">
          <label class="block"><span class="label">实验室</span><select v-model="form.labId" aria-label="实验室" class="input" required><option value="">选择实验室</option><option v-for="l in labs" :key="l.labId" :value="l.labId" :disabled="l.status!=='开放'">{{ l.labName }}{{ l.status!=='开放'?'（暂停开放）':'' }}</option></select></label>
          <div v-if="form.labId" class="text-xs text-ink-2 p-3 bg-page"><p>所需资质：{{ labs.find(l=>l.labId===form.labId)?.requiredCerts.join('、') }}</p><p v-for="issue in labs.find(l=>l.labId===form.labId)?.issues??[]" :key="issue" class="text-warn mt-1">{{ issue }}</p><p v-if="labs.find(l=>l.labId===form.labId)?.needsDouble" class="mt-1">需双人准入；许可申请不代替现场同行核验。</p></div>
          <label class="block"><span class="label">申请类型</span><select v-model="form.kind" class="input"><option>新申请</option><option>续期</option></select></label>
          <div class="grid sm:grid-cols-2 gap-4"><label><span class="label">开始日期</span><input v-model="form.startDate" type="date" class="input" required></label><label><span class="label">结束日期</span><input v-model="form.endDate" type="date" class="input" :min="form.startDate" required></label></div>
          <label class="block"><span class="label">实验用途</span><textarea v-model="form.purpose" class="textarea" rows="4" required minlength="5" maxlength="2000" placeholder="说明课题、实验内容和使用目的" /></label>
          <p class="text-xs text-ink-3">保存后可上传材料，再提交审批。申请身份自动关联本人。</p>
          <div class="flex gap-3"><button class="btn-primary" :disabled="busy">保存申请</button><button type="button" class="btn-default" @click="editing=false">取消</button></div>
        </form>
      </section>
      <section v-else-if="selected" class="panel p-6 self-start space-y-5">
        <div class="flex justify-between items-start gap-3"><div><h2 class="text-xl">{{ labName(selected.lab_id) }}</h2><p class="text-xs text-ink-3 mt-2">{{ selected.id }}</p></div><button class="btn-ghost" @click="selected=null">关闭</button></div>
        <dl class="grid sm:grid-cols-2 gap-4 text-sm"><div><dt class="text-ink-3">申请人</dt><dd>{{ selected.applicant_name }}</dd></div><div><dt class="text-ink-3">申请类型</dt><dd>{{ selected.kind }}</dd></div><div><dt class="text-ink-3">有效区间</dt><dd>{{ selected.start_date }} 至 {{ selected.end_date }}</dd></div><div><dt class="text-ink-3">处理状态</dt><dd>{{ selected.status }}{{ selected.status==='已通过'?` · ${selected.execution_status}`:'' }}</dd></div></dl>
        <p class="whitespace-pre-wrap text-ink-2">{{ selected.purpose }}</p>
        <div><h3 class="font-medium mb-2">申请材料</h3><p v-if="!selected.attachments.length" class="text-xs text-ink-3">暂无附件</p><a v-for="file in selected.attachments" :key="file.id" :href="`/api/attachments/${file.id}`" class="block underline text-sm py-1" download>{{ file.name }}</a><label v-if="editable" class="inline-block mt-3"><span class="label">上传 PDF / PNG / JPEG，每份不超过 2 MB</span><input type="file" accept=".pdf,.png,.jpg,.jpeg" :disabled="busy" class="text-sm max-w-full" @change="upload"></label></div>
        <div v-if="!admin" class="flex flex-wrap gap-2"><button v-if="editable" class="btn-default" :disabled="busy" @click="edit">编辑资料</button><button v-if="editable" class="btn-primary" :disabled="busy" @click="action('submit')">提交申请</button><button v-if="['草稿','待审批','待补充'].includes(selected.status)" class="btn-danger" :disabled="busy" @click="action('withdraw')">撤回申请</button></div>
        <div v-if="canReview" class="border-t border-line pt-5 space-y-3"><label class="block"><span class="label">审批意见（驳回或要求补充时必填）</span><textarea v-model="note" class="textarea" rows="3" maxlength="2000" /></label><div class="flex flex-wrap gap-2"><button class="btn-primary" :disabled="busy" @click="action('review',{decision:'通过',note})">通过申请</button><button class="btn-default" :disabled="busy" @click="action('review',{decision:'补充材料',note})">要求补充</button><button class="btn-danger" :disabled="busy" @click="action('review',{decision:'驳回',note})">驳回</button></div></div>
        <p v-if="admin&&selected.user_id===auth.user?.id&&selected.status==='待审批'" class="text-warn">本人申请须交由其他有权管理员审批。</p>
        <div v-if="admin&&selected.status==='已通过'&&selected.execution_status==='待生效'" class="border-t border-line pt-5 space-y-3"><h3 class="font-medium">授权登记与核对</h3><p class="text-xs text-ink-2">确认登记后系统核对授权区间。许可登记与门禁下发分别记录。</p><label class="block"><span class="label">授权登记凭证编号</span><input v-model="reference" class="input" placeholder="填写登记编号或执行依据" minlength="3" maxlength="200"></label><button class="btn-primary" :disabled="busy||reference.trim().length<3" @click="action('execution-confirmation',{reference})">登记并核对许可</button></div>
        <p v-if="selected.execution_ref" class="text-xs text-ink-3">授权登记凭证：{{ selected.execution_ref }}。门禁下发未接入。</p>
        <div class="border-t border-line pt-5"><h3 class="font-medium mb-4">处理时间线</h3><ol class="space-y-4 border-l border-line ml-1 pl-5"><li v-for="e in selected.events" :key="e.id"><p class="text-sm">{{ e.action }} <span class="text-ink-3 ml-2">{{ e.actor_name }}</span></p><p v-if="e.note" class="text-xs text-ink-2 mt-1 whitespace-pre-wrap break-all">{{ e.note }}</p><time class="text-xs text-ink-3">{{ e.created_at }}</time></li></ol></div>
      </section>
    </div>
  </div>
</template>
