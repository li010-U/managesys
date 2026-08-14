# SQLite → PostgreSQL 迁移说明

本系统后端已内置 PostgreSQL 支持：数据库引擎、Alembic 迁移、数据一致性体检（check-data）与备份/还原均已按 DATABASE_URL 自动切换。下面的步骤把现有 SQLite 数据完整搬到 PostgreSQL。

## 快速：一键迁移脚本（推荐）

系统提供 `backend/scripts/migrate_to_pg.py`，把「建库 → 迁移数据 → alembic → 体检 → 切换 .env」整合为一条命令，并支持回滚。

在 `backend/` 目录执行：

```
# 1) 先预览（不建库/不写库/不切配置）
python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://postgres:密码@127.0.0.1:5432/managesys" --dry-run

# 2) 全自动迁移：自动建库 + 迁移 + alembic + 体检 + 把 .env 切到 PostgreSQL
python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://postgres:密码@127.0.0.1:5432/managesys" --create-db --apply-env

# 切完后重启后端生效：
start_prod.bat
```

常用选项：
- `--dry-run`：只预览 Plan/DDL，不写任何库、不切换配置。
- `--create-db`：自动连接 `postgres` 维护库创建目标数据库（需该账号有建库权限）。
- `--apply-env`：迁移成功后自动把 `backend/.env` 的 `DATABASE_URL`（及 `DATABASE_URL_SYNC`）改到 PostgreSQL，并备份原文件为 `.env.pgmigrate.bak`。
- `--only rooms,racks,...`：只迁指定表；`--drop`：覆盖已存在的目标表。
- `--no-check`：跳过迁移后的 `check-data` 体检。

回滚（还原 .env 到迁移前的 SQLite 配置）：
```
python scripts/migrate_to_pg.py --rollback
```

> 前置要求：目标 PostgreSQL 服务可访问，且 PATH 里有 `psql`、`pg_dump`、`pg_restore`（`--create-db` 还需 `createdb`）。迁移脚本会先自动备份当前 SQLite 库（`manage.py backup`）。

---

## 0. 迁移前必读
- 迁移不影响当前 SQLite 库，可随时回滚。
- 先做一次备份，防止意外：
  ```
  cd backend
  python manage.py backup
  ```
- 以下命令都在 `backend/` 目录执行；默认读取 `backend/.env`（无则用环境变量）。

## 1. 准备 PostgreSQL
需要一台可访问的 PostgreSQL 服务器（本机或远端），并确认客户端工具可用：
```
psql --version
pg_dump --version
pg_restore --version
```
创建目标数据库（表结构由迁移脚本/Alembic 建立，不需要先建表）：
```
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE managesys;"
```

## 2. 先预览迁移计划（不建表/不写库）
```
python migrate_sqlite_to_pg.py --target "postgresql+asyncpg://postgres:YOUR_PASS@127.0.0.1:5432/managesys" --dry-run
```
检查打印出的 PostgreSQL DDL 是否符合预期。

## 3. 执行迁移（建表 + 拷贝数据）
```
python migrate_sqlite_to_pg.py --target "postgresql+asyncpg://postgres:YOUR_PASS@127.0.0.1:5432/managesys"
```
- 默认源库 `data/managesys.db`；如需指定用 `--sqlite <path>`。
- 目标表已存在且未用 `--drop` 时会以 `IF NOT EXISTS` 跳过建表并跳过外键冲突项。
- 可选 `--only rooms,racks,devices,...` 只迁指定表。
- 迁移结束会逐表输出行数，可对照源库核对。
- 需要覆盖已存在的表时加 `--drop`（会先 DROP 本次涉及的表）。

## 4. 用 Alembic 校验/补齐 schema 版本
迁移脚本已建表并写入数据，但为让 Alembic 版本表与线上一致，需在目标库跑一次升级：
```
$env:DATABASE_URL="postgresql+asyncpg://postgres:YOUR_PASS@127.0.0.1:5432/managesys"
python -c "from alembic.config import Config; from alembic import command; command.upgrade(Config('alembic.ini'), 'head')"
```
PG 使用 `asyncpg`（已写入 requirements.txt），无需 psycopg2。

## 5. 切换应用指向 PostgreSQL
编辑 `backend/.env`，把数据库连接串改为：
```
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASS@127.0.0.1:5432/managesys
```
（`.env.example` 中有相关注释。）改完重启后端即可。

## 6. 迁后体检（check-data 是否仍然通过）
```
$env:DATABASE_URL="postgresql+asyncpg://postgres:YOUR_PASS@127.0.0.1:5432/managesys"
python manage.py check-data --fix
```
`check-data` 已改为按 DATABASE_URL 自动适配 SQLite/PostgreSQL，同一套检查在 PG 上也能跑。

## 7. 备份 / 还原（PostgreSQL）
切换到 PG 后，`manage.py backup` / `restore` 会自动使用 `pg_dump -Fc` / `pg_restore`：
```
python manage.py backup                 # 生成 backups/managesys_<时间戳>.dump
python manage.py restore <备份.dump> --force   # 还原（会先自动再备份当前库）
```
- 要求服务器上装有 pg_dump / pg_restore（通常在 PostgreSQL 安装目录）。
- 计划任务里的每日 03:00 备份脚本（scripts/auto_backup.py）同样自动适配。

## 8. 回滚 / 回到 SQLite
- PostgreSQL 是“增量导入”，原 SQLite 库始终没被动过。
- 需要回退时，把 `backend/.env` 的 DATABASE_URL 改回：
  ```
  DATABASE_URL=sqlite+aiosqlite:///./data/managesys.db
  ```
- 若之后想从 PG 再导回 SQLite，可先用 `python manage.py export-json` 导出全量 JSON，再在 SQLite 下 `import-json` 拉回（两条命令均兼容两种库运行时的导出/导入逻辑）。

## 9. 注意点
- 迁移工具不负责创建 PostgreSQL 数据库本身，需先在步骤 1 建好。
- 首次在空库上建 schema 用 `alembic upgrade head`；不要先用 `manage.py init` 的 create_all 造成与 Alembic 表重复。
- PG 连接池/查询超时参数（DB_POOL_SIZE 等）在 .env 里可调。
