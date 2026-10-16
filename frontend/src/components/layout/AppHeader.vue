<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu, Search, CircleHelp, Plus, ChevronRight, Bot, Microscope, Users, Workflow as WorkflowIcon } from 'lucide-vue-next'
import { useWorkspaceStore } from '@/stores/workspace'

const emit = defineEmits<{ (e: 'open-mobile'): void }>()

const route = useRoute()
const router = useRouter()
const workspace = useWorkspaceStore()

const crumbs = computed(() => {
  const list: { label: string; to?: string }[] = []
  const group = route.meta.group as string | undefined
  if (group) list.push({ label: group })
  const parent = route.meta.parent as string | undefined
  if (parent) {
    const parentRoute = router.resolve(parent)
    list.push({ label: String(parentRoute.meta.title ?? ''), to: parent })
  }
  list.push({ label: String(route.meta.title ?? '') })
  return list
})

// 全局搜索：覆盖 Agent、工作流、设备与人员名称，点击结果跳转
const keyword = ref('')
const open = ref(false)
const results = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return []
  const hits: { key: string; label: string; sub: string; to: string; kind: string }[] = []
  for (const a of workspace.state.agents) {
    if (a.name.toLowerCase().includes(q)) hits.push({ key: a.id, label: a.name, sub: 'Agent', to: `/agents/${a.id}`, kind: 'agent' })
  }
  for (const w of workspace.state.workflows) {
    if (w.name.toLowerCase().includes(q)) hits.push({ key: w.id, label: w.name, sub: '工作流', to: `/workflows/${w.id}`, kind: 'wf' })
  }
  for (const e of workspace.state.equipment) {
    if (e.equipName.toLowerCase().includes(q) || e.equipId.toLowerCase().includes(q)) {
      hits.push({ key: e.id, label: e.equipName, sub: `设备 ${e.equipId}`, to: `/equipment/${e.id}`, kind: 'equip' })
    }
  }
  for (const p of workspace.state.persons) {
    if (p.name.toLowerCase().includes(q) || p.empNo.toLowerCase().includes(q)) {
      hits.push({ key: p.id, label: p.name, sub: `人员 ${p.empNo}`, to: `/persons/${p.id}`, kind: 'person' })
    }
  }
  return hits.slice(0, 8)
})

function go(to: string) {
  open.value = false
  keyword.value = ''
  router.push(to)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
  if (e.key === 'Enter' && results.value[0]) go(results.value[0].to)
}

watch(() => route.path, () => { open.value = false })

const quickAction = computed(() => {
  if (route.path.startsWith('/equipment')) return { label: '新增设备', to: '/equipment?create=1' }
  if (route.path.startsWith('/workflows')) return { label: '新建工作流', to: '/workflows?create=1' }
  return { label: '新建 Agent', to: '/agents?create=1' }
})
</script>

<template>
  <header class="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-surface px-4 md:px-7">
    <button
      type="button"
      class="btn-ghost h-8 w-8 p-0 md:hidden"
      aria-label="打开导航菜单"
      @click="emit('open-mobile')"
    >
      <Menu class="size-4" />
    </button>

    <!-- 面包屑 -->
    <nav aria-label="面包屑" class="flex min-w-0 items-center gap-1.5 text-[13px]">
      <template v-for="(c, i) in crumbs" :key="i">
        <ChevronRight v-if="i > 0" class="size-3.5 shrink-0 text-ink-3" aria-hidden="true" />
        <RouterLink v-if="c.to" :to="c.to" class="truncate text-ink-2 hover:text-ink">{{ c.label }}</RouterLink>
        <span v-else class="truncate font-medium text-ink" :aria-current="i === crumbs.length - 1 ? 'page' : undefined">
          {{ c.label }}
        </span>
      </template>
    </nav>

    <div class="ml-auto flex items-center gap-2">
      <!-- 全局搜索 -->
      <div class="relative hidden sm:block w-64">
        <label class="sr-only" for="global-search">全局搜索</label>
        <Search class="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
        <input
          id="global-search"
          v-model="keyword"
          class="input pl-8"
          placeholder="搜索 Agent、工作流、设备、人员…"
          autocomplete="off"
          @focus="open = true"
          @blur="open = false"
          @keydown="onKey"
        />
        <div
          v-if="open && keyword.trim()"
          class="absolute right-0 left-0 top-10 panel shadow-lg py-1 max-h-72 overflow-y-auto"
          role="listbox"
        >
          <p v-if="!results.length" class="px-3 py-2 text-[12px] text-ink-3">没有匹配结果</p>
          <button
            v-for="r in results"
            :key="r.kind + r.key"
            type="button"
            role="option"
            class="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-page"
            @mousedown.prevent="go(r.to)"
          >
            <Bot v-if="r.kind === 'agent'" class="size-4 text-ink-3" aria-hidden="true" />
            <Microscope v-else-if="r.kind === 'equip'" class="size-4 text-ink-3" aria-hidden="true" />
            <Users v-else-if="r.kind === 'person'" class="size-4 text-ink-3" aria-hidden="true" />
            <WorkflowIcon v-else class="size-4 text-ink-3" aria-hidden="true" />
            <span class="truncate text-[13px] text-ink">{{ r.label }}</span>
            <span class="ml-auto text-[12px] text-ink-3">{{ r.sub }}</span>
          </button>
        </div>
      </div>

      <RouterLink :to="quickAction.to" class="btn-default hidden md:inline-flex">
        <Plus class="size-4" aria-hidden="true" />{{ quickAction.label }}
      </RouterLink>

      <button type="button" class="btn-ghost h-8 w-8 p-0" aria-label="帮助" title="帮助">
        <CircleHelp class="size-4" aria-hidden="true" />
      </button>
    </div>
  </header>
</template>
