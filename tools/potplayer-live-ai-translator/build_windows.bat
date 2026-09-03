@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher not found.
  pause
  exit /b 1
)

py -m pip install --upgrade pyinstaller
if errorlevel 1 goto :fail

py -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "PotPlayer本地AI实时翻译配置器" ^
  --add-data "plugin;plugin" ^
  app\configurator.py
if errorlevel 1 goto :fail

set "PKG=release\PotPlayer-LocalAI-Live-Translator"
set "ZIP=release\PotPlayer-LocalAI-Live-Translator-Windows.zip"

if exist "%PKG%" rmdir /s /q "%PKG%"
if exist "%ZIP%" del /q "%ZIP%"
mkdir "%PKG%"

copy /y "dist\PotPlayer本地AI实时翻译配置器.exe" "%PKG%\" >nul
copy /y "README.md" "%PKG%\README.md" >nul
copy /y "docs\使用说明.md" "%PKG%\使用说明.md" >nul
copy /y "docs\实机验收清单.md" "%PKG%\实机验收清单.md" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path '%PKG%\*' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 goto :fail

echo.
echo Build finished:
echo %cd%\dist\PotPlayer本地AI实时翻译配置器.exe
echo.
echo Customer package:
echo %cd%\%ZIP%
echo.
echo NOTE: AI models are NOT included in this package.
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
