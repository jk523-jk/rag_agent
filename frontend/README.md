# 实验室危化品准入智能问答系统 · 前端工作台（Nexus AI Workspace）

只读问答 Agent 的前端界面。当前阶段**只做前端**：不连接后端、大模型、MySQL 或向量库，全部业务数据来自本地模拟层。

- 技术栈：Vue 3 + TypeScript + Vite + Tailwind CSS v4 + Vue Router + Pinia + Lucide + Vue Flow + marked + Vitest（趋势图为手写 SVG，不依赖图表库）
- 设计规范：极简工作台风格，配色、圆角、间距与排版按设计要求集中定义在 `src/styles/main.css` 的 CSS 变量中

## 快速开始

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 ，会自动跳转到 `/dashboard`。

其他命令：

```bash
npm run build
```

```bash
npm run preview
```

## 测试与校验

```bash
npm test
```

```bash
npx vue-tsc -b
```

`npm test` 覆盖三类关键逻辑：

- **控制类指令预检**：直接读取 `src/mocks/data.ts` 中的 13 条评测用例，5 条控制类必须拦截，其余咨询/查询类必须放行（与后端 `evals/cases.yaml` 的 `expect_refuse` 对齐）
- **剧毒品区间化**：边界值与“区间不含精确数字”的断言
- **SSE 解析与流式对话**：分包拼接、错误事件、HTTP 失败

## 运行模式

由 `VITE_API_MODE` 决定（见 `.env.example`）：

| 取值 | 行为 | 界面标签 |
|---|---|---|
| `mock`（默认） | 本地模拟引擎，回答为预设内容 | 橙色「模拟模式 · 未连接真实模型」 |
| `backend` | 通过 `fetch` 调用 `POST /api/chat/stream`（SSE） | 绿色「已连接后端服务」 |

后端模式需要先启动 FastAPI 服务；开发时 `/api` 由 Vite 代理到 `http://localhost:8000`。

## Docker 部署

```bash
docker build --build-arg VITE_API_MODE=backend -t lab-hazmat-frontend .
```

镜像内 `nginx.conf` 已对 `/api/` 关闭 `proxy_buffering`，保证流式输出不被攒批。

开发服务器已配置 `/api` 代理到 `http://localhost:8000`，接入真实后端时无需改动前端代码。

## 目录结构

```text
frontend/src/
├── components/
│   ├── common/      # PageHeader / StatCard / StatusBadge / DataTable / ConfirmDialog / AppDrawer / CodeBlock …
│   ├── layout/      # AppSidebar / AppHeader
│   ├── chat/        # ChatPanel / ChatSessionList / ChatContextPanel / MessageContent
│   ├── knowledge/   # DocumentChunkViewer
│   └── forms/       # AgentForm / KnowledgeForm
├── layouts/         # AppLayout（统一的侧边导航 + 顶栏 + 内容区）
├── pages/           # 12 个业务页面 + 404
├── router/          # 路由表（导航项与路由一一对应）
├── stores/          # Pinia：workspace / chat / ui
├── services/        # 模拟服务层（mockApi / chatEngine）
├── mocks/           # 演示数据（data / trend）
├── types/           # 领域类型定义
├── utils/           # storage / guard / validators / format / nav / echarts
└── styles/          # 设计令牌与组件基类
```

## 页面清单

| 路由 | 页面 | 说明 |
|---|---|---|
| `/dashboard` | 工作台 | 4 个指标、对话趋势图（7/30 天切换）、最近任务、最近活动 |
| `/chat` | AI 对话 | 会话列表 + 聊天区 + 检索上下文面板，流式输出、停止生成、重新生成 |
| `/agents` `/agents/:id` | Agent 管理 / 详情 | 卡片与表格双视图、创建/编辑/复制/启停/删除、测试运行入口 |
| `/knowledge` `/knowledge/:id` | 知识库 / 详情 | 四个 Tab（文档 / 分块 / 索引配置 / 处理记录）、上传与模拟处理流程、分块查看器 |
| `/retrieval` | 检索实验室 | 检索流程可视化、BM25 与向量召回对比、重排序前后排名、评估指标、检索历史 |
| `/workflows` `/workflows/:id` | 工作流 / 编辑器 | 节点画布（Vue Flow）、节点配置、模拟执行与节点级日志 |
| `/logs` | 运行日志 | 关键词/类型/状态/时间筛选、排序、分页、详情抽屉、导出 |
| `/evaluations` | 评估中心 | 评估总览、测试集管理（含控制类拒绝用例）、评估任务、失败案例 |
| `/settings` | 系统设置 | 通用 / 模型 / Embedding / 检索 / 外观 / 数据管理，保存到 LocalStorage |
| `*` | 404 | 兜底页 |

## 模拟数据说明

**所有业务数据均为虚构演示数据，页面上以 `DEMO` / `模拟` 标签明确标注，不代表真实生产数据。**

- `src/mocks/data.ts`：Agent、知识库、文档、分块、工作流、日志、评估用例与任务、检索预设结果
- `src/mocks/trend.ts`：工作台趋势图数据
- `src/services/mockApi.ts`：统一异步模拟服务（含 `fail` 开关，用于测试错误态与重试）
- `src/services/chatEngine.ts`：对话模拟引擎，按问题关键词返回预设回答并逐字流式输出
- 数据层为**固定演示内容**，不调用任何真实模型、数据库或向量库

### 与后端约定保持一致的几处设计

- **只读边界**：`src/utils/guard.ts` 复刻了后端 `core/guard.py` 的控制类指令预检正则，含「怎么/如何/规定」等咨询词的问法一律放行，避免误杀
- **剧毒品区间化**：`toInterval()` 与后端 `query_inventory` 的口径一致，精确数量一律换算为区间
- **SDS 不串段**：分块数据中「应急处置」与「储存」严格分列，应急类回答不引用储存要求
- **高亮置顶**：资质过期、授权异常、台账差异、缺见证人会在对话区单独高亮

## 数据持久化

LocalStorage 三个键，均带 `version` 字段（当前为 1）：

| 键 | 内容 |
|---|---|
| `nexus-workspace` | Agent、知识库、文档、分块、工作流、评估、日志、系统配置 |
| `nexus-chat` | 会话与消息历史 |
| `nexus-ui` | 界面偏好（导航折叠状态） |

数据损坏或版本不兼容时自动回退为演示数据；「系统设置 → 数据管理」可导出或重置。

## 已完成的验收清单

- [x] 11 条导航路由全部可访问，无失效地址，无空白占位页
- [x] Agent 可创建、编辑、复制、启用/停用、删除（删除二次确认）
- [x] 知识库可创建、编辑、删除；文档上传校验格式与大小，展示五阶段模拟处理流程，可取消、重试、删除
- [x] 分块查看器支持搜索、展开原文、复制片段，元数据可见
- [x] 对话支持多轮消息、会话增删改查、复制回答、重新生成、停止生成、清空会话
- [x] 检索实验室可切换 BM25 / 向量 / 混合，展示多路召回对比与重排序前后排名变化
- [x] 工作流可添加/拖动/删除节点、编辑参数、连线、保存发布、模拟运行，并展示节点级输入输出与失败详情
- [x] 日志可搜索、筛选、排序、分页、查看详情、复制任务 ID 与错误信息、导出当前记录
- [x] 评估中心可管理测试集、启动模拟评估、查看指标与失败案例
- [x] 设置可修改、保存、恢复默认值、重置演示数据
- [x] 侧边栏可折叠（64px 图标栏，带 Tooltip），移动端为抽屉菜单
- [x] 全局搜索覆盖 Agent、知识库、工作流并可跳转
- [x] 危险操作均有二次确认；状态不只靠颜色区分（图标 + 文字）
- [x] `vue-tsc` 类型检查通过；`npm run build` 构建成功；浏览器控制台无报错
- [x] 响应式：≥1280px 完整布局 / 768–1279px 折叠与两列 / <768px 单列与抽屉

## 已知限制

- 不解析真实 PDF / Word / Excel，文档处理为模拟流程，只保留文件元数据
- 不调用真实模型与向量库，检索分数、Token 消耗、耗时均为演示值
- 不要求也不保存任何 API Key
- 外观设置当前仅支持浅色模式
- 后端接口未联调，`/api` 代理已预留

## 接入真实后端

前端已按开发文档 §8 的接口契约实现了真实调用路径：`src/services/chatApi.ts` 解析 `POST /api/chat/stream` 的 SSE 流，`src/services/sse.ts` 负责分包拼接。切换到后端模式只需设置 `VITE_API_MODE=backend`，页面组件无需改动。

仍为模拟的部分（接后端时需逐步替换）：`mockApi.ts` 中的知识库上传、检索、工作流运行与评估，以及 `chatEngine.ts` 的模拟回答。SSE 必须用 `fetch` 而非 `EventSource`（后者只支持 GET，带不了 `thread_id`）。
