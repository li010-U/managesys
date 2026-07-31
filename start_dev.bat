@echo off
chcp 65001 >nul

echo ============================================
echo    设计总院 · 数据中心资源智能管理系统
echo    开发模式启动
echo ============================================
echo.

set ROOT_DIR=%~dp0
set BACKEND_DIR=%ROOT_DIR%backend
set FRONTEND_DIR=%ROOT_DIR%frontend

:: 检查后端依赖
echo [检查] 后端依赖...
cd /d "%BACKEND_DIR%"
python -c "import fastapi, uvicorn, sqlalchemy" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [安装] 安装后端 Python 依赖...
    pip install -r requirements.txt
)
echo [OK] 后端依赖检查通过

:: 初始化数据库
echo [检查] 数据库状态...
python manage.py init 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [警告] 数据库初始化异常，数据可能已存在
)

:: 启动后端服务
echo [启动] 后端服务 (http://127.0.0.1:8000)...
cd /d "%BACKEND_DIR%"
start "DCIM-Backend" cmd /c "title DCIM-Backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 /nobreak >nul

:: 检查前端依赖
cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo [安装] 安装前端 npm 依赖...
    call npm install
)

:: 启动前端服务
echo [启动] 前端开发服务器 (http://127.0.0.1:5173)...
cd /d "%FRONTEND_DIR%"
start "DCIM-Frontend" cmd /c "title DCIM-Frontend && npx vite --host 127.0.0.1"

echo.
echo ============================================
echo   ✅ 开发环境启动完成！
echo.
echo   前端: http://127.0.0.1:5173
echo   后端: http://127.0.0.1:8000
echo   API文档: http://127.0.0.1:8000/docs
echo.
echo   默认管理员: admin / admin@123456
echo ============================================
echo.
echo 按任意键关闭所有服务...
pause >nul

echo 正在关闭服务...
taskkill /f /fi "WINDOWTITLE eq DCIM-Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq DCIM-Frontend" >nul 2>&1
echo 已关闭
