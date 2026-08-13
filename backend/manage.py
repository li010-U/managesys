#!/usr/bin/env python3
"""数据库管理入口"""
import os
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))


def cmd_help():
    """显示帮助信息"""
    print("""
数据库管理工具 - 数据中心资源智能管理系统
===========================================

用法: python manage.py <command> [args]

命令:
  init          - 初始化数据库（创建表 + 内置数据）
  migrate       - 创建新迁移（检测模型变更）
  upgrade       - 应用所有待处理的迁移
  downgrade     - 回滚最后一步迁移
  reset         - 重置数据库（删除所有表重建 + 初始化数据）
  show          - 显示当前数据库信息
  create-admin  - 重新创建管理员账号
  backup        - 在线一致性备份数据库 -> backups/managesys_<时间戳>.db
  restore       - 从备份还原数据库: python manage.py restore <backup.db> [--force]
  export-json   - 全量表数据导出为 JSON: python manage.py export-json [输出路径]
  import-json   - 导入 JSON（清空+重放，幂等）: python manage.py import-json <input.json> [--force]
  check-data    - 数据一致性体检: python manage.py check-data [--fix] [--db <path>]
环境变量:
  DATABASE_URL  - 数据库连接字符串（可选，默认使用 .env 配置）

示例:
  python manage.py init       初始化数据库
  python manage.py migrate    创建新迁移
  python manage.py upgrade    升级数据库
  python manage.py reset      重置数据库
  python manage.py show       查看数据库信息
  python manage.py backup                      备份数据库
  python manage.py restore <backup.db> --force 还原数据库
  python manage.py export-json                  导出全量表为 JSON
  python manage.py import-json <input.json>     导入 JSON
  python manage.py check-data                    数据一致性体检
""")


def cmd_init():
    """初始化数据库"""
    from app.main import lifespan
    from app.db.session import engine
    from app.db.base import Base

    import asyncio
    import app.models  # noqa: F401

    async def _init():
        # 创建表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] 数据库表创建完成")

        # 初始化内置数据
        from app.main import _init_builtin_data
        await _init_builtin_data()
        print("[OK] 内置数据初始化完成")

        await engine.dispose()

    asyncio.run(_init())
    print(f"[OK] 数据库初始化完成 (table count: {len(Base.metadata.tables)})")


def cmd_reset():
    """重置数据库"""
    import asyncio
    from app.db.session import engine
    from app.db.base import Base
    import app.models  # noqa: F401

    async def _reset():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            print("[OK] 所有表已删除")
            await conn.run_sync(Base.metadata.create_all)
            print("[OK] 所有表已重新创建")
        await engine.dispose()

    confirm = input("确定要重置数据库吗？所有数据将丢失！(yes/no): ")
    if confirm.lower() == "yes":
        asyncio.run(_reset())
        cmd_init()
    else:
        print("取消操作")


def cmd_show():
    """显示数据库信息"""
    import asyncio
    from app.db.session import engine
    from app.db.base import Base
    import app.models  # noqa: F401

    async def _show():
        print(f"\n数据库引擎: {engine.url}")
        tables = list(Base.metadata.tables.keys())
        print(f"模型表数: {len(tables)}")
        for t in sorted(tables):
            columns = Base.metadata.tables[t].columns.keys()
            print(f"  - {t} ({len(columns)}列)")
        print()

        # 检查数据
        from app.db.session import async_session_factory
        from sqlalchemy import select, func

        async with async_session_factory() as session:
            for tbl_name, tbl in sorted(Base.metadata.tables.items()):
                try:
                    result = await session.execute(select(func.count()).select_from(tbl))
                    count = result.scalar()
                    print(f"  {tbl_name}: {count} 条记录")
                except Exception:
                    pass
            await session.commit()

        await engine.dispose()

    asyncio.run(_show())


def cmd_create_admin():
    """创建管理员账号"""
    import asyncio
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from app.models.user import User
    from app.models.role import Role
    from app.core.security import hash_password

    async def _create():
        async with async_session_factory() as session:
            # 检查管理员是否存在
            result = await session.execute(select(User).where(User.username == "admin"))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"管理员已存在: admin (ID: {existing.id})")
                reset = input("重置密码为 admin@123456 ? (yes/no): ")
                if reset.lower() == "yes":
                    existing.hashed_password = hash_password("admin@123456")
                    existing.is_active = True
                    existing.is_super_admin = True
                    existing.locked_until = None
                    existing.login_attempts = 0
                    await session.commit()
                    print("[OK] 管理员密码已重置")
                return

            # 获取超级管理员角色
            result = await session.execute(select(Role).where(Role.code == "super_admin"))
            admin_role = result.scalar_one_or_none()
            if not admin_role:
                print("[ERROR] 超级管理员角色不存在，请先执行 python manage.py init")
                return

            admin = User(
                username="admin",
                real_name="系统管理员",
                email="admin@managesys.local",
                hashed_password=hash_password("admin@123456"),
                is_active=True,
                is_super_admin=True,
            )
            admin.roles = [admin_role]
            session.add(admin)
            await session.commit()
            print(f"[OK] 管理员创建成功: admin / admin@123456")

        await session.commit()

    asyncio.run(_create())



def _backup_utils():
    import backup_utils
    return backup_utils


def cmd_backup():
    """\u5907\u4efd\u6570\u636e\u5e93\uff08\u5728\u7ebf\u4e00\u81f4\u6027\uff0c\u542b WAL\uff09\n\u7528\u6cd5: python manage.py backup [target_dir] [--keep N] [--log <file>]\n\u53ef\u88ab\u8ba1\u5212\u4efb\u52a1\u8c03\u7528\uff1a\u6210\u529f\u8fd4\u56de 0\uff0c\u5931\u8d25\u8fd4\u56de\u975e 0"""
    import sys as _s
    args = _s.argv[2:]
    target = None
    keep = 30
    logfile = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--keep" and i + 1 < len(args):
            keep = int(args[i + 1]); i += 2
        elif a == "--log" and i + 1 < len(args):
            logfile = args[i + 1]; i += 2
        elif a.startswith("--"):
            i += 1
        else:
            target = a
            i += 1
    try:
        path = _backup_utils().backup(target, keep=keep)
        msg = f"[OK] \u5907\u4efd\u5b8c\u6210 -> {path}"
        print(msg)
        if logfile:
            with open(logfile, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        return 0
    except Exception as e:
        msg = f"[ERROR] \u5907\u4efd\u5931\u8d25: {e}"
        print(msg)
        if logfile:
            with open(logfile, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        return 1


def cmd_restore():
    """\u8fd8\u539f\u6570\u636e\u5e93\uff1apython manage.py restore <backup.db> [--force]"""
    import sys as _s
    if len(_s.argv) < 3:
        print("[ERROR] \u7528\u6cd5: python manage.py restore <backup.db> [--force]")
        return
    src = _s.argv[2]
    force = "--force" in _s.argv
    try:
        path = _backup_utils().restore(src, force=force)
        print(f"[OK] \u8fd8\u539f\u5b8c\u6210 -> {path}\n\u8bf7\u91cd\u542f\u540e\u7aef\u670d\u52a1\u4f7f\u751f\u6548\u3002")
    except Exception as e:
        print(f"[ERROR] {e}")


def cmd_export():
    """\u5bfc\u51fa\u5168\u91cf\u6570\u636e\u4e3a JSON\uff1apython manage.py export-json [out.json]"""
    import sys as _s
    out = _s.argv[2] if len(_s.argv) > 2 else None
    try:
        path = _backup_utils().export_json(out)
        print(f"[OK] \u5bfc\u51fa\u5b8c\u6210 -> {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


def cmd_import():
    """\u5bfc\u5165 JSON\uff08\u6e05\u7a7a+\u91cd\u653e\uff0c\u5e42\u7b49\uff09\uff1apython manage.py import-json <file.json> [--force]"""
    import sys as _s
    if len(_s.argv) < 3:
        print("[ERROR] \u7528\u6cd5: python manage.py import-json <file.json> [--force]")
        return
    src = _s.argv[2]
    force = "--force" in _s.argv
    try:
        total = _backup_utils().import_json(src, force=force)
        print(f"[OK] \u5bfc\u5165\u5b8c\u6210\uff0c\u91cd\u653e {total} \u6761\u8bb0\u5f55\uff08\u5e42\u7b49\uff0c\u53ef\u91cd\u590d\u6267\u884c\uff09\n\u8bf7\u91cd\u542f\u540e\u7aef\u670d\u52a1\u4f7f\u751f\u6548\u3002")
    except Exception as e:
        print(f"[ERROR] {e}")


def cmd_check_data():
    """\u6570\u636e\u4e00\u81f4\u6027\u4f53\u68c0\uff1apython manage.py check-data [--fix] [--db <path>]"""
    import sys as _s
    args = _s.argv[2:]
    fix = "--fix" in args
    db = None
    if "--db" in args:
        i = args.index("--db")
        if i + 1 < len(args):
            db = args[i + 1]
    try:
        import data_audit
        report = data_audit.run_audit(db)
        print(data_audit.format_report(report))
        if fix:
            fixed = data_audit.apply_fixes(db)
            print(f"[FIX] \u5df2\u4fee\u590d: {fixed}\u9879")
        return 1 if report["summary"]["error"] else 0
    except Exception as e:
        print(f"[ERROR] \u4f53\u68c0\u5931\u8d25: {e}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)

    cmd = sys.argv[1]
    commands = {
        "help": cmd_help,
        "init": cmd_init,
        "reset": cmd_reset,
        "show": cmd_show,
        "create-admin": cmd_create_admin,
        "backup": cmd_backup,
        "restore": cmd_restore,
        "export-json": cmd_export,
        "import-json": cmd_import,
        "check-data": cmd_check_data,
    }

    if cmd in commands:
        rc = commands[cmd]()
        if isinstance(rc, int) and rc != 0:
            sys.exit(rc)
    elif cmd in ("migrate", "upgrade", "downgrade"):
        # 委托给 Alembic
        from alembic.config import main as alembic_main
        alembic_main([cmd, *sys.argv[2:]])
    else:
        print(f"未知命令: {cmd}")
        cmd_help()