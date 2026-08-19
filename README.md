# 数据中心资源智能管理系统

面向数据中心/机房运维场景的资源智能管理系统，涵盖设备与机房管理、实时监控、告警生命周期、AI 智能助手、工单与巡检、IP/VLAN 资源、审计与权限等能力。

## 技术栈
- **后端**：FastAPI + SQLAlchemy (asyncio) + SQLite（可迁移 PostgreSQL）
- **前端**：Vue 3 + TypeScript + Vite + Element Plus + ECharts + Three.js
- **数据库迁移**：Alembic

## 目录结构
- `backend/app`：后端源码（`api` 路由、`services` 业务、`models` 模型、`schemas` 数据校验、`core` 配置/安全/限流、`db` 数据库会话与兼容层）
- `backend/manage.py`：命令行入口（`init` 初始化数据库、`backup` 备份等）
- `frontend`：Vue 3 前端
- `scripts`：启动/停止脚本
- `docs`：设计文档
- `tools`：压测 / 辅助工具

## 快速开始
```bash
# 1) 初始化数据库（建表 + 内置数据，幂等）
cd backend
..\.venv\Scripts\python.exe manage.py init

# 2) 启动后端（生产脚本：scripts\start_prod.bat，开发：scripts\start_dev.bat）
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3) 启动前端（另开终端）
cd ../frontend
npm install
npm run dev
# 浏览器访问 http://localhost:5173
```

## 测试
```bash
# 项目根目录或 backend 目录均可（根目录已配置 pytest.ini）
.venv\Scripts\python.exe -m pytest -q
```

## 部署与运维
- 部署、升级、安全加固、PostgreSQL 迁移、内网访问配置详见根目录 `DEPLOY.md`。
- 生产以 `scripts\start_prod.bat` 启动，默认端口 `8000`，SQLite 单进程、PostgreSQL 自动多 worker。
