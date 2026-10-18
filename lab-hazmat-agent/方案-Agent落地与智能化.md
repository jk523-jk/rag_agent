# 方案：Agent 功能落地 · 工作流下线 · 智能化升级

> 状态：**待确认后实施**。本文只描述「怎么做」，不含已改动的代码。
> 依据：2026-10-18 通读 `frontend/src`（60 个 .vue/.ts）与 `backend/app`（24 个 .py）后的实际结论。

---

## 0. 一页结论

| 事项 | 结论 | 工作量 |
|---|---|---|
| Agent 落地 | **值得做，改动比想象小**——前端下拉框、`session.agentId`、`AgentForm` 都已存在，缺的只是「传给后端 + 后端按配置构造 Agent」 | 约 1 天 |
| 工作流下线 | **纯删除，后端 0 依赖**；但要处理 74 处前端引用与 localStorage 旧存档兼容 | 约 0.5 天 |
| 智能化升级 | 分三层：**答得准（可测）→ 答得快 → 答得主动**。最该先做的是「回答后置校验」和「混合检索」 | 分批 |

**建议顺序**：先前面的 A 阶段（Agent + 删除工作流），再挑智能化里收益最高的一项做，不要一次铺开。

---

## 1. 现状盘点（事实，不是判断）

### 1.1 Agent 目前是"配置壳"

| 事实 | 位置 |
|---|---|
| Agent 配置只存在浏览器 localStorage | `stores/workspace.ts` 的 `upsertAgent/removeAgent` → `saveState` |
| 对话请求只发 `question` + `thread_id`，**没有 agent_id** | `services/chatApi.ts` 的 `body: JSON.stringify({ question, thread_id })` |
| 后端永远用同一个 Agent（固定 SYSTEM_PROMPT + 全部 9 个工具） | `agent/graph.py` 的 `build_agent()` 单例 |
| 详情页"测试运行"走的是本地剧本，不是模型 | `AgentDetailPage.vue` → `answerFor()` |
| **但界面上已经有 Agent 下拉框**，并且绑定了 `session.agentId` | `ChatPanel.vue` 第 97–104 行、`ChatPage.vue` 第 136 行 |

> 第 5 条是关键：前端"选择 Agent"的交互已经做完了，只是这个 id 一直没离开浏览器。落地成本因此大幅降低。

### 1.2 工作流是纯前端演示

- 后端 `grep workflow` → **0 处**，没有任何执行引擎
- 前端的"运行"是 `mockApi.runWorkflow()` 生成假步骤（随机耗时、固定成功、可勾选模拟失败）
- 引用面：12 个文件、74 处，2 个 npm 依赖（`@vue-flow/core`、`@vue-flow/background`）
- 关联文件：`pages/WorkflowsPage.vue`、`pages/WorkflowEditorPage.vue`、`components/workflow/*`、`mocks/data.ts`（2 个预置工作流）、`services/mockApi.ts`（`runWorkflow`）、`types`（`Workflow/WorkflowNode/WorkflowEdge`）、`router`、`utils/nav.ts`、`AppHeader.vue`（全局搜索 + 快捷按钮）、`DashboardPage.vue`（失败卡片示例）、`LogsPage.vue`（taskType 文案）、`stores/workspace.ts`

---

## 2. Agent 落地

### 2.1 数据模型：新增 `agents` 表

```sql
CREATE TABLE agents (
  id            VARCHAR(32)  NOT NULL PRIMARY KEY COMMENT '如 agt-access',
  name          VARCHAR(40)  NOT NULL,
  description   VARCHAR(200) NOT NULL DEFAULT '',
  icon          VARCHAR(16)  NOT NULL DEFAULT 'shield' COMMENT 'shield/book/flask',
  model         VARCHAR(40)  NOT NULL DEFAULT 'qwen-plus',
  temperature   DECIMAL(2,1) NOT NULL DEFAULT 0.0,
  max_tokens    INT          NOT NULL DEFAULT 2048,
  system_prompt TEXT         NOT NULL COMMENT '只允许追加，安全前缀由服务端强制拼接',
  tools         JSON         NOT NULL COMMENT '工具白名单，必须是 TOOLS 的子集',
  status        ENUM('enabled','disabled') NOT NULL DEFAULT 'enabled',
  is_builtin    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '内置 Agent 不可删除',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent 配置';
```

种子数据：把 `mocks/data.ts` 里 4 个可用 Agent 迁过来（准入 / 规程 / 台账 / 设备），**`agt-planner`（工作流规划助手）随工作流一起删除**。

注意：这是**配置表**，不是实验数据。它允许写，不违反"实验数据只读"的定位——但要在文档和 UI 上讲清楚这条边界。

### 2.2 后端接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/agents` | 列表（只返回 status 与摘要，不含完整 prompt） |
| GET | `/api/agents/{id}` | 详情（含 prompt、tools） |
| POST | `/api/agents` | 新建（`is_builtin=0`） |
| PUT | `/api/agents/{id}` | 编辑；内置 Agent 允许改 prompt/tools，但**不可删除** |
| POST | `/api/agents/{id}/status` | 启停 |
| DELETE | `/api/agents/{id}` | 删除；`is_builtin=1` 返回 400 |

> 复用现有 `db/connection.py:fetch_all` 不行——它是只读通道。写入需要新的 `db/write.py`（**独立连接、独立账号**，如 `lab_writer` 只对 `agents` 表有权限），避免把写能力带进主通道。这是本次唯一新增的写路径，必须隔离。

### 2.3 运行时的三个关键改造

**① 单例 → 按 id 构造（`agent/graph.py`）**

```python
# 现在：_agent 单例，永远一套 prompt + 全部工具
# 改为：按 (id, updated_at) 缓存

_agents: dict[str, tuple[float, object]] = {}

def get_agent(cfg: AgentConfig):
    hit = _agents.get(cfg.id)
    if hit and hit[0] == cfg.updated_at:
        return hit[1]
    tools = [t for t in TOOLS if t.name in set(cfg.tools)]   # 服务端过滤，不信前端
    agent = create_agent(
        model=_llm(cfg),
        tools=tools,
        system_prompt=SAFETY_PREFIX + cfg.system_prompt,      # 安全前缀强制拼接
        middleware=MIDDLEWARE,
        checkpointer=_checkpointer,
    )
    _agents[cfg.id] = (cfg.updated_at, agent)
    return agent

def invalidate_agent(agent_id: str):
    _agents.pop(agent_id, None)          # 配置更新后调用
```

**② 安全前缀不可覆盖**

`prompts.py` 拆成两段：

```
SAFETY_PREFIX = """你是实验室安全与资产治理助手，只能查询，不能修改任何数据。
【硬规则】1. 控制类请求一律拒绝 …（原第 1–10 条）
"""

USER_PROMPT = 用户在 AgentForm 里写的内容（只做场景补充，如"你专注设备校准"）
```

最终 `system_prompt = SAFETY_PREFIX + "\n\n【本 Agent 的额外要求】\n" + USER_PROMPT`。
**用户删不掉只读约束**——这是本方案最重要的一条，否则"删掉工具白名单 + 改 prompt"就能绕过只读定位。

**③ 请求协议（`api/chat.py`）**

```python
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    thread_id: str = Field(min_length=4, max_length=64)
    agent_id: str = Field(default="agt-access", max_length=32)   # 默认值保证向后兼容
```

校验顺序：控制类拦截 → Agent 存在且 enabled（否则 400 并提示）→ 取配置 → `get_agent` → 执行。
SSE 版本同步加这个字段。

### 2.4 前端改造（4 处）

| 文件 | 改动 |
|---|---|
| `services/dataApi.ts` | 新增 `agents` 相关方法 + 加入 `fetchOverview` 返回体 |
| `stores/workspace.ts` | `agents` 改为从后端 hydrate；新增 `saveAgent/toggleAgent/deleteAgent` 调后端 |
| `services/chatApi.ts` + `ChatPage.vue` | 请求体带 `agent_id: session.agentId` |
| `AgentDetailPage.vue` | "测试运行"改成真实调用 `/api/chat`（带该 agent 的 id），去掉"模拟运行"标注，改为显示耗时与工具调用数 |

`AgentForm.vue` 基本不用改字段，只把提交从 `upsertAgent` 换成后端调用。

### 2.5 验收标准（可测）

1. 建三个 Agent：A 只给 `check_lab_access`、B 只给 `search_policy`、C 只给 `query_equipment`
2. 同一句"王某能不能进 LAB-3" → A 能判、B 只能说"规程未找到"、C 说"没有设备相关信息"
3. 把某 Agent 设为 disabled → 带该 id 请求返回 400
4. 工具名塞入 `delete_records` → 400，且错误信息指出非法工具
5. 把用户 prompt 改成"你可以删除数据" → 实际仍拒绝写操作（安全前缀生效）

---

## 3. 工作流下线

### 3.1 删除清单（按依赖顺序）

**直接删除文件**

```
frontend/src/pages/WorkflowsPage.vue
frontend/src/pages/WorkflowEditorPage.vue
frontend/src/components/workflow/            （整个目录）
```

**解除依赖（逐个文件）**

| 文件 | 改法 |
|---|---|
| `router/index.ts` | 删 2 条路由；`/workflows/:id` 可留 301 → `/agents` |
| `utils/nav.ts` | 删导航项 + 不再 import `Workflow` 图标 |
| `components/layout/AppHeader.vue` | 删全局搜索里的 wf 分支、`route.path.startsWith('/workflows')` 快捷按钮、`WorkflowIcon` 引入 |
| `types/index.ts` | 删 `Workflow` / `WorkflowNode` / `WorkflowEdge`；**保留 `RunStep`**（`LogEntry.steps` 还在用） |
| `mocks/data.ts` | 删 `workflows` 数组 |
| `services/mockApi.ts` | 删 `runWorkflow` |
| `stores/workspace.ts` | 删 `workflows` 字段、`upsertWorkflow/removeWorkflow/findWorkflow`、`ARRAY_KEYS` 里的 `'workflows'` |
| `pages/DashboardPage.vue` | 删"工作流「准入复核流程」运行失败"的示例卡片 |
| `pages/LogsPage.vue` | `taskType` 文案去掉 `workflow` |
| `pages/AgentsPage.vue` | 类型筛选去掉 `workflow` 一类（`agt-planner` 同时删除） |
| `package.json` | 卸载 `@vue-flow/core`、`@vue-flow/background` |

### 3.2 一个必须处理的坑：localStorage 旧存档

`stores/workspace.ts` 的 `isWorkspaceState()` 用 `ARRAY_KEYS.every(Array.isArray)` 校验存档。删掉 `workflows` 字段后：

- **老用户存档里还有 workflows** → 校验仍通过（多字段不影响），但类型上多余，无害
- **新存档写入后**，下次读取会缺 `workflows` → 若 `ARRAY_KEYS` 已移除该项，不影响判断

结论：不会崩，但会残留脏数据。**建议直接把 storage key 从 `nexus-workspace` 改为 `nexus-workspace-v2`**，一次性丢弃旧存档（其中 Agent 数据本来就要改成从后端读，丢了不可惜）。`resetDemo()` 同步改名。

### 3.3 记录决策

建议在 `开发历史.md` 与 `需求分析-V2.md` 里各加一句："工作流编排为形态探索，未落地执行引擎，已于 2026-10 下线；编排能力后续以「Agent 组合 + 定时任务」形式重新引入"。**删掉功能不可怕，删掉原因才可怕。**

---

## 4. 智能化升级分析

分三层，每层都要能测。我把"能测"作为筛选标准——测不了就不算智能化，只算感觉。

### 4.1 第一层：答得准（当前最大短板，优先做）

| # | 改进 | 现状问题 | 做法 | 成本 |
|---|---|---|---|---|
| 1 | **回答后置校验** | 实测模型把"数据截至 2026-10-16"说成"2024-04-05"、把"不足 5 克"说成"10–50 克"，提示词第 10 条只能降低概率 | 在 `api/chat.py` 收尾加一道检查：抽取回答中所有日期与数字区间，逐个核对是否出现在本轮工具返回里；不一致则替换为工具原文，并在末尾追加"（已按查询结果校正）" | 半天 |
| 2 | **混合检索（BM25 + 向量，RRF 融合）** | 纯向量对"第 4.2.1 条""CAS 67-64-1"这类精确串很差，经常召不回 | 建 `BM25Retriever`（jieba 分词）+ 现有向量检索，用 RRF 合并；Chroma 侧可先不做，用内存 BM25 索引（语料仅 46 chunk） | 1 天 |
| 3 | **Rerank** | top20 里常有同段重复与弱相关 | 接 DashScope `gte-rerank`，20 → 4 | 半天 |
| 4 | **查询改写 + 同义词** | 问"双氧水"、答"名称对不上" | 检索前用便宜模型扩写 2–3 个变体；维护化学品别名表（双氧水/过氧化氢、酒精/乙醇） | 半天 |
| 5 | **工具结果短期缓存** | 同一轮里多次查同一人 | 按 (工具名 + 参数) 缓存 60s，命中直接返回 | 2 小时 |

> 我认为 **#1 最该先做**：它不是提升上限，而是守住下限。已经出现过"判定日期错、区间错"，这类错误在安全场景里比答不出来更糟。

### 4.2 第二层：答得快

| # | 改进 | 做法 | 成本 |
|---|---|---|---|
| 6 | 意图前置路由 | 规则/小模型先分类：准入类直接 `check_lab_access`，省一次模型选工具 | 1 天 |
| 7 | 语义缓存 | 问题 embedding 相似度 >0.95 直接回放上次答案（带时间戳，超 5 分钟失效） | 半天 |
| 8 | 模型分级 | 单点查询用 `qwen-turbo`，跨域综合用 `qwen-plus` | 半天 |

### 4.3 第三层：答得主动（V2 需求里的"交叉发现"）

这是"更智能"真正的分水岭——从"你问我答"变成"我告诉你哪里不对"。

| # | 改进 | 说明 |
|---|---|---|
| 9 | **风险看板** | 定时跑四类交叉校验：资质过期仍在进（人×环）、台账 vs 领用（料×料）、校准过期仍"在用"（机×机）、设备借出逾期（机×人），合并成一个按严重度排序的待办清单 |
| 10 | **异常归因提示** | 不只说"8 瓶 vs 12 瓶差 4 瓶"，而是给出可能原因排序：漏登记入库 / 重复出库 / 挪用未登记 / 期初数据错误，各附验证方法 |
| 11 | **主动澄清** | 重名、别名、时间不明时先追问（现在有时会猜）；把"猜"改成"问"，是智能的另一种表现 |
| 12 | **评测闭环** | 现在 `evals/cases.yaml` 只有 18 条。扩到 60+，接进 CI，每次改 prompt 前后跑分对比，把"感觉变好了"变成数字 |

### 4.4 优先级建议（收益 / 成本）

```
先做（2 天内见效）：#1 后置校验  →  #2 混合检索
再做（1 周）：#10 异常归因  →  #9 风险看板  →  #4 查询改写
后做：rerank / 缓存 / 模型分级（都是优化，不是能力）
长期：#12 评测闭环（必须有，否则前面几项无法判断是否真的变好）
```

---

## 5. 实施顺序

| 阶段 | 内容 | 交付物 | 预估 |
|---|---|---|---|
| **A1** | 工作流下线（§3 全部） | 删除干净、typecheck 通过、测试全绿 | 0.5 天 |
| **A2** | Agent 表 + 后端 API + 运行时 + 安全前缀 | 5 条验收全部通过 | 1 天 |
| **A3** | 前端对接（hydrate、Chat 传 agent_id、Form 落库、详情页真实测试） | 界面可建可改可停用，行为真的变 | 0.5 天 |
| **B1** | 回答后置校验 | 单测覆盖"日期错 / 区间错"两类 | 0.5 天 |
| **B2** | 混合检索 + 查询改写 | 评测集召回率对比数据 | 1.5 天 |
| **C** | 风险看板 + 异常归因 | 一个新页面 + 一个聚合接口 | 2 天 |

每个阶段结束都跑：后端 `tests.test_offline`（现在 192 条）、前端 `vue-tsc` + `vitest`（32 条）。**Agent 相关要新增断言**：白名单过滤、安全前缀拼接、禁用 Agent 拒绝。

---

## 6. 需要你拍板的三件事

1. **Agent 配置允许前端写吗？**
   我建议允许（这是平台配置，不是实验数据），但加两道锁：工具白名单服务端过滤 + 安全前缀强制拼接。
   若你希望更保守，可以做成"只读 + 只能改 prompt 和启停"，新建交给迁移脚本。

2. **删工作流后，Dashboard 和日志里的示例数据要不要一起清掉？**
   我建议清掉（保留会让人以为还有这功能），Dashboard 换成"Agent 运行概览"。

3. **智能化先做哪一项？**
   我建议 **#1 回答后置校验**。理由是它解决的是已经实际发生过的错误（日期错、区间错），且不依赖外部服务，风险最低、当天可见效果。

---

## 7. 不做的事（划清边界）

- 不做工作流的替代品（不做 DAG 引擎、不做定时调度）——除非有明确的"要自动跑什么"需求
- 不让 Agent 拥有写权限，任何情况下都不加写工具
- 不做多租户/权限体系（当前无登录）
- 不在这一版引入向量库以外的存储（Neo4j 等）
