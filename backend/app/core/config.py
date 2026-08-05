"""应用配置"""
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    APP_NAME: str = "数据中心资源智能管理系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ===== 数据库 =====
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/managesys.db"
    DATABASE_URL_SYNC: str = "sqlite:///./data/managesys.db"

    # ===== JWT =====
    SECRET_KEY: str = "dev-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

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

    # ===== CORS =====
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # ===== 密码策略 =====
    PASSWORD_MIN_LENGTH: int = 8
    ENABLE_CAPTCHA: bool = False
    # --- 端口限流（防止暴力碰库 / 注册垃圾账号） ---
    # 每个 IP 每窗口内允许的请求数与窗口长度（秒）
    RATE_LIMIT_LOGIN_MAX: int = 10
    RATE_LIMIT_REGISTER_MAX: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 30

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


settings = Settings()
