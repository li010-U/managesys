@echo off
chcp 65001 >nul

echo ============================================
echo    设计总院 · 数据中心资源智能管理系统
echo    生产模式启动
echo ============================================
echo.

set ROOT_DIR=%~dp0
set BACKEND_DIR=%ROOT_DIR%backend

:: 检查环境变量
if "%DATABASE_URL%"=="" (
    echo [信息] 使用 SQLite 作为数据库
) else (
    echo [信息] 使用 PostgreSQL 作为数据库: %DATABASE_URL%
)

:: 启动后端服务
echo [启动] 后端服务 (http://127.0.0.1:8000)...
cd /d "%BACKEND_DIR%"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --log-level info

echo.
echo 服务已停止
