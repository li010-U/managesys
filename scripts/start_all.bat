·AA@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo   设计总院·数据中心资源智能管理系统
echo   一键启动（PG + 后端守护）
echo ============================================
echo.

set ROOT_DIR=%~dp0..
set BACKEND_DIR=%ROOT_DIR%backend
set PG_SVC=managesys-pg
set DAEMON=%BACKEND_DIR%\scripts\start_backend.ps1

:: ---------- 1) 启动 PostgreSQL 服务 ----------
echo [1/3] 检查数据库服务 %PG_SVC% ...
net start %PG_SVC% >nul 2>&1
if errorlevel 1 (
    sc query %PG_SVC% | findstr /i "RUNNING" >nul 2>&1
    if not errorlevel 1 (
        echo      数据库服务已在运行。
    ) else (
        echo      [警告] 无法启动数据库服务。请以管理员身份重新运行本脚本，或手动执行: net start %PG_SVC%
    )
) else (
    echo      数据库服务已启动。
)

:: ---------- 2) 等待数据库就绪 ----------
echo [2/3] 等待数据库就绪 ...
set /a tries=0
:wait_db
set /a tries+=1
powershell -NoProfile -Command "try { $c = Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto db_ok
if %tries% GEQ 15 (
    echo      [警告] 等待超时（约30秒），数据库可能未就绪。仍将尝试启动后端。
    goto db_ok
)
timeout /t 2 /nobreak >nul
goto wait_db
:db_ok
echo      数据库已就绪（端口 5433）。

:: ---------- 3) 启动后端守护 ----------
echo [3/3] 启动后端守护（后台运行，日志: backend\scripts\backend.out.log）...
if not exist "%DAEMON%" (
    echo      [错误] 未找到守护脚本: %DAEMON%
    goto end
)
start "managesys-backend" powershell -NoProfile -ExecutionPolicy Bypass -File "%DAEMON%"

echo.
echo 后端守护已在后台启动。访问: http://localhost:8000
echo 停止后端守护请运行 scripts\stop_all.bat，停库请执行: net stop %PG_SVC%
:end
endlocal
