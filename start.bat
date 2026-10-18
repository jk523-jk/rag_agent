@echo off
rem ===========================================================================
rem 双击即可启动。实际逻辑在 run.py（跨平台、只依赖标准库）。
rem 参数原样透传，例如：
rem   start.bat --reload        start.bat backend
rem   start.bat stop            start.bat status
rem   start.bat check           start.bat --open
rem ===========================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto no_python

python run.py %*
if errorlevel 1 pause
exit /b %errorlevel%

:no_python
echo [!] 未找到 python，尝试旧版 PowerShell 启动脚本...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
exit /b %errorlevel%
