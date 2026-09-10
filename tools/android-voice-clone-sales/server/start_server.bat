@echo off
setlocal
chcp 65001 >nul
if "%COSYVOICE_ROOT%"=="" set "COSYVOICE_ROOT=D:\CosyVoice"
if "%COSYVOICE_MODEL%"=="" set "COSYVOICE_MODEL=%COSYVOICE_ROOT%\pretrained_models\Fun-CosyVoice3-0.5B"

echo [声音复刻服务]
echo COSYVOICE_ROOT=%COSYVOICE_ROOT%
echo MODEL=%COSYVOICE_MODEL%
echo.
python -m pip install -r "%~dp0requirements-extra.txt"
if errorlevel 1 goto :err
python "%~dp0app.py"
goto :eof

:err
echo.
echo 安装依赖失败，请确认当前终端已经进入 CosyVoice 的 Python/Conda 环境。
pause
