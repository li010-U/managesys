# 数据中心资源智能管理系统 · 前端

《数据中心资源智能管理系统》的 Web 前端，基于 Vue 3 + TypeScript + Vite。

## 技术栈
- **框架**：Vue 3（`<script setup>`）+ TypeScript
- **构建**：Vite
- **UI**：Element Plus + Element Plus 图标
- **状态管理**：Pinia
- **路由**：Vue Router
- **图表**：ECharts（vue-echarts）
- **3D 机柜视图**：Three.js
- **HTTP**：Axios（含统一拦截器与登录过期处理）

## 目录
- `src/api`：接口封装与 Axios 实例 / 拦截器
- `src/views`：业务页面（设备、机房、监控、告警、工单、巡检、系统等）
- `src/components`：通用组件（含 AI 桌宠、聊天面板等）
- `src/stores`：Pinia 状态
- `src/router`：路由配置

## 常用命令
```bash
npm install      # 安装依赖
npm run dev      # 启动开发服务器（默认 http://localhost:5173）
npm run build    # 类型检查 + 生产构建（输出到 dist/）
npm run preview  # 预览生产构建
npm run test     # 运行单元测试（Vitest）
```

## 说明
- 开发时后端默认运行在 `http://127.0.0.1:8000`，跨域来源需在 `backend/.env` 的 `CORS_ORIGINS` 中放行当前地址（详见根目录 `DEPLOY.md`）。
- 生产部署时建议由 Nginx 同源托管 `dist/` 并反向代理 `/api`，可避免额外跨域配置。
