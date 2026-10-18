# 重构说明：启动入口收敛到 run.py

> 日期：2026-10-17　范围：仓库根这一层（启动/运行期），不改变业务逻辑

## 1. 为什么做这次重构

改之前，仓库根同时存在三套启动方式，各自实现了一遍「找解释器、装依赖、探数据库、起进程、等就绪」：

| 入口 | 平台 | 问题 |
|---|---|---|
| `start.ps1`（361 行） | 仅 Windows | 逻辑最全，但 PowerShell 把 Python 项目的启动流程又写了一遍；换端口、加子命令都要改两处 |
| `start.bat` | 仅 Windows | 只是 `start.ps1` 的外壳 |
| 手工 `uvicorn ...` + `npm run dev` | 任意 | 文档里给的两条命令，容易忘 `PYTHONPATH` 或工作目录 |

由此带来三个实际故障点：

1. **工作目录是隐式契约。** `.env` 和 `CHROMA_DIR=./corpus/chroma` 都按 CWD 解析，从仓库根或任意目录启动后端时，向量库会静默指向一个空目录——表现为「检索永远为空」，没有任何报错。
2. **前后端端口无法一起改。** `vite.config.ts` 把代理目标写死成 `http://localhost:8000`，`run.py`/`start.ps1` 换后端端口启动时，前端仍在打 8000。
3. **启动脚本不可跨平台、不可测。** 逻辑埋在 PowerShell 里，只能靠手工点一遍来验证。

## 2. 改了什么

### 2.1 新增 `run.py`：唯一启动入口

只用标准库（`argparse / subprocess / socket / urllib / threading`），Windows 与 Linux/macOS 通用。

```
python run.py                  # 后端 + 前端，Ctrl+C 一起停
python run.py backend          # 只后端   （--reload / --db-check / --no-install）
python run.py frontend         # 只前端   （--api-mode mock|backend）
python run.py stop             # 停掉 8000 / 5173 上的进程
python run.py status           # 端口 + /api/health + MySQL + LLM 状态
python run.py check            # 环境自检，不启动服务
python run.py db-check         # scripts.db_check 分层自检
python run.py init-db          # scripts.init_db 建表灌数
python run.py ingest           # app.rag.ingest 重建向量索引
python run.py test [guard...]  # 离线回归测试
python run.py build            # 前端生产构建
```

保留原有约束不变：

- 后端工作目录固定 `lab-hazmat-agent/`，用 `uvicorn --app-dir backend` 而非 `cd backend`（否则 `.env` 落错位置）。
- 解释器优先级：`--python` / `LAB_AGENT_PYTHON` → 仓库 `.venv` → conda `agent` 环境 → PATH 上的 `python`。
- 缺依赖时优先在 `.venv` 里装，不污染 conda/系统环境；`--no-install` 可强制报错退出。
- MySQL 不可达不阻断启动（后端 degraded，与 `app/main.py` 的原设计一致）。

新增的运行期能力：

- **进程树回收**：子进程由 Python 统一 `Popen` + 线程转发输出（`[api]` / `[web]` 前缀），任一服务退出即整体收尾；Windows 用 `taskkill /T` 连 npm→node 的子进程一起结束。
- **换端口可用**：`--backend-port` / `--frontend-port` 会同步注入 `VITE_DEV_PORT` / `VITE_API_TARGET`，前端代理跟着走。
- **数据源切换**：`--api-mode mock` 可临时以纯模拟数据起前端，无需改 `frontend/.env`。

### 2.2 `start.ps1` 降级为兼容壳

361 行缩到约 80 行，只做参数翻译后转发给 `run.py`。老用法全部照旧：

```
.\start.ps1                 → python run.py
.\start.ps1 -Reload         → python run.py --reload
.\start.ps1 -BackendOnly    → python run.py backend
.\start.ps1 -Stop           → python run.py stop
.\start.ps1 -Python <path>  → python run.py --python <path>
```

`start.bat` 直接调 `run.py`，找不到 Python 时才回落到 `start.ps1`。

### 2.3 向量库路径改为「按项目根解析」

`app/core/config.py` 新增 `Settings.chroma_path`：

```python
path = Path(self.chroma_dir).expanduser()
return path if path.is_absolute() else (_PROJECT_ROOT / path).resolve()
```

`ingest.py`、`retriever.py`、`health.py`、`main.py` 四处调用点从 `s.chroma_dir` 改为 `s.chroma_path`。

行为变化：`CHROMA_DIR=./corpus/chroma` 现在恒定解析到 `lab-hazmat-agent/corpus/chroma`，无论从哪个目录启动。绝对路径原样使用，容器挂载（`/data/chroma`）不受影响。`.env` 解析依赖 CWD 的部分未改动——`run.py` 已负责把 CWD 固定正确。

### 2.4 Vite 代理可配置

`frontend/vite.config.ts` 改为函数式配置，从环境变量读：

| 变量 | 来源 | 默认 |
|---|---|---|
| `VITE_DEV_PORT` | `run.py --frontend-port` 注入 | 5173 |
| `VITE_API_TARGET` | `run.py --backend-port` 注入 | `http://127.0.0.1:8000` |

同时加 `strictPort: true`：端口被占时直接失败，而不是悄悄换到 5174 导致访问地址对不上。

## 3. 验证记录

| 项 | 命令 | 结果 |
|---|---|---|
| 环境自检 | `python run.py check` | 通过（解释器 conda agent / MySQL 可达 / 7 个建表脚本 / node_modules 就绪） |
| 一键启动 | `python run.py` | 后端 `{"status":"ok","mysql":true}`，前端 `ready`，访问地址正确 |
| 换端口启动 | `python run.py start --backend-port 8010 --frontend-port 5183` | 两端口均就绪，代理指向 8010 |
| 数据源切换 | `--api-mode mock` | 前端以模拟模式启动 |
| 状态 / 停止 | `python run.py status` / `stop` | 端口进程树被完整回收，重复 stop 幂等 |
| 兼容壳 | `powershell -File .\start.ps1 -Stop` | 正确转发 |
| 离线回归 | `python run.py test` | 192/192 通过 |
| 浏览器验证 | Vite 5199 + 后端 8000 | 工作台正常渲染、「实时数据库」徽标、`fetch('/api/health')` 经代理返回 ok，无 console error / 失败请求 |

## 4. 未做的事（刻意保留）

- **没有搬动目录结构。** `lab-hazmat-agent/` 与 `frontend/` 的并列布局被 `.env`、`corpus/`、文档和现有脚本大量引用，收益不足以抵消改动风险。
- **没有删 `start.ps1`。** 既有文档、快捷方式可能还在用；保留薄壳成本远低于改所有引用。
- **没有统一 MySQL 配置的读法。** `run.py` 为了不依赖第三方包自带了一个极简 `.env` 解析器（只读 `MYSQL_HOST/PORT/PASSWORD/LLM_API_KEY` 用于探测与提示），后端仍以 `pydantic-settings` 为准。两者解析同一份文件，不存在第二份真值。
- **没有改前端 `.env` 的默认值。** `frontend/.env` 当前是 `VITE_API_MODE=mock`，`run.py` 默认尊重它；要连真实后端用 `python run.py --api-mode backend`，或改 `.env`。

## 5. 回滚方式

删除 `run.py`、恢复 `start.ps1`/`start.bat` 与 `frontend/vite.config.ts` 的上一版即可。`config.py` 的改动是增量属性（`chroma_path`），四处调用点改回 `s.chroma_dir` 即可复原；无数据迁移、无 schema 变更。
