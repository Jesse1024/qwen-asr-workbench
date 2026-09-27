@echo off
title Qwen3-ASR 语音转写工作台
set BASE=%~dp0..

rem 已在运行则直接打开
curl -s -o nul -m 2 http://127.0.0.1:8321/api/health
if not errorlevel 1 goto open

rem 启动后台服务（最小化窗口）
if exist "%BASE%\.venv\Scripts\pythonw.exe" (
    start "Qwen3-ASR Server" /min "%BASE%\.venv\Scripts\pythonw.exe" "%BASE%\server.py"
) else (
    echo [错误] 未找到虚拟环境，请先运行 install.bat
    pause
    exit /b 1
)

rem 等待模型加载（页面会显示连接状态）
timeout /t 12 /nobreak >nul

:open
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:8321"
) else if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:8321"
) else (
    start "" http://127.0.0.1:8321
)
