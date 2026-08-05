@echo off
chcp 65001 >nul

echo ============================================
echo    设计总院 · 数据中心资源智能管理系统
echo    生产模式启动
echo ============================================
echo.

set ROOT_DIR=%~dp0
set BACKEND_DIR=%ROOT_DIR%backend

:: 判断数据库类型
set IS_POSTGRES=0
if not "%DATABASE_URL%"=="" (
    echo "%DATABASE_URL%" | findstr /i "postgres postgresql" >nul 2>&1
    if not errorlevel 1 set IS_POSTGRES=1
)

if "%IS_POSTGRES%"=="1" (
    echo [信息] 使用 PostgreSQL: %DATABASE_URL%
    if "%WORKERS%"=="" ( set UVICORN_WORKERS=2 ) else ( set UVICORN_WORKERS=%WORKERS% )
) else (
    if "%DATABASE_URL%"=="" (
        echo [信息] 使用 SQLite（单进程，最稳定）
    ) else (
        echo [警告] DATABASE_URL 非 PostgreSQL，回退为单进程模式：%DATABASE_URL%
    )
    set UVICORN_WORKERS=1
)

:: 初始化数据库（建表 + 内置数据）。create_all 幂等，可重复执行。
cd /d "%BACKEND_DIR%"
echo [初始化] 检查 / 初始化数据库结构...
python manage.py init
if errorlevel 1 (
    echo [警告] 数据库初始化异常，请检查 DATABASE_URL 与数据库服务是否可用
)

:: 启动后端服务
echo [启动] 后端服务 (http://0.0.0.0:8000, workers=%UVICORN_WORKERS%)...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers %UVICORN_WORKERS% --log-level info

echo.
echo 服务已停止
