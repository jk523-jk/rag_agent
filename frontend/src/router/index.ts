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
    { path: '/workflows', name: 'workflows', component: () => import('@/pages/WorkflowsPage.vue'), meta: { title: '工作流', group: 'AI 应用' } },
    { path: '/workflows/:id', name: 'workflow-editor', component: () => import('@/pages/WorkflowEditorPage.vue'), meta: { title: '工作流编辑器', group: 'AI 应用', parent: '/workflows' } },
    { path: '/knowledge', name: 'knowledge', component: () => import('@/pages/KnowledgePage.vue'), meta: { title: '知识库', group: '知识与检索' } },
    { path: '/knowledge/:id', name: 'knowledge-detail', component: () => import('@/pages/KnowledgeDetailPage.vue'), meta: { title: '知识库详情', group: '知识与检索', parent: '/knowledge' } },
    { path: '/retrieval', name: 'retrieval', component: () => import('@/pages/RetrievalPage.vue'), meta: { title: '检索实验室', group: '知识与检索' } },
    { path: '/logs', name: 'logs', component: () => import('@/pages/LogsPage.vue'), meta: { title: '运行日志', group: '系统观测' } },
    { path: '/evaluations', name: 'evaluations', component: () => import('@/pages/EvaluationsPage.vue'), meta: { title: '评估中心', group: '系统观测' } },
    { path: '/settings', name: 'settings', component: () => import('@/pages/SettingsPage.vue'), meta: { title: '系统设置', group: '设置' } },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/pages/NotFoundPage.vue'), meta: { title: '页面不存在' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  document.title = `${(to.meta.title as string) ?? 'Nexus AI'} · 危化品准入 Workspace`
})

export default router
