@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title 短剧文案拆解工具 - AI 轻量联网版

echo ========================================
echo   短剧文案拆解工具 - AI 轻量联网版
echo ========================================
echo.
if not exist "DramaCopyAnalyzer.exe" goto :unpack
if not exist "prepare_ai_runtime.ps1" goto :unpack

if exist "Runtime\llama-server.exe" (
  for %%F in ("Models\*.gguf") do if exist "%%~fF" goto :launch
)

echo 第一次运行会自动准备本地 AI。
echo 客户不需要提前安装模型。
echo 下载完成后以后可以断网使用。
echo.
set "BACKEND=cpu"
where nvidia-smi.exe >nul 2>nul
if not errorlevel 1 set "BACKEND=cuda12"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_ai_runtime.ps1" -Backend %BACKEND%
if errorlevel 1 goto :fail

:launch
echo.
echo 正在启动软件...
start "" "%~dp0DramaCopyAnalyzer.exe"
timeout /t 3 /nobreak >nul
exit /b 0

:unpack
echo [错误] 文件不完整。
echo 请先右键压缩包 ^> 全部解压，再从解压后的文件夹运行。
echo.
pause
exit /b 2

:fail
echo.
echo [错误] AI 环境没有准备完成，本窗口不会自动关闭。
echo 请检查 ai_server.log / 下载错误后再重试。
echo.
pause
exit /b 1
