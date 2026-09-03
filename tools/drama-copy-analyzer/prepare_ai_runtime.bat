@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo 短剧文案拆解工具 - 本地AI环境准备
echo ========================================
echo [1] 通用 CPU x64  ^(兼容优先，适合大多数 Windows 电脑^)
echo [2] NVIDIA CUDA 12 x64  ^(性能优先，适合 NVIDIA 显卡^)
echo.
choice /c 12 /n /m "请选择 [1/2]: "
if errorlevel 2 (
    set "BACKEND=cuda12"
) else (
    set "BACKEND=cpu"
)

echo.
echo 将准备：llama.cpp Windows 运行时 + Qwen3.5-4B Q4_K_M GGUF
echo 模型约 2.7 GB，请确保网络和磁盘空间正常。
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_ai_runtime.ps1" -Backend %BACKEND%
if errorlevel 1 goto :fail

echo.
echo ========================================
echo [完成] 本地AI运行时和模型已准备好。
echo 下一步：双击 build_ai_release.bat
echo ========================================
pause
exit /b 0

:fail
echo.
echo [失败] 本地AI环境准备未完成。
echo 请检查网络、磁盘空间和上方错误信息后重试。
pause
exit /b 1
