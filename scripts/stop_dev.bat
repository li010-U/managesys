@echo off
chcp 65001 >nul
title DCIM Dev Stop
echo 正在关闭数据中心管理系统的开发环境...
cd /d "%~dp0"
python dev_server.py stop
echo.
echo 服务已关闭。
pause
