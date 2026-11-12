from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, get_settings
from app.db import make_engine
from app.routers import auth, families, invites, items, locations


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="家庭物品管理",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    engine = make_engine(settings.database_url)
    app.state.engine = engine
    app.state.SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    # 签名 Cookie：HttpOnly、SameSite=Lax；线上 https_only=True
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="hi_session",
        max_age=60 * 60 * 24 * 30,
        same_site="lax",
        https_only=settings.cookie_secure,
    )

    @app.get("/api/health")
    def health():
        return {"ok": True}

    app.include_router(auth.router, prefix="/api")
    app.include_router(families.router, prefix="/api")
    app.include_router(invites.router, prefix="/api")
    app.include_router(locations.router, prefix="/api")
    app.include_router(locations.lookup_router, prefix="/api")
    app.include_router(items.router, prefix="/api")

    return app


app = create_app()
