@echo off
title Qwen3-ASR 语音转文字
if "%~1"=="" (
    echo 用法：把音频文件拖到本文件图标上
    echo.
    pause
    exit /b
)
E:\qwen3-asr\.venv\Scripts\python.exe E:\qwen3-asr\transcribe.py %*
echo.
echo ==================== 完成 ====================
pause
