<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { PanelLeftClose, PanelLeftOpen, X, CircleUser } from 'lucide-vue-next'
import { NAV_GROUPS } from '@/utils/nav'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'

defineProps<{ mobileOpen: boolean }>()
const emit = defineEmits<{ (e: 'close-mobile'): void }>()

const route = useRoute()
const ui = useUiStore()
const workspace = useWorkspaceStore()

const collapsed = computed(() => ui.prefs.sidebarCollapsed)
const isActive = (path: string) => route.path === path || route.path.startsWith(`${path}/`)
</script>

<template>
  <div
    v-if="mobileOpen"
    class="fixed inset-0 z-30 bg-ink/30 md:hidden"
    aria-hidden="true"
    @click="emit('close-mobile')"
  />
  <aside
    :class="[
      'fixed inset-y-0 left-0 z-40 flex flex-col bg-surface border-r border-line transition-[width,transform] duration-200',
      collapsed ? 'md:w-16' : 'md:w-60',
      mobileOpen ? 'translate-x-0 w-60' : '-translate-x-full md:translate-x-0',
    ]"
    aria-label="主导航"
  >
    <!-- 品牌区 -->
    <div class="flex h-14 items-center gap-2.5 px-4 border-b border-line">
      <RouterLink to="/dashboard" class="flex items-center gap-2.5 min-w-0" aria-label="返回工作台">
        <span class="grid size-7 shrink-0 place-items-center rounded-[6px] bg-brand text-white text-[13px] font-semibold">N</span>
        <span v-show="!collapsed || mobileOpen" class="min-w-0 leading-tight">
          <span class="block text-[14px] font-semibold text-ink">Nexus AI</span>
          <span class="block text-[12px] text-ink-2">Workspace</span>
        </span>
      </RouterLink>
      <button
        v-if="mobileOpen"
        type="button"
        class="btn-ghost ml-auto h-8 w-8 p-0 md:hidden"
        aria-label="关闭导航"
        @click="emit('close-mobile')"
      >
        <X class="size-4" />
      </button>
    </div>

    <!-- 导航 -->
    <nav class="flex-1 overflow-y-auto px-2 py-3 space-y-4">
      <div v-for="group in NAV_GROUPS" :key="group.title">
        <p v-show="!collapsed || mobileOpen" class="px-2 mb-1 text-[12px] text-ink-3">{{ group.title }}</p>
        <ul class="space-y-0.5">
          <li v-for="item in group.items" :key="item.path">
            <RouterLink
              :to="item.path"
              :title="collapsed && !mobileOpen ? item.label : undefined"
              :aria-current="isActive(item.path) ? 'page' : undefined"
              :class="[
                'group flex h-9 items-center gap-2.5 rounded-[var(--radius-control)] px-2.5 text-[13px] transition-colors',
                isActive(item.path)
                  ? 'bg-brand-soft text-brand font-medium'
                  : 'text-ink-2 hover:bg-page hover:text-ink',
              ]"
              @click="emit('close-mobile')"
            >
              <component :is="item.icon" class="size-4 shrink-0" aria-hidden="true" />
              <span v-show="!collapsed || mobileOpen" class="truncate">{{ item.label }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>
    </nav>

    <!-- 底部：工作区、模拟标签、用户 -->
    <div class="border-t border-line p-3 space-y-2">
      <div v-show="!collapsed || mobileOpen" class="flex items-center justify-between gap-2">
        <span class="truncate text-[12px] text-ink-2">{{ workspace.state.settings.workspaceName }}</span>
        <span class="mock-tag shrink-0" title="当前为前端模拟环境，数据不是真实生产数据">DEMO</span>
      </div>
      <div class="flex items-center gap-2.5">
        <CircleUser class="size-7 text-ink-3 shrink-0" aria-hidden="true" />
        <div v-show="!collapsed || mobileOpen" class="min-w-0 leading-tight">
          <p class="truncate text-[13px] text-ink">安全员（演示）</p>
          <p class="truncate text-[12px] text-ink-3">只读权限</p>
        </div>
      </div>
      <button
        type="button"
        class="btn-ghost w-full hidden md:inline-flex"
        :aria-label="collapsed ? '展开导航' : '收起导航'"
        @click="ui.toggleSidebar"
      >
        <PanelLeftOpen v-if="collapsed" class="size-4" />
        <PanelLeftClose v-else class="size-4" />
        <span v-show="!collapsed">收起导航</span>
      </button>
    </div>
  </aside>
</template>
