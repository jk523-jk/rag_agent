<#
.SYNOPSIS
    兼容层：把旧的 start.ps1 参数翻译成 run.py 的参数后转发。

.DESCRIPTION
    启动逻辑已经收敛到仓库根的 run.py（跨平台、只用标准库）。本脚本保留，
    仅为兼容既有文档与习惯：老参数照旧可用，实际执行的是 run.py。

        旧参数              →  run.py
        -BackendOnly        →  backend
        -FrontendOnly       →  frontend
        -Reload             →  --reload
        -ForceInstall       →  --force-install
        -DbCheck            →  --db-check
        -Stop               →  stop
        -Python <path>      →  --python <path>

.EXAMPLE
    .\start.ps1
    .\start.ps1 -Reload
    .\start.ps1 -DbCheck
    .\start.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Reload,
    [switch]$ForceInstall,
    [switch]$DbCheck,
    [switch]$Stop,
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$RunPy = Join-Path $Root 'run.py'

if (-not (Test-Path $RunPy)) {
    Write-Host "!! 未找到 $RunPy" -ForegroundColor Red
    exit 1
}

# 优先用户 PATH 上的 python；找不到再问 py 启动器
$pythonExe = $Python
if (-not $pythonExe) {
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $pythonExe) {
    $pythonExe = (Get-Command py -ErrorAction SilentlyContinue).Source
}
if (-not $pythonExe) {
    Write-Host '!! 未找到 Python，请先安装 Python 3.10+' -ForegroundColor Red
    exit 1
}

$arguments = @($RunPy)
if ($Stop) {
    $arguments += 'stop'
}
elseif ($BackendOnly) {
    $arguments += 'backend'
}
elseif ($FrontendOnly) {
    $arguments += 'frontend'
}
if ($Reload) { $arguments += '--reload' }
if ($ForceInstall) { $arguments += '--force-install' }
if ($DbCheck) { $arguments += '--db-check' }
if ($Python) { $arguments += @('--python', $Python) }

& $pythonExe @arguments
exit $LASTEXITCODE
