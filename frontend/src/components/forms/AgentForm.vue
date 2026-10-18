<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { Agent } from '@/types'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { newId } from '@/utils/format'
import { MODEL_OPTIONS, TOOL_OPTIONS, validateAgent, type AgentDraft } from '@/utils/validators'
import AppDrawer from '@/components/common/AppDrawer.vue'

const props = defineProps<{ open: boolean; agent: Agent | null }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void; (e: 'saved', agent: Agent): void }>()

const workspace = useWorkspaceStore()
const ui = useUiStore()

const form = reactive<AgentDraft>({
  name: '', description: '', systemPrompt: '', model: 'qwen-plus',
  temperature: 0, maxTokens: 2048, tools: [], status: 'enabled',
})
const errors = ref<Partial<Record<keyof AgentDraft, string>>>({})
const submitting = ref(false)

watch(() => props.open, (v) => {
  if (!v) return
  errors.value = {}
  const a = props.agent
  Object.assign(form, a
    ? { name: a.name, description: a.description, systemPrompt: a.systemPrompt, model: a.model,
        temperature: a.temperature, maxTokens: a.maxTokens,
        tools: [...a.tools], status: a.status }
    : { name: '', description: '', systemPrompt: '', model: 'qwen-plus', temperature: 0,
        maxTokens: 2048, tools: [], status: 'enabled' })
})

const title = computed(() => (props.agent ? '编辑 Agent' : '新建 Agent'))

function toggle(key: 'tools', value: string) {
  const list = form[key]
  const i = list.indexOf(value)
  if (i >= 0) list.splice(i, 1)
  else list.push(value)
}

async function submit() {
  errors.value = validateAgent(form)
  if (Object.keys(errors.value).length) {
    ui.toast('请修正表单中标红的字段', 'error')
    return
  }
  submitting.value = true
  const agent: Agent = {
    id: props.agent?.id ?? newId('agt'),
    icon: props.agent?.icon ?? 'shield',
    name: form.name.trim(),
    description: form.description.trim(),
    systemPrompt: form.systemPrompt.trim(),
    model: form.model,
    temperature: Number(form.temperature),
    maxTokens: Number(form.maxTokens),
    tools: [...form.tools],
    status: form.status,
    lastRunAt: props.agent?.lastRunAt ?? '—',
    runCount: props.agent?.runCount ?? 0,
  }
  try {
    // backend 模式写穿到 /api/agents；失败时不改本地，避免"界面成功、后端没存"
    const saved = await workspace.saveAgent(agent, !props.agent)
    emit('saved', saved)
    emit('update:open', false)
    ui.toast(props.agent ? 'Agent 已更新' : 'Agent 已创建')
  } catch (e) {
    ui.toast(e instanceof Error ? e.message : '保存失败，请稍后重试', 'error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppDrawer :open="open" :title="title" width="lg" @update:open="emit('update:open', $event)">
    <form id="agent-form" class="space-y-4" novalidate @submit.prevent="submit">
      <div>
        <label class="label" for="agent-name">Agent 名称 <span class="text-err">*</span></label>
        <input id="agent-name" v-model="form.name" class="input" maxlength="40" :aria-invalid="!!errors.name" aria-describedby="agent-name-err" />
        <p v-if="errors.name" id="agent-name-err" class="mt-1 text-[12px] text-err">{{ errors.name }}</p>
      </div>

      <div>
        <label class="label" for="agent-desc">描述</label>
        <textarea id="agent-desc" v-model="form.description" class="textarea" rows="2" maxlength="200" :aria-invalid="!!errors.description" />
        <p v-if="errors.description" class="mt-1 text-[12px] text-err">{{ errors.description }}</p>
      </div>

      <div>
        <label class="label" for="agent-prompt">系统提示词 <span class="text-err">*</span></label>
        <textarea id="agent-prompt" v-model="form.systemPrompt" class="textarea font-mono text-[12px]" rows="6" maxlength="2000" :aria-invalid="!!errors.systemPrompt" aria-describedby="agent-prompt-help" />
        <p id="agent-prompt-help" class="mt-1 text-[12px] text-ink-3">{{ form.systemPrompt.length }} / 2000</p>
        <p v-if="errors.systemPrompt" class="mt-1 text-[12px] text-err">{{ errors.systemPrompt }}</p>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label class="label" for="agent-model">模型名称</label>
          <select id="agent-model" v-model="form.model" class="input">
            <option v-for="m in MODEL_OPTIONS" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div>
          <label class="label" for="agent-temp">温度（0–1）</label>
          <input id="agent-temp" v-model.number="form.temperature" type="number" step="0.1" min="0" max="1" class="input tabular-nums" :aria-invalid="!!errors.temperature" />
          <p v-if="errors.temperature" class="mt-1 text-[12px] text-err">{{ errors.temperature }}</p>
        </div>
        <div>
          <label class="label" for="agent-max">最大输出 Token</label>
          <input id="agent-max" v-model.number="form.maxTokens" type="number" step="128" min="128" max="8192" class="input tabular-nums" :aria-invalid="!!errors.maxTokens" />
          <p v-if="errors.maxTokens" class="mt-1 text-[12px] text-err">{{ errors.maxTokens }}</p>
        </div>
      </div>

      <fieldset>
        <legend class="label">可用工具</legend>
        <div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          <label v-for="t in TOOL_OPTIONS" :key="t.id" class="flex items-start gap-2 rounded-[var(--radius-control)] border border-line px-3 py-2 text-[13px] has-[:checked]:border-brand has-[:checked]:bg-brand-soft">
            <input type="checkbox" class="mt-1 accent-[#2f2c28]" :checked="form.tools.includes(t.id)" @change="toggle('tools', t.id)" />
            <span><span class="block text-ink">{{ t.id }}</span><span class="block text-[12px] text-ink-3">{{ t.desc }}</span></span>
          </label>
        </div>
        <p v-if="errors.tools" class="mt-1 text-[12px] text-err">{{ errors.tools }}</p>
      </fieldset>

      <div>
        <label class="label" for="agent-status">Agent 状态</label>
        <select id="agent-status" v-model="form.status" class="input w-auto">
          <option value="enabled">启用</option>
          <option value="disabled">停用</option>
        </select>
      </div>
    </form>

    <template #footer>
      <button type="button" class="btn-default" @click="emit('update:open', false)">取消</button>
      <button type="submit" form="agent-form" class="btn-primary" :disabled="submitting">
        {{ submitting ? '保存中…' : '保存' }}
      </button>
    </template>
  </AppDrawer>
</template>
