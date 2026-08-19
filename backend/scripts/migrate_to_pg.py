# -*- coding: utf-8 -*-
"""SQLite -> PostgreSQL 一键迁移脚本。

把"建库 -> 迁移数据 -> alembic 补齐版本 -> 体检 -> 切换 .env"整合为一条命令，
并支持回滚（还原 .env）。所有步骤幂等、可重复执行。

用法（在 backend 目录下）:
    # 1) 预览（不建库/不写库/不切配置）
    python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://postgres:密码@127.0.0.1:5432/managesys" --dry-run

    # 2) 全自动迁移（自动建库 + 迁移数据 + alembic + 体检 + 切换 .env，需重启后端生效）
    python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://postgres:密码@127.0.0.1:5432/managesys" --create-db --apply-env

    # 3) 只迁移数据、不切配置（仍用 SQLite 跑，等确认后再手动切）
    python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://postgres:密码@127.0.0.1:5432/managesys"

    # 4) 回滚 .env 到迁移前的 SQLite 配置
    python scripts/migrate_to_pg.py --rollback

环境变量:
    PG_URL         - 目标 PostgreSQL 连接串（--pg-url 优先级更高）
    也接受 DATABASE_URL（但注意：应用当前 DATABASE_URL 若已是 PG，迁移源仍是 SQLite 文件）
"""
from __future__ import annotations
import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # backend/
ENV_FILE = ROOT / ".env"
ENV_BAK = ROOT / ".env.pgmigrate.bak"
SQLITE_DEFAULT = ROOT / "data" / "managesys.db"


# ---------- 工具 ----------
def sh(cmd: list[str], env: dict | None = None, cwd: str | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    sys.stdout.flush()
    return subprocess.run(cmd, env=full_env, cwd=cwd or str(ROOT))


def _e(msg: str):
    print("[错误] " + msg, file=sys.stderr)


def _ok(msg: str):
    print("[OK] " + msg)


def _info(msg: str):
    print("[信息] " + msg)


def _has_tool(name: str) -> bool:
    return shutil.which(name) is not None


# ---------- 解析 PG URL ----------
def parse_pg_url(url: str) -> dict:
    """解析连接串。full 保留 asyncpg 风格（应用/alembic/迁移所需）；
    psql 为去掉 +asyncpg 的客户端 DSN（psql/pg_dump/createdb 用）。"""
    raw = url.strip()
    # 校验并把 postgres:// 归一为 postgresql://，但保留 +asyncpg 标志
    u = raw
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    base = u.replace("+asyncpg://", "://", 1)
    if not base.startswith("postgresql://"):
        raise ValueError("不是 PostgreSQL 连接串: " + url[:40])
    parsed = urllib.parse.urlparse(base)
    db = parsed.path.lstrip("/")
    return {
        "full": u,                                       # 应用用（含 +asyncpg）
        "psql": base,                                    # 客户端工具用（去 +asyncpg）
        "user": parsed.username or "",
        "password": parsed.password or "",
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "db": db,
    }


def maint_url(info: dict) -> str:
    """连接 'postgres' 维护库以执行 CREATE DATABASE。"""
    auth = ""
    if info["user"]:
        auth = info["user"]
        if info["password"]:
            auth += ":" + urllib.parse.quote(info["password"], safe="")
        auth += "@"
    return "postgresql://%s%s:%s/postgres" % (auth, info["host"], info["port"])


def db_exists(info: dict) -> bool:
    # 用维护库查询目标库是否存在。psql 不支持 :db 参数绑定，db 名需文本转义。
    # 与 create_db 一致地传入 _pg_env，保证 host/port/user/password 与 PG* 环境统一生效。
    dbq = info["db"].replace("'", "''")
    cmd = ["psql", maint_url(info), "-tAc", "SELECT 1 FROM pg_database WHERE datname='%s'" % dbq]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, **_pg_env(info)))
    return r.returncode == 0 and r.stdout.strip() == "1"


def create_db(info: dict) -> bool:
    _info("创建数据库: %s" % info["db"])
    cmd = ["createdb", "-h", info["host"], "-p", str(info["port"]), info["db"]]
    auth_env = _pg_env(info)
    r = subprocess.run(cmd, env=dict(os.environ, **auth_env), capture_output=True, text=True)
    if r.returncode == 0:
        return True
    # 已存在也视为成功
    if "already exists" in (r.stderr or "").lower() or "does already exist" in (r.stderr or "").lower():
        _info("数据库已存在，跳过创建")
        return True
    _e("创建数据库失败: %s" % (r.stderr or r.stdout))
    return False


def _pg_env(info: dict) -> dict:
    """psql/pg_dump 需要的环境变量，避免密码出现在命令行进程列表。"""
    env = {}
    if info["user"]:
        env["PGUSER"] = info["user"]
    if info["password"]:
        env["PGPASSWORD"] = info["password"]
    env["PGHOST"] = info["host"]
    env["PGPORT"] = str(info["port"])
    return env


# ---------- .env 切换 ----------
def read_env() -> str:
    if ENV_FILE.exists():
        return ENV_FILE.read_text(encoding="utf-8")
    return ""


def backup_env():
    if ENV_FILE.exists() and not ENV_BAK.exists():
        shutil.copy2(ENV_FILE, ENV_BAK)
        _info("已备份原 .env -> %s" % ENV_BAK)


def set_databases_url(pg_dsn: str):
    """把 .env 里的 DATABASE_URL 与 DATABASE_URL_SYNC 设为 PG。"""
    backup_env()
    lines = []
    had_async = had_sync = False
    for line in read_env().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("DATABASE_URL=") or stripped.startswith("DATABASE_URL "):
            lines.append("DATABASE_URL=" + pg_dsn)
            had_async = True
            continue
        if stripped.startswith("DATABASE_URL_SYNC=") or stripped.startswith("DATABASE_URL_SYNC "):
            sync = pg_dsn.replace("+asyncpg://", "://", 1).replace("+aiosqlite://", "://", 1)
            lines.append("DATABASE_URL_SYNC=" + sync)
            had_sync = True
            continue
        lines.append(line)
    if not had_async:
        lines.append("DATABASE_URL=" + pg_dsn)
    if not had_sync:
        lines.append("DATABASE_URL_SYNC=" + pg_dsn.replace("+asyncpg://", "://", 1))
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _ok(".env 已切换 DATABASE_URL 到 PostgreSQL")


def rollback_env() -> bool:
    if not ENV_BAK.exists():
        _e("找不到备份 %s，无法回滚" % ENV_BAK)
        return False
    shutil.copy2(ENV_BAK, ENV_FILE)
    _ok("已还原 .env 到迁移前配置")
    return True


# ---------- 迁移主流程 ----------
def run_migrate(info: dict, sqlite: str, dry_run: bool, only: str | None, drop: bool):
    import subprocess as sp
    cmd = [sys.executable, str(ROOT / "migrate_sqlite_to_pg.py"), "--sqlite", sqlite, "--target", info["full"]]
    if dry_run:
        cmd.append("--dry-run")
    if only:
        cmd += ["--only", only]
    if drop:
        cmd.append("--drop")
    r = sp.run(cmd, cwd=str(ROOT))
    return r.returncode == 0


def run_alembic(info: dict):
    env = dict(os.environ, DATABASE_URL=info["full"])
    _info("对 PostgreSQL 运行 alembic upgrade head ...")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=str(ROOT), env=env)
    if r.returncode != 0:
        _e("alembic upgrade head 失败。schema 已由迁移脚本建立，可忽略或手动检查。")
        return False
    _ok("alembic upgrade head OK")
    return True


def run_check_data(info: dict, fix: bool):
    env = dict(os.environ, DATABASE_URL=info["full"])
    cmd = [sys.executable, "manage.py", "check-data"]
    if fix:
        cmd.append("--fix")
    _info("对 PostgreSQL 运行数据一致性体检 check-data ...")
    r = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return r.returncode == 0


def main() -> int:
    p = argparse.ArgumentParser(description="SQLite -> PostgreSQL 一键迁移")
    p.add_argument("--pg-url", default=None, help="目标 PostgreSQL 连接串")
    p.add_argument("--sqlite", default=str(SQLITE_DEFAULT), help="源 SQLite 文件")
    p.add_argument("--create-db", action="store_true", help="自动创建目标数据库")
    p.add_argument("--apply-env", action="store_true", help="迁移成功后把 .env 切到 PostgreSQL")
    p.add_argument("--dry-run", action="store_true", help="仅预览不写库不切配置")
    p.add_argument("--only", default=None, help="只迁指定表（逗号分隔）")
    p.add_argument("--drop", action="store_true", help="覆盖已存在的目标表")
    p.add_argument("--no-check", action="store_true", help="跳过迁移后的体检")
    p.add_argument("--rollback", action="store_true", help="还原 .env 到迁移前配置")
    args = p.parse_args()

    if args.rollback:
        return 0 if rollback_env() else 1

    pg_url = args.pg_url or os.environ.get("PG_URL")
    if not pg_url:
        _e("请提供 --pg-url 或设置 PG_URL")
        return 2
    try:
        info = parse_pg_url(pg_url)
    except ValueError as e:
        _e(str(e))
        return 2

    sqlite = str(Path(args.sqlite).resolve())
    if not Path(sqlite).exists():
        _e("源 SQLite 库不存在: %s" % sqlite)
        return 2

    if not args.dry_run:
        need = ["psql", "pg_dump", "pg_restore", "createdb"] if args.create_db else ["psql", "pg_dump", "pg_restore"]
        missing = [t for t in need if not _has_tool(t)]
        if missing:
            _e("缺少 PostgreSQL 客户端工具: %s（请安装并加入 PATH）" % ", ".join(missing))
            return 2

        _info("迁移前备份 SQLite 库（安全）...")
        # 用 manage.py backup 取在线一致性备份
        r = subprocess.run([sys.executable, "manage.py", "backup"], cwd=str(ROOT))
        if r.returncode != 0:
            _e("SQLite 备份失败，已中止，以免意外。")
            return 1

    if args.create_db and not db_exists(info):
        if not create_db(info):
            return 1

    _info("目标: %s" % info["psql"])
    if not run_migrate(info, sqlite, args.dry_run, args.only, args.drop):
        _e("数据迁移失败")
        return 1

    if not args.dry_run:
        run_alembic(info)
        if not args.no_check:
            run_check_data(info, fix=True)

    if args.apply_env and not args.dry_run:
        set_databases_url(info["full"])

    if args.apply_env and not args.dry_run:
        _info("完成！请重启后端生效：start_prod.bat 或 python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    elif args.dry_run:
        _info("[DRY-RUN] 完成，未建库/未写库/未切换配置。")
    else:
        _info("数据已迁移到 PostgreSQL，但 .env 未切换，系统仍在 SQLite 上运行。确认后执行:")
        _info('  python scripts/migrate_to_pg.py --pg-url "%s" --apply-env' % pg_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
