# 安全与并发稳定性修复总结

> 针对《数据中心资源智能管理系统》的一次系统性安全审计 + 并发/多人稳定性加固。
> 覆盖 14 项审计发现（#1–#14），并额外修复一个隐性数据丢失 Bug。
> 后端测试基线：62 passed；前端构建通过。

---

## 一、严重安全漏洞

### #1 文件下载路径穿越（任意文件读取）— 已修复
- **位置**：`backend/app/services/file_service.py`
- **风险**：`get_file_path()` 直接用用户可控的 `sub_dir/year/month/filename` 拼相对路径，可请求 `../../.env` 读到服务器文件（含 `SECRET_KEY`、数据库账号）。
- **修复**：
  - 新增 `_resolve_safe_path()`：`Path.resolve()` 后校验 `is_relative_to(upload_dir)`，越界抛 `ValueError`。
  - `get_file_path()` / `delete_file()` 捕获 `ValueError`，越界返回 `None`/`False`。
  - `save_upload()` 对 `sub_dir` 过滤 `/`、`\\`、`..`、开头 `.`。
- **测试**：`backend/tests/test_path_traversal.py`（正常读 / 父目录穿越 / 绝对路径 / 直接逃逸 / 删除越界 / 恶意 `sub_dir` 全部覆盖）。HTTP 冒烟确认 `../../.env`、`..%2F..%2F.env`、`a/../` 均返回 404。

### #2 RBAC 权限模型落地
- `backend/app/core/deps.py` 已有 `require_permission()` / `require_any_permission()` / `has_permission()`；各写接口补挂权限依赖。
- 覆盖：工单（work:view/create/edit/delete）、巡检（inspection:view/create/edit/delete）、机房/设备/系统/告警等接口均已接入；仅 `users.py`/`roles.py`/登录日志做 super_admin 判断的地方保持不变。
- 前端 `v-permission` 仅用于隐藏按钮，后端强制校验，不可绕过。测试：`test_permissions.py`。

### #3 注册接口开放 + 无限流 — 已修复
- 新增 `backend/app/core/ratelimit.py`（内存滑动窗口限流 `SlidingWindowLimiter` + `rate_limit()` 依赖 + `get_client_ip`）。
- 配置：`RATE_LIMIT_LOGIN_MAX=10`、`RATE_LIMIT_REGISTER_MAX=5`、`RATE_LIMIT_WINDOW_SECONDS=60`。
- 接入：`auth.py` 的 `login`/`register` 挂 `rate_limit(...)`；登录已有单账号锁定（`LOGIN_MAX_ATTEMPTS`）。
- 测试：`test_ratelimit.py`（登录/注册 429 集成测试）。

### #4 默认配置过弱 — 启动告警
- `backend/app/main.py` 新增 `_check_security_config()`，启动时若 `DEBUG=true` / `SECRET_KEY` 为默认值 / `ENABLE_CAPTCHA=false` 输出 WARNING 日志。

---

## 二、明确的代码 Bug

### #5 工单“可选处理人”接口报错（`status='active'` 列不存在）
- `get_assignable_users`：`WHERE status='active'` → `WHERE is_active = ?`（`users` 表无 `status` 列）。修复后前端处理人下拉恢复。

### #6 工单/巡检多步写操作非原子 — 已修复
- 所有状态流转（complete/verify/assign/start/close）已改为：**先 UPDATE + 再 INSERT 评论，最后单次 `with_commit_retry(db.commit)`**，同一事务一次提交，状态与评论不会出现不一致。
- 巡检 `create_task`（建任务 + 批量建巡检记录 + 更新 total_items）同样单事务提交。

### #7 巡检/工单状态机 + 归属校验 — 已修复
- **状态机**：
  - 工单：`start` 仅 `assigned/pending→processing`；`complete` 仅 `processing→pending_verify`；`verify` 仅 `pending_verify→completed/processing`；`close` 仅 `completed→closed`。非法转换返回 400。
  - 巡检任务：`start` 仅 `pending→in_progress`；`complete` 仅 `in_progress/pending→completed`。
- **归属校验**：start/complete 校验 `assignee_id`，verify/close 校验 `creator_id`（`is_super_admin` 可绕过）。

### #8 统计接口硬编码 / N+1 查询 — 已修复
- 工单 `get_stats`：7 次 COUNT → 2 次 `GROUP BY`，`my_processing` 改为真实统计（原来写死 0）。
- 巡检 `get_stats`：7 次 COUNT → 3 次（plans/tasks/issues 各一条用 `SUM(CASE ...)`），`issue_resolved` 统计 `status IN ('resolved','closed')`。

### 关键修复：`get_db` 提交判定缺陷（静默数据丢失 Bug）
- **现象**：`register` 返回 200 且给出自增 id，但 DB 中无此用户，立刻 `login` 报“用户名或密码错误”。设备/机房/用户/角色等大量 ORM 写入存在同样隐患。
- **根因**：`get_db` 只在 `session.new or session.dirty or session.deleted` 非空时提交；但服务层普遍先 `add → flush → refresh`，`flush()` 后对象已不在 `new/dirty` 中 → 判定为假 → **数据被静默回滚**（接口却返回成功）。
- **修复**：改写请求（`POST/PUT/PATCH/DELETE`）无条件提交；纯读 GET 仅在有待提交变更时提交，保证读并发不受写串行影响。
- **验证**：register→login 立即成功；device type 创建后立即可读回。
- **测试**：`test_db_retry.py::TestGetDbAutoCommitOnFlush`（回归防护）。

---

## 三、并发 / 多人稳定性

### #9 SSE 长连接占用 / 断连检测
- `assistant/stream`、`chat/messages/stream`：用 `sse_semaphore()` 限制并发长连接（`SSE_MAX_CONNECTIONS=30`），超出返回 503；每个 tick / 每字符 `request.is_disconnected()` 检测；每个 tick 用独立短会话（`async_session_factory()`），不长期占用连接池；`finally` 释放信号量。
- 前端 `PetAssistant.vue` 卸载时通过 `AbortController` 中断流。

### #10 SQLite 多进程锁隐患
- `start_prod.bat`：非 PostgreSQL 强制 `UVICORN_WORKERS=1`；仅 PostgreSQL 用 2 workers。

### #11 轮询 + 长连接叠加 — 前端可见性暂停
- `PetAssistant.vue`：页面 `document.hidden` 时 `stopStreaming()`（断 SSE + 停轮询），可见且开启实时时恢复。
- `NotificationPanel.vue`：页面隐藏时暂停 60s 轮询、可见时恢复。

### #13 统一事务 / 回滚规范
- 裸 SQL 写接口统一走 `exec_sql()` + 单次 `with_commit_retry(db.commit)`。
- `backend/app/db/retry.py`：SQLite 写锁识别 + 退遯重试 + 进程内写锁串行化（按事件循环懒创建）。
- 巡检中自动 `commit` 的辅助函数死代码已删除。

### #14 快速点击加载 / 并发超时兜底
- `backend/app/core/middleware.py`：全局 HTTP 并发限流（`HTTP_MAX_CONCURRENCY=200`），超限迅速 503 而非无限排队。
- `backend/app/core/concurrency.py`：按事件循环的信号量工具。
- `backend/app/db/compat_sql.py`：`exec_sql()` 带 `DB_QUERY_TIMEOUT=30` 单条查询超时保护。
- 前端 `api/index.ts`：请求取消（AbortController + `app:navigate`）+ `timeout: 30000` + NProgress。

---

## 四、一致性 / 设计缺失

### #12 模型/接口“半 ORM 半裸 SQL” → Pydantic schema 校验 — 已修复
- 工单写接口全部改用既有 schema：`WorkOrderCreate/Update/Assign/Process/Verify/Close/CommentCreate/CategoryCreate`。
- 巡检写接口改用：`InspectionTemplateCreate/PlanCreate/PlanUpdate/RecordCreate/IssueCreate`。
- 修复 `update_plan` 中一段有隐患的取值逻辑，改用 `model_dump(exclude_unset=True)`。
- 效果：缺必填字段（如 `title`、`assignee_id`、`accept`、`item_name`、`issue_title`）或非法取值（如 `satisfaction=99`）统一返回 **422**。

---

## 五、验证

| 项 | 结果 |
| --- | --- |
| 后端 pytest | **62 passed** |
| 应用加载 | openapi 路径 77 |
| 前端构建 | `npm run build` 通过 |
| 真实 uvicorn 冒烟 | 工单全状态机 / 巡检增改 / RBAC / 路径穿越 404 / register→login 持久化 / device 持久化 全部通过 |

---

## 六、涉及文件

**后端核心**
- `backend/app/core/deps.py`、`config.py`、`main.py`
- `backend/app/core/ratelimit.py`（新）、`concurrency.py`（新）、`middleware.py`（新）
- `backend/app/db/retry.py`（新）、`compat_sql.py`（新）
- `backend/app/services/file_service.py`

**后端接口**
- `api/v1/auth.py`、`alerts.py`、`devices.py`、`facilities.py`、`sensors.py`、`systems.py`、`users.py`、`roles.py`、`work_orders.py`、`inspection.py`、`assistant.py`、`chat.py`、`audit_logs.py`

**前端**
- `src/api/index.ts`、`src/router/index.ts`、`src/App.vue`、`src/layouts/MainLayout.vue`
- `src/components/assistant/PetAssistant.vue`、`src/components/notification/NotificationPanel.vue`
- `src/views/dashboard/DashboardView.vue`

**测试**（均为新增）
- `backend/tests/test_concurrency.py`、`test_db_retry.py`、`test_path_traversal.py`、`test_permissions.py`、`test_ratelimit.py`

**启动/运维**
- `start_prod.bat`、`backend/.env.example`