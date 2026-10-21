<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { PanelLeftClose, PanelLeftOpen, X, CircleUser } from 'lucide-vue-next'
import { NAV_GROUPS } from '@/utils/nav'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import { auth, logout } from '@/services/auth'

defineProps<{ mobileOpen: boolean }>()
const emit = defineEmits<{ (e: 'close-mobile'): void }>()

const route = useRoute()
const ui = useUiStore()
const workspace = useWorkspaceStore()

const collapsed = computed(() => ui.prefs.sidebarCollapsed)
const isActive = (path: string) => route.path === path || route.path.startsWith(`${path}/`)
const environmentLabel = computed(() => ({
  mock: '未连接',
  loading: '连接中',
  mysql: '数据已更新',
  error: '数据连接异常',
}[workspace.dataSource]))
const userLabel = computed(() => auth.user?.displayName ?? '')
const groups = computed(() => NAV_GROUPS.map(g => ({...g,items:g.items.filter(i => auth.user?.systemAdmin || ['/dashboard','/reagents','/equipment','/persons','/permits','/applications','/access'].includes(i.path))})).filter(g=>g.items.length))
async function exit() { try { await logout() } catch (e) { ui.toast((e as Error).message, 'error') } }
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
      <RouterLink to="/dashboard" class="flex items-center gap-2.5 min-w-0" aria-label="实验室智能管理agent · 返回工作台">
        <!-- 品牌标记：一枚未闭合的圆相（円相），比实心字母更接近水墨气质 -->
        <svg viewBox="0 0 32 32" class="size-7 shrink-0" aria-hidden="true">
          <path
            d="M22.5 6.4C18 3.1 11.2 3.6 7.3 8.1 3 13.1 3.9 21 9.4 24.6c5.2 3.4 12.6 2 15.6-3.3 1.6-2.9 1.4-6.4-.4-9.1"
            fill="none"
            stroke="#1a1a1a"
            stroke-width="2.1"
            stroke-linecap="round"
            stroke-opacity="0.86"
          />
          <path
            d="M25.4 12.6c1.3 3.4.6 7.3-1.9 10"
            fill="none"
            stroke="#1a1a1a"
            stroke-width="3.4"
            stroke-linecap="round"
            stroke-opacity="0.22"
          />
        </svg>
        <span v-show="!collapsed || mobileOpen" class="min-w-0 leading-tight">
          <span class="block truncate text-[14px] font-medium text-ink">实验室智能管理</span>
          <span class="block text-[11px] tracking-[0.18em] text-ink-3">AGENT</span>
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
      <div v-for="group in groups" :key="group.title">
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

    <!-- 底部：工作区、环境状态、用户 -->
    <div class="border-t border-line p-3 space-y-2">
      <div class="flex items-center justify-between gap-2">
        <span v-show="!collapsed || mobileOpen" class="truncate text-[12px] text-ink-2">{{ workspace.state.settings.workspaceName }}</span>
        <span
          class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium"
          :class="workspace.dataSource === 'mock' ? 'mock-tag' : workspace.dataSource === 'error' ? 'bg-err-soft text-err' : 'bg-info-soft text-info'"
          :title="workspace.dataSource === 'mysql' ? `数据读取于 ${workspace.serverTime}` : workspace.dataError"
        >{{ environmentLabel }}</span>
      </div>
      <div class="flex items-center gap-2.5">
        <CircleUser class="size-7 text-ink-3 shrink-0" aria-hidden="true" />
        <div v-show="!collapsed || mobileOpen" class="min-w-0 leading-tight">
          <p class="truncate text-[13px] text-ink">{{ userLabel }}</p>
          <p class="truncate text-[12px] text-ink-3">{{ auth.user?.systemAdmin ? '系统管理员' : '实验室管理员' }}</p>
        </div>
      </div>
      <div class="flex gap-2 flex-wrap" v-show="!collapsed || mobileOpen"><RouterLink to="/portal" class="btn-ghost">个人门户</RouterLink><button class="btn-ghost" @click="exit">退出登录</button></div>
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
