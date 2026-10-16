import type { Component } from 'vue'
import {
  LayoutDashboard, MessagesSquare, Bot, Workflow, FlaskConical, Microscope,
  Users, ShieldCheck, DoorOpen, ScrollText, ClipboardCheck, Settings,
} from 'lucide-vue-next'

export interface NavItem {
  path: string
  label: string
  icon: Component
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

// 导航顺序与设计规范 §3.1 一致，路径必须与 router 中的定义对应。
// 「实验室管理」为本项目重构后的分组：原有「知识与检索」（知识库 / 检索实验室）
// 已被药剂、设备、人员、许可、出入五个管理页面取代。
export const NAV_GROUPS: NavGroup[] = [
  {
    title: '工作空间',
    items: [
      { path: '/dashboard', label: '工作台', icon: LayoutDashboard },
      { path: '/chat', label: 'AI 对话', icon: MessagesSquare },
    ],
  },
  {
    title: 'AI 应用',
    items: [
      { path: '/agents', label: 'Agent 管理', icon: Bot },
      { path: '/workflows', label: '工作流', icon: Workflow },
    ],
  },
  {
    title: '实验室管理',
    items: [
      { path: '/reagents', label: '药剂管理', icon: FlaskConical },
      { path: '/equipment', label: '设备管理', icon: Microscope },
      { path: '/persons', label: '人员管理', icon: Users },
      { path: '/permits', label: '许可管理', icon: ShieldCheck },
      { path: '/access', label: '出入管理', icon: DoorOpen },
    ],
  },
  {
    title: '系统观测',
    items: [
      { path: '/logs', label: '运行日志', icon: ScrollText },
      { path: '/evaluations', label: '评估中心', icon: ClipboardCheck },
    ],
  },
  {
    title: '设置',
    items: [{ path: '/settings', label: '系统设置', icon: Settings }],
  },
]

export const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items)
