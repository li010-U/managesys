@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo   设计总院·数据中心资源智能管理系统
echo   一键停止（后端守护 + 可选 PG）
echo ============================================

set ROOT_DIR=%~dp0..
set BACKEND_DIR=%ROOT_DIR%backend
set DAEMON=%BACKEND_DIR%\scripts\start_backend.ps1
set PG_SVC=managesys-pg

:: ---------- 1) 停止后端守护与进程 ----------
echo [1/2] 停止后端服务...
if exist "%DAEMON%" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%DAEMON%" -Stop
) else (
    :: 兜底：按端口停 uvicorn
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%P >nul 2>&1
    )
)

:: ---------- 2) 停止 PostgreSQL 服务 ----------
echo [2/2] 停止数据库服务 %PG_SVC%...
net stop %PG_SVC% >nul 2>&1
if errorlevel 1 (
    echo      [提示] 数据库服务停止失败或本需管理员权限（可忽略，或手动执行: net stop %PG_SVC%）
) else (
    echo      数据库服务已停止。
)

echo.
echo 已停止。如仅需重启后端，运行 scripts\start_all.bat 即可自动重新拉起 PG。
endlocal
