@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo.
    echo [错误] 卖家打包电脑未检测到 Python 3。
    echo 买家不需要 Python；这里只是卖家出包电脑需要 Python。
    pause
    exit /b 1
)

echo [1/7] 创建独立打包环境...
if not exist ".build-venv\Scripts\python.exe" (
    %PY_CMD% -m venv ".build-venv"
    if errorlevel 1 goto :fail
)
call ".build-venv\Scripts\activate.bat"

echo [2/7] 安装 PyInstaller...
python -m pip install --disable-pip-version-check -q --upgrade pip
if errorlevel 1 goto :fail
python -m pip install --disable-pip-version-check -q -r requirements-build.txt
if errorlevel 1 goto :fail

echo [3/7] 运行源码自检...
python self_check.py
if errorlevel 1 goto :fail

echo [4/7] 清理旧产物并打包...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "release\DramaCopyAnalyzer_Windows" rmdir /s /q "release\DramaCopyAnalyzer_Windows"
if exist "release\DramaCopyAnalyzer_Windows.zip" del /q "release\DramaCopyAnalyzer_Windows.zip"
python -m PyInstaller --noconfirm --clean drama-copy-analyzer.spec
if errorlevel 1 goto :fail

echo [5/7] 组装买家绿色包...
mkdir "release\DramaCopyAnalyzer_Windows" >nul 2>nul
xcopy "dist\DramaCopyAnalyzer\*" "release\DramaCopyAnalyzer_Windows\" /E /I /Y >nul
if errorlevel 1 goto :fail
copy /Y "买家使用说明.txt" "release\DramaCopyAnalyzer_Windows\买家使用说明.txt" >nul

echo [6/7] 验证打包后的 EXE...
start "" /wait "release\DramaCopyAnalyzer_Windows\DramaCopyAnalyzer.exe" --self-check
if errorlevel 1 goto :fail

echo [7/7] 生成可交付 ZIP...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\DramaCopyAnalyzer_Windows' -DestinationPath 'release\DramaCopyAnalyzer_Windows.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo ========================================
echo [完成] 卖家绿色文件夹：
echo %CD%\release\DramaCopyAnalyzer_Windows\
echo.
echo [完成] 闲鱼可交付压缩包：
echo %CD%\release\DramaCopyAnalyzer_Windows.zip
echo ========================================
echo.
echo 买家无需安装 Python，解压后双击 DramaCopyAnalyzer.exe。
pause
exit /b 0

:fail
echo.
echo [失败] 出包中止。上方步骤未通过，不要把当前产物发给买家。
pause
exit /b 1
