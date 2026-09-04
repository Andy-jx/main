@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo 请把原文 SRT 字幕直接拖到这个 BAT 上。
    pause
    exit /b 1
)

if exist "%~dp0Runtime\Python\python.exe" (
    "%~dp0Runtime\Python\python.exe" "%~dp0cli.py" translate "%~1"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 没找到 Python 运行环境。
        pause
        exit /b 1
    )
    python "%~dp0cli.py" translate "%~1"
)

if errorlevel 1 (
    echo.
    echo 翻译失败，请查看上面的错误信息。
) else (
    echo.
    echo 已完成：已生成高精校中文字幕 SRT。
)
pause
