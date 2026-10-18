import { createRouter, createWebHistory } from 'vue-router'

// 路由与导航一一对应；所有导航项必须指向已存在的页面（见设计规范 §3.1）
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'dashboard', component: () => import('@/pages/DashboardPage.vue'), meta: { title: '工作台', group: '工作空间' } },
    { path: '/chat', name: 'chat', component: () => import('@/pages/ChatPage.vue'), meta: { title: 'AI 对话', group: '工作空间' } },
    { path: '/agents', name: 'agents', component: () => import('@/pages/AgentsPage.vue'), meta: { title: 'Agent 管理', group: 'AI 应用' } },
    { path: '/agents/:id', name: 'agent-detail', component: () => import('@/pages/AgentDetailPage.vue'), meta: { title: 'Agent 详情', group: 'AI 应用', parent: '/agents' } },
    // 实验室管理：由原「知识与检索」分组重构而来
    { path: '/reagents', name: 'reagents', component: () => import('@/pages/ReagentsPage.vue'), meta: { title: '药剂管理', group: '实验室管理' } },
    { path: '/equipment', name: 'equipment', component: () => import('@/pages/EquipmentPage.vue'), meta: { title: '设备管理', group: '实验室管理' } },
    { path: '/equipment/:id', name: 'equipment-detail', component: () => import('@/pages/EquipmentDetailPage.vue'), meta: { title: '设备详情', group: '实验室管理', parent: '/equipment' } },
    { path: '/persons', name: 'persons', component: () => import('@/pages/PersonsPage.vue'), meta: { title: '人员管理', group: '实验室管理' } },
    { path: '/persons/:id', name: 'person-detail', component: () => import('@/pages/PersonDetailPage.vue'), meta: { title: '人员详情', group: '实验室管理', parent: '/persons' } },
    { path: '/permits', name: 'permits', component: () => import('@/pages/PermitsPage.vue'), meta: { title: '许可管理', group: '实验室管理' } },
    { path: '/access', name: 'access', component: () => import('@/pages/AccessPage.vue'), meta: { title: '出入管理', group: '实验室管理' } },
    { path: '/logs', name: 'logs', component: () => import('@/pages/LogsPage.vue'), meta: { title: '运行日志', group: '系统观测' } },
    { path: '/evaluations', name: 'evaluations', component: () => import('@/pages/EvaluationsPage.vue'), meta: { title: '评估中心', group: '系统观测' } },
    { path: '/settings', name: 'settings', component: () => import('@/pages/SettingsPage.vue'), meta: { title: '系统设置', group: '设置' } },
    // 工作流编排已于 v2.0 下线（未落地执行引擎），旧链接重定向到 Agent 管理
    { path: '/workflows', redirect: '/agents' },
    { path: '/workflows/:id', redirect: '/agents' },
    // 旧书签重定向：原知识库 / 检索实验室已并入实验室管理
    { path: '/knowledge', redirect: '/reagents' },
    { path: '/knowledge/:id', redirect: '/reagents' },
    { path: '/retrieval', redirect: '/equipment' },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/pages/NotFoundPage.vue'), meta: { title: '页面不存在' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  document.title = `${(to.meta.title as string) ?? '实验室智能管理'} · 实验室智能管理agent`
})

export default router
