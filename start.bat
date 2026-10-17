@echo off
rem 双击即可启动：绕过 PowerShell 执行策略调用 start.ps1，参数原样透传
rem 例：start.bat -Reload    start.bat -FrontendOnly    start.bat -Stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
