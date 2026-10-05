@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>nul || (echo [ERROR] Need Git & pause & exit /b 1)
where node >nul 2>nul || (echo [ERROR] Need Node.js 18+ & pause & exit /b 1)
if not exist runtime\qishui-api\.git (
  mkdir runtime 2>nul
  git clone https://github.com/guowenye/qishui-api.git runtime\qishui-api
) else (
  git -C runtime\qishui-api pull --ff-only
)
cd runtime\qishui-api
call npm install
if errorlevel 1 pause & exit /b 1
echo.
echo qishui-api starting on http://0.0.0.0:3300
echo Keep this window open while Kodi is using the plugin.
call npm start
pause
