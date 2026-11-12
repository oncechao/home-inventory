import os
from dataclasses import dataclass

DEV_SECRET = "dev-insecure-secret-change-me"


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = DEV_SECRET
    cookie_secure: bool = False


def normalize_db_url(url: str) -> str:
    """Neon/Vercel 给的是 postgres:// 或 postgresql://，SQLAlchemy 需要指明 psycopg 驱动。"""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def get_settings() -> Settings:
    on_vercel = bool(os.environ.get("VERCEL"))
    secret = os.environ.get("SECRET_KEY", DEV_SECRET)
    if on_vercel and secret == DEV_SECRET:
        raise RuntimeError("线上环境必须设置 SECRET_KEY 环境变量")
    secure_default = "true" if on_vercel else "false"
    return Settings(
        database_url=normalize_db_url(os.environ.get("DATABASE_URL", "sqlite:///./dev.db")),
        secret_key=secret,
        cookie_secure=os.environ.get("COOKIE_SECURE", secure_default).lower() == "true",
    )
