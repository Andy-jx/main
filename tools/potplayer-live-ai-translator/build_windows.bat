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

echo.
echo Build finished:
echo %cd%\dist\PotPlayer本地AI实时翻译配置器.exe
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
