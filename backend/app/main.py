"""FastAPI 应用入口"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.config import settings
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
    from app.models.role import Role, Permission
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
                  "monitor:view_alerts", "monitor:handle_alert"]),
                ("运维人员", "operator", "日常运维操作权限", False,
                 ["room:view", "rack:view",
                  "device:view", "device:mount", "device:unmount",
                  "monitor:view_dashboard", "monitor:view_alerts", "monitor:handle_alert"]),
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 50)
    logger.info("  %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("  数据库: %s", settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://")[:80])
    logger.info("=" * 50)

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
