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

环境变量:
  DATABASE_URL  - 数据库连接字符串（可选，默认使用 .env 配置）

示例:
  python manage.py init       初始化数据库
  python manage.py migrate    创建新迁移
  python manage.py upgrade    升级数据库
  python manage.py reset      重置数据库
  python manage.py show       查看数据库信息
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
    }

    if cmd in commands:
        commands[cmd]()
    elif cmd in ("migrate", "upgrade", "downgrade"):
        # 委托给 Alembic
        from alembic.config import main as alembic_main
        alembic_main([cmd, *sys.argv[2:]])
    else:
        print(f"未知命令: {cmd}")
        cmd_help()