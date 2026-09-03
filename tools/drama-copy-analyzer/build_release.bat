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
    echo [错误] 卖家打包电脑未检测到 Python 3。
    goto :fail
)

if /I "%REQUIRE_AI%"=="1" (
    if not exist "Runtime\llama-server.exe" (
        echo [错误] AI成品包缺少 Runtime\llama-server.exe
        goto :fail
    )
    dir /b "Models\*.gguf" >nul 2>nul
    if errorlevel 1 (
        echo [错误] AI成品包缺少 Models\*.gguf
        goto :fail
    )
)

echo [1/8] 创建独立打包环境...
if not exist ".build-venv\Scripts\python.exe" (
    %PY_CMD% -m venv ".build-venv"
    if errorlevel 1 goto :fail
)
call ".build-venv\Scripts\activate.bat"

echo [2/8] 安装 PyInstaller...
python -m pip install --disable-pip-version-check -q --upgrade pip
if errorlevel 1 goto :fail
python -m pip install --disable-pip-version-check -q -r requirements-build.txt
if errorlevel 1 goto :fail

echo [3/8] 运行源码自检（含本地AI假服务合同测试）...
python self_check.py
if errorlevel 1 goto :fail

echo [4/8] 清理旧产物并打包主程序...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "release\DramaCopyAnalyzer_Windows" rmdir /s /q "release\DramaCopyAnalyzer_Windows"
if exist "release\DramaCopyAnalyzer_Windows.zip" del /q "release\DramaCopyAnalyzer_Windows.zip"
python -m PyInstaller --noconfirm --clean drama-copy-analyzer.spec
if errorlevel 1 goto :fail

echo [5/8] 组装绿色包...
mkdir "release\DramaCopyAnalyzer_Windows" >nul 2>nul
xcopy "dist\DramaCopyAnalyzer\*" "release\DramaCopyAnalyzer_Windows\" /E /I /Y >nul
if errorlevel 1 goto :fail
copy /Y "买家使用说明.txt" "release\DramaCopyAnalyzer_Windows\买家使用说明.txt" >nul
if exist "AI_本地模型部署说明.md" copy /Y "AI_本地模型部署说明.md" "release\DramaCopyAnalyzer_Windows\AI_本地模型部署说明.md" >nul
if exist "THIRD_PARTY_NOTICES.md" copy /Y "THIRD_PARTY_NOTICES.md" "release\DramaCopyAnalyzer_Windows\THIRD_PARTY_NOTICES.md" >nul

echo [6/8] 复制可选本地AI运行时和模型...
if exist "Runtime" xcopy "Runtime\*" "release\DramaCopyAnalyzer_Windows\Runtime\" /E /I /Y >nul
if exist "Models" xcopy "Models\*" "release\DramaCopyAnalyzer_Windows\Models\" /E /I /Y >nul

echo [7/8] 验证打包后的 EXE...
start "" /wait "release\DramaCopyAnalyzer_Windows\DramaCopyAnalyzer.exe" --self-check
if errorlevel 1 goto :fail

echo [8/8] 生成可交付 ZIP...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\DramaCopyAnalyzer_Windows' -DestinationPath 'release\DramaCopyAnalyzer_Windows.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo ========================================
echo [完成] 绿色文件夹：%CD%\release\DramaCopyAnalyzer_Windows\
echo [完成] ZIP：%CD%\release\DramaCopyAnalyzer_Windows.zip
if /I "%REQUIRE_AI%"=="1" echo [AI] 已强制校验 Runtime\llama-server.exe + Models\*.gguf
echo ========================================
if not defined NO_PAUSE pause
exit /b 0

:fail
echo.
echo [失败] 出包中止。当前产物不要发给买家。
if not defined NO_PAUSE pause
exit /b 1
