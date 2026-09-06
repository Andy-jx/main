@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo 请把原视频直接拖到这个 BAT 上。
    echo 随后会弹窗让你选择中文字幕 SRT。
    pause
    exit /b 1
)

if exist "%~dp0Runtime\Python\python.exe" (
    "%~dp0Runtime\Python\python.exe" "%~dp0cli.py" burn-select "%~1"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 没找到 Python 运行环境。
        pause
        exit /b 1
    )
    python "%~dp0cli.py" burn-select "%~1"
)

if errorlevel 1 (
    echo.
    echo 烧入未完成，请查看上面的错误信息。
) else (
    echo.
    echo 已完成：中文字幕成片已生成。
)
pause
