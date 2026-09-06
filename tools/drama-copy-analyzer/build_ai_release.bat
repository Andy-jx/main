@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "REQUIRE_AI=1"
set "NO_PAUSE=1"
call build_release.bat
if errorlevel 1 goto :fail
copy /Y "release\DramaCopyAnalyzer_Windows.zip" "release\DramaCopyAnalyzer_AI_Windows.zip" >nul
echo.
echo ========================================
echo [完成] 本地AI正式交付包：
echo %CD%\release\DramaCopyAnalyzer_AI_Windows.zip
echo ========================================
pause
exit /b 0
:fail
echo [失败] AI交付包未生成。请先按 AI_本地模型部署说明.md 补齐 Runtime 和 Models。
pause
exit /b 1
