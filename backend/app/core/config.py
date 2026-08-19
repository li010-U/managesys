"""应用配置"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode
from typing import Optional, List, Annotated


class Settings(BaseSettings):
    APP_NAME: str = "数据中心资源智能管理系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ===== 数据库 =====
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/managesys.db"
    DATABASE_URL_SYNC: str = "sqlite:///./data/managesys.db"

    # ===== JWT =====
    SECRET_KEY: str = "dev-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    # 刷新令牌有效期（分钟）：短访问令牌 + 长刷新令牌（默认 7 天，可覆盖）
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60
    # ===== 初始管理员密码（仅首次初始化时使用，建议从环境变量设置）=====
    # 生产环境必须通过环境变量 INIT_ADMIN_PASSWORD 设置为强随机密码，不要使用默认。
    INIT_ADMIN_PASSWORD: str = "admin@123456"

    # ===== AI / LLM =====
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com"
    # internal / self-hosted OpenAI-compatible endpoint (e.g. coding paas v4)
    INTERNAL_LLM_KEY: str = ""
    INTERNAL_LLM_BASE_URL: str = ""
    LLM_MODEL: str = "deepseek-chat"
    # 每个 provider 可独立指定模型，切换 LLM_PROVIDER 时模型自动联动。
    DEEPSEEK_MODEL: str = "deepseek-chat"
    OPENAI_MODEL: str = "gpt-4o-mini"
    INTERNAL_MODEL: str = "deepseek-chat"
    # LLM 调用超时（秒）：可配置，避免上游悬置拖死请求。
    LLM_TIMEOUT_SECONDS: int = 60

    # ===== CORS =====
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # ===== 密码策略 =====
    PASSWORD_MIN_LENGTH: int = 8
    ENABLE_CAPTCHA: bool = False
    # 生产纯开启后，启动时对不可妥协项直接拒绝启动（DEBUG=true 等）
    ENFORCE_SECURITY: bool = False
    # ===== 注册开关（由 .env 配置 REGISTER_ENABLED）=====
    REGISTER_ENABLED: bool = False
    # --- 端口限流（防止暴力碰库 / 注册垃圾账号） ---
    # 每个 IP 每窗口内允许的请求数与窗口长度（秒）
    RATE_LIMIT_LOGIN_MAX: int = 10
    # 允许的 Host 头（防 Host 头投毒；若需多域名请在 .env 使用 ALLOWED_HOSTS，逗号分隔）
    ALLOWED_HOSTS: Annotated[list[str], NoDecode] = [
        "localhost", "127.0.0.1",
        "testserver", "test", "localhost:5173", "localhost:3000",
    ]
    RATE_LIMIT_REGISTER_MAX: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    # 可信任的反向代理/内网网段（逗号分隔），仅当直连对端在这些网段才信任转发头
    # 空（默认）= 一律不信任 X-Forwarded-For / X-Real-IP，用直连 IP（防伪造，推荐直连公网场景）
    TRUSTED_PROXIES: str = ""
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 30

    # ===== Centralized rate limiting (optional Redis) =====
    # Leave empty for in-process memory limiting (single worker).
    # Set e.g. redis://127.0.0.1:6379/0 so multiple workers share one counter.
    REDIS_URL: str = ""
    # 验证码有效期（秒）：默认 5 分钟。多 worker 部署建议配置 REDIS_URL，
    # 使验证码跨进程共享并原子一次性消费，彻底消除“验证码正确却提示错误”。
    CAPTCHA_TTL_SECONDS: int = 300
    # 验证码 Redis 键前缀（避免与限流计数等冲突）
    CAPTCHA_REDIS_PREFIX: str = "captcha:"

    # ===== 文件上传 =====
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS: str = ".doc,.docx,.xls,.xlsx,.ppt,.pptx,.pdf,.txt,.md,.csv,.jpg,.jpeg,.png,.gif,.bmp,.zip,.rar,.7z,.json,.xml"

    # ===== 数据库连接池 =====
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE: int = 3600
    # 连接池等待超时（秒）：防止请求在池空时无限排队导致“点快了加载不出来”
    DB_POOL_TIMEOUT: int = 10
    # 单条 SQL 执行超时（秒）：避免查询悬置拖死请求（SQLite 靠 busy_timeout，PostgreSQL 用 command_timeout）
    DB_QUERY_TIMEOUT: int = 30
    # 全局并发请求上限（同时在飞）：超出后迅速返回 503，而非无限排队
    HTTP_MAX_CONCURRENCY: int = 200
    # 全局 SSRF功能（SSE长连接）并发上限
    SSE_MAX_CONNECTIONS: int = 30
    # ===== AI 聊天限流（防止 LLM 资源/成本滥用）=====
    # 每个用户每窗口内允许的聊天请求数与窗口长度（秒）
    CHAT_RATE_LIMIT_MAX: int = 20
    CHAT_RATE_LIMIT_WINDOW_SECONDS: int = 60
    # ===== 数据保留与异常留痕 =====
    # 业务数据（传感器时序/异常留痕）最低保留天数
    DATA_RETENTION_DAYS: int = 180
    # 删除时保留的额外"安全余量"天数（避免时区/边界误删，实际删 now-(DAYS+BUFFER) 前的数据）
    DATA_RETENTION_BUFFER_DAYS: int = 3
    # 期望的采集间隔（秒）：默认每小时一条
    SENSOR_EXPECTED_INTERVAL_SECONDS: int = 3600
    # 缺失/异常窗口判定容差倍数：间隔 > 期望*c 视为"不在采集点"的异常窗口
    SENSOR_GAP_TOLERANCE: float = 1.5
    # 进程内每日保留清理任务：是否启用
    DATA_RETENTION_TASK_ENABLED: bool = True
    # 进程内告警自动升级任务：是否启用（测试环境可关闭以避免 TestClient 挂起）
    ALERT_INTEL_TASK_ENABLED: bool = True
    # ===== 告警生命周期（自动恢复 / 去重防抖 / 偶发故障） =====
    # "已解决"判定：设备参数连续保持正常的最短时长（分钟）
    ALERT_AUTO_RESOLVE_MINUTES: int = 30
    # 偶发(短时自愈)故障窗口：故障发生在此秒数内恢复，则记为偶发、只记录不推送
    ALERT_TRANSIENT_MAX_SECONDS: int = 300
    # 去重防抖：同一设备已解决后，再次出现异常需等待的冷却时长（分钟）
    ALERT_COOLDOWN_MINUTES: int = 5
    # 进程内告警生命周期任务（自动恢复扫描/偶发识别/去重归一）：是否启用
    ALERT_LIFECYCLE_TASK_ENABLED: bool = True
    # 生命周期扫描间隔（秒）
    ALERT_LIFECYCLE_INTERVAL_SECONDS: int = 60
    # 环境/气象关联统计历史保留天数
    ENV_RETENTION_DAYS: int = 180
    # ===== 环境/气象自动轮询采集（后台常驻任务，默认关闭） =====
    # 是否启用进程内环境采集轮询任务
    ENV_POLL_TASK_ENABLED: bool = False
    # 轮询间隔（秒）
    ENV_POLL_INTERVAL_SECONDS: int = 300
    # 数据源：sim=演示值 / real=Open-Meteo 真实天气
    ENV_POLL_SOURCE: str = "sim"
    # real 源定位（默认合肥）
    ENV_POLL_LAT: float = 31.82
    ENV_POLL_LON: float = 117.23
    # 采集写入的位置名/位置ID
    ENV_POLL_LOCATION_NAME: str = "主机房"
    ENV_POLL_LOCATION_ID: int = 0

    # ===== 邮件服务 =====
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "DCIManage 系统"
    SMTP_USE_TLS: bool = True
    SMTP_ENABLED: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


    @staticmethod
    def _parse_host_list(raw) -> list[str]:
        import json as _json
        if raw is None:
            return []
        if isinstance(raw, list):
            items = raw
        else:
            text = str(raw).strip()
            if not text:
                return []
            if text.startswith("[") and text.endswith("]"):
                try:
                    items = _json.loads(text)
                except Exception:
                    items = [p.strip() for p in text.strip("[]").split(",") if p.strip()]
            else:
                items = [p.strip() for p in text.split(",") if p.strip()]
        out = []
        for it in items:
            s = str(it).strip()
            if s and s not in out:
                out.append(s)
        return out

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def _parse_host_origins(cls, v):
        return cls._parse_host_list(v)


    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_insecure_secret(cls, v: str) -> str:
        insecure = {"dev-secret-key-change-in-production-2024", "changeme", "secret", "insecure"}
        if not v or v in insecure or v.startswith("dev-"):
            raise ValueError("SECRET_KEY 未设置，请在 .env 配置一个足够长的安全密钥字符串")
        return v

settings = Settings()


