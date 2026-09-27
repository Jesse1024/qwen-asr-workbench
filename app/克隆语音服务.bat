@echo off
title GPT-SoVITS 克隆语音服务
set BASE=%~dp0..
curl -s -o nul -m 2 http://127.0.0.1:9880/docs
if not errorlevel 1 goto run

if exist "E:\gpt-sovits\repo\api_v2.py" (
    echo [第一次启动需加载模型，约 1-2 分钟]
    cd /d E:\gpt-sovits\repo
    E:\gpt-sovits\.venv\Scripts\python.exe api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS\configs\tts_infer_pro.yaml
) else (
    echo [未找到 GPT-SoVITS，语音克隆功能不可用]
    pause
    exit /b
)
:run
echo 服务已在运行
pause
