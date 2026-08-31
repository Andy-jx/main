@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python Launcher。
    echo 请先安装 Python 3.10+，再安装 PyInstaller：py -m pip install pyinstaller
    pause
    exit /b 1
)

py -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [错误] 当前环境未安装 PyInstaller。
    echo 请先执行：py -m pip install pyinstaller
    pause
    exit /b 1
)

py -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "短剧文案拆解工具" ^
  --add-data "sample_script.txt;." ^
  main.py

if errorlevel 1 (
    echo.
    echo [失败] 打包未完成，请查看上方错误。
    pause
    exit /b 1
)

echo.
echo [完成] 成品目录：dist\短剧文案拆解工具\
echo 正式售卖前，请在没有 Python 的 Windows 电脑或虚拟机中验收。
pause
endlocal
