@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist "%~dp0Runtime\Python\pythonw.exe" (
    start "" "%~dp0Runtime\Python\pythonw.exe" "%~dp0app.py"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0app.py"
    exit /b 0
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0app.py"
    exit /b %errorlevel%
)

echo [错误] 没找到 Python 运行环境。
echo 请把嵌入式 Python 放到 Runtime\Python\，或在系统安装 Python 3.10/3.11。
pause
exit /b 1
