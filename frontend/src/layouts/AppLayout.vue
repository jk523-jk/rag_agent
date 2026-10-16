<script setup lang="ts">
import { ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppToast from '@/components/common/AppToast.vue'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const ui = useUiStore()
const workspace = useWorkspaceStore()
const mobileOpen = ref(false)
watch(() => route.path, () => { mobileOpen.value = false })

// 信息密度偏好写到 <html data-density>，由 main.css 统一生效
watchEffect(() => {
  document.documentElement.dataset.density = workspace.state.settings.appearance?.density ?? 'comfortable'
})
</script>

<template>
  <div class="min-h-full">
    <AppSidebar :mobile-open="mobileOpen" @close-mobile="mobileOpen = false" />
    <div
      :class="[
        'flex min-h-screen flex-col transition-[padding] duration-200',
        ui.prefs.sidebarCollapsed ? 'md:pl-16' : 'md:pl-60',
      ]"
    >
      <AppHeader @open-mobile="mobileOpen = true" />
      <main class="flex-1 min-w-0 px-4 py-6 md:px-7">
        <div class="mx-auto w-full max-w-[1280px]">
          <RouterView v-slot="{ Component }">
            <Transition name="fade" mode="out-in">
              <component :is="Component" :key="route.fullPath" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>
    <AppToast />
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.12s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
