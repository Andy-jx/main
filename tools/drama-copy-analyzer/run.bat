@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 main.py
    goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python main.py
    goto :end
)

echo.
echo [错误] 未检测到 Python 3。
echo 请先安装 Python 3.10 或更高版本，并勾选 Add Python to PATH。
echo.
pause

:end
if not %errorlevel%==0 (
    echo.
    echo 程序异常退出，错误码：%errorlevel%
    pause
)
endlocal
