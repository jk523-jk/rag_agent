# 实验室安全与资产治理智能问答平台 · 前端工作台（Nexus AI Workspace）

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

## 构建与部署

```bash
npm run build
```

产物在 `dist/`，是纯静态站点，交给任意静态服务器即可。`/api` 需反向代理到 FastAPI（开发期由 `vite.config.ts` 提供代理，接真实后端时无需改前端代码）。

流式问答走 SSE，反向代理**必须关闭缓冲**，否则回答会攒到结束才一次性吐出：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    add_header X-Accel-Buffering no;
}
```

本地一键起服（前后端一起）在仓库根目录：`python run.py`（或双击 `start.bat`）。
`.\start.ps1` 仍可用，它是 `run.py` 的兼容壳。详见根目录 `重构说明-run.py.md`。

## 目录结构

```text
frontend/src/
├── components/
│   ├── common/      # PageHeader / StatCard / StatusBadge / DataTable / ConfirmDialog / AppDrawer / CodeBlock …
│   ├── layout/      # AppSidebar / AppHeader
│   ├── chat/        # ChatPanel / ChatSessionList / ChatContextPanel / MessageContent
│   ├── workflow/    # 工作流节点画布组件
│   └── forms/       # AgentForm / EquipmentForm
├── layouts/         # AppLayout（统一的侧边导航 + 顶栏 + 内容区）
├── pages/           # 16 个业务页面 + 404
├── router/          # 路由表（导航项与路由一一对应）
├── stores/          # Pinia：workspace / chat / ui
├── services/        # 模拟服务层（mockApi / chatEngine / chatApi / sse）
├── mocks/           # 演示数据（data / labData / trend）
├── types/           # 领域类型定义
├── utils/           # storage / guard / accessDecision / validators / format / nav
└── styles/          # 设计令牌与组件基类
```

## 页面清单

| 路由 | 页面 | 说明 |
|---|---|---|
| `/dashboard` | 工作台 | 设备、校准、资质、借出指标卡，对话趋势图（7/30 天切换）、最近任务、最近活动 |
| `/chat` | AI 对话 | 会话列表 + 聊天区 + 检索上下文面板，流式输出、停止生成、重新生成 |
| `/agents` `/agents/:id` | Agent 管理 / 详情 | 卡片与表格双视图、创建/编辑/复制/启停/删除、测试运行入口 |
| `/reagents` | 药剂管理 | 危化品台账、存放柜、结存（剧毒/易制爆区间化）、领用记录与账物校验 |
| `/equipment` `/equipment/:id` | 设备管理 / 详情 | 设备台账、状态、校准有效期、借还状态与逾期告警、借还历史 |
| `/persons` `/persons/:id` | 人员管理 / 详情 | 人员名录（重名以工号区分）、资质台账、实验室授权、通行记录 |
| `/permits` | 许可管理 | 授权台账 + 交互式三闸判定器（资质闸→授权闸→双人闸） |
| `/access` | 出入管理 | 人员门禁通行记录与设备借还流水，违规进入与逾期未还告警 |
| `/workflows` `/workflows/:id` | 工作流 / 编辑器 | 节点画布（Vue Flow）、节点配置、模拟执行与节点级日志 |
| `/logs` | 运行日志 | 关键词/类型/状态/时间筛选、排序、分页、详情抽屉、导出 |
| `/evaluations` | 评估中心 | 评估总览、测试集管理（含控制类拒绝用例）、评估任务、失败案例 |
| `/settings` | 系统设置 | 通用 / 模型 / 外观 / 数据管理，保存到 LocalStorage |
| `*` | 404 | 兜底页 |

旧路径 `/knowledge` 与 `/retrieval` 重定向到 `/reagents` 与 `/equipment`。

## 模拟数据说明

**所有业务数据均为虚构演示数据，页面上以 `DEMO` / `模拟` 标签明确标注，不代表真实生产数据。**

- `src/mocks/labData.ts`：实验室领域数据（实验室、人员、资质、授权、门禁、台账、领用、设备、借还），
  口径严格对齐后端 `lab_hazmat` 库的种子脚本，含六类边界样本
- `src/mocks/data.ts`：Agent、工作流、日志、评估用例与任务
- `src/mocks/trend.ts`：工作台趋势图数据
- `src/services/mockApi.ts`：统一异步模拟服务（含 `fail` 开关，用于测试错误态与重试）
- `src/services/chatEngine.ts`：对话模拟引擎，按问题关键词返回预设回答并逐字流式输出
- 数据层为**固定演示内容**，不调用任何真实模型、数据库或向量库

### 与后端约定保持一致的几处设计

- **只读边界**：`src/utils/guard.ts` 复刻了后端 `core/guard.py` 的控制类指令预检正则，含「怎么/如何/规定」等咨询词的问法一律放行，避免误杀。借还与归还登记同属控制类，一并拦截
- **三闸判定**：`src/utils/accessDecision.ts` 复刻后端 `access_tools` 的判定，闸序固定为资质闸 → 授权闸 → 双人闸，任一闸未通过即短路；双人闸查不到当日记录时 fail-closed
- **资质以有效期为准**：台账中存在「状态仍是有效、有效期早已过期」的记录（王某的合格证即如此），页面把状态与有效期作为两个独立信号展示
- **剧毒品区间化**：`toInterval()` 与后端 `query_inventory` 的口径一致（下界不低于 5，避免「约 0–5」变相暴露精确值）
- **校准以有效期为准**：设备校准是否过期一律看校准有效期字段，不看状态字段——台账中存在状态仍为「在用」但校准已过期的记录
- **重名以工号区分**：李某 ×2 在名录与判定器中均显示工号，判定器按工号锁定人员

## 数据持久化

LocalStorage 三个键，均带 `version` 字段。`nexus-workspace` 当前为 **version 2**
（实验室管理重构后结构变更，旧版存档自动回退为演示数据）：

| 键 | 内容 |
|---|---|
| `nexus-workspace` | Agent、工作流、评估、日志、实验室领域数据（实验室/人员/资质/授权/门禁/台账/领用/设备/借还）、系统配置 |
| `nexus-chat` | 会话与消息历史 |
| `nexus-ui` | 界面偏好（导航折叠状态） |

数据损坏或版本不兼容时自动回退为演示数据；「系统设置 → 数据管理」可导出或重置。

## 已完成的验收清单

- [x] 16 条导航路由全部可访问，无失效地址，无空白占位页；旧 `/knowledge`、`/retrieval` 正确重定向
- [x] Agent 可创建、编辑、复制、启用/停用、删除（删除二次确认）
- [x] 药剂管理：台账搜索与筛选、结存展示、领用明细、账物校验；剧毒/易制爆数量区间化
- [x] 设备管理：台账增删改（表单校验）、状态与校准到期高亮、借出与逾期告警、借还历史
- [x] 人员管理：名录搜索筛选、重名以工号区分并显式提示、资质状态与有效期分列、授权与通行记录
- [x] 许可管理：授权台账筛选 + 交互式三闸判定器，输出四类结论与逐闸依据
- [x] 出入管理：人员门禁与设备借还双 Tab，双人准入违规与逾期未还告警
- [x] 对话支持多轮消息、会话增删改查、复制回答、重新生成、停止生成、清空会话
- [x] 工作流可添加/拖动/删除节点、编辑参数、连线、保存发布、模拟运行，并展示节点级输入输出与失败详情
- [x] 日志可搜索、筛选、排序、分页、查看详情、复制任务 ID 与错误信息、导出当前记录
- [x] 评估中心可管理测试集、启动模拟评估、查看指标与失败案例
- [x] 设置可修改、保存、恢复默认值、重置演示数据
- [x] 侧边栏可折叠（64px 图标栏，带 Tooltip），移动端为抽屉菜单
- [x] 全局搜索覆盖 Agent、工作流、设备、人员并可跳转
- [x] 危险操作均有二次确认；状态不只靠颜色区分（图标 + 文字）
- [x] `vue-tsc` 类型检查通过；`npm test` 32 项通过；`npm run build` 构建成功
- [x] 响应式：≥1280px 完整布局 / 768–1279px 折叠与两列 / <768px 单列与抽屉

## 已知限制

- 不解析真实 PDF / Word / Excel
- 不调用真实模型与向量库，Token 消耗与耗时均为演示值
- 不要求也不保存任何 API Key
- 外观设置当前仅支持浅色模式
- 实验室领域数据为前端演示数据；后端的设备查询走 Agent 工具，尚未提供 REST 接口
- 「设置许可」「出入管理」「设备借还」均为只读展示与判定模拟，不写入任何真实数据

## 接入真实后端

前端已按开发文档 §8 的接口契约实现了真实调用路径：`src/services/chatApi.ts` 解析 `POST /api/chat/stream` 的 SSE 流，`src/services/sse.ts` 负责分包拼接。切换到后端模式只需设置 `VITE_API_MODE=backend`，页面组件无需改动。

仍为模拟的部分（接后端时需逐步替换）：`mockApi.ts` 中的工作流运行与评估，以及 `chatEngine.ts` 的模拟回答。SSE 必须用 `fetch` 而非 `EventSource`（后者只支持 GET，带不了 `thread_id`）。

后端的设备查询已通过 `query_equipment` / `check_equipment_loan` / `list_calibration_due` 三个只读工具提供，
目前经 AI 对话调用；若要让设备管理页直连真实数据，需在后端新增 REST 端点后替换 `mocks/labData.ts`。
