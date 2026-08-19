# 部署与升级指南

本文档说明如何把代码部署到**内网服务器**，以及如何切换/更换 AI 助手的模型 provider。

> 重点\uff1a内网部署版必须升级到本仓库最新代码，AI 助手的重复回复修复才会生效。
> 若回复仍出现\u300c大量重复/滚雪球/英文乱码\u300d\uff0c多数情况是**模型渠道退化**\uff0c请按\u300c更换模型\u300d一节处理。

---

## 1. 内网部署版升级到最新代码\uff08解决\u300c回复还是重复\u300d\uff09

生产环境由 `scripts\start_dev.bat` 启动\uff08后端 0.0.0.0:8000\uff0c前端构建后由 Nginx/静态托管\uff09\u3002

在内网服务器上执行\uff1a

```bat
:: 1) 拉取最新代码\uff08含全部 AI 助手修复\uff09
cd <内网项目目录>
git pull origin main

:: 2) 确认/安装后端依赖
cd backend
pip install -r requirements.txt

:: 3) 初始化数据库\uff08建表 + 内置数据，幂等可重复执行\uff09
python manage.py init

:: 4) 确认 .env 中的 LLM 配置\uff08见 \u7b2c 2 节\uff09
::     把 .env.example 里新增的 LLM 段拷贝到 backend/.env

:: 5) 停止旧后端并重新启动
::    生产：在项目根执行 scripts\start_dev.bat（开发）或 scripts\start_prod.bat（生产）
::    或后台启动：python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

:: 6) 重新构建并部署前端\uff08前端也改过桌宠轮询频率\uff09
cd ..\frontend
npm install
npm run build
:: 把 frontend/dist 部署到 Nginx/静态目录
```

验证升级成功\uff1a
- 打开系统 \u2192 AI 助手提问\u300c给今天的运维建议\u300d\uff0c回复应是**单份、无重复**的内容。
- 后端日志无 SyntaxError/导入错误。

---

## 2. AI 助手模型 provider 配置\uff08backend\.env\uff09

`.env.example` 已新增完整 LLM 配置段。 `backend\.env` 里由 `LLM_PROVIDER` 控制使用哪家，`=deepseek / openai / internal` 三选一\uff1a

```ini
# --- 当前使用的 provider ---
LLM_PROVIDER=deepseek

# --- DeepSeek ---
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=换成正常的key
LLM_MODEL=deepseek-chat

# --- OpenAI (切到 openai 时用) ---
# OPENAI_BASE_URL=https://api.openai.com
# OPENAI_API_KEY=...

# --- 内网 coding/paas (切到 internal 时用) ---
# INTERNAL_LLM_BASE_URL=http://172.16.133.249/api/coding/paas/v4
# INTERNAL_LLM_KEY=...
```

改完 .env 后**必须重启后端**才生效。

---

## 3. 更换/切换正常中文模型

AI 助手需要**能正确识别中文**的模型。两个可用方向\uff1a

1. 更换 DeepSeek/其它中文key\uff1a申请一个正常的 `deepseek-chat` / 通义 / 智谱 等 key，填入 `DEEPSEEK_API_KEY`\u3002
2. 切回内网渠道\uff1a当内网 coding/paas 恢复\uff08此前偶发 503 无可用渠道\uff09后，`LLM_PROVIDER=internal` 并填 `INTERNAL_LLM_BASE_URL`\u3001`INTERNAL_LLM_KEY`\u3002

> 排查\uff1a若某个 key 回复总是把中文当\u300c问号/乱码\u300d并给英文话术，就是这个模型变体不识别中文（例如异常的 deepseek-v4-flash），请换 key 而非改代码。

---

## 4. 本仓库已内置的 AI 助手稳定性修复\uff08含本次升级\uff09

- 重复回复\uff1a历史回填截断、频率/存在惩罚、流式复读早停、输出裁剪、历史清洗\u3002
- 中文乱码守卫\uff1a模型把中文当乱码输出英文时，自动回退中文提示\u3002
- 快照缓存 + 桌宠轮询降频\uff1a降低多人同时在线时的请求/数据库查询量\u3002
- 并发控制\uff1aSSE 长连接上限、HTTP 并发限流\uff0c避免\u300c点快了加载不出来\u300d\u3002

---

## 5. 常见问题排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 回复大量重复/滚雪球 | 内网还是旧代码 | 先按 \u7b2c 1 节升级 |
| 升级后仍乱码/英文 | 模型 key 退化 | 按 \u7b2c 3 节换 key/\u5207 provider |
| 登录不了 | SECRET_KEY 未改或重置 | 检查 .env 的 SECRET_KEY 是否一致 |
| 内网接口 503 | coding/paas 渠道不可用 | 暂时切到能用的 provider |


---

## 6. Python 运行环境（统一）

系统统一使用仓库根目录的 `.venv` 作为 Python 解释器（`.venv\Scripts\python.exe`），
不存在时回退系统 Python。`.venv` 已配置为复用系统 site-packages（`include-system-site-packages=true`），
因此无需重新下载依赖即可直接运行。

- 所有入口已统一解析 `.venv`：`scripts\start_prod.bat`、`scripts\start_dev.bat`（及 `scripts\dev_server.py`）、
  `backend\scripts\start_backend.ps1`（开机守护）、`backend\scripts\install_tasks.ps1`（计划任务）。
- 手动操作建议：`cd backend && ..\.venv\Scripts\python.exe manage.py <命令>`。
- `requirements.txt` 已更新为 Python 3.14 可安装的已验证版本。若在全新机器上从零建环境：
  ```
  cd D:managesys
  python -m venv --system-site-packages .venv
  .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  ```
  其中 `--system-site-packages` 让 `.venv` 复用系统已装包；如需完全隔离可去掉该参数（需联网安装）。

---

## 10. 安全加固清单（本版本新增）说明

部署前请在 `backend/.env` 中确认以下配置（`backend/.env.example` 已含注释）：

1. **SECRET_KEY（必须）**：务必设置为随机强密钥，不要使用默认值。
   否则攻击者可用已知密钥伪造任意用户登录。生成方式：
   `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. **INIT_ADMIN_PASSWORD（必须）**：首次初始化管理员初始密码的随机值。
   默认管理员账号首次登录会被**强制修改密码**（前端弹窗），但初始值本身
   仍应设置为强随机值，避免初始化后被猜到。
3. **DEBUG=false**：生产环境必须关闭，避免回显完整 SQL / 详细报错。
4. **ENABLE_CAPTCHA=true**：公网暴露时建议开启验证码。
5. **ENABLE_CAPTCHA / LOGIN_MAX_ATTEMPTS**：登录失败锁定已内置。
6. **ENFORCE_SECURITY（生产建议 true）**：设为 true 后，启动时若检测到不可妥协项
   （`DEBUG=true` 或默认 `SECRET_KEY`），应用会**直接拒绝启动**（raise），不再仅仅
   发出警告，避免带病上线。开发环境保持 false。

本版本新增/强化的行为：
- JWT 采用 `PyJWT`（`requirements.txt` 已替换 `python-jose`，修复相关 CVE；
  若旧环境未安装，请 `pip install -r requirements.txt`）。
- 修改密码后使已签发令牌全部失效（`token_version` 递增），实现会话作废。
- 新增 `ALLOWED_HOSTS`：校验 Host 头，防 Host 头投毒（生产按实际域名配置）。
- 新增安全响应头（CSP / X-Frame-Options / X-Content-Type-Options 等）。
- AI 助手与聊天接口：需要 `monitor:view_dashboard` 权限，并按用户限流
  （`CHAT_RATE_LIMIT_MAX` / `CHAT_RATE_LIMIT_WINDOW_SECONDS`），防 LLM 成本滥用。
- 通用文件上传 `/files/upload` 收紧为仅超级管理员可用，头像上传校验真实图片文件头。

> 注：`DEPLOY.md` 全文历史说明（如"回帖重复/模型渠道"等）对应此前迭代，
> 与本次安全加固无关，可保留。

## 11. 数据库迁移（Alembic）

从本版开始，数据库表结构改动建议统一走 Alembic 迁移，不再依赖启动时的 create_all 硬加列（_ensure_columns）。

当前已生成根基线迁移：`backend/alembic/versions/5c9d0be78b8c_baseline_full_schema.py`，并将现有数据库标记为已应用该迁移（stamp）。

当你修改了 `backend/app/models/` 中的模型（新增/删除表或列、修改约束）后：

```bash
cd backend
# 生成迁移脚本（自动对比模型与数据库）
python -m alembic revision --autogenerate -m "describe your change"
# 审查生成的文件，然后应用
python -m alembic upgrade head
```

常用命令：
- `python -m alembic current`：查看当前迁移版本
- `python -m alembic history`：查看迁移历史
- `python -m alembic check`：检查模型与数据库是否有差异（只报告不修改）

注意：
- 迁移文件属于源码，应随版本控制提交。
- 不依赖 Alembic 时建议保持启动时的 create_all 作为新存数据库的底座，在新存库上 可用 `alembic upgrade head` 建立全量结构；已有数据库不会重复创建。


## 12. 运行测试

后端测试套件（pytest）：在**项目根目录**或 **backend 目录**均可直接运行，两种方式等效（根目录已提供 pytest.ini 指定 testpaths 与 asyncio 配置）：

```bat
cd D:\managesys
.venv\Scripts\python.exe -m pytest -q -p no:warnings

:: 或
cd D:\managesys\backend
..\.venv\Scripts\python.exe -m pytest -q -p no:warnings
```

说明：
- 根目录 `pytest.ini` 仅配置了 pytest-asyncio（asyncio_mode=auto）与 `testpaths = backend/tests`。该配置为单一源，从根目录或 backend 目录运行时 pytest 都会向上发现根目录 `pytest.ini`。
- 测试使用隔离的临时 SQLite，不会触碰线上 `data/managesys.db`。



## 12.1 多进程（worker）部署说明：限流与后台任务

当前系统的并发限流、SSE 连接数限制，以及 4 个内置后台任务（数据保留清理、告警自动升级、告警生命周期、环境数据轮询）都是**单进程内**实现（内存信号量与 asyncio 任务，位于 `app/core/concurrency.py` 与 `app/main.py` 的启动逻辑）。这意味着：

- **单 worker（`uvicorn --workers 1`，默认/开发模式）**：各限流与后台任务工作正常，这是推荐且已充分验证的部署形态。
- **盲目开启多 worker（`--workers N`，N>1）**：每个 worker 会各自再跑一遍后台任务（出现「重复清理/重复升级/重复轮询」），且限流与 SSH 连接数各按进程独立计数，整体行为会失真，甚至出现数据竞争。

因此生产扩容请遵循以下原则，**不要「拆东墙补西墙」地直接加 worker**：
1. 优先迁移到 PostgreSQL（见第 13 节）以提升写入并发，仍保持单 worker。
2. 确实需要多 worker 时，必须先落地 Redis 集中状态（`requirements.txt` 取消 `redis` 注释、`.env` 配置 `REDIS_URL`，并将后台任务调度改为「分布式互斥/只在一个实例执行」），否则多 worker 会引入新问题。
3. 在未配置 Redis 前，`--workers` 请一律保持为 1。

## 13. 迁移到 PostgreSQL（提升并发承载）

当前系统默认使用 SQLite（单写者串行化，高并发下 `sensor_data` 高频写入会出现排队超时）。若需支撑更高并发，建议迁移到 PostgreSQL。工具链与代码方言适配均已就绪，可直接按下面步骤执行。

### 前置条件
- 安装 PostgreSQL 服务器与客户端工具（`psql / pg_dump / pg_restore / createdb`），并确保其所在目录已加入 `PATH`。
- 安装 PyPI 依赖：`pip install asyncpg psycopg2-binary`。
- （可选，多 worker）如需开启多个 worker，请先阅读下方「多进程（worker）部署说明」并配置 Redis 集中限流/任务互斥，否则不要盲目开启多个 worker。

### 一键迁移（在 backend 目录下）
```bat
:: 1) 先备份 SQLite 库（迁移脚本也会自动再做一次）
python manage.py backup

:: 2) 预览（不建库/不写库/不切配置）
python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://user:pass@127.0.0.1:5432/managesys" --dry-run

:: 3) 全自动迁移：建库 + 搬数据 + alembic 补齐 + 体检 + 切换 .env
python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://user:pass@127.0.0.1:5432/managesys" --create-db --apply-env

:: 4) 重启后端生效（scripts\start_prod.bat 或 uvicorn 均会读取 .env 里的 DATABASE_URL）
```

### 回滚
```bat
:: 还原 .env 到迁移前的 SQLite 配置
python scripts/migrate_to_pg.py --rollback
```

### 跨方言兼容说明
- 检索类 `LIKE` 已统一为 `LOWER(col) LIKE ?` 且参数小写化，SQLite 与 PostgreSQL 搜索结果一致。
- 原生 INSERT 里 SQLite 专有的 `datetime('now','localtime')` 已由 `app/db/compat_sql.py` 的 `translate_sql()` 在非 SQLite 方言下自动映射为 `CURRENT_TIMESTAMP`；`?` 占位符也由同一模块按方言转换。
- 模型时间列多为 `DateTime(timezone=True)`，PostgreSQL 存 UTC timestamptz、读取时转本地时区；SQLite 存本地时间文本，两侧语义各自一致。


---

## 14. 内网部署访问配置（CORS / ALLOWED_HOSTS）

多人通过内网 IP/域名访问时，后端默认只放行 localhost，必须按实际访问地址配置 `.env`。
以下条目**逗号分隔或 JSON 数组两种写法都支持**（已在配置层统一兼容，避免启动报错）。

### 14.1 允许访问的 Host（必配）
```ini
# 填前端/后端的实际访问域名或 IP（可带端口），逗号分隔
ALLOWED_HOSTS=192.168.1.10,dcimanage.example.com,10.0.0.5:5173
```

### 14.2 允许跨域的前端来源 CORS（按需）
```ini
# 仅当"前端页面"与"后端 API"不同源（不同端口/IP）时才需要。
# 生产若由 Nginx 同源托管 dist 并反代 /api，可留空为 localhost 两项。
CORS_ORIGINS=http://192.168.1.10:5173,http://10.0.0.5:5173
```

### 14.3 PostgreSQL 连接（提高并发承载，多人必选）
```ini
DATABASE_URL=postgresql+asyncpg://用户名:密码@127.0.0.1:5432/managesys
```
- 完整的 SQLite→PostgreSQL 迁移（建库、搬数据、切 .env）见 **第 13 节** 的 `scripts/migrate_to_pg.py` 一键流程。
- `start_prod.bat` 会自动识别 PostgreSQL 并切到多 worker；SQLite 时保持单进程最稳。
- 多个后端 worker 共享限流/验证码时，建议再配 `REDIS_URL`（见 `backend/.env.example`）。

> 改完 `.env` 后必须重启后端才生效。
