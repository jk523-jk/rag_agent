<#
.SYNOPSIS
    一键启动「实验室安全与资产治理智能问答平台」（FastAPI 后端 + Vue3 前端）。

.DESCRIPTION
    默认做的事：
      1. 检查 Python / Node 环境；首次运行自动创建 .venv 并安装后端依赖
      2. frontend/node_modules 缺失时自动 npm install
      3. 检查 .env，并按 MYSQL_HOST / MYSQL_PORT 探测 MySQL 端点（本地或云库）
      4. 后端 uvicorn(127.0.0.1:8000) 与前端 Vite(127.0.0.1:5173) 各开一个独立窗口
      5. 轮询 /api/health 确认后端真的起来了，再打印访问地址

    后端工作目录固定为 lab-hazmat-agent/：.env 由 pydantic-settings 按相对当前
    目录加载，CHROMA_DIR=./corpus/chroma 也是相对路径。app 包在 backend/ 下，
    因此用 uvicorn --app-dir backend 把它加进 sys.path，而不是 cd backend，
    否则 .env 落在 backend/ 里会找不到。

.PARAMETER BackendOnly
    只启动后端。

.PARAMETER FrontendOnly
    只启动前端。

.PARAMETER Reload
    后端开启热重载（只监听 backend/ 目录，不扫描 corpus）。

.PARAMETER ForceInstall
    强制重新安装后端依赖与前端依赖。

.PARAMETER DbCheck
    启动前先跑 backend/scripts/db_check.py：TCP → TLS/认证 → 库 → 只读护栏 → 表 → 种子数据逐层自检。

.PARAMETER Stop
    停止占用 8000 / 5173 的进程，并停掉 MySQL 容器。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\start.ps1

.EXAMPLE
    .\start.ps1 -Reload

.EXAMPLE
    .\start.ps1 -DbCheck

.EXAMPLE
    .\start.ps1 -FrontendOnly

.EXAMPLE
    .\start.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Reload,
    [switch]$ForceInstall,
    [switch]$DbCheck,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'

# ---- 目录与端口 -------------------------------------------------------------
$Root         = $PSScriptRoot
$BackendDir   = Join-Path $Root 'lab-hazmat-agent'      # 后端工作目录（.env 所在）
$BackendSrc   = Join-Path $BackendDir 'backend'         # app 包所在
$FrontendDir  = Join-Path $Root 'frontend'
$VenvDir      = Join-Path $Root '.venv'
$VenvPython   = Join-Path $VenvDir 'Scripts\python.exe'
$Requirements = Join-Path $BackendSrc 'requirements.txt'
$BackendPort  = 8000
$FrontendPort = 5173

function Write-Step($Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok($Message)   { Write-Host "  OK  $Message" -ForegroundColor Green }
function Write-Tip($Message)  { Write-Host "  ??  $Message" -ForegroundColor Yellow }
function Write-Bad($Message)  { Write-Host "  !!  $Message" -ForegroundColor Red }

# 主机端口是否可连：用 TcpClient 探测，不依赖 Get-NetTCPConnection
function Test-EndpointOpen([string]$Server, [int]$Port, [int]$TimeoutMs = 1500) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($Server, $Port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne($TimeoutMs) -and $client.Connected) { return $true }
        return $false
    }
    catch { return $false }
    finally { $client.Close() }
}

function Test-PortOpen([int]$Port) {
    return (Test-EndpointOpen '127.0.0.1' $Port 400)
}

# 读 .env 中的键值；文件不存在或键缺失返回空串
function Get-DotEnvValue([string]$Path, [string]$Key) {
    if (-not (Test-Path $Path)) { return '' }
    $line = Select-String -Path $Path -Pattern "^\s*$Key\s*=\s*(.*)$" | Select-Object -First 1
    if (-not $line) { return '' }
    return $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
}

# 取监听端口的进程，拿不到返回 $null
function Get-PortOwner([int]$Port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        if (-not $conn) { return $null }
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        return @{ Pid = $conn.OwningProcess; Name = $proc.ProcessName }
    }
    catch { return $null }
}

function Stop-PortOwner([int]$Port) {
    $owner = Get-PortOwner $Port
    if (-not $owner) { Write-Tip "端口 $Port 无监听进程"; return }
    try {
        Stop-Process -Id $owner.Pid -Force -ErrorAction Stop
        Write-Ok "已停止端口 $Port 上的 $($owner.Name)（PID $($owner.Pid)）"
    }
    catch { Write-Bad "停止端口 $Port 失败：$($_.Exception.Message)" }
}

# 按 py 启动器优先、python 兜底的顺序找 3.10+ 解释器
function Find-Python {
    $candidates = @(
        @{ Exe = 'py';      Args = @('-3.11') },
        @{ Exe = 'py';      Args = @('-3.12') },
        @{ Exe = 'py';      Args = @('-3') },
        @{ Exe = 'python';  Args = @() },
        @{ Exe = 'python3'; Args = @() }
    )
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
        $prefix = $c.Args
        $version = & $c.Exe @prefix -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $version) { continue }
        if ([version]$version.Trim() -ge [version]'3.10') { return $c }
    }
    return $null
}

function Test-BackendDeps {
    if (-not (Test-Path $VenvPython)) { return $false }
    & $VenvPython -c "import fastapi, uvicorn, aiomysql, sqlglot, langchain_chroma" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Wait-BackendReady([int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            return Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 3 -ErrorAction Stop
        }
        catch { Start-Sleep -Milliseconds 800 }
    }
    return $null
}

# ---- 停止模式 ---------------------------------------------------------------
if ($Stop) {
    Write-Step '停止项目服务'
    Stop-PortOwner $BackendPort
    Stop-PortOwner $FrontendPort
    return
}

foreach ($required in @($BackendDir, $BackendSrc, $FrontendDir)) {
    if (-not (Test-Path $required)) { Write-Bad "目录不存在：$required"; exit 1 }
}

$doBackend  = -not $FrontendOnly
$doFrontend = -not $BackendOnly

Write-Host ''
Write-Host '实验室安全与资产治理智能问答平台 · 本地启动' -ForegroundColor White
Write-Host ('=' * 56) -ForegroundColor DarkGray

# ---- 1. 端口占用 ------------------------------------------------------------
foreach ($item in @(@{ Port = $BackendPort; On = $doBackend }, @{ Port = $FrontendPort; On = $doFrontend })) {
    if (-not $item.On) { continue }
    if (Test-PortOpen $item.Port) {
        $owner = Get-PortOwner $item.Port
        $hint = ''
        if ($owner) { $hint = "（$($owner.Name) PID $($owner.Pid)）" }
        Write-Bad "端口 $($item.Port) 已被占用$hint，先执行 .\start.ps1 -Stop 或换端口"
        exit 1
    }
}

# ---- 2. 后端依赖 ------------------------------------------------------------
if ($doBackend) {
    if (-not (Test-Path $VenvPython)) {
        Write-Step "未找到虚拟环境，创建 $VenvDir"
        $py = Find-Python
        if (-not $py) { Write-Bad '未找到 Python 3.10+，请先安装 Python 3.11'; exit 1 }
        $prefix = $py.Args
        & $py.Exe @prefix -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { Write-Bad '创建虚拟环境失败'; exit 1 }
        Write-Ok "虚拟环境就绪：$VenvPython"
    }

    if ($ForceInstall -or -not (Test-BackendDeps)) {
        Write-Step '安装后端依赖（首次约需 2-5 分钟，取决于网络）'
        & $VenvPython -m pip install --disable-pip-version-check -r $Requirements
        if ($LASTEXITCODE -ne 0) { Write-Bad '后端依赖安装失败，请检查网络或 pip 源'; exit 1 }
        Write-Ok '后端依赖安装完成'
    }
    else {
        Write-Ok '后端依赖已就绪'
    }
}

# ---- 3. 前端依赖 ------------------------------------------------------------
if ($doFrontend) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Bad '未找到 npm，请先安装 Node.js 18+'; exit 1 }
    if ($ForceInstall -or -not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
        Write-Step '安装前端依赖（npm install）'
        Push-Location $FrontendDir
        try {
            & npm install --no-fund --no-audit
            if ($LASTEXITCODE -ne 0) { Write-Bad 'npm install 失败'; exit 1 }
        }
        finally { Pop-Location }
        Write-Ok '前端依赖安装完成'
    }
    else {
        Write-Ok '前端依赖已就绪'
    }
}

# ---- 4. 配置文件与数据库 ----------------------------------------------------
if ($doBackend) {
    $envPath = Join-Path $BackendDir '.env'
    $envSample = Join-Path $BackendDir '.env.example'
    if (-not (Test-Path $envPath) -and (Test-Path $envSample)) {
        Copy-Item $envSample $envPath
        Write-Tip '已从 .env.example 生成 .env，请补全 LLM_API_KEY 与 MySQL 口令'
    }
    if (Test-Path $envPath) {
        $keyLine = Select-String -Path $envPath -Pattern '^\s*LLM_API_KEY\s*=\s*(.*)$' | Select-Object -First 1
        if ($keyLine) {
            $key = $keyLine.Matches[0].Groups[1].Value.Trim()
            if (-not $key -or $key -like 'sk-x*') {
                Write-Tip 'LLM_API_KEY 仍是占位值：问答与向量检索会失败，其余功能不受影响'
            }
        }
    }

    # MySQL 端点从 .env 读，不写死 3306：本地实例与云库公网端口（如 27959）都适用
    $mysqlHost = Get-DotEnvValue $envPath 'MYSQL_HOST'
    if (-not $mysqlHost) { $mysqlHost = '127.0.0.1' }
    $mysqlPort = 3306
    $mysqlPortText = Get-DotEnvValue $envPath 'MYSQL_PORT'
    if ($mysqlPortText -match '^\d+$') { $mysqlPort = [int]$mysqlPortText }
    $mysqlTarget = "${mysqlHost}:${mysqlPort}"

    if (Test-EndpointOpen $mysqlHost $mysqlPort 3000) {
        Write-Ok "MySQL 端点可达：$mysqlTarget"
    }
    else {
        Write-Tip "MySQL 端点不可达（$mysqlTarget）：后端仍会启动，/api/health 显示 degraded；云库请检查公网地址、安全组白名单与 SSL 配置"
    }

    if ($DbCheck) {
        Write-Step '数据库分层自检（scripts.db_check）'
        $savedPythonPath = $env:PYTHONPATH
        $env:PYTHONPATH = 'backend'
        Push-Location $BackendDir
        try {
            & $VenvPython -m scripts.db_check
            if ($LASTEXITCODE -ne 0) { Write-Tip '自检存在未通过项，见上方分层输出' }
        }
        finally {
            Pop-Location
            $env:PYTHONPATH = $savedPythonPath
        }
    }
}

# ---- 5. 启动服务 ------------------------------------------------------------
if ($doBackend) {
    Write-Step "启动后端（127.0.0.1:$BackendPort，工作目录 lab-hazmat-agent）"
    $uvicorn = "& '$VenvPython' -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --app-dir backend"
    if ($Reload) { $uvicorn = $uvicorn + ' --reload --reload-dir backend' }
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $BackendDir `
        -ArgumentList @('-NoExit', '-NoLogo', '-ExecutionPolicy', 'Bypass', '-Command', $uvicorn) | Out-Null
}

if ($doFrontend) {
    Write-Step "启动前端（127.0.0.1:$FrontendPort）"
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $FrontendDir `
        -ArgumentList @('-NoExit', '-NoLogo', '-ExecutionPolicy', 'Bypass', '-Command', 'npm run dev') | Out-Null
}

# ---- 6. 就绪检测与访问地址 --------------------------------------------------
if ($doBackend) {
    Write-Step '等待后端就绪（首次导入依赖较慢，最多 60 秒）'
    $health = Wait-BackendReady 60
    if ($health) {
        if ($health.status -eq 'ok') { Write-Ok '后端已就绪，MySQL 连通' }
        else { Write-Tip '后端已就绪，但 MySQL 不可用（degraded）；排障：Invoke-RestMethod http://127.0.0.1:8000/api/health/detail' }
    }
    else {
        Write-Bad '后端 60 秒内未响应，请查看后端窗口的报错'
    }
}

if ($doFrontend) {
    $frontendDeadline = (Get-Date).AddSeconds(40)
    while (-not (Test-PortOpen $FrontendPort) -and (Get-Date) -lt $frontendDeadline) {
        Start-Sleep -Milliseconds 500
    }
}

Write-Host ('=' * 56) -ForegroundColor DarkGray
if ($doFrontend) { Write-Host "  前端工作台   http://localhost:$FrontendPort" -ForegroundColor White }
if ($doBackend) {
    Write-Host "  接口文档     http://127.0.0.1:$BackendPort/docs" -ForegroundColor White
    Write-Host "  健康检查     http://127.0.0.1:$BackendPort/api/health" -ForegroundColor White
}
Write-Host "  停止服务     .\start.ps1 -Stop" -ForegroundColor DarkGray
Write-Host ''
