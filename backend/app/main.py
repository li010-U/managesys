"""FastAPI 应用入口"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.concurrency import sse_semaphore
from app.core.middleware import ConcurrencyLimitMiddleware
from app.api.v1 import router as api_router
from app.db.base import Base
from app.db.session import engine, async_session_factory

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("uvicorn_app.log", encoding="utf-8"),
    ],
)
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
            logger.info("内置数据初始化完成（31权限 + 6角色 + admin用户）")

        except Exception as e:
            await session.rollback()
            logger.error("内置数据初始化失败: %s", str(e))
            raise




# ???????????????????????
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
      "work:view", "work:create", "work:edit", "work:delete", "inspection:view", "inspection:create", "inspection:edit", "inspection:delete"]),
    ("\u8fd0\u7ef4\u4eba\u5458", "operator", "\u65e5\u5e38\u8fd0\u7ef4\u64cd\u4f5c\u6743\u9650", False,
     ["room:view", "rack:view", "device:view", "device:mount", "device:unmount",
      "system:view", "monitor:view_dashboard", "monitor:view_alerts", "monitor:handle_alert",
      "work:view", "work:create", "work:edit", "inspection:view", "inspection:create", "inspection:edit"]),
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
    """?????????????????????????????????????"""
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
    """启动时检查常用安全配置，重要项目输出警告。"""
    weak = []
    if settings.DEBUG:
        weak.append("DEBUG=true 已开启（生产版请关闭）")
    if settings.SECRET_KEY == "dev-secret-key-change-in-production-2024":
        weak.append("SECRET_KEY 是默认值（请更改为强随机密钥）")
    if not settings.ENABLE_CAPTCHA:
        weak.append("ENABLE_CAPTCHA=false （建议生产环境开启验证码）")
    if weak:
        logger.warning("=" * 60)
        logger.warning("安全配置弱化警告：")
        for item in weak:
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

    # 导入所有模型以确保注册到 Base.metadata
    import app.models  # noqa: F401

    # 创建数据库表
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
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

    yield

    # 关闭时释放资源
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

    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
