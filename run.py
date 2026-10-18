#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab_agent 统一启动器 —— 一条命令拉起后端与前端。

用法（在仓库根目录执行，任意平台）：

    python run.py                  # 启动后端 + 前端，Ctrl+C 一起停
    python run.py backend          # 只启动后端
    python run.py frontend         # 只启动前端
    python run.py --reload         # 后端热重载（只监听 backend/）
    python run.py stop             # 停止占用 8000 / 5173 的进程
    python run.py status           # 看端口与健康状态
    python run.py check            # 环境自检（解释器/依赖/.env/MySQL/Node）
    python run.py db-check         # 数据库分层自检
    python run.py init-db          # 建表 + 灌种子数据（需可写账号）
    python run.py ingest           # 重建向量索引（需有效 LLM_API_KEY）
    python run.py test             # 离线回归测试（不依赖 MySQL / LLM）
    python run.py build            # 前端生产构建

设计约束（与项目既有约定一致）：
- 后端工作目录必须是 lab-hazmat-agent/：.env 由 pydantic-settings 按 CWD 加载，
  CHROMA_DIR=./corpus/chroma 也是相对路径；app 包在 backend/ 下，用
  `uvicorn --app-dir backend` 加入 sys.path，而不是 cd backend。
- 本脚本只用标准库，不依赖第三方包，也不依赖 conda CLI。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------- 路径与常量

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "lab-hazmat-agent"      # 后端工作目录（.env 所在）
BACKEND_SRC = BACKEND_DIR / "backend"        # app 包所在
FRONTEND_DIR = ROOT / "frontend"
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = BACKEND_SRC / "requirements.txt"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173

IS_WIN = os.name == "nt"
PYTHON_MIN = (3, 10)
BACKEND_IMPORTS = ("fastapi", "uvicorn", "aiomysql", "sqlglot", "langchain_chroma")

_print_lock = threading.Lock()


# ---------------------------------------------------------------- 终端输出

class C:
    """ANSI 颜色；非 TTY 或 Windows 无法开启时自动降级为空串。"""

    _enabled = False
    RESET = BOLD = DIM = CYAN = GREEN = YELLOW = RED = MAGENTA = ""

    @classmethod
    def enable(cls) -> None:
        cls._enabled = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
        if cls._enabled and IS_WIN:
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetStdHandle(-11)
                mode = ctypes.c_uint32()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
                else:
                    cls._enabled = False
            except Exception:
                cls._enabled = False
        if cls._enabled:
            cls.RESET, cls.BOLD, cls.DIM = "\033[0m", "\033[1m", "\033[2m"
            cls.CYAN, cls.GREEN, cls.YELLOW = "\033[36m", "\033[32m", "\033[33m"
            cls.RED, cls.MAGENTA = "\033[31m", "\033[35m"


def _emit(text: str) -> None:
    with _print_lock:
        # 子进程输出是直接写 fd 的，这里必须 flush，否则管道里顺序会乱
        print(text, flush=True)


def step(msg: str) -> None:
    _emit(f"{C.CYAN}==>{C.RESET} {msg}")


def ok(msg: str) -> None:
    _emit(f"  {C.GREEN}OK{C.RESET}  {msg}")


def tip(msg: str) -> None:
    _emit(f"  {C.YELLOW}??{C.RESET}  {msg}")


def bad(msg: str) -> None:
    _emit(f"  {C.RED}!!{C.RESET}  {msg}")


def die(msg: str, code: int = 1) -> "NoReturn":  # noqa: F821
    bad(msg)
    raise SystemExit(code)


# ---------------------------------------------------------------- 基础工具

def read_dotenv(path: Path) -> dict[str, str]:
    """极简 .env 解析：够用即可，忽略注释与空行，去掉成对引号。"""
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        data[key] = value
    return data


def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def http_json(url: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None


# ---------------------------------------------------------------- 解释器解析

def _runs(python: Path) -> tuple[int, int] | None:
    try:
        out = subprocess.run(
            [str(python), "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    match = re.search(r"(\d+)\.(\d+)", out.stdout)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _py_launcher_path() -> Path | None:
    """`py -3` 只是启动器，解析出真实解释器路径。"""
    launcher = shutil.which("py") if IS_WIN else None
    if not launcher:
        return None
    try:
        out = subprocess.run(
            [launcher, "-3", "-c", "import sys;print(sys.executable)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
    except Exception:
        return None
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip())
    return None


def _conda_agent_python() -> Path | None:
    """定位 conda 的 agent 环境，不调用 conda CLI（部分机器上 conda.bat 自身会报错）。"""
    candidates: list[Path] = []

    prefix = os.environ.get("CONDA_PREFIX")
    if prefix and Path(prefix).name == "agent":
        candidates.append(Path(prefix) / ("python.exe" if IS_WIN else "bin/python"))

    # 由当前解释器反推 envs/agent：Anaconda 装在非默认路径时同样适用
    candidates.append(Path(sys.executable).parent / "envs" / "agent" /
                      ("python.exe" if IS_WIN else "bin/python"))

    which_python = shutil.which("python") or shutil.which("python3")
    if which_python:
        candidates.append(Path(which_python).parent / "envs" / "agent" /
                          ("python.exe" if IS_WIN else "bin/python"))

    home = Path.home()
    for root in (home / "anaconda3", home / "miniconda3", Path("C:/Anaconda3"),
                 Path("D:/Anaconda3"), Path("G:/Anaconda3")):
        candidates.append(root / "envs" / "agent" / ("python.exe" if IS_WIN else "bin/python"))

    for path in candidates:
        if path.is_file() and (_runs(path) or (0, 0)) >= PYTHON_MIN:
            return path
    return None


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if IS_WIN else "bin/python")


def backend_deps_ok(python: Path) -> bool:
    try:
        out = subprocess.run(
            [str(python), "-c", "import " + ", ".join(BACKEND_IMPORTS)],
            capture_output=True, timeout=60,
        )
        return out.returncode == 0
    except Exception:
        return False


def candidate_pythons(explicit: str | None) -> list[Path]:
    found: list[Path] = []
    if explicit:
        found.append(Path(explicit).expanduser())
    if os.environ.get("LAB_AGENT_PYTHON"):
        found.append(Path(os.environ["LAB_AGENT_PYTHON"]).expanduser())
    if venv_python().is_file():
        found.append(venv_python())
    conda = _conda_agent_python()
    if conda:
        found.append(conda)
    for name in ("python", "python3"):
        exe = shutil.which(name)
        if exe:
            found.append(Path(exe))
    py3 = _py_launcher_path()
    if py3:
        found.append(py3)
    # 当前进程兜底
    found.append(Path(sys.executable))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def resolve_python(explicit: str | None, need_deps: bool = True) -> Path:
    """按优先级挑一个能用的后端解释器：显式指定 > .venv > conda agent > PATH。"""
    usable: list[Path] = []
    for path in candidate_pythons(explicit):
        if not path.is_file():
            continue
        version = _runs(path)
        if version is None or version < PYTHON_MIN:
            continue
        usable.append(path)
        if not need_deps or backend_deps_ok(path):
            return path

    if explicit:
        die(f"指定的解释器不可用或不满足 Python >= {PYTHON_MIN[0]}.{PYTHON_MIN[1]}：{explicit}")
    if usable:
        # 有可用解释器但缺依赖，交给 ensure_backend_env 处理
        return usable[0]
    die(f"未找到 Python >= {PYTHON_MIN[0]}.{PYTHON_MIN[1]}，请先安装 Python 3.11")


def pip_install(python: Path, force: bool = False) -> None:
    step("安装后端依赖（首次约需 2-5 分钟，取决于网络）")
    cmd = [str(python), "-m", "pip", "install", "--disable-pip-version-check",
           "-r", str(REQUIREMENTS)]
    if force:
        cmd.append("--upgrade")
    if subprocess.run(cmd, cwd=str(ROOT)).returncode != 0:
        die("后端依赖安装失败，请检查网络或 pip 源")
    ok("后端依赖安装完成")


def ensure_backend_env(explicit: str | None, *, force: bool, no_install: bool) -> Path:
    """返回带依赖的解释器；缺依赖时按需创建 .venv 并安装。"""
    python = resolve_python(explicit)

    if backend_deps_ok(python) and not force:
        ok(f"后端解释器：{python}（Python {'%d.%d' % _runs(python)}）")
        return python

    if no_install:
        die(f"解释器 {python} 缺少后端依赖，且已指定 --no-install")

    if force:
        pip_install(python, force=True)
        return python

    # 缺依赖：优先在 .venv 里装，避免污染 conda / 系统环境
    if not venv_python().is_file():
        step(f"创建虚拟环境 {VENV_DIR}")
        if subprocess.run([str(python), "-m", "venv", str(VENV_DIR)]).returncode != 0:
            tip("创建 .venv 失败，改为在当前解释器安装依赖")
            pip_install(python)
            return python
    pip_install(venv_python())
    if not backend_deps_ok(venv_python()):
        die("依赖安装后导入自检仍失败，请查看上方 pip 输出")
    ok(f"后端解释器：{venv_python()}（Python {'%d.%d' % _runs(venv_python())}）")
    return venv_python()


def ensure_frontend_env(force: bool) -> None:
    npm = shutil.which("npm")
    if not npm:
        die("未找到 npm，请先安装 Node.js 18+")
    node = shutil.which("node")
    if node:
        try:
            version = subprocess.run([node, "-v"], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=20).stdout.strip()
            ok(f"Node.js {version}，npm {npm}")
        except Exception:
            ok(f"npm：{npm}")
    if force or not (FRONTEND_DIR / "node_modules").is_dir():
        step("安装前端依赖（npm install）")
        if subprocess.run([npm, "install", "--no-fund", "--no-audit"],
                          cwd=str(FRONTEND_DIR)).returncode != 0:
            die("npm install 失败")
        ok("前端依赖安装完成")
    else:
        ok("前端依赖已就绪")


# ---------------------------------------------------------------- 配置与数据库

def backend_env_path() -> Path:
    return BACKEND_DIR / ".env"


def ensure_dotenv() -> dict[str, str]:
    env_path = backend_env_path()
    sample = BACKEND_DIR / ".env.example"
    if not env_path.is_file() and sample.is_file():
        shutil.copyfile(sample, env_path)
        tip("已从 .env.example 生成 .env，请补全 LLM_API_KEY 与 MySQL 口令")
        print()
        print(f"  首次运行需要编辑：{env_path}")
        print("  必填：LLM_API_KEY（DashScope）、MYSQL_PASSWORD；云库还需核对 MYSQL_HOST / MYSQL_PORT")
        raise SystemExit(2)
    values = read_dotenv(env_path)
    key = values.get("LLM_API_KEY", "")
    if not key or key.startswith("sk-x"):
        tip("LLM_API_KEY 仍是占位值：问答与向量检索会失败，控制台与数据接口不受影响")
    if values.get("MYSQL_PASSWORD") in ("", "change_me"):
        tip("MYSQL_PASSWORD 仍是占位值：/api/health 会显示 degraded")
    return values


def probe_mysql(values: dict[str, str]) -> bool:
    host = values.get("MYSQL_HOST") or "127.0.0.1"
    port_text = values.get("MYSQL_PORT") or "3306"
    port = int(port_text) if port_text.isdigit() else 3306
    if port_open(host, port, timeout=3.0):
        ok(f"MySQL 端点可达：{host}:{port}")
        return True
    tip(f"MySQL 端点不可达（{host}:{port}）：后端仍会启动，/api/health 显示 degraded")
    tip("云库请检查公网地址、安全组白名单与 MYSQL_SSL 配置")
    return False


# ---------------------------------------------------------------- 进程监督

class Service:
    """一个被监督的子进程；输出逐行加前缀转发到当前控制台。"""

    def __init__(self, name: str, color: str, cmd: list[str], cwd: Path,
                 env: dict[str, str] | None = None):
        self.name = name
        self.color = color
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        kwargs: dict = {
            "cwd": str(self.cwd),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "env": self.env,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if IS_WIN:
            kwargs["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(self.cmd, **kwargs)  # type: ignore[arg-type]
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        prefix = f"{self.color}[{self.name}]{C.RESET} "
        for line in self.proc.stdout:
            with _print_lock:
                sys.stdout.write(prefix + line)
                sys.stdout.flush()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def returncode(self) -> int | None:
        return self.proc.poll() if self.proc else None

    def stop(self, timeout: float = 8.0) -> None:
        if not self.proc or self.proc.poll() is not None:
            return
        step(f"停止 {self.name}（PID {self.proc.pid}）")
        try:
            if IS_WIN:
                # npm 会再拉起 node，必须连进程树一起结束
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                               capture_output=True, timeout=20)
            else:
                import signal

                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    return
                try:
                    self.proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except Exception as exc:  # noqa: BLE001 - 停止失败不应吞掉主流程
            tip(f"停止 {self.name} 时出现问题：{exc}")
        try:
            self.proc.wait(timeout=5)
        except Exception:
            pass


def listening_pids(port: int) -> list[int]:
    pids: set[int] = set()
    if IS_WIN:
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=20).stdout
        except Exception:
            return []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3].upper() == "LISTENING" and parts[1].endswith(f":{port}"):
                if parts[4].isdigit():
                    pids.add(int(parts[4]))
        return sorted(pids)

    # lsof 输出就是 PID 列表；ss 需要从 users:(("node",pid=123,...)) 里抠 pid
    for cmd, pattern in (
        (["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], r"\d+"),
        (["ss", "-lptnH", f"sport = :{port}"], r"pid=(\d+)"),
    ):
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        try:
            out = subprocess.run([exe] + cmd[1:], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=20).stdout
        except Exception:
            continue
        pids.update(int(m) for m in re.findall(pattern, out))
        if pids:
            break
    return sorted(pids)


def kill_pids(pids: list[int]) -> None:
    for pid in pids:
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=20)
            else:
                os.kill(pid, 15)
        except Exception as exc:  # noqa: BLE001
            tip(f"结束 PID {pid} 失败：{exc}")


# ---------------------------------------------------------------- 启动流程

def backend_command(python: Path, port: int, reload: bool) -> list[str]:
    cmd = [str(python), "-m", "uvicorn", "app.main:app",
           "--host", "127.0.0.1", "--port", str(port), "--app-dir", "backend"]
    if reload:
        cmd += ["--reload", "--reload-dir", "backend"]
    return cmd


def frontend_command(port: int) -> list[str]:
    npm = shutil.which("npm") or "npm"
    args = ["run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]
    if IS_WIN:
        # npm 在 Windows 上是 npm.cmd，必须经 cmd.exe 才能被 CreateProcess 拉起
        return ["cmd", "/c", npm] + args
    return [npm] + args


def wait_backend_ready(services: list[Service], timeout: float = 90.0) -> dict | None:
    deadline = time.time() + timeout
    step(f"等待后端就绪（最多 {int(timeout)} 秒）")
    url = f"http://127.0.0.1:{BACKEND_PORT}/api/health"
    while time.time() < deadline:
        if not all(svc.alive() for svc in services if svc.name == "api"):
            return None
        body = http_json(url)
        if body is not None:
            return body
        time.sleep(0.8)
    return None


def wait_port(port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open("127.0.0.1", port):
            return True
        time.sleep(0.4)
    return False


def cmd_start(args: argparse.Namespace) -> int:
    do_backend = not args.frontend_only
    do_frontend = not args.backend_only

    for required in (BACKEND_DIR, BACKEND_SRC, FRONTEND_DIR):
        if not required.is_dir():
            die(f"目录不存在：{required}")

    print()
    print(f"{C.BOLD}实验室安全与资产治理智能问答平台 · 本地启动{C.RESET}")
    print(f"{C.DIM}{'=' * 60}{C.RESET}")

    # 1. 端口占用检查
    busy = False
    for label, port, enabled in (("后端", args.backend_port, do_backend),
                                 ("前端", args.frontend_port, do_frontend)):
        if enabled and port_open("127.0.0.1", port):
            pids = listening_pids(port)
            hint = f"（PID {', '.join(map(str, pids))}）" if pids else ""
            bad(f"{label}端口 {port} 已被占用{hint}，先执行 python run.py stop")
            busy = True
    if busy:
        return 1

    services: list[Service] = []

    # 2. 后端：解释器 + 依赖 + 配置 + 数据库探测
    if do_backend:
        python = ensure_backend_env(args.python, force=args.force_install,
                                    no_install=args.no_install)
        env_values = ensure_dotenv()
        probe_mysql(env_values)

        if args.db_check:
            run_backend_module(python, "scripts.db_check", [])

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(BACKEND_SRC)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env["UVICORN_FORWARDED_ALLOW_IPS"] = "127.0.0.1"

    # 3. 前端依赖
    if do_frontend:
        ensure_frontend_env(args.force_install)

    # 4. 拉起进程
    if do_backend:
        step(f"启动后端（127.0.0.1:{args.backend_port}，工作目录 lab-hazmat-agent）")
        services.append(Service(
            "api", C.CYAN,
            backend_command(python, args.backend_port, args.reload),
            BACKEND_DIR, env,
        ))
    if do_frontend:
        step(f"启动前端（127.0.0.1:{args.frontend_port}）")
        web_env = os.environ.copy()
        # vite.config.ts 从这里读端口与代理目标，换端口启动时代理才不会仍打 8000
        web_env["VITE_DEV_PORT"] = str(args.frontend_port)
        web_env["VITE_API_TARGET"] = f"http://127.0.0.1:{args.backend_port}"
        # 只在显式指定时覆盖；否则尊重 frontend/.env 里的 VITE_API_MODE
        if args.api_mode:
            web_env["VITE_API_MODE"] = args.api_mode
        else:
            web_env.pop("VITE_API_MODE", None)
        services.append(Service(
            "web", C.MAGENTA, frontend_command(args.frontend_port), FRONTEND_DIR, web_env,
        ))

    for svc in services:
        svc.start()

    # 5. 就绪检测
    exit_code = 0
    try:
        if do_backend:
            health = wait_backend_ready([svc for svc in services if svc.name == "api"])
            if health is None:
                bad("后端未在超时内响应，见上方 [api] 输出")
                exit_code = 1
            elif health.get("status") == "ok":
                ok("后端已就绪，MySQL 连通")
            else:
                tip("后端已就绪，但 MySQL 不可用（degraded）")
                tip(f"排障：curl http://127.0.0.1:{args.backend_port}/api/health/detail")
        if do_frontend:
            if wait_port(args.frontend_port):
                ok(f"前端已就绪：http://127.0.0.1:{args.frontend_port}")
            else:
                bad("前端未在超时内响应，见上方 [web] 输出")
                exit_code = 1

        print()
        print(f"{C.DIM}{'=' * 60}{C.RESET}")
        if do_frontend:
            print(f"  前端工作台   {C.BOLD}http://localhost:{args.frontend_port}{C.RESET}")
        if do_backend:
            print(f"  接口文档     http://127.0.0.1:{args.backend_port}/docs")
            print(f"  健康检查     http://127.0.0.1:{args.backend_port}/api/health")
        print(f"{C.DIM}  按 Ctrl+C 停止全部服务{C.RESET}")
        print()

        if args.open and do_frontend:
            webbrowser.open(f"http://localhost:{args.frontend_port}")

        # 6. 守护：任一进程退出就整体收工
        while True:
            for svc in services:
                if not svc.alive():
                    bad(f"{svc.name} 已退出（退出码 {svc.returncode()}），停止其余服务")
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        step("收到中断信号")
        return exit_code
    finally:
        for svc in reversed(services):
            svc.stop()
        print(f"{C.DIM}已停止。{C.RESET}")


def run_backend_module(python: Path, module: str, extra: list[str]) -> int:
    """在 lab-hazmat-agent/ 下以 `python -m <module>` 执行脚本。"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND_SRC)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([str(python), "-m", module] + extra, cwd=str(BACKEND_DIR), env=env).returncode


# ---------------------------------------------------------------- 子命令

def cmd_stop(_: argparse.Namespace) -> int:
    step("停止项目服务")
    stopped = False
    for label, port in (("后端", BACKEND_PORT), ("前端", FRONTEND_PORT)):
        pids = listening_pids(port)
        if not pids:
            tip(f"{label}端口 {port} 无监听进程")
            continue
        kill_pids(pids)
        ok(f"已停止端口 {port} 上的进程（PID {', '.join(map(str, pids))}）")
        stopped = True
    if stopped:
        time.sleep(1)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(f"{C.BOLD}服务状态{C.RESET}")
    for label, port in (("后端", BACKEND_PORT), ("前端", FRONTEND_PORT)):
        pids = listening_pids(port)
        state = f"运行中（PID {', '.join(map(str, pids))}）" if pids else "未启动"
        color = C.GREEN if pids else C.DIM
        print(f"  {label}  :{port}  {color}{state}{C.RESET}")
    health = http_json(f"http://127.0.0.1:{BACKEND_PORT}/api/health")
    if health:
        print(f"  健康检查  {json.dumps(health, ensure_ascii=False)}")
        detail = http_json(f"http://127.0.0.1:{BACKEND_PORT}/api/health/detail")
        if detail:
            config = detail.get("config", {})
            print(f"  MySQL     {config.get('endpoint')}  ssl={config.get('ssl')}")
            llm = detail.get("llm", {})
            print(f"  LLM       {llm.get('model')}  key_set={llm.get('api_key_set')}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    step("环境自检")
    problems = 0

    # Python 与后端依赖
    try:
        python = resolve_python(args.python)
        version = "%d.%d" % _runs(python)
        if backend_deps_ok(python):
            ok(f"Python {version} @ {python}，后端依赖齐全")
        else:
            tip(f"Python {version} @ {python}，但缺少后端依赖（启动时会自动安装到 .venv）")
    except SystemExit as exc:
        bad(f"后端解释器不可用（退出码 {exc.code}）")
        problems += 1

    # .env
    env_path = backend_env_path()
    if env_path.is_file():
        values = read_dotenv(env_path)
        ok(f"配置文件 {env_path}")
        if values.get("LLM_API_KEY", "").startswith("sk-x") or not values.get("LLM_API_KEY"):
            tip("LLM_API_KEY 是占位值")
            problems += 1
        if values.get("MYSQL_PASSWORD") in ("", "change_me"):
            tip("MYSQL_PASSWORD 是占位值")
            problems += 1
        probe_mysql(values)
    else:
        bad("缺少 lab-hazmat-agent/.env（首次启动会自动从 .env.example 生成）")
        problems += 1

    # 数据与知识库
    ddl = sorted((BACKEND_DIR / "mysql" / "init").glob("*.sql"))
    ok(f"建表脚本 {len(ddl)} 个") if ddl else tip("未找到 mysql/init/*.sql")
    chroma = BACKEND_DIR / "corpus" / "chroma"
    ok("向量库目录存在") if chroma.is_dir() else tip(f"向量库目录不存在：{chroma}（需运行 python run.py ingest）")

    # Node 与前端
    if shutil.which("npm"):
        installed = (FRONTEND_DIR / "node_modules").is_dir()
        ok("npm 可用，前端依赖已安装") if installed else tip("npm 可用，但 node_modules 缺失（启动时会自动安装）")
    else:
        bad("未找到 npm，请安装 Node.js 18+")
        problems += 1

    # 端口
    for label, port in (("后端", BACKEND_PORT), ("前端", FRONTEND_PORT)):
        if port_open("127.0.0.1", port):
            pids = listening_pids(port)
            tip(f"{label}端口 {port} 已被占用（PID {', '.join(map(str, pids)) or '未知'}）")

    print()
    if problems:
        bad(f"自检发现 {problems} 项需要处理")
        return 1
    ok("自检通过")
    return 0


def cmd_db_check(args: argparse.Namespace) -> int:
    python = ensure_backend_env(args.python, force=False, no_install=args.no_install)
    step("数据库分层自检（scripts.db_check）")
    return run_backend_module(python, "scripts.db_check", [])


def cmd_init_db(args: argparse.Namespace) -> int:
    python = ensure_backend_env(args.python, force=False, no_install=args.no_install)
    step("建表 + 灌种子数据（scripts.init_db）")
    return run_backend_module(python, "scripts.init_db", [])


def cmd_ingest(args: argparse.Namespace) -> int:
    python = ensure_backend_env(args.python, force=False, no_install=args.no_install)
    step("重建向量索引（app.rag.ingest）")
    return run_backend_module(python, "app.rag.ingest", [])


def cmd_test(args: argparse.Namespace) -> int:
    python = ensure_backend_env(args.python, force=False, no_install=args.no_install)
    step("离线回归测试（tests.test_offline）")
    return run_backend_module(python, "tests.test_offline", args.extra)


def cmd_build(_: argparse.Namespace) -> int:
    ensure_frontend_env(force=False)
    step("前端生产构建（npm run build）")
    npm = shutil.which("npm") or "npm"
    cmd = ["cmd", "/c", npm, "run", "build"] if IS_WIN else [npm, "run", "build"]
    return subprocess.run(cmd, cwd=str(FRONTEND_DIR)).returncode


# ---------------------------------------------------------------- 入口

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="lab_agent 统一启动器（后端 FastAPI + 前端 Vite）",
    )
    sub = parser.add_subparsers(dest="command")

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--python", default=None, help="指定后端解释器路径")
        p.add_argument("--no-install", action="store_true", help="缺依赖时不自动安装，直接报错")

    p_start = sub.add_parser("start", help="启动服务（默认命令）")
    add_common(p_start)
    mode = p_start.add_mutually_exclusive_group()
    mode.add_argument("--backend-only", action="store_true", help="只启动后端")
    mode.add_argument("--frontend-only", action="store_true", help="只启动前端")
    p_start.add_argument("--reload", action="store_true", help="后端热重载（只监听 backend/）")
    p_start.add_argument("--force-install", action="store_true", help="强制重装依赖")
    p_start.add_argument("--db-check", action="store_true", help="启动前先跑数据库分层自检")
    p_start.add_argument("--open", action="store_true", help="就绪后打开浏览器")
    p_start.add_argument("--api-mode", choices=("backend", "mock"), default=None,
                         help="前端数据模式：backend=真实接口（默认），mock=本地模拟数据")
    p_start.add_argument("--backend-port", type=int, default=BACKEND_PORT)
    p_start.add_argument("--frontend-port", type=int, default=FRONTEND_PORT)
    p_start.set_defaults(func=cmd_start)

    # 兼容旧写法：python run.py backend / frontend
    p_backend = sub.add_parser("backend", help="只启动后端（start 的简写）")
    add_common(p_backend)
    p_backend.add_argument("--reload", action="store_true")
    p_backend.add_argument("--force-install", action="store_true")
    p_backend.add_argument("--db-check", action="store_true")
    p_backend.add_argument("--open", action="store_true")
    p_backend.add_argument("--api-mode", choices=("backend", "mock"), default=None)
    p_backend.add_argument("--backend-port", type=int, default=BACKEND_PORT)
    p_backend.add_argument("--frontend-port", type=int, default=FRONTEND_PORT)
    p_backend.set_defaults(func=cmd_start, frontend_only=False, backend_only=True)

    p_frontend = sub.add_parser("frontend", help="只启动前端（start 的简写）")
    add_common(p_frontend)
    p_frontend.add_argument("--reload", action="store_true")
    p_frontend.add_argument("--force-install", action="store_true")
    p_frontend.add_argument("--db-check", action="store_true")
    p_frontend.add_argument("--open", action="store_true")
    p_frontend.add_argument("--api-mode", choices=("backend", "mock"), default=None)
    p_frontend.add_argument("--backend-port", type=int, default=BACKEND_PORT)
    p_frontend.add_argument("--frontend-port", type=int, default=FRONTEND_PORT)
    p_frontend.set_defaults(func=cmd_start, frontend_only=True, backend_only=False)

    p_stop = sub.add_parser("stop", help="停止占用 8000 / 5173 的进程")
    p_stop.set_defaults(func=cmd_stop)

    p_status = sub.add_parser("status", help="查看端口与健康状态")
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("check", help="环境自检")
    add_common(p_check)
    p_check.set_defaults(func=cmd_check)

    p_db = sub.add_parser("db-check", help="数据库分层自检")
    add_common(p_db)
    p_db.set_defaults(func=cmd_db_check)

    p_init = sub.add_parser("init-db", help="建表 + 灌种子数据")
    add_common(p_init)
    p_init.set_defaults(func=cmd_init_db)

    p_ingest = sub.add_parser("ingest", help="重建向量索引")
    add_common(p_ingest)
    p_ingest.set_defaults(func=cmd_ingest)

    p_test = sub.add_parser("test", help="离线回归测试")
    add_common(p_test)
    p_test.add_argument("extra", nargs="*", help="传给测试的用例分组，如 guard")
    p_test.set_defaults(func=cmd_test)

    p_build = sub.add_parser("build", help="前端生产构建")
    p_build.set_defaults(func=cmd_build)

    return parser


def main(argv: list[str] | None = None) -> int:
    C.enable()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    argv = list(sys.argv[1:] if argv is None else argv)
    # `python run.py` / `python run.py --reload` 都按 start 处理
    if not argv or argv[0] not in {
        "start", "backend", "frontend", "stop", "status", "check",
        "db-check", "init-db", "ingest", "test", "build", "-h", "--help",
    }:
        argv = ["start"] + argv

    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    # 子命令缺省值补齐（backend/frontend 简写复用 cmd_start）
    for attr, default in (("reload", False), ("force_install", False), ("db_check", False),
                          ("open", False), ("backend_only", False), ("frontend_only", False),
                          ("backend_port", BACKEND_PORT), ("frontend_port", FRONTEND_PORT),
                          ("api_mode", None)):
        if not hasattr(args, attr):
            setattr(args, attr, default)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
