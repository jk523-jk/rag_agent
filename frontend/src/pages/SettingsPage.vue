<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Save, RotateCcw, Database } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import DataTable, { type Column } from '@/components/common/DataTable.vue'
import { useWorkspaceStore, DEFAULT_SETTINGS } from '@/stores/workspace'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { STORAGE_VERSION, removeState } from '@/utils/storage'
import { downloadText, plainClone } from '@/utils/format'
import type { AppSettings } from '@/types'

const workspace = useWorkspaceStore()
const chat = useChatStore()
const ui = useUiStore()

type Section = 'general' | 'model' | 'appearance' | 'data'
const section = ref<Section>('general')

const NAV: { key: Section; label: string }[] = [
  { key: 'general', label: '通用设置' },
  { key: 'model', label: '模型配置' },
  { key: 'appearance', label: '外观设置' },
  { key: 'data', label: '数据管理' },
]

// 本地草稿：保存后才写入 store 与 LocalStorage，避免边改边生效
const draft = reactive<AppSettings>(plainClone(workspace.state.settings))
const errors = ref<Record<string, string>>({})

watch(section, () => {
  Object.assign(draft, plainClone(workspace.state.settings))
  errors.value = {}
})

function validate(): boolean {
  const e: Record<string, string> = {}
  if (!draft.workspaceName.trim()) e.workspaceName = '工作区名称不能为空'
  else if (draft.workspaceName.length > 30) e.workspaceName = '工作区名称不能超过 30 个字符'

  if (!draft.model.name.trim()) e.modelName = '模型名称不能为空'
  else if (!/^[\w.\-]+$/.test(draft.model.name.trim())) e.modelName = '模型名称只能包含字母、数字、点、横线与下划线'
  if (draft.model.temperature < 0 || draft.model.temperature > 1) e.temperature = '温度需在 0–1 之间'
  if (!Number.isInteger(draft.model.maxTokens) || draft.model.maxTokens < 128 || draft.model.maxTokens > 8192) {
    e.maxTokens = '最大输出 Token 需为 128–8192 的整数'
  }
  if (!Number.isInteger(draft.model.timeoutSec) || draft.model.timeoutSec < 5 || draft.model.timeoutSec > 300) {
    e.timeoutSec = '超时需为 5–300 秒'
  }

  errors.value = e
  return Object.keys(e).length === 0
}

function save() {
  if (!validate()) {
    ui.toast('请修正标红的字段后再保存', 'error')
    return
  }
  workspace.updateSettings(plainClone(draft))
  ui.toast('配置已保存到本地（LocalStorage）')
}

function resetDraft() {
  Object.assign(draft, plainClone(DEFAULT_SETTINGS))
  errors.value = {}
  ui.toast('已恢复为默认值，点击保存后生效', 'info')
}

const confirmReset = ref(false)
function doReset() {
  workspace.resetDemo()
  removeState('nexus-chat')
  Object.assign(draft, plainClone(DEFAULT_SETTINGS))
  confirmReset.value = false
  ui.toast('演示数据已重置为初始状态')
}

function exportAll() {
  downloadText('nexus-workspace-export.json', JSON.stringify({
    version: STORAGE_VERSION,
    exportedAt: '2026-10-15 10:00',
    isMock: true,
    workspace: workspace.state,
  }, null, 2))
  ui.toast('已导出演示数据（含模拟标记）')
}

const columns: Column[] = [
  { key: 'name', label: '存储键' },
  { key: 'content', label: '内容' },
  { key: 'size', label: '大小', align: 'right' },
]

interface StorageRow {
  id: string
  name: string
  content: string
  size: string
}

const storageRows = computed<StorageRow[]>(() => [
  { id: 'k1', name: 'nexus-workspace', content: 'Agent / 工作流 / 评估 / 日志 / 实验室领域数据（人员·资质·授权·门禁·台账·设备） / 配置', size: `${(JSON.stringify(workspace.state).length / 1024).toFixed(1)} KB` },
  { id: 'k2', name: 'nexus-chat', content: `会话 ${chat.state.sessions.length} 个`, size: `${(JSON.stringify(chat.state).length / 1024).toFixed(1)} KB` },
  { id: 'k3', name: 'nexus-ui', content: '界面偏好（导航折叠状态）', size: '< 1 KB' },
])
</script>

<template>
  <PageHeader title="系统设置" description="配置模型、外观与演示数据。">
    <template #actions>
      <button type="button" class="btn-default" @click="resetDraft"><RotateCcw class="size-4" aria-hidden="true" />恢复默认值</button>
      <button type="button" class="btn-primary" @click="save"><Save class="size-4" aria-hidden="true" />保存配置</button>
    </template>
  </PageHeader>

  <div class="grid grid-cols-1 gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
    <nav class="panel p-2 h-max" aria-label="设置分类">
      <ul class="space-y-0.5">
        <li v-for="n in NAV" :key="n.key">
          <button
            type="button"
            :aria-current="section === n.key ? 'true' : undefined"
            :class="['w-full rounded-[var(--radius-control)] px-3 py-2 text-left text-[13px]', section === n.key ? 'bg-brand-soft font-medium text-brand' : 'text-ink-2 hover:bg-page hover:text-ink']"
            @click="section = n.key"
          >{{ n.label }}</button>
        </li>
      </ul>
    </nav>

    <div class="space-y-4">
      <!-- 通用 -->
      <section v-if="section === 'general'" class="panel p-4" aria-labelledby="s-general">
        <h2 id="s-general" class="mb-3 text-[15px] font-semibold text-ink">通用设置</h2>
        <div class="max-w-md space-y-4">
          <div>
            <label class="label" for="set-workspace">工作区名称</label>
            <input id="set-workspace" v-model="draft.workspaceName" class="input" maxlength="30" :aria-invalid="!!errors.workspaceName" />
            <p v-if="errors.workspaceName" class="mt-1 text-[12px] text-err">{{ errors.workspaceName }}</p>
          </div>
          <div>
            <span class="label">运行环境</span>
            <p class="flex items-center gap-2 text-[13px] text-ink">
              <span class="mock-tag">DEMO</span>前端演示环境，未连接后端、数据库与向量库
            </p>
          </div>
          <div>
            <span class="label">只读约束</span>
            <p class="rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
              本系统只读。修改资质、台账、授权、导出名单与开门操作一律被拒绝，实际生产环境还有工具层与数据库层拦截。
            </p>
          </div>
        </div>
      </section>

      <!-- 模型 -->
      <section v-else-if="section === 'model'" class="panel p-4" aria-labelledby="s-model">
        <h2 id="s-model" class="mb-1 text-[15px] font-semibold text-ink">模型配置</h2>
        <p class="mb-3 text-[12px] text-ink-3">仅保存配置，不会调用真实 API，也不需要填写 API Key。</p>
        <div class="grid max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label class="label" for="set-model">模型名称</label>
            <input id="set-model" v-model="draft.model.name" class="input" :aria-invalid="!!errors.modelName" />
            <p v-if="errors.modelName" class="mt-1 text-[12px] text-err">{{ errors.modelName }}</p>
          </div>
          <div>
            <label class="label" for="set-temp">温度（0–1）</label>
            <input id="set-temp" v-model.number="draft.model.temperature" type="number" min="0" max="1" step="0.1" class="input tabular-nums" :aria-invalid="!!errors.temperature" />
            <p v-if="errors.temperature" class="mt-1 text-[12px] text-err">{{ errors.temperature }}</p>
          </div>
          <div>
            <label class="label" for="set-max">最大输出 Token</label>
            <input id="set-max" v-model.number="draft.model.maxTokens" type="number" min="128" max="8192" step="128" class="input tabular-nums" :aria-invalid="!!errors.maxTokens" />
            <p v-if="errors.maxTokens" class="mt-1 text-[12px] text-err">{{ errors.maxTokens }}</p>
          </div>
          <div>
            <label class="label" for="set-timeout">请求超时（秒）</label>
            <input id="set-timeout" v-model.number="draft.model.timeoutSec" type="number" min="5" max="300" class="input tabular-nums" :aria-invalid="!!errors.timeoutSec" />
            <p v-if="errors.timeoutSec" class="mt-1 text-[12px] text-err">{{ errors.timeoutSec }}</p>
          </div>
        </div>
      </section>

      <!-- 外观 -->
      <section v-else-if="section === 'appearance'" class="panel p-4" aria-labelledby="s-look">
        <h2 id="s-look" class="mb-3 text-[15px] font-semibold text-ink">外观设置</h2>
        <div class="max-w-md space-y-4">
          <div>
            <span class="label">主题</span>
            <p class="text-[13px] text-ink">浅色模式（当前唯一支持的主题）</p>
          </div>
          <div>
            <span class="label" id="density-label">信息密度</span>
            <div role="radiogroup" aria-labelledby="density-label" class="mt-1 inline-flex rounded-[var(--radius-control)] border border-line p-0.5">
              <button
                v-for="d in [{ k: 'comfortable', l: '宽松' }, { k: 'compact', l: '紧凑' }]"
                :key="d.k"
                type="button"
                role="radio"
                :aria-checked="draft.appearance.density === d.k"
                :class="['h-7 px-3 rounded-[4px] text-[12px]', draft.appearance.density === d.k ? 'bg-brand-soft font-medium text-brand' : 'text-ink-2 hover:text-ink']"
                @click="draft.appearance.density = d.k as 'comfortable' | 'compact'"
              >{{ d.l }}</button>
            </div>
          </div>
          <label class="flex items-center gap-2 text-[13px] text-ink">
            <input type="checkbox" class="accent-[#2f2c28] opacity-60" disabled />
            尊重系统“减少动态效果”设置（自动生效，无需配置）
          </label>
        </div>
      </section>

      <!-- 数据管理 -->
      <template v-else>
        <section class="panel p-4" aria-labelledby="s-data">
          <h2 id="s-data" class="mb-1 text-[15px] font-semibold text-ink">本地数据</h2>
          <p class="mb-3 text-[12px] text-ink-3">
            数据保存在浏览器 LocalStorage，带版本号 {{ STORAGE_VERSION }}；数据损坏或版本不兼容时会自动回退为演示数据。
          </p>
          <DataTable :columns="columns" :rows="storageRows" caption="本地存储键" />
          <div class="mt-4 flex flex-wrap gap-2">
            <button type="button" class="btn-default" @click="exportAll"><Database class="size-4" aria-hidden="true" />导出演示数据</button>
            <button type="button" class="btn-danger" @click="confirmReset = true"><RotateCcw class="size-4" aria-hidden="true" />重置演示数据</button>
          </div>
          <p class="mt-3 text-[12px] text-ink-3">
            重置会清空本地修改（Agent、工作流、实验室领域数据、会话与配置）并恢复初始演示数据，此操作不可撤销。
          </p>
        </section>

        <EmptyState title="关于 API Key" description="当前阶段不要求填写真实 API Key，也不会在前端保存或展示任何密钥。生产部署时密钥由后端环境变量管理。" />
      </template>
    </div>
  </div>

  <ConfirmDialog
    :open="confirmReset"
    title="重置全部演示数据？"
    description="将清空本地修改、会话记录与配置，恢复为初始演示数据。"
    confirm-text="确认重置"
    danger
    @update:open="confirmReset = false"
    @confirm="doReset"
  />
</template>
