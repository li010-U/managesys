@echo off
chcp 65001 >nul
title DCIM Dev Server

echo ============================================
echo   数据中心资源智能管理系统 · 一键启动
echo ============================================
echo.
cd /d "%~dp0"

:: 检测并启动服务
python dev_server.py start

echo.
timeout /t 2 /nobreak >nul

:: 自动打开前端页面
start "" "http://127.0.0.1:5173"

echo ------------------------------------------------------------
echo   已启动！
echo     前端: http://127.0.0.1:5173
echo     后端: http://127.0.0.1:8000
echo     API文档: http://127.0.0.1:8000/docs
echo.
echo   关闭全部服务请运行  stop_dev.bat
echo ------------------------------------------------------------
echo.
pause
