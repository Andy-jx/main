@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo 请把 WAV / MP3 / M4A 等音频文件直接拖到这个 BAT 上。
    pause
    exit /b 1
)

if exist "%~dp0Runtime\Python\python.exe" (
    "%~dp0Runtime\Python\python.exe" "%~dp0cli.py" transcribe "%~1" --language ja
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 没找到 Python 运行环境。
        pause
        exit /b 1
    )
    python "%~dp0cli.py" transcribe "%~1" --language ja
)

if errorlevel 1 (
    echo.
    echo 识别失败，请查看上面的错误信息。
) else (
    echo.
    echo 已完成：已生成原文 SRT，并自动复听可疑片段。
)
pause
