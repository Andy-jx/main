@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo 请把视频文件直接拖到这个 BAT 上。
    pause
    exit /b 1
)

if exist "%~dp0Runtime\Python\python.exe" (
    "%~dp0Runtime\Python\python.exe" "%~dp0cli.py" extract "%~1"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 没找到 Python 运行环境。
        pause
        exit /b 1
    )
    python "%~dp0cli.py" extract "%~1"
)

if errorlevel 1 (
    echo.
    echo 处理失败，请查看上面的错误信息。
) else (
    echo.
    echo 已完成：视频声音已提取。
)
pause
