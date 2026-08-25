"""FastAPI 应用入口"""
import asyncio
import logging
import logging.handlers
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.concurrency import sse_semaphore
from app.core.middleware import ConcurrencyLimitMiddleware
from app.core.request_id import RequestIDMiddleware, RequestIDFilter
from app.api.v1 import router as api_router
from app.db.base import Base
from app.db.session import engine, async_session_factory, IS_SQLITE

# ===== 日志配置 =====
# 日志目录固定在后端根目录下的 logs/，避免随启动目录变化在异地写入日志
BASE_LOG_DIR = (Path(__file__).resolve().parent.parent / "logs")
BASE_LOG_DIR.mkdir(parents=True, exist_ok=True)
APP_LOG_PATH = BASE_LOG_DIR / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | [%(req_id)s] | %(name)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.TimedRotatingFileHandler(
            str(APP_LOG_PATH),
            when="D",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        ),
    ],
)
# ???????? request-id ???????????????? req_id
for _h in logging.getLogger().handlers:
    if not any(isinstance(_f, RequestIDFilter) for _f in _h.filters):
        _h.addFilter(RequestIDFilter())
logger = logging.getLogger("managesys")


async def _seed_default_facility():
    from app.models.facility import DataCenter, Room
    from sqlalchemy import select
    
    async with async_session_factory() as session:
        result = await session.execute(select(DataCenter).limit(1))
        if result.scalar_one_or_none():
            logger.info("Data center exists, skip")
            return
        
        dc = DataCenter(name="主数据中心", code="DC-MAIN", address="安徽省合肥市", description="默认主数据中心", status="active")
        session.add(dc)
        await session.flush()
        
        room = Room(data_center_id=dc.id, name="主机房", code="RM-001", floor="3楼", tier_level="Tier III", description="默认主机房", status="active")
        session.add(room)
        await session.commit()
        logger.info("Created default data center and room")


def _run_migrations_sync(conn):
    """Run Alembic migrations to head at startup.

    Invoked as a subprocess using the current interpreter so that env.py''s
    online migration (which internally calls asyncio.run) does not collide with
    the already-running event loop. The migration scripts carry idempotent
    guards so they are safe on databases previously built via create_all.
    """
    import os
    import subprocess
    import sys as _sys
    from pathlib import Path
    # alembic.ini lives in the backend/ dir (parent of the app package);
    # pin the working directory so uvicorn''s CWD cannot break discovery.
    app_pkg_dir = Path(__file__).resolve().parent
    backend_dir = app_pkg_dir.parent
    env = dict(os.environ)
    cmd = [_sys.executable, "-m", "alembic", "upgrade", "head"]
    proc = subprocess.run(cmd, cwd=str(backend_dir), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("Alembic migration failed: " + (proc.stderr or proc.stdout or "")[:2000])
    return proc


async def _init_builtin_data():
    """初始化内置角色和权限数据（幂等）"""
    from app.models.role import Role
    from app.models.permission import Permission
    from app.models.user import User
    from app.core.security import hash_password

    async with async_session_factory() as session:
        try:
            # 检查是否已初始化
            result = await session.execute(select(Permission).limit(1))
            if result.scalar_one_or_none():
                logger.info("内置数据已存在，跳过初始化")
                return

            logger.info("开始初始化内置数据...")

            # 创建权限
            permissions_data = [
                ("查看机房", "room:view", "机房管理"),
                ("创建机房", "room:create", "机房管理"),
                ("编辑机房", "room:edit", "机房管理"),
                ("删除机房", "room:delete", "机房管理"),
                ("查看机柜", "rack:view", "机房管理"),
                ("创建机柜", "rack:create", "机房管理"),
                ("编辑机柜", "rack:edit", "机房管理"),
                ("删除机柜", "rack:delete", "机房管理"),
                ("查看设备", "device:view", "设备管理"),
                ("创建设备", "device:create", "设备管理"),
                ("编辑设备", "device:edit", "设备管理"),
                ("删除设备", "device:delete", "设备管理"),
                ("上架设备", "device:mount", "设备管理"),
                ("下架设备", "device:unmount", "设备管理"),
                ("查看监控大盘", "monitor:view_dashboard", "监控管理"),
                ("查看告警", "monitor:view_alerts", "监控管理"),
                ("处理告警", "monitor:handle_alert", "监控管理"),
                ("配置告警规则", "monitor:config_rule", "监控管理"),
                ("查看业务系统", "system:view", "系统管理"),
                ("创建业务系统", "system:create", "系统管理"),
                ("编辑业务系统", "system:edit", "系统管理"),
                ("删除业务系统", "system:delete", "系统管理"),
                ("查看用户", "user:view", "账号管理"),
                ("创建用户", "user:create", "账号管理"),
                ("编辑用户", "user:edit", "账号管理"),
                ("删除用户", "user:delete", "账号管理"),
                ("查看角色", "role:view", "账号管理"),
                ("创建角色", "role:create", "账号管理"),
                ("编辑角色", "role:edit", "账号管理"),
                ("删除角色", "role:delete", "账号管理"),
                ("查看审计日志", "audit:view", "账号管理"),
                ("创建工单", "work:create", "运维工单"),
                ("处理工单", "work:edit", "运维工单"),
                ("删除工单", "work:delete", "运维工单"),
                ("查看工单", "work:view", "运维工单"),
                ("创建巡检", "inspection:create", "设备巡检"),
                ("处理巡检", "inspection:edit", "设备巡检"),
                ("删除巡检", "inspection:delete", "设备巡检"),
                ("查看巡检", "inspection:view", "设备巡检"),
            ]

            permissions = {}
            for name, code, module in permissions_data:
                perm = Permission(name=name, code=code, module=module)
                session.add(perm)
                permissions[code] = perm

            await session.flush()

            # 创建内置角色
            roles_data = [
                ("超级管理员", "super_admin", "拥有系统全部权限", True, list(permissions.keys())),
                ("机房管理员", "room_admin", "机房和设备管理权限", False,
                 ["room:view", "room:create", "room:edit", "room:delete",
                  "rack:view", "rack:create", "rack:edit", "rack:delete",
                  "device:view", "device:create", "device:edit", "device:delete",
                  "device:mount", "device:unmount", "monitor:view_dashboard",
                  "monitor:view_alerts", "monitor:handle_alert",
                  "work:create", "work:edit", "work:delete",
                  "inspection:create", "inspection:edit", "inspection:delete"]),
                ("运维人员", "operator", "日常运维操作权限", False,
                 ["room:view", "rack:view",
                  "device:view", "device:mount", "device:unmount",
                  "monitor:view_dashboard", "monitor:view_alerts", "monitor:handle_alert", "work:create", "work:edit", "inspection:create", "inspection:edit"]),
                ("普通用户", "user", "基础查看权限", False,
                 ["room:view", "rack:view", "device:view", "monitor:view_dashboard",
                  "monitor:view_alerts", "system:view"]),
                ("访客", "guest", "只读访客权限", False,
                 ["room:view", "rack:view", "device:view", "monitor:view_dashboard",
                  "monitor:view_alerts", "system:view", "user:view", "role:view"]),
                ("审计员", "auditor", "审计相关权限", False,
                 ["room:view", "device:view", "monitor:view_dashboard",
                  "monitor:view_alerts", "system:view", "user:view", "role:view", "audit:view"]),
            ]

            for name, code, desc, is_builtin, perm_codes in roles_data:
                role = Role(name=name, code=code, description=desc, is_builtin=is_builtin)
                role.permissions = [permissions[pc] for pc in perm_codes if pc in permissions]
                session.add(role)

            await session.flush()

            # 创建默认超级管理员
            admin_role = (await session.execute(
                select(Role).where(Role.code == "super_admin")
            )).scalar_one()

            admin_password = settings.INIT_ADMIN_PASSWORD
            admin = User(
                username="admin",
                real_name="系统管理员",
                email="admin@managesys.local",
                hashed_password=hash_password(admin_password),
                is_active=True,
                is_super_admin=True,
                must_change_password=True,
            )
            admin.roles = [admin_role]
            session.add(admin)
            await session.commit()
            logger.info("内置数据初始化完成（31权限 + 6角色 + admin用户）")
            if not admin_password or admin_password == "admin@123456":
                logger.warning("=" * 60)
                logger.warning("检测到初始管理员使用默认密码 admin@123456！")
                logger.warning("请立即登录并修改密码，或通过环境变量 INIT_ADMIN_PASSWORD 配置强随机初始密码。")
                logger.warning("=" * 60)

        except Exception as e:
            await session.rollback()
            logger.error("内置数据初始化失败: %s", str(e))
            raise




# ===== 后台保留清理任务（每日滚动删除超期数据）=====

_periodic_leader = True
_periodic_leader_conn = None
_PERIODIC_LEADER_LOCK_KEY = 20260825


async def _acquire_periodic_leader() -> bool:
    """多 worker 下选出唯一 leader 运行定时任务。
    使用 PostgreSQL 会话级 advisory lock：leader 进程退出后锁随连接释放，
    重启的 worker 可重新拿回 leadership。SQLite 单进程终为 leader。
    失败时默认放行（fail-open）以不停止定时任务。"""
    global _periodic_leader, _periodic_leader_conn
    if IS_SQLITE:
        _periodic_leader = True
        return True
    try:
        from sqlalchemy import text
        conn = await engine.connect()
        row = (await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _PERIODIC_LEADER_LOCK_KEY})).scalar()
        if row:
            _periodic_leader = True
            _periodic_leader_conn = conn  #持有连接以保持锁
            logger.info("本进程获得周期任务 leader 权限")
            return True
        await conn.close()
        _periodic_leader = False
        logger.info("其他 worker 已持有周期任务，本进程跳过")
        return False
    except Exception as e:
        _periodic_leader = True
        logger.warning("周期任务选主失败默认放行: %s", e)
        return True


async def _release_periodic_leader():
    global _periodic_leader_conn
    if _periodic_leader_conn is not None:
        try:
            await _periodic_leader_conn.close()
        except Exception:
            pass
        _periodic_leader_conn = None

_retention_task: Optional[asyncio.Task] = None


async def _run_retention_pass() -> dict:
    """执行一次保留清理 + 异常留痕对账。独立会话，失败不影响主流程。"""
    from app.services.sensor_anomaly_service import SensorAnomalyService
    async with async_session_factory() as db:
        svc = SensorAnomalyService(db)
        gap_added = await svc.reconcile_from_alerts(since=None)
        retention = await svc.run_retention()
        logger.info("数据保留清理完成: %s, 异常留痕新增 %d", retention, gap_added)
        return retention


async def _retention_loop():
    """进程内每日保留清理任务（启动即跑一次，然后每日一次）。"""
    try:
        await _run_retention_pass()
    except Exception as e:
        logger.warning("数据保留清理(启动)失败: %s", str(e))
    while True:
        await asyncio.sleep(24 * 3600)
        try:
            await _run_retention_pass()
        except Exception as e:
            logger.warning("数据保留清理(每日)失败: %s", str(e))


def _start_retention_task():
    global _retention_task
    if not settings.DATA_RETENTION_TASK_ENABLED:
        logger.info("数据保留清理任务未启用（DATA_RETENTION_TASK_ENABLED=false）")
        return
    _retention_task = asyncio.create_task(_retention_loop())


async def _stop_retention_task():
    global _retention_task
    if _retention_task is not None:
        _retention_task.cancel()
        try:
            await _retention_task
        except (asyncio.CancelledError, Exception):
            pass
        _retention_task = None

_alert_intel_task: Optional[asyncio.Task] = None


async def _alert_escalation_loop():
    """进程内告警自动升级任务：周期扫描未确认 emergency 告警。"""
    from app.services.alert_intelligence_service import AlertIntelligenceService
    while True:
        try:
            async with async_session_factory() as db:
                svc = AlertIntelligenceService(db, escalate_after_minutes=30)
                ids = await svc.auto_escalate()
                if ids:
                    logger.info("告警自动升级 %d 条: %s", len(ids), ids)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("告警自动升级扫描失败: %s", e)
        await asyncio.sleep(300)


def _start_alert_intel_task():
    global _alert_intel_task
    if not settings.ALERT_INTEL_TASK_ENABLED:
        logger.info("告警自动升级任务未启用（ALERT_INTEL_TASK_ENABLED=false）")
        return
    _alert_intel_task = asyncio.create_task(_alert_escalation_loop())


async def _stop_alert_intel_task():
    global _alert_intel_task
    if _alert_intel_task is not None:
        _alert_intel_task.cancel()
        try:
            await _alert_intel_task
        except (asyncio.CancelledError, Exception):
            pass
        _alert_intel_task = None


_alert_lifecycle_task: Optional[asyncio.Task] = None


async def _alert_lifecycle_loop():
    """进程内告警生命周期任务：周期扫描自动恢复（连续正常->已解决）与偶发登记。"""
    from app.services.alert_lifecycle_service import AlertLifecycleService
    interval = settings.ALERT_LIFECYCLE_INTERVAL_SECONDS
    while True:
        try:
            async with async_session_factory() as db:
                svc = AlertLifecycleService(db)
                ids = await svc.sweep_auto_resolve()
                if ids:
                    logger.info("告警自动恢复 %d 条: %s", len(ids), ids)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("告警生命周期扫描失败: %s", e)
        await asyncio.sleep(interval)


def _start_alert_lifecycle_task():
    global _alert_lifecycle_task
    if not settings.ALERT_LIFECYCLE_TASK_ENABLED:
        logger.info("告警生命周期任务未启用（ALERT_LIFECYCLE_TASK_ENABLED=false）")
        return
    _alert_lifecycle_task = asyncio.create_task(_alert_lifecycle_loop())


async def _stop_alert_lifecycle_task():
    global _alert_lifecycle_task
    if _alert_lifecycle_task is not None:
        _alert_lifecycle_task.cancel()
        try:
            await _alert_lifecycle_task
        except (asyncio.CancelledError, Exception):
            pass
        _alert_lifecycle_task = None


_env_poll_task: Optional[asyncio.Task] = None


async def _env_poll_loop():
    """进程内环境/气象自动轮询采集任务（默认关闭，由 ENV_POLL_TASK_ENABLED 开启）。"""
    from app.services.environment_service import EnvPoller
    interval = settings.ENV_POLL_INTERVAL_SECONDS
    while True:
        try:
            async with async_session_factory() as db:
                values = await EnvPoller(db).poll_once()
                if values:
                    logger.info("环境采集: %s %s°C / %s%%RH / %sm/s",
                                values.get("weather"), values.get("temperature"),
                                values.get("humidity"), values.get("windspeed"))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("环境采集失败: %s", e)
        await asyncio.sleep(interval)


def _start_env_poll_task():
    global _env_poll_task
    if not settings.ENV_POLL_TASK_ENABLED:
        logger.info("环境采集任务未启用（ENV_POLL_TASK_ENABLED=false）")
        return
    _env_poll_task = asyncio.create_task(_env_poll_loop())


async def _stop_env_poll_task():
    global _env_poll_task
    if _env_poll_task is not None:
        _env_poll_task.cancel()
        try:
            await _env_poll_task
        except (asyncio.CancelledError, Exception):
            pass
        _env_poll_task = None



async def _flag_default_password_admin():
    """对仍在使用默认初始密码的账号打上"需强制改密"标记（兼容历史库 admin）。

    幂等：仅当密码仍等于默认 INIT_ADMIN_PASSWORD 时置位；修改密码后自动清除。
    用于把本版本之前创建的、未改过默认密码的 admin 也纳入强制改密流程。
    """
    from app.core.security import verify_password
    from app.models.user import User
    default = settings.INIT_ADMIN_PASSWORD
    if not default:
        return
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(User).where(User.username == "admin"))
            admin = result.scalar_one_or_none()
            if admin and not admin.must_change_password and verify_password(default, admin.hashed_password):
                admin.must_change_password = True
                await session.commit()
                logger.warning("检测到 admin 仍使用默认初始密码，已标记为需强制修改密码。")
        except Exception as e:
            await session.rollback()
            logger.warning("默认密码检查失败: %s", str(e))

BUILTIN_PERMISSIONS = [
    ("\u67e5\u770b\u673a\u623f", "room:view", "\u673a\u623f\u7ba1\u7406"),
    ("\u521b\u5efa\u673a\u623f", "room:create", "\u673a\u623f\u7ba1\u7406"),
    ("\u7f16\u8f91\u673a\u623f", "room:edit", "\u673a\u623f\u7ba1\u7406"),
    ("\u5220\u9664\u673a\u623f", "room:delete", "\u673a\u623f\u7ba1\u7406"),
    ("\u67e5\u770b\u673a\u67dc", "rack:view", "\u673a\u623f\u7ba1\u7406"),
    ("\u521b\u5efa\u673a\u67dc", "rack:create", "\u673a\u623f\u7ba1\u7406"),
    ("\u7f16\u8f91\u673a\u67dc", "rack:edit", "\u673a\u623f\u7ba1\u7406"),
    ("\u5220\u9664\u673a\u67dc", "rack:delete", "\u673a\u623f\u7ba1\u7406"),
    ("\u67e5\u770b\u8bbe\u5907", "device:view", "\u8bbe\u5907\u7ba1\u7406"),
    ("\u521b\u5efa\u8bbe\u5907", "device:create", "\u8bbe\u5907\u7ba1\u7406"),
    ("\u7f16\u8f91\u8bbe\u5907", "device:edit", "\u8bbe\u5907\u7ba1\u7406"),
    ("\u5220\u9664\u8bbe\u5907", "device:delete", "\u8bbe\u5907\u7ba1\u7406"),
    ("\u4e0a\u67b6\u8bbe\u5907", "device:mount", "\u8bbe\u5907\u7ba1\u7406"),
    ("\u4e0b\u67b6\u8bbe\u5907", "device:unmount", "\u8bbe\u5907\u7ba1\u7406"),
    ("\u67e5\u770b IP \u8d44\u6e90", "ip:view", "IP\u8d44\u6e90\u7ba1\u7406"),
    ("\u7f16\u8f91 IP \u53f0\u8d26/\u7f51\u6b65", "ip:edit", "IP\u8d44\u6e90\u7ba1\u7406"),
    ("\u5206\u914d / \u91ca\u653e IP", "ip:allocate", "IP\u8d44\u6e90\u7ba1\u7406"),
    ("\u56de\u6536\u95f2\u7f6e IP", "ip:recycle", "IP\u8d44\u6e90\u7ba1\u7406"),
    ("\u67e5\u770b\u76d1\u63a7\u5927\u76d8", "monitor:view_dashboard", "\u76d1\u63a7\u7ba1\u7406"),
    ("\u67e5\u770b\u544a\u8b66", "monitor:view_alerts", "\u76d1\u63a7\u7ba1\u7406"),
    ("\u5904\u7406\u544a\u8b66", "monitor:handle_alert", "\u76d1\u63a7\u7ba1\u7406"),
    ("\u914d\u7f6e\u544a\u8b66\u89c4\u5219", "monitor:config_rule", "\u76d1\u63a7\u7ba1\u7406"),
    ("\u67e5\u770b\u4e1a\u52a1\u7cfb\u7edf", "system:view", "\u7cfb\u7edf\u7ba1\u7406"),
    ("\u521b\u5efa\u4e1a\u52a1\u7cfb\u7edf", "system:create", "\u7cfb\u7edf\u7ba1\u7406"),
    ("\u7f16\u8f91\u4e1a\u52a1\u7cfb\u7edf", "system:edit", "\u7cfb\u7edf\u7ba1\u7406"),
    ("\u5220\u9664\u4e1a\u52a1\u7cfb\u7edf", "system:delete", "\u7cfb\u7edf\u7ba1\u7406"),
    ("\u67e5\u770b\u7528\u6237", "user:view", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u521b\u5efa\u7528\u6237", "user:create", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u7f16\u8f91\u7528\u6237", "user:edit", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u5220\u9664\u7528\u6237", "user:delete", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u67e5\u770b\u89d2\u8272", "role:view", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u521b\u5efa\u89d2\u8272", "role:create", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u7f16\u8f91\u89d2\u8272", "role:edit", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u5220\u9664\u89d2\u8272", "role:delete", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u67e5\u770b\u5ba1\u8ba1\u65e5\u5fd7", "audit:view", "\u8d26\u53f7\u7ba1\u7406"),
    ("\u521b\u5efa\u5de5\u5355", "work:create", "\u8fd0\u7ef4\u5de5\u5355"),
    ("\u5904\u7406\u5de5\u5355", "work:edit", "\u8fd0\u7ef4\u5de5\u5355"),
    ("\u5220\u9664\u5de5\u5355", "work:delete", "\u8fd0\u7ef4\u5de5\u5355"),
    ("\u67e5\u770b\u5de5\u5355", "work:view", "\u8fd0\u7ef4\u5de5\u5355"),
    ("\u521b\u5efa\u5de1\u68c0", "inspection:create", "\u8bbe\u5907\u5de1\u68c0"),
    ("\u5904\u7406\u5de1\u68c0", "inspection:edit", "\u8bbe\u5907\u5de1\u68c0"),
    ("\u5220\u9664\u5de1\u68c0", "inspection:delete", "\u8bbe\u5907\u5de1\u68c0"),
    ("\u67e5\u770b\u5de1\u68c0", "inspection:view", "\u8bbe\u5907\u5de1\u68c0"),
]

BUILTIN_ROLES = [
    ("\u8d85\u7ea7\u7ba1\u7406\u5458", "super_admin", "\u62e5\u6709\u7cfb\u7edf\u5168\u90e8\u6743\u9650", True, [p[1] for p in BUILTIN_PERMISSIONS]),
    ("\u673a\u623f\u7ba1\u7406\u5458", "room_admin", "\u673a\u623f\u548c\u8bbe\u5907\u7ba1\u7406\u6743\u9650", False,
     ["room:view", "room:create", "room:edit", "room:delete", "rack:view", "rack:create", "rack:edit", "rack:delete",
      "device:view", "device:create", "device:edit", "device:delete", "device:mount", "device:unmount",
      "monitor:view_dashboard", "monitor:view_alerts", "monitor:handle_alert",
      "work:view", "work:create", "work:edit", "work:delete", "inspection:view", "inspection:create", "inspection:edit", "inspection:delete",
      "ip:view", "ip:edit", "ip:allocate", "ip:recycle"]),
    ("\u8fd0\u7ef4\u4eba\u5458", "operator", "\u65e5\u5e38\u8fd0\u7ef4\u64cd\u4f5c\u6743\u9650", False,
     ["room:view", "rack:view", "device:view", "device:mount", "device:unmount",
      "system:view", "monitor:view_dashboard", "monitor:view_alerts", "monitor:handle_alert",
      "work:view", "work:create", "work:edit", "inspection:view", "inspection:create", "inspection:edit",
      "ip:view"]),
    ("\u666e\u901a\u7528\u6237", "user", "\u57fa\u7840\u67e5\u770b\u6743\u9650", False,
     ["room:view", "rack:view", "device:view", "monitor:view_dashboard", "monitor:view_alerts", "system:view", "work:view", "inspection:view"]),
    ("\u8bbf\u5ba2", "guest", "\u53ea\u8bfb\u8bbf\u5ba2\u6743\u9650", False,
     ["room:view", "rack:view", "device:view", "monitor:view_dashboard", "monitor:view_alerts",
      "system:view", "user:view", "role:view", "work:view", "inspection:view"]),
    ("\u5ba1\u8ba1\u5458", "auditor", "\u5ba1\u8ba1\u76f8\u5173\u6743\u9650", False,
     ["room:view", "device:view", "monitor:view_dashboard", "monitor:view_alerts",
      "system:view", "user:view", "role:view", "audit:view", "work:view", "inspection:view"]),
]


async def _sync_builtin_data():
    """同步内置角色与权限（幂等）；生产保留任务启动时调用。"""
    from app.models.role import Role
    from app.models.permission import Permission
    from sqlalchemy import select as _sel

    async with async_session_factory() as session:
        try:
            existing = set((await session.execute(_sel(Permission.code))).scalars().all())
            permissions_by_code = {}
            for name, code, module in BUILTIN_PERMISSIONS:
                if code not in existing:
                    session.add(Permission(name=name, code=code, module=module))
            await session.flush()
            for p in (await session.execute(_sel(Permission))).scalars().all():
                permissions_by_code[p.code] = p

            for name, code, desc, is_builtin, perm_codes in BUILTIN_ROLES:
                if code == "super_admin":
                    continue
                role = (await session.execute(_sel(Role).where(Role.code == code))).scalar_one_or_none()
                if role is None:
                    role = Role(name=name, code=code, description=desc, is_builtin=is_builtin)
                    session.add(role)
                have = {p.code for p in role.permissions}
                for pc in perm_codes:
                    if pc in permissions_by_code and pc not in have:
                        role.permissions.append(permissions_by_code[pc])
            await session.commit()
            logger.info("\u5185\u7f6e\u6570\u636e\u540c\u6b65\u5b8c\u6210\uff08\u8865\u9f50\u7f3a\u5931\u6743\u9650/\u89d2\u8272\uff09")
        except Exception as e:
            await session.rollback()
            logger.warning("\u5185\u7f6e\u6570\u636e\u540c\u6b65\u5931\u8d25: %s", str(e))

def _check_security_config():
    """启动时检查安全配置。ENFORCE_SECURITY=true 时对不可妥协项直接拒绝启动。"""
    critical = []
    weak = []
    if settings.DEBUG:
        critical.append("DEBUG=true 已开启（生产版必须关闭）")
    if settings.SECRET_KEY == "dev-secret-key-change-in-production-2024":
        critical.append("SECRET_KEY 是默认值（请更改为强随机密钥）")
    import re as _cfg_re
    if settings.INIT_ADMIN_PASSWORD in ("", "admin@123456", "admin123456", "12345678", "password"):
        critical.append("INIT_ADMIN_PASSWORD 是默认/弱口令（请通过环境变量设置为强随机初始密码）")
    elif len(settings.INIT_ADMIN_PASSWORD) < settings.PASSWORD_MIN_LENGTH:
        critical.append("INIT_ADMIN_PASSWORD 长度不足（需 >= %d 位）" % settings.PASSWORD_MIN_LENGTH)
    elif not (_cfg_re.search(r"[a-zA-Z]", settings.INIT_ADMIN_PASSWORD)
              and _cfg_re.search(r"[0-9]", settings.INIT_ADMIN_PASSWORD)):
        critical.append("INIT_ADMIN_PASSWORD 需同时包含字母与数字")
    if not settings.ENABLE_CAPTCHA:
        weak.append("ENABLE_CAPTCHA=false （建议生产环境开启验证码）")
    if critical and settings.ENFORCE_SECURITY:
        logger.error("=" * 60)
        for item in critical:
            logger.error("  - %s", item)
        logger.error("生产安全准入未通过（ENFORCE_SECURITY=true 已拒绝启动）")
        logger.error("=" * 60)
        raise RuntimeError("生产安全准入未通过: " + "; ".join(critical))
    if critical or weak:
        logger.warning("=" * 60)
        for item in critical + weak:
            logger.warning("  - %s", item)
        logger.warning("请在部署前在 backend/.env 中修改 SECRET_KEY / DEBUG / ENABLE_CAPTCHA）")
        logger.warning("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 50)
    logger.info("  %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("  数据库: %s", settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://")[:80])
    logger.info("=" * 50)

    _check_security_config()

    # 将可信任反代网段注入 IP 提取工具（默认空=不信任转发头，取直连 IP）
    from app.core import iputils as _iputils
    _iputils.TRUSTED_PROXIES = [p.strip() for p in settings.TRUSTED_PROXIES.split(",") if p.strip()]


    # 导入所有模型以确保注册到 Base.metadata
    import app.models  # noqa: F401

    # 创建数据库表
    try:
        async with engine.begin() as conn:
            # Consolidate legacy create_all + _ensure_columns DDL into Alembic.
            # Migration scripts are idempotent for both fresh and existing DBs.
            await conn.run_sync(Base.metadata.create_all)
            # 先以模型为准建全表结构，再做迁移补齐，保证新库/存量库 schema 完整。
            await conn.run_sync(_run_migrations_sync)
        logger.info("数据库表结构检查/创建完成")
    except Exception as e:
        logger.error("数据库表创建失败: %s", str(e))
        raise

    # 初始化内置数据
    try:
        await _init_builtin_data()
    except Exception as e:
        logger.warning("内置数据初始化异常（可能已存在）: %s", str(e))
    # 幂等同步内置权限/角色（补齐新加的 work/inspection 权限，兼容已存在的库）
    try:
        await _sync_builtin_data()
    except Exception as e:
        logger.warning("内置数据同步异常: %s", str(e))

    # 兼容历史库：把仍使用默认初始密码的 admin 标记为"需强制改密"
    try:
        await _flag_default_password_admin()
    except Exception as e:
        logger.warning("默认密码检查失败: %s", str(e))


    try:
        await _seed_default_facility()
    except Exception as e:
        logger.warning("默认数据中心创建异常: %s", str(e))

    # 初始化邮件服务
    if settings.SMTP_ENABLED and settings.SMTP_HOST:
        try:
            from app.services.email_service import init_email_service
            init_email_service(
                smtp_host=settings.SMTP_HOST,
                smtp_port=settings.SMTP_PORT,
                smtp_user=settings.SMTP_USER,
                smtp_password=settings.SMTP_PASSWORD,
                from_name=settings.SMTP_FROM_NAME,
                use_tls=settings.SMTP_USE_TLS,
            )
            logger.info("邮件服务初始化成功 (SMTP: %s:%d)", settings.SMTP_HOST, settings.SMTP_PORT)
        except Exception as e:
            logger.warning("邮件服务初始化失败: %s", str(e))
    else:
        logger.info("邮件服务未启用（SMTP_ENABLED=false 或 SMTP_HOST 未配置）")

    # 启动进程内每日数据保留清理任务（含启动即跑一次作为兜底）
    await _acquire_periodic_leader()
    if _periodic_leader:
        try:
            _start_retention_task()
            _start_alert_intel_task()
            _start_alert_lifecycle_task()
            _start_env_poll_task()
        except Exception as e:
            logger.warning("启动周期任务失败: %s", str(e))
    else:
        logger.info("非 leader 进程跳过周期任务")

    yield

    # 关闭时释放资源
    await _stop_alert_intel_task()
    await _stop_alert_lifecycle_task()
    await _stop_env_poll_task()
    await _stop_retention_task()
    await _release_periodic_leader()
    await engine.dispose()
    logger.info("应用已关闭，数据库连接已释放")


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning("HTTP %s: %s %s -> %s", exc.status_code, request.method, request.url.path, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("校验失败: %s %s -> %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=422,
            content={"detail": "请求参数校验失败", "errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("未捕获异常: %s %s -> %s", request.method, request.url.path, str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请联系管理员"},
        )


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # 请求链路识别：置于最外层，保证后续中间件/路由均可获得 req_id
    app.add_middleware(RequestIDMiddleware)
    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    # 安全响应头 + Host 头校验（防 Host 头投毒 / 浏览器端加固）
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    # 全局并发请求限流：防止“点快了加载不出来”与多人同时在线时的资源恜死。
    app.add_middleware(ConcurrencyLimitMiddleware)

    # 注册全局异常处理器
    register_exception_handlers(app)

    # 注册路由
    app.include_router(api_router)

    # 健康检查
    @app.get("/health")
    async def health_check():
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "database": "connected" if engine else "disconnected",
            "email_service": "enabled" if settings.SMTP_ENABLED else "disabled",
        }

    return app


app = create_app()
