# 家庭物品存放位置管理系统 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用 FastAPI + Vue 3 重写项目，做成一个支持多家庭、多层级位置、条码录入和收纳箱二维码的家庭物品存放位置管理系统，并能部署到 Vercel。

**Architecture:** 同一个仓库、同一个 Vercel 项目。`frontend/` 是 Vue 3 + Vite 单页应用，构建成静态文件；`backend/app/` 是 FastAPI 应用，通过 `api/index.py` 作为 Vercel Python 函数处理 `/api/*`。数据用 SQLAlchemy 访问，本地和测试用 SQLite，线上用 Neon Postgres；登录状态放在签名 Cookie 里；所有物品和位置接口都挂在 `/api/families/{family_id}/` 下，并先校验成员身份。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、Pydantic 2、argon2-cffi、pytest；Vue 3、Vite、TypeScript、Vue Router、Vant 4、vue-qrcode-reader、qrcode。

设计文档：`docs/plans/2026-11-12-home-inventory-design.md`

---

## 约定

- 所有命令都在仓库根目录 `/Users/wangshichao/Dev/serial-code-system` 下执行。
- Python 虚拟环境在 `.venv/`，用 `uv` 创建。测试命令统一用 `.venv/bin/pytest`。
- 后端包名是 `app`，源码在 `backend/app/`。`pytest.ini` 会把 `backend/` 加进 `sys.path`。
- 接口错误统一用 `HTTPException(status_code, "中文提示")`。
- 每个任务结束时提交一次。提交信息末尾加上：
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

---

### Task 1: 移走旧代码，搭后端骨架

**Files:**
- Delete（移到废纸篓）: `server.js`, `routes/`, `public/`, `data/`, `package.json`, `package-lock.json`, `node_modules/`, `.DS_Store`
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.python-version`
- Create: `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/models.py`, `backend/app/main.py`
- Test: `backend/tests/conftest.py`, `backend/tests/helpers.py`, `backend/tests/test_health.py`

**Step 1: 把旧代码移到废纸篓（可恢复，不直接删除）**

旧代码不在 git 里，所以不用 `rm`，而是移到 macOS 废纸篓：

```bash
mkdir -p ~/.Trash/serial-code-system-old-2026-11-12 && mv server.js routes public data package.json package-lock.json node_modules .DS_Store ~/.Trash/serial-code-system-old-2026-11-12/
```

Run: `git status --short`
Expected: 没有输出，工作区干净。

**Step 2: 写依赖文件和 pytest 配置**

`requirements.txt`（Vercel 会自动安装这个文件里的依赖）：

```
fastapi>=0.115,<1
sqlalchemy>=2.0.36,<2.1
alembic>=1.14,<2
pydantic>=2.9,<3
argon2-cffi>=23.1
itsdangerous>=2.2
psycopg[binary]>=3.2,<4
```

`requirements-dev.txt`：

```
-r requirements.txt
pytest>=8.3
httpx>=0.27
uvicorn[standard]>=0.32
```

`pytest.ini`：

```ini
[pytest]
testpaths = backend/tests
pythonpath = backend
```

`.python-version`：

```
3.12
```

**Step 3: 创建虚拟环境并安装依赖**

```bash
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements-dev.txt
```

Expected: 安装成功，最后一行类似 `Installed N packages`。

**Step 4: 写配置、数据库和模型**

`backend/app/__init__.py`：空文件。

`backend/app/config.py`：

```python
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
```

`backend/app/db.py`：

```python
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # 内存数据库：所有连接共用同一个，否则每个连接看到的都是空库
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine
    # Vercel 上每次调用可能是新实例：用 Neon 的连接池地址，SQLAlchemy 端不再维护连接池
    return create_engine(url, poolclass=NullPool)
```

`backend/app/models.py`：

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """SQLite 读回来的时间不带时区，统一当作 UTC。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Family(Base):
    __tablename__ = "families"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(lazy="joined")


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (Index("ix_locations_family_parent", "family_id", "parent_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"))
    name: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    updater: Mapped[User | None] = relationship(lazy="joined")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (Index("ix_items_family_barcode", "family_id", "barcode"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"))
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    barcode: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    updater: Mapped[User | None] = relationship(lazy="joined")
```

**Step 5: 写测试夹具和第一个失败的测试**

`backend/tests/conftest.py`：

```python
import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401  确保所有模型都注册到 Base.metadata
from app.config import Settings
from app.db import Base
from app.main import create_app


@pytest.fixture
def app():
    application = create_app(
        Settings(database_url="sqlite://", secret_key="test-secret", cookie_secure=False)
    )
    Base.metadata.create_all(application.state.engine)
    return application


@pytest.fixture
def new_client(app):
    """每调用一次就返回一个 Cookie 独立的客户端，用来模拟不同的人。"""

    def _make() -> TestClient:
        return TestClient(app)

    return _make


@pytest.fixture
def client(new_client):
    return new_client()
```

`backend/tests/helpers.py`（后面的任务会往这里追加函数）：

```python
PASSWORD = "password123"
```

`backend/tests/test_health.py`：

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

**Step 6: 运行测试，确认失败**

Run: `.venv/bin/pytest -q`
Expected: FAIL，报 `ModuleNotFoundError: No module named 'app.main'`。

**Step 7: 写 `main.py`**

`backend/app/main.py`：

```python
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, get_settings
from app.db import make_engine


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

    return app


app = create_app()
```

**Step 8: 运行测试，确认通过**

Run: `.venv/bin/pytest -q`
Expected: `1 passed`

**Step 9: Commit**

```bash
git add requirements.txt requirements-dev.txt pytest.ini .python-version backend/
git commit -m "feat: scaffold FastAPI backend with models"
```

---

### Task 2: 注册、登录、退出、修改密码

**Files:**
- Create: `backend/app/security.py`, `backend/app/deps.py`, `backend/app/schemas.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_auth.py`

**Step 1: 在 helpers 里加 `register`**

在 `backend/tests/helpers.py` 末尾追加：

```python
def register(client, username):
    r = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()
```

**Step 2: 写失败的测试**

`backend/tests/test_auth.py`：

```python
from sqlalchemy import select

from app.models import User
from helpers import PASSWORD, register


def test_register_logs_user_in(client):
    user = register(client, "alice")
    assert user["username"] == "alice"
    assert client.get("/api/auth/me").json()["username"] == "alice"


def test_register_rejects_duplicate_username(client, new_client):
    register(client, "alice")
    r = new_client().post("/api/auth/register", json={"username": "alice", "password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["detail"] == "用户名已被占用"


def test_register_validates_input(client):
    assert client.post("/api/auth/register", json={"username": "bob", "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "a b", "password": PASSWORD}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "张三丰", "password": PASSWORD}).status_code == 201


def test_password_is_hashed(app, client):
    register(client, "alice")
    with app.state.SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("$argon2")


def test_me_requires_login(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "请先登录"


def test_login_and_logout(client, new_client):
    register(client, "alice")
    other = new_client()
    assert other.post("/api/auth/login", json={"username": "alice", "password": "wrong-pass"}).status_code == 401
    assert other.post("/api/auth/login", json={"username": "nobody", "password": PASSWORD}).status_code == 401
    assert other.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 200
    assert other.get("/api/auth/me").status_code == 200
    assert other.post("/api/auth/logout").status_code == 204
    assert other.get("/api/auth/me").status_code == 401


def test_change_password(client, new_client):
    register(client, "alice")
    bad = client.post("/api/auth/password", json={"old_password": "nope", "new_password": "newpassword1"})
    assert bad.status_code == 400
    ok = client.post("/api/auth/password", json={"old_password": PASSWORD, "new_password": "newpassword1"})
    assert ok.status_code == 204
    other = new_client()
    assert other.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 401
    assert other.post("/api/auth/login", json={"username": "alice", "password": "newpassword1"}).status_code == 200
```

**Step 3: 运行测试，确认失败**

Run: `.venv/bin/pytest backend/tests/test_auth.py -q`
Expected: FAIL，所有接口都返回 404。

**Step 4: 写密码工具、依赖项和请求/响应模型**

`backend/app/security.py`：

```python
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
```

`backend/app/deps.py`：

```python
import uuid
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import Family, Membership, User


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.session.get("uid")
    user = None
    if raw:
        try:
            user = db.get(User, uuid.UUID(raw))
        except ValueError:
            user = None
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def member_family(
    family_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Family:
    """路径里的家庭必须是当前账号所在的家庭；否则一律 404，不暴露家庭是否存在。"""
    if db.get(Membership, (user.id, family_id)) is None:
        raise HTTPException(status_code=404, detail="家庭不存在")
    return db.get(Family, family_id)
```

`backend/app/schemas.py`（后面的任务会往这里追加）：

```python
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import as_utc

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
UtcDatetime = Annotated[datetime, AfterValidator(as_utc)]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- 账号 ----------

class RegisterIn(BaseModel):
    username: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50, pattern=r"^\w+$")
    ]
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: str = Field(min_length=1, max_length=128)


class PasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(OrmModel):
    id: uuid.UUID
    username: str
```

**Step 5: 写认证路由并注册到应用**

`backend/app/routers/__init__.py`：空文件。

`backend/app/routers/auth.py`：

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import User
from app.schemas import LoginIn, PasswordIn, RegisterIn, UserOut
from app.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserOut)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # 并发注册同名
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名已被占用")
    request.session["uid"] = str(user.id)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    request.session["uid"] = str(user.id)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/password", status_code=204)
def change_password(
    body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if not verify_password(user.password_hash, body.old_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    db.commit()
```

在 `backend/app/main.py` 里：在文件顶部的导入中加上 `from app.routers import auth`；在 `health` 函数定义之后、`return app` 之前加上：

```python
    app.include_router(auth.router, prefix="/api")
```

**Step 6: 运行测试，确认通过**

Run: `.venv/bin/pytest -q`
Expected: 全部通过（8 passed）。

**Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add registration, login and password change"
```

---

### Task 3: 家庭：创建、列表、详情、改名、解散、移除成员

**Files:**
- Create: `backend/app/services.py`, `backend/app/routers/families.py`
- Modify: `backend/app/schemas.py`, `backend/app/main.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_families.py`

**Step 1: 在 helpers 里加 `create_family`**

追加到 `backend/tests/helpers.py`：

```python
def create_family(client, name="我家"):
    r = client.post("/api/families", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]
```

**Step 2: 写失败的测试**

`backend/tests/test_families.py`：

```python
import uuid

from app.models import Family
from helpers import create_family, register


def test_create_list_and_detail(client):
    register(client, "alice")
    fid = create_family(client, "张家")
    assert [f["name"] for f in client.get("/api/families").json()] == ["张家"]
    detail = client.get(f"/api/families/{fid}").json()
    assert detail["name"] == "张家"
    assert [m["username"] for m in detail["members"]] == ["alice"]


def test_user_can_have_multiple_families(client):
    register(client, "alice")
    create_family(client, "自己家")
    create_family(client, "爸妈家")
    assert [f["name"] for f in client.get("/api/families").json()] == ["自己家", "爸妈家"]


def test_rename_family(client):
    register(client, "alice")
    fid = create_family(client, "张家")
    r = client.patch(f"/api/families/{fid}", json={"name": "  新张家  "})
    assert r.status_code == 200
    assert r.json()["name"] == "新张家"


def test_family_name_required(client):
    register(client, "alice")
    assert client.post("/api/families", json={"name": "   "}).status_code == 422


def test_non_member_gets_404(client, new_client):
    register(client, "alice")
    fid = create_family(client)
    bob = new_client()
    register(bob, "bob")
    assert bob.get(f"/api/families/{fid}").status_code == 404
    assert bob.patch(f"/api/families/{fid}", json={"name": "x"}).status_code == 404
    assert bob.delete(f"/api/families/{fid}").status_code == 404
    assert bob.get(f"/api/families/{uuid.uuid4()}").status_code == 404


def test_requires_login(client):
    assert client.get("/api/families").status_code == 401


def test_dissolve_family(app, client):
    register(client, "alice")
    fid = create_family(client)
    assert client.delete(f"/api/families/{fid}").status_code == 204
    assert client.get(f"/api/families/{fid}").status_code == 404
    assert client.get("/api/families").json() == []
    with app.state.SessionLocal() as db:
        assert db.get(Family, uuid.UUID(fid)) is None


def test_last_member_leaving_deletes_family(app, client):
    alice = register(client, "alice")
    fid = create_family(client)
    assert client.delete(f"/api/families/{fid}/members/{alice['id']}").status_code == 204
    assert client.get("/api/families").json() == []
    with app.state.SessionLocal() as db:
        assert db.get(Family, uuid.UUID(fid)) is None


def test_remove_unknown_member_is_404(client):
    register(client, "alice")
    fid = create_family(client)
    assert client.delete(f"/api/families/{fid}/members/{uuid.uuid4()}").status_code == 404
```

**Step 3: 运行测试，确认失败**

Run: `.venv/bin/pytest backend/tests/test_families.py -q`
Expected: FAIL（接口返回 404 / 405）。

**Step 4: 追加 schemas**

追加到 `backend/app/schemas.py`：

```python
# ---------- 家庭 ----------

class FamilyIn(BaseModel):
    name: Name


class FamilyOut(OrmModel):
    id: uuid.UUID
    name: str


class MemberOut(BaseModel):
    id: uuid.UUID
    username: str
    joined_at: UtcDatetime


class FamilyDetail(FamilyOut):
    members: list[MemberOut]
```

**Step 5: 写 services 和家庭路由**

`backend/app/services.py`（后面的任务会追加）：

```python
import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Family, Invite, Item, Location, Membership


def delete_family(db: Session, family_id: uuid.UUID) -> None:
    """按依赖顺序删除一个家庭的全部数据。调用方负责 commit。"""
    db.execute(delete(Item).where(Item.family_id == family_id))
    db.execute(delete(Location).where(Location.family_id == family_id))
    db.execute(delete(Invite).where(Invite.family_id == family_id))
    db.execute(delete(Membership).where(Membership.family_id == family_id))
    db.execute(delete(Family).where(Family.id == family_id))
```

`backend/app/routers/families.py`：

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Membership, User
from app.schemas import FamilyDetail, FamilyIn, FamilyOut, MemberOut
from app.services import delete_family

router = APIRouter(prefix="/families", tags=["families"])


@router.get("", response_model=list[FamilyOut])
def list_families(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Family)
        .join(Membership, Membership.family_id == Family.id)
        .where(Membership.user_id == user.id)
        .order_by(Membership.joined_at)
    )
    return db.scalars(stmt).all()


@router.post("", status_code=201, response_model=FamilyOut)
def create_family(
    body: FamilyIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    family = Family(name=body.name)
    db.add(family)
    db.flush()
    db.add(Membership(user_id=user.id, family_id=family.id))
    db.commit()
    return family


@router.get("/{family_id}", response_model=FamilyDetail)
def get_family(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    memberships = db.scalars(
        select(Membership)
        .where(Membership.family_id == family.id)
        .order_by(Membership.joined_at)
    ).all()
    return FamilyDetail(
        id=family.id,
        name=family.name,
        members=[
            MemberOut(id=m.user.id, username=m.user.username, joined_at=m.joined_at)
            for m in memberships
        ],
    )


@router.patch("/{family_id}", response_model=FamilyOut)
def rename_family(
    body: FamilyIn, family: Family = Depends(member_family), db: Session = Depends(get_db)
):
    family.name = body.name
    db.commit()
    return family


@router.delete("/{family_id}", status_code=204)
def dissolve_family(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    delete_family(db, family.id)
    db.commit()


@router.delete("/{family_id}/members/{user_id}", status_code=204)
def remove_member(
    user_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    """移除成员；user_id 是自己时就是退出家庭。最后一个人离开时删除整个家庭。"""
    membership = db.get(Membership, (user_id, family.id))
    if membership is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    db.delete(membership)
    db.flush()
    remaining = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.family_id == family.id)
    )
    if remaining == 0:
        delete_family(db, family.id)
    db.commit()
```

在 `backend/app/main.py` 的导入里改成 `from app.routers import auth, families`，并在 `include_router(auth.router ...)` 后面加：

```python
    app.include_router(families.router, prefix="/api")
```

**Step 6: 运行测试，确认通过**

Run: `.venv/bin/pytest -q`
Expected: 全部通过。

**Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add families with membership checks"
```

---

### Task 4: 邀请链接

**Files:**
- Create: `backend/app/routers/invites.py`
- Modify: `backend/app/schemas.py`, `backend/app/routers/families.py`, `backend/app/main.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_invites.py`

**Step 1: 在 helpers 里加 `invite_and_join`**

追加到 `backend/tests/helpers.py`：

```python
def invite_and_join(owner, joiner, fid):
    code = owner.post(f"/api/families/{fid}/invites").json()["code"]
    r = joiner.post(f"/api/invites/{code}/accept")
    assert r.status_code == 200, r.text
```

**Step 2: 写失败的测试**

`backend/tests/test_invites.py`：

```python
from datetime import timedelta

from sqlalchemy import select

from app.models import Invite, utcnow
from helpers import create_family, invite_and_join, register


def setup_two(client, new_client):
    alice = register(client, "alice")
    fid = create_family(client, "张家")
    bob_client = new_client()
    bob = register(bob_client, "bob")
    return alice, bob, bob_client, fid


def test_invite_preview_and_accept(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    invite = client.post(f"/api/families/{fid}/invites")
    assert invite.status_code == 201
    code = invite.json()["code"]

    preview = bob.get(f"/api/invites/{code}").json()
    assert preview == {"family_id": fid, "family_name": "张家", "already_member": False}

    r = bob.post(f"/api/invites/{code}/accept")
    assert r.status_code == 200
    assert r.json()["id"] == fid
    assert [f["id"] for f in bob.get("/api/families").json()] == [fid]
    members = client.get(f"/api/families/{fid}").json()["members"]
    assert [m["username"] for m in members] == ["alice", "bob"]


def test_accept_twice_is_ok(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    code = client.post(f"/api/families/{fid}/invites").json()["code"]
    assert bob.post(f"/api/invites/{code}/accept").status_code == 200
    assert bob.get(f"/api/invites/{code}").json()["already_member"] is True
    assert bob.post(f"/api/invites/{code}/accept").status_code == 200
    assert len(client.get(f"/api/families/{fid}").json()["members"]) == 2


def test_revoked_invite_rejected(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    invite = client.post(f"/api/families/{fid}/invites").json()
    assert client.delete(f"/api/families/{fid}/invites/{invite['id']}").status_code == 204
    assert client.get(f"/api/families/{fid}/invites").json() == []
    r = bob.post(f"/api/invites/{invite['code']}/accept")
    assert r.status_code == 404
    assert r.json()["detail"] == "邀请无效或已过期"


def test_expired_invite_rejected(app, client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    code = client.post(f"/api/families/{fid}/invites").json()["code"]
    with app.state.SessionLocal() as db:
        invite = db.scalar(select(Invite).where(Invite.code == code))
        invite.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert bob.get(f"/api/invites/{code}").status_code == 404
    assert bob.post(f"/api/invites/{code}/accept").status_code == 404
    assert client.get(f"/api/families/{fid}/invites").json() == []


def test_invite_expires_in_7_days(client):
    register(client, "alice")
    fid = create_family(client)
    invite = client.post(f"/api/families/{fid}/invites").json()
    assert invite["expires_at"]
    assert len(client.get(f"/api/families/{fid}/invites").json()) == 1


def test_preview_requires_login(client, new_client):
    register(client, "alice")
    fid = create_family(client)
    code = client.post(f"/api/families/{fid}/invites").json()["code"]
    assert new_client().get(f"/api/invites/{code}").status_code == 401


def test_non_member_cannot_manage_invites(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    assert bob.post(f"/api/families/{fid}/invites").status_code == 404
    assert bob.get(f"/api/families/{fid}/invites").status_code == 404


def test_member_can_remove_other_member(client, new_client):
    _, bob_user, bob, fid = setup_two(client, new_client)
    invite_and_join(client, bob, fid)
    assert client.delete(f"/api/families/{fid}/members/{bob_user['id']}").status_code == 204
    assert bob.get(f"/api/families/{fid}").status_code == 404


def test_member_can_leave_and_family_stays(client, new_client):
    _, bob_user, bob, fid = setup_two(client, new_client)
    invite_and_join(client, bob, fid)
    assert bob.delete(f"/api/families/{fid}/members/{bob_user['id']}").status_code == 204
    assert bob.get("/api/families").json() == []
    assert [m["username"] for m in client.get(f"/api/families/{fid}").json()["members"]] == ["alice"]


def test_any_member_can_dissolve(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    invite_and_join(client, bob, fid)
    assert bob.delete(f"/api/families/{fid}").status_code == 204
    assert client.get("/api/families").json() == []
```

**Step 3: 运行测试，确认失败**

Run: `.venv/bin/pytest backend/tests/test_invites.py -q`
Expected: FAIL。

**Step 4: 追加 schemas**

追加到 `backend/app/schemas.py`：

```python
# ---------- 邀请 ----------

class InviteOut(OrmModel):
    id: uuid.UUID
    code: str
    expires_at: UtcDatetime


class InvitePreview(BaseModel):
    family_id: uuid.UUID
    family_name: str
    already_member: bool
```

**Step 5: 在家庭路由里加邀请管理接口**

在 `backend/app/routers/families.py` 中：

1. 把导入改成：

```python
import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Invite, Membership, User, as_utc, utcnow
from app.schemas import FamilyDetail, FamilyIn, FamilyOut, InviteOut, MemberOut
from app.services import delete_family

INVITE_TTL = timedelta(days=7)
```

2. 在文件末尾追加：

```python
@router.get("/{family_id}/invites", response_model=list[InviteOut])
def list_invites(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    now = utcnow()
    invites = db.scalars(
        select(Invite)
        .where(Invite.family_id == family.id, Invite.revoked_at.is_(None))
        .order_by(Invite.created_at.desc())
    ).all()
    return [i for i in invites if as_utc(i.expires_at) > now]


@router.post("/{family_id}/invites", status_code=201, response_model=InviteOut)
def create_invite(
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    invite = Invite(
        family_id=family.id,
        code=secrets.token_urlsafe(9),  # 12 个字符，URL 安全
        created_by=user.id,
        expires_at=utcnow() + INVITE_TTL,
    )
    db.add(invite)
    db.commit()
    return invite


@router.delete("/{family_id}/invites/{invite_id}", status_code=204)
def revoke_invite(
    invite_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    invite = db.get(Invite, invite_id)
    if invite is None or invite.family_id != family.id:
        raise HTTPException(status_code=404, detail="邀请不存在")
    invite.revoked_at = utcnow()
    db.commit()
```

**Step 6: 写接受邀请的路由**

`backend/app/routers/invites.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Family, Invite, Membership, User, as_utc, utcnow
from app.schemas import FamilyOut, InvitePreview

router = APIRouter(prefix="/invites", tags=["invites"])


def _valid_invite(db: Session, code: str) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.code == code))
    if invite is None or invite.revoked_at is not None or as_utc(invite.expires_at) <= utcnow():
        raise HTTPException(status_code=404, detail="邀请无效或已过期")
    return invite


@router.get("/{code}", response_model=InvitePreview)
def preview_invite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    invite = _valid_invite(db, code)
    family = db.get(Family, invite.family_id)
    return InvitePreview(
        family_id=family.id,
        family_name=family.name,
        already_member=db.get(Membership, (user.id, family.id)) is not None,
    )


@router.post("/{code}/accept", response_model=FamilyOut)
def accept_invite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    invite = _valid_invite(db, code)
    if db.get(Membership, (user.id, invite.family_id)) is None:
        db.add(Membership(user_id=user.id, family_id=invite.family_id))
        db.commit()
    return db.get(Family, invite.family_id)
```

在 `backend/app/main.py` 的导入里改成 `from app.routers import auth, families, invites`，并加：

```python
    app.include_router(invites.router, prefix="/api")
```

**Step 7: 运行测试，确认通过**

Run: `.venv/bin/pytest -q`
Expected: 全部通过。

**Step 8: Commit**

```bash
git add backend/
git commit -m "feat: add family invites"
```

---

### Task 5: 位置树

**Files:**
- Create: `backend/app/routers/locations.py`
- Modify: `backend/app/schemas.py`, `backend/app/services.py`, `backend/app/main.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_locations.py`

**Step 1: 在 helpers 里加 `create_location`**

追加到 `backend/tests/helpers.py`：

```python
def create_location(client, fid, name, parent_id=None):
    r = client.post(f"/api/families/{fid}/locations", json={"name": name, "parent_id": parent_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]
```

**Step 2: 写失败的测试**

`backend/tests/test_locations.py`：

```python
import uuid

import pytest

from helpers import create_family, create_location, register


@pytest.fixture
def fam(client):
    register(client, "alice")
    return create_family(client)


def names(path):
    return [n["name"] for n in path]


def test_nested_locations_have_full_path(client, fam):
    bedroom = create_location(client, fam, "主卧")
    wardrobe = create_location(client, fam, "衣柜", bedroom)
    box = create_location(client, fam, "蓝色收纳盒", wardrobe)

    detail = client.get(f"/api/families/{fam}/locations/{box}").json()
    assert names(detail["path"]) == ["主卧", "衣柜", "蓝色收纳盒"]
    assert detail["updated_by_name"] == "alice"

    wardrobe_detail = client.get(f"/api/families/{fam}/locations/{wardrobe}").json()
    assert [c["name"] for c in wardrobe_detail["children"]] == ["蓝色收纳盒"]


def test_list_is_sorted_by_path(client, fam):
    study = create_location(client, fam, "书房")
    bedroom = create_location(client, fam, "主卧")
    create_location(client, fam, "书桌", study)
    create_location(client, fam, "衣柜", bedroom)
    listed = client.get(f"/api/families/{fam}/locations").json()
    assert [" › ".join(names(l["path"])) for l in listed] == sorted(
        ["书房", "书房 › 书桌", "主卧", "主卧 › 衣柜"]
    )


def test_parent_must_exist(client, fam):
    r = client.post(
        f"/api/families/{fam}/locations", json={"name": "x", "parent_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "上级位置不存在"


def test_rename_and_note(client, fam):
    loc = create_location(client, fam, "客厅")
    r = client.patch(f"/api/families/{fam}/locations/{loc}", json={"name": "大客厅", "note": "电视柜"})
    assert r.status_code == 200
    assert r.json()["name"] == "大客厅"
    assert r.json()["note"] == "电视柜"
    assert r.json()["parent_id"] is None  # 没传 parent_id 时不改动


def test_move_location(client, fam):
    bedroom = create_location(client, fam, "主卧")
    study = create_location(client, fam, "书房")
    wardrobe = create_location(client, fam, "衣柜", bedroom)
    box = create_location(client, fam, "盒子", wardrobe)

    r = client.patch(f"/api/families/{fam}/locations/{wardrobe}", json={"parent_id": study})
    assert r.status_code == 200
    box_path = client.get(f"/api/families/{fam}/locations/{box}").json()["path"]
    assert names(box_path) == ["书房", "衣柜", "盒子"]

    r = client.patch(f"/api/families/{fam}/locations/{wardrobe}", json={"parent_id": None})
    assert names(r.json()["path"]) == ["衣柜"]


def test_cannot_move_into_itself_or_descendant(client, fam):
    a = create_location(client, fam, "A")
    b = create_location(client, fam, "B", a)
    c = create_location(client, fam, "C", b)
    for target in (a, b, c):
        r = client.patch(f"/api/families/{fam}/locations/{a}", json={"parent_id": target})
        assert r.status_code == 409, target
        assert r.json()["detail"] == "不能移动到它自己或它的下级位置里"


def test_delete_only_empty_location(client, fam):
    parent = create_location(client, fam, "主卧")
    child = create_location(client, fam, "衣柜", parent)
    r = client.delete(f"/api/families/{fam}/locations/{parent}")
    assert r.status_code == 409
    assert r.json()["detail"] == "位置里还有子位置或物品，请先移走"
    assert client.delete(f"/api/families/{fam}/locations/{child}").status_code == 204
    assert client.delete(f"/api/families/{fam}/locations/{parent}").status_code == 204
    assert client.get(f"/api/families/{fam}/locations").json() == []


def test_lookup_returns_family_for_member(client, new_client, fam):
    loc = create_location(client, fam, "客厅")
    assert client.get(f"/api/locations/{loc}").json() == {"family_id": fam}
    bob = new_client()
    register(bob, "bob")
    assert bob.get(f"/api/locations/{loc}").status_code == 404
    assert client.get(f"/api/locations/{uuid.uuid4()}").status_code == 404
```

**Step 3: 运行测试，确认失败**

Run: `.venv/bin/pytest backend/tests/test_locations.py -q`
Expected: FAIL。

**Step 4: 追加 schemas**

追加到 `backend/app/schemas.py`：

```python
# ---------- 位置 ----------

class PathNode(BaseModel):
    id: uuid.UUID
    name: str


class LocationIn(BaseModel):
    name: Name
    note: Note = ""
    parent_id: uuid.UUID | None = None


class LocationPatch(BaseModel):
    """不传的字段不修改；parent_id 显式传 null 表示移到顶层。"""

    name: Name | None = None
    note: Note | None = None
    parent_id: uuid.UUID | None = None


class LocationOut(BaseModel):
    id: uuid.UUID
    name: str
    note: str
    parent_id: uuid.UUID | None
    path: list[PathNode]
    updated_at: UtcDatetime
    updated_by_name: str | None


class LocationDetail(LocationOut):
    children: list[LocationOut]
```

**Step 5: 追加 services**

在 `backend/app/services.py` 中，把导入改成：

```python
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Family, Invite, Item, Location, Membership
from app.schemas import LocationOut, PathNode
```

并在文件末尾追加：

```python
def location_paths(db: Session, family_id: uuid.UUID) -> dict[uuid.UUID, list[PathNode]]:
    """一次读出家庭内全部位置，在内存里拼出每个位置的完整路径（从顶层到自己）。"""
    rows = db.execute(
        select(Location.id, Location.parent_id, Location.name).where(
            Location.family_id == family_id
        )
    ).all()
    by_id = {r.id: r for r in rows}
    cache: dict[uuid.UUID, list[PathNode]] = {}

    def path_of(location_id: uuid.UUID) -> list[PathNode]:
        if location_id not in cache:
            row = by_id[location_id]
            parent = path_of(row.parent_id) if row.parent_id in by_id else []
            cache[location_id] = parent + [PathNode(id=row.id, name=row.name)]
        return cache[location_id]

    return {location_id: path_of(location_id) for location_id in by_id}


def would_create_cycle(
    db: Session, family_id: uuid.UUID, location_id: uuid.UUID, new_parent_id: uuid.UUID
) -> bool:
    """从新的上级位置一路往上找，如果遇到自己，说明会形成循环。"""
    parents = dict(
        db.execute(
            select(Location.id, Location.parent_id).where(Location.family_id == family_id)
        ).all()
    )
    current: uuid.UUID | None = new_parent_id
    while current is not None:
        if current == location_id:
            return True
        current = parents.get(current)
    return False


def get_location_in_family(
    db: Session, family_id: uuid.UUID, location_id: uuid.UUID, detail: str = "位置不存在"
) -> Location:
    location = db.get(Location, location_id)
    if location is None or location.family_id != family_id:
        raise HTTPException(status_code=404, detail=detail)
    return location


def location_out(location: Location, paths: dict[uuid.UUID, list[PathNode]]) -> LocationOut:
    return LocationOut(
        id=location.id,
        name=location.name,
        note=location.note,
        parent_id=location.parent_id,
        path=paths[location.id],
        updated_at=location.updated_at,
        updated_by_name=location.updater.username if location.updater else None,
    )
```

**Step 6: 写位置路由**

`backend/app/routers/locations.py`：

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Item, Location, Membership, User
from app.schemas import LocationDetail, LocationIn, LocationOut, LocationPatch
from app.services import (
    get_location_in_family,
    location_out,
    location_paths,
    would_create_cycle,
)

router = APIRouter(prefix="/families/{family_id}/locations", tags=["locations"])
lookup_router = APIRouter(tags=["locations"])


@router.get("", response_model=list[LocationOut])
def list_locations(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    paths = location_paths(db, family.id)
    locations = db.scalars(select(Location).where(Location.family_id == family.id)).all()
    return sorted(
        (location_out(l, paths) for l in locations),
        key=lambda out: [node.name for node in out.path],
    )


@router.post("", status_code=201, response_model=LocationOut)
def create_location(
    body: LocationIn,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if body.parent_id is not None:
        get_location_in_family(db, family.id, body.parent_id, "上级位置不存在")
    location = Location(
        family_id=family.id,
        parent_id=body.parent_id,
        name=body.name,
        note=body.note,
        updated_by=user.id,
    )
    db.add(location)
    db.commit()
    return location_out(location, location_paths(db, family.id))


@router.get("/{location_id}", response_model=LocationDetail)
def get_location(
    location_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    location = get_location_in_family(db, family.id, location_id)
    paths = location_paths(db, family.id)
    children = db.scalars(
        select(Location).where(Location.parent_id == location.id).order_by(Location.name)
    ).all()
    return LocationDetail(
        **location_out(location, paths).model_dump(),
        children=[location_out(c, paths) for c in children],
    )


@router.patch("/{location_id}", response_model=LocationOut)
def update_location(
    location_id: uuid.UUID,
    body: LocationPatch,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    location = get_location_in_family(db, family.id, location_id)
    if body.name is not None:
        location.name = body.name
    if body.note is not None:
        location.note = body.note
    if "parent_id" in body.model_fields_set:
        if body.parent_id is not None:
            get_location_in_family(db, family.id, body.parent_id, "上级位置不存在")
            if would_create_cycle(db, family.id, location.id, body.parent_id):
                raise HTTPException(status_code=409, detail="不能移动到它自己或它的下级位置里")
        location.parent_id = body.parent_id
    location.updated_by = user.id
    db.commit()
    return location_out(location, location_paths(db, family.id))


@router.delete("/{location_id}", status_code=204)
def delete_location(
    location_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    location = get_location_in_family(db, family.id, location_id)
    has_child = db.scalar(select(Location.id).where(Location.parent_id == location.id).limit(1))
    has_item = db.scalar(select(Item.id).where(Item.location_id == location.id).limit(1))
    if has_child or has_item:
        raise HTTPException(status_code=409, detail="位置里还有子位置或物品，请先移走")
    db.delete(location)
    db.commit()


@lookup_router.get("/locations/{location_id}")
def lookup_location(
    location_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """二维码入口：告诉前端这个位置属于哪个家庭。不是成员时 404。"""
    location = db.get(Location, location_id)
    if location is None or db.get(Membership, (user.id, location.family_id)) is None:
        raise HTTPException(status_code=404, detail="位置不存在")
    return {"family_id": str(location.family_id)}
```

在 `backend/app/main.py` 的导入里改成 `from app.routers import auth, families, invites, locations`，并加：

```python
    app.include_router(locations.router, prefix="/api")
    app.include_router(locations.lookup_router, prefix="/api")
```

**Step 7: 运行测试，确认通过**

Run: `.venv/bin/pytest -q`
Expected: 全部通过。

**Step 8: Commit**

```bash
git add backend/
git commit -m "feat: add nested locations with move and cycle checks"
```

---

### Task 6: 物品与搜索

**Files:**
- Create: `backend/app/routers/items.py`
- Modify: `backend/app/schemas.py`, `backend/app/services.py`, `backend/app/routers/locations.py`, `backend/app/main.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_items.py`

**Step 1: 在 helpers 里加 `create_item`**

追加到 `backend/tests/helpers.py`：

```python
def create_item(client, fid, name, location_id, barcode=None, note=""):
    r = client.post(
        f"/api/families/{fid}/items",
        json={"name": name, "location_id": location_id, "barcode": barcode, "note": note},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]
```

**Step 2: 写失败的测试**

`backend/tests/test_items.py`：

```python
import uuid

import pytest
from sqlalchemy import func, select

from app.models import Item, Location
from helpers import create_family, create_item, create_location, register


@pytest.fixture
def fam(client):
    register(client, "alice")
    return create_family(client)


def item_names(resp):
    return sorted(i["name"] for i in resp.json())


def test_create_item_with_path(client, fam):
    room = create_location(client, fam, "书房")
    drawer = create_location(client, fam, "左侧抽屉", room)
    iid = create_item(client, fam, "护照", drawer, note="在文件袋里")
    item = client.get(f"/api/families/{fam}/items/{iid}").json()
    assert [n["name"] for n in item["path"]] == ["书房", "左侧抽屉"]
    assert item["barcode"] is None
    assert item["updated_by_name"] == "alice"


def test_location_must_exist(client, fam):
    r = client.post(
        f"/api/families/{fam}/items", json={"name": "x", "location_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "位置不存在"


def test_empty_barcode_is_null(client, fam):
    loc = create_location(client, fam, "客厅")
    iid = create_item(client, fam, "遥控器", loc, barcode="  ")
    assert client.get(f"/api/families/{fam}/items/{iid}").json()["barcode"] is None


def test_search_by_name_barcode_and_note(client, fam):
    loc = create_location(client, fam, "厨房")
    create_item(client, fam, "Sharp Knife", loc)
    create_item(client, fam, "洗洁精", loc, barcode="6901234567890")
    create_item(client, fam, "保鲜膜", loc, note="备用的在上层")
    base = f"/api/families/{fam}/items"
    assert item_names(client.get(base, params={"q": "knife"})) == ["Sharp Knife"]
    assert item_names(client.get(base, params={"q": "洁精"})) == ["洗洁精"]
    assert item_names(client.get(base, params={"q": "1234567"})) == ["洗洁精"]
    assert item_names(client.get(base, params={"q": "备用"})) == ["保鲜膜"]
    assert len(client.get(base).json()) == 3  # 不带条件时返回最近更新的物品


def test_search_escapes_wildcards(client, fam):
    loc = create_location(client, fam, "衣柜")
    create_item(client, fam, "100%纯棉T恤", loc)
    create_item(client, fam, "毛衣", loc)
    assert item_names(client.get(f"/api/families/{fam}/items", params={"q": "%"})) == ["100%纯棉T恤"]
    assert item_names(client.get(f"/api/families/{fam}/items", params={"q": "_"})) == []


def test_barcode_matches_multiple_items(client, fam):
    a = create_location(client, fam, "浴室")
    b = create_location(client, fam, "储物间")
    create_item(client, fam, "洗发水", a, barcode="6900000000001")
    create_item(client, fam, "洗发水（备用）", b, barcode="6900000000001")
    base = f"/api/families/{fam}/items"
    assert item_names(client.get(base, params={"barcode": "6900000000001"})) == ["洗发水", "洗发水（备用）"]
    assert client.get(base, params={"barcode": "000"}).json() == []


def test_update_and_move_item(client, fam):
    a = create_location(client, fam, "客厅")
    b = create_location(client, fam, "卧室")
    iid = create_item(client, fam, "充电器", a, barcode="123")
    r = client.patch(
        f"/api/families/{fam}/items/{iid}",
        json={"location_id": b, "name": "手机充电器", "barcode": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "手机充电器"
    assert body["barcode"] is None
    assert [n["name"] for n in body["path"]] == ["卧室"]


def test_location_detail_lists_items_and_blocks_delete(client, fam):
    loc = create_location(client, fam, "玄关")
    iid = create_item(client, fam, "钥匙", loc)
    detail = client.get(f"/api/families/{fam}/locations/{loc}").json()
    assert [i["name"] for i in detail["items"]] == ["钥匙"]
    assert client.delete(f"/api/families/{fam}/locations/{loc}").status_code == 409
    assert client.delete(f"/api/families/{fam}/items/{iid}").status_code == 204
    assert client.get(f"/api/families/{fam}/items/{iid}").status_code == 404
    assert client.delete(f"/api/families/{fam}/locations/{loc}").status_code == 204


def test_dissolving_family_deletes_its_data(app, client, fam):
    room = create_location(client, fam, "书房")
    box = create_location(client, fam, "盒子", room)
    create_item(client, fam, "U盘", box)
    assert client.delete(f"/api/families/{fam}").status_code == 204
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Item)) == 0
        assert db.scalar(select(func.count()).select_from(Location)) == 0
```

**Step 3: 运行测试，确认失败**

Run: `.venv/bin/pytest backend/tests/test_items.py -q`
Expected: FAIL。

**Step 4: 追加 schemas，并让位置详情带上物品**

在 `backend/app/schemas.py` 中：

1. 把导入的 pydantic 那一行改成：

```python
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator
```

2. **删除**原来的 `LocationDetail` 类，在文件末尾追加：

```python
# ---------- 物品 ----------

ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Barcode = Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]


class ItemIn(BaseModel):
    name: ItemName
    barcode: Barcode | None = None
    note: Note = ""
    location_id: uuid.UUID

    @field_validator("barcode")
    @classmethod
    def empty_barcode_to_none(cls, v: str | None) -> str | None:
        return v or None


class ItemPatch(BaseModel):
    """不传的字段不修改；barcode 显式传 null 或空字符串表示清空。"""

    name: ItemName | None = None
    barcode: Barcode | None = None
    note: Note | None = None
    location_id: uuid.UUID | None = None

    @field_validator("barcode")
    @classmethod
    def empty_barcode_to_none(cls, v: str | None) -> str | None:
        return v or None


class ItemOut(BaseModel):
    id: uuid.UUID
    name: str
    barcode: str | None
    note: str
    location_id: uuid.UUID
    path: list[PathNode]
    updated_at: UtcDatetime
    updated_by_name: str | None


class LocationDetail(LocationOut):
    children: list[LocationOut]
    items: list[ItemOut]
```

**Step 5: 追加 services**

在 `backend/app/services.py` 中，把 `from app.schemas import ...` 改成：

```python
from app.schemas import ItemOut, LocationOut, PathNode
```

并在文件末尾追加：

```python
def item_out(item: Item, paths: dict[uuid.UUID, list[PathNode]]) -> ItemOut:
    return ItemOut(
        id=item.id,
        name=item.name,
        barcode=item.barcode,
        note=item.note,
        location_id=item.location_id,
        path=paths[item.location_id],
        updated_at=item.updated_at,
        updated_by_name=item.updater.username if item.updater else None,
    )


def escape_like(text: str) -> str:
    """让用户输入的 % 和 _ 按字面匹配。配合 ilike(..., escape='\\\\') 使用。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
```

**Step 6: 位置详情返回物品**

在 `backend/app/routers/locations.py` 中：

1. 把 `from app.services import (...)` 改成同时导入 `item_out`：

```python
from app.services import (
    get_location_in_family,
    item_out,
    location_out,
    location_paths,
    would_create_cycle,
)
```

2. 把 `get_location` 函数的 `return` 部分替换为：

```python
    items = db.scalars(
        select(Item).where(Item.location_id == location.id).order_by(Item.name)
    ).all()
    return LocationDetail(
        **location_out(location, paths).model_dump(),
        children=[location_out(c, paths) for c in children],
        items=[item_out(i, paths) for i in items],
    )
```

**Step 7: 写物品路由**

`backend/app/routers/items.py`：

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Item, User
from app.schemas import ItemIn, ItemOut, ItemPatch
from app.services import escape_like, get_location_in_family, item_out, location_paths

router = APIRouter(prefix="/families/{family_id}/items", tags=["items"])


def _get_item(db: Session, family: Family, item_id: uuid.UUID) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.family_id != family.id:
        raise HTTPException(status_code=404, detail="物品不存在")
    return item


@router.get("", response_model=list[ItemOut])
def list_items(
    q: str | None = None,
    barcode: str | None = None,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    """q：按名称/条码/备注模糊搜索；barcode：按条码精确匹配；都不传则返回最近更新的物品。"""
    stmt = select(Item).where(Item.family_id == family.id)
    filtered = False
    if barcode and barcode.strip():
        stmt = stmt.where(Item.barcode == barcode.strip())
        filtered = True
    if q and q.strip():
        pattern = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                Item.name.ilike(pattern, escape="\\"),
                Item.barcode.ilike(pattern, escape="\\"),
                Item.note.ilike(pattern, escape="\\"),
            )
        )
        filtered = True
    stmt = stmt.order_by(Item.updated_at.desc()).limit(200 if filtered else 50)
    paths = location_paths(db, family.id)
    return [item_out(i, paths) for i in db.scalars(stmt).all()]


@router.post("", status_code=201, response_model=ItemOut)
def create_item(
    body: ItemIn,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_location_in_family(db, family.id, body.location_id)
    item = Item(
        family_id=family.id,
        location_id=body.location_id,
        name=body.name,
        barcode=body.barcode,
        note=body.note,
        updated_by=user.id,
    )
    db.add(item)
    db.commit()
    return item_out(item, location_paths(db, family.id))


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: uuid.UUID, family: Family = Depends(member_family), db: Session = Depends(get_db)
):
    return item_out(_get_item(db, family, item_id), location_paths(db, family.id))


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID,
    body: ItemPatch,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = _get_item(db, family, item_id)
    if body.name is not None:
        item.name = body.name
    if "barcode" in body.model_fields_set:
        item.barcode = body.barcode
    if body.note is not None:
        item.note = body.note
    if body.location_id is not None:
        get_location_in_family(db, family.id, body.location_id)
        item.location_id = body.location_id
    item.updated_by = user.id
    db.commit()
    return item_out(item, location_paths(db, family.id))


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: uuid.UUID, family: Family = Depends(member_family), db: Session = Depends(get_db)
):
    db.delete(_get_item(db, family, item_id))
    db.commit()
```

在 `backend/app/main.py` 的导入里改成 `from app.routers import auth, families, invites, items, locations`，并加：

```python
    app.include_router(items.router, prefix="/api")
```

**Step 8: 运行测试，确认通过**

Run: `.venv/bin/pytest -q`
Expected: 全部通过。

**Step 9: Commit**

```bash
git add backend/
git commit -m "feat: add items with search and barcode lookup"
```

---

### Task 7: 跨家庭隔离测试

这是整个系统最重要的安全约束，单独写一组测试。实现已经在前面完成，这些测试预期直接通过；如果有失败，说明有接口漏了家庭校验，要修实现，不能改测试。

**Files:**
- Test: `backend/tests/test_isolation.py`

**Step 1: 写测试**

`backend/tests/test_isolation.py`：

```python
import pytest

from helpers import create_family, create_item, create_location, register


@pytest.fixture
def world(client, new_client):
    """alice 在 A 家庭，bob 在 B 家庭，各自有位置和物品。"""
    alice = register(client, "alice")
    fa = create_family(client, "A家")
    loc_a = create_location(client, fa, "A的客厅")
    item_a = create_item(client, fa, "A的护照", loc_a, barcode="111")
    invite_a = client.post(f"/api/families/{fa}/invites").json()["id"]

    bob = new_client()
    register(bob, "bob")
    fb = create_family(bob, "B家")
    loc_b = create_location(bob, fb, "B的客厅")
    item_b = create_item(bob, fb, "B的钥匙", loc_b)
    return {
        "alice": alice, "bob": bob, "fa": fa, "fb": fb,
        "loc_a": loc_a, "item_a": item_a, "invite_a": invite_a,
        "loc_b": loc_b, "item_b": item_b,
    }


@pytest.mark.parametrize(
    "method,url,body",
    [
        # 直接访问 A 家庭的路径
        ("get", "/api/families/{fa}", None),
        ("get", "/api/families/{fa}/locations", None),
        ("get", "/api/families/{fa}/locations/{loc_a}", None),
        ("patch", "/api/families/{fa}/locations/{loc_a}", {"name": "x"}),
        ("delete", "/api/families/{fa}/locations/{loc_a}", None),
        ("post", "/api/families/{fa}/locations", {"name": "x"}),
        ("get", "/api/families/{fa}/items", None),
        ("get", "/api/families/{fa}/items/{item_a}", None),
        ("patch", "/api/families/{fa}/items/{item_a}", {"name": "x"}),
        ("delete", "/api/families/{fa}/items/{item_a}", None),
        ("get", "/api/families/{fa}/invites", None),
        ("delete", "/api/families/{fa}/invites/{invite_a}", None),
        ("delete", "/api/families/{fa}/members/{alice_id}", None),
        # 借自己家庭 B 的路径，夹带 A 家庭的 ID
        ("get", "/api/families/{fb}/locations/{loc_a}", None),
        ("patch", "/api/families/{fb}/locations/{loc_a}", {"name": "x"}),
        ("delete", "/api/families/{fb}/locations/{loc_a}", None),
        ("get", "/api/families/{fb}/items/{item_a}", None),
        ("patch", "/api/families/{fb}/items/{item_a}", {"name": "x"}),
        ("delete", "/api/families/{fb}/items/{item_a}", None),
        ("delete", "/api/families/{fb}/invites/{invite_a}", None),
        ("delete", "/api/families/{fb}/members/{alice_id}", None),
        # 把 A 家庭的位置当作上级位置或存放位置
        ("post", "/api/families/{fb}/locations", {"name": "x", "parent_id": "{loc_a}"}),
        ("patch", "/api/families/{fb}/locations/{loc_b}", {"parent_id": "{loc_a}"}),
        ("post", "/api/families/{fb}/items", {"name": "x", "location_id": "{loc_a}"}),
        ("patch", "/api/families/{fb}/items/{item_b}", {"location_id": "{loc_a}"}),
        # 二维码入口
        ("get", "/api/locations/{loc_a}", None),
    ],
)
def test_bob_cannot_touch_family_a(world, method, url, body):
    ids = {k: v for k, v in world.items() if isinstance(v, str)}
    ids["alice_id"] = world["alice"]["id"]
    url = url.format(**ids)
    if body:
        body = {k: v.format(**ids) if isinstance(v, str) else v for k, v in body.items()}
    r = getattr(world["bob"], method)(url, **({"json": body} if body else {}))
    assert r.status_code == 404, (method, url, r.text)


def test_search_never_leaks_other_family(world):
    bob, fb = world["bob"], world["fb"]
    assert bob.get(f"/api/families/{fb}/items", params={"q": "护照"}).json() == []
    assert bob.get(f"/api/families/{fb}/items", params={"barcode": "111"}).json() == []
    assert [l["name"] for l in bob.get(f"/api/families/{fb}/locations").json()] == ["B的客厅"]


def test_family_a_data_unchanged(world, client):
    fa = world["fa"]
    assert client.get(f"/api/families/{fa}/items/{world['item_a']}").json()["name"] == "A的护照"
    assert client.get(f"/api/families/{fa}/locations/{world['loc_a']}").json()["name"] == "A的客厅"
```

注意：`client` 夹具和 `world` 里 alice 用的是同一个客户端实例（pytest 夹具在同一个测试里只创建一次）。

**Step 2: 运行测试**

Run: `.venv/bin/pytest backend/tests/test_isolation.py -q`
Expected: 全部通过（28 passed）。如果有失败，修对应接口的家庭校验，然后重跑。

**Step 3: Commit**

```bash
git add backend/tests/test_isolation.py
git commit -m "test: cover cross-family isolation for every endpoint"
```

---

### Task 8: Alembic 数据库迁移

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/<自动生成>_initial_schema.py`
- Test: `backend/tests/test_migrations.py`

**Step 1: 写失败的测试**

`backend/tests/test_migrations.py`：

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app import models  # noqa: F401
from app.db import Base

INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def test_migrations_create_every_table_and_column(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config(str(INI)), "head")

    inspector = inspect(create_engine(url))
    for table in Base.metadata.sorted_tables:
        assert table.name in inspector.get_table_names(), table.name
        columns = {c["name"] for c in inspector.get_columns(table.name)}
        assert columns == {c.name for c in table.columns}, table.name
```

Run: `.venv/bin/pytest backend/tests/test_migrations.py -q`
Expected: FAIL（找不到 `alembic.ini`）。

**Step 2: 写 Alembic 配置**

`backend/alembic.ini`：

```ini
[alembic]
script_location = %(here)s/alembic
prepend_sys_path = %(here)s
```

`backend/alembic/env.py`：

```python
from alembic import context

from app import models  # noqa: F401  注册所有模型
from app.config import get_settings
from app.db import Base, make_engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite 修改表结构需要 batch 模式
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`backend/alembic/script.py.mako`：

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

**Step 3: 自动生成初始迁移**

```bash
mkdir -p backend/alembic/versions && rm -f dev.db && .venv/bin/alembic -c backend/alembic.ini revision --autogenerate -m "initial schema"
```

Expected: 输出里有 `Detected added table 'users'`、`'families'`、`'memberships'`、`'invites'`、`'locations'`、`'items'`，以及两个索引，并生成 `backend/alembic/versions/xxxx_initial_schema.py`。打开这个文件确认：
- 有 6 个 `op.create_table`；
- `id` 等列的类型是 `sa.Uuid()`；
- 有 `ix_locations_family_parent` 和 `ix_items_family_barcode` 两个索引。

**Step 4: 运行测试，并在本地数据库上执行迁移**

Run: `.venv/bin/pytest -q`
Expected: 全部通过。

```bash
.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Expected: 输出 `Running upgrade  -> xxxx, initial schema`，根目录生成 `dev.db`（已被 `.gitignore` 忽略）。

**Step 5: Commit**

```bash
git add backend/alembic.ini backend/alembic backend/tests/test_migrations.py
git commit -m "feat: add alembic migrations"
```

---

### Task 9: Vercel 入口和配置

**Files:**
- Create: `api/index.py`, `vercel.json`, `.claude/launch.json`
- Test: `backend/tests/test_vercel_entry.py`

**Step 1: 写失败的测试**

`backend/tests/test_vercel_entry.py`：

```python
import importlib.util
import json
from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]


def test_vercel_entry_exposes_fastapi_app():
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.app, FastAPI)


def test_vercel_config_routes_api_and_spa():
    config = json.loads((ROOT / "vercel.json").read_text())
    rewrites = config["rewrites"]
    assert rewrites[0] == {"source": "/api/(.*)", "destination": "/api/index"}
    assert rewrites[-1] == {"source": "/(.*)", "destination": "/index.html"}
    assert config["outputDirectory"] == "frontend/dist"
```

Run: `.venv/bin/pytest backend/tests/test_vercel_entry.py -q`
Expected: FAIL（文件不存在）。

**Step 2: 写入口和配置**

`api/index.py`：

```python
"""Vercel Python 函数入口：所有 /api/* 请求都会被改写到这里。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
```

`vercel.json`：

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "installCommand": "cd frontend && npm ci",
  "buildCommand": "cd frontend && npm run build",
  "outputDirectory": "frontend/dist",
  "functions": {
    "api/index.py": { "includeFiles": "backend/app/**" }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/index" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

`.claude/launch.json`（本地预览用）：

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "backend",
      "runtimeExecutable": ".venv/bin/uvicorn",
      "runtimeArgs": ["app.main:app", "--app-dir", "backend", "--port", "8000", "--reload"],
      "port": 8000
    },
    {
      "name": "frontend",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "frontend", "run", "dev", "--", "--port", "5173", "--strictPort"],
      "port": 5173
    }
  ]
}
```

**Step 3: 运行测试，确认通过**

Run: `.venv/bin/pytest -q`
Expected: 全部通过。

**Step 4: Commit**

```bash
git add api/ vercel.json .claude/launch.json backend/tests/test_vercel_entry.py
git commit -m "feat: add Vercel entry point and config"
```

---

### Task 10: 前端骨架（Vite + Vue + Vant + 路由 + 会话）

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/env.d.ts`, `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/style.css`
- Create: `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/session.ts`, `frontend/src/ui.ts`, `frontend/src/router.ts`
- Create: 占位页面 `frontend/src/views/*.vue`（后面的任务逐个替换）

**Step 1: 写工程配置**

`frontend/package.json`：

```json
{
  "name": "home-inventory-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "typecheck": "vue-tsc --noEmit",
    "preview": "vite preview"
  },
  "dependencies": {
    "qrcode": "^1.5.4",
    "vant": "^4.9.0",
    "vue": "^3.5.0",
    "vue-qrcode-reader": "^5.5.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@types/qrcode": "^1.5.5",
    "@vitejs/plugin-vue": "^5.2.0",
    "typescript": "~5.6.0",
    "vite": "^6.0.0",
    "vue-tsc": "^2.2.0"
  }
}
```

`frontend/tsconfig.json`：

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "types": ["vite/client"],
    "strict": true,
    "jsx": "preserve",
    "noEmit": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "useDefineForClassFields": true,
    "skipLibCheck": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "vite.config.ts"]
}
```

`frontend/vite.config.ts`：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
```

`frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <meta name="theme-color" content="#1989fa" />
    <title>家庭物品管理</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

**Step 2: 安装依赖**

```bash
npm --prefix frontend install
```

Expected: 生成 `frontend/package-lock.json`，没有 `ERR!`。

**Step 3: 写公共模块**

`frontend/src/env.d.ts`：

```ts
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
```

`frontend/src/types.ts`：

```ts
export interface User { id: string; username: string }
export interface Family { id: string; name: string }
export interface Member { id: string; username: string; joined_at: string }
export interface FamilyDetail extends Family { members: Member[] }
export interface Invite { id: string; code: string; expires_at: string }
export interface InvitePreview { family_id: string; family_name: string; already_member: boolean }
export interface PathNode { id: string; name: string }

export interface Location {
  id: string
  name: string
  note: string
  parent_id: string | null
  path: PathNode[]
  updated_at: string
  updated_by_name: string | null
}

export interface Item {
  id: string
  name: string
  barcode: string | null
  note: string
  location_id: string
  path: PathNode[]
  updated_at: string
  updated_by_name: string | null
}

export interface LocationDetail extends Location {
  children: Location[]
  items: Item[]
}
```

`frontend/src/api.ts`：

```ts
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

let unauthorizedHandler: (() => void) | null = null

/** 业务接口返回 401（登录失效）时调用；/auth/* 自己处理，不触发。 */
export function onUnauthorized(handler: () => void) {
  unauthorizedHandler = handler
}

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
  })
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/')) unauthorizedHandler?.()
    let message = '请求失败，请稍后再试'
    const detail = data?.detail
    if (typeof detail === 'string') message = detail
    else if (Array.isArray(detail) && detail[0]?.msg) message = `输入有误：${detail[0].msg}`
    throw new ApiError(res.status, message)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: (path: string) => request<void>('DELETE', path),
}
```

`frontend/src/session.ts`：

```ts
import { reactive } from 'vue'
import { api, ApiError } from './api'
import type { Family, User } from './types'

const KEY = 'currentFamilyId'

function readSaved(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

function save(id: string | null) {
  try {
    if (id) localStorage.setItem(KEY, id)
    else localStorage.removeItem(KEY)
  } catch {
    /* 隐私模式等情况下 localStorage 不可用，忽略 */
  }
}

export const session = reactive({
  loaded: false,
  user: null as User | null,
  families: [] as Family[],
  currentFamilyId: null as string | null,
})

export function currentFamily(): Family | null {
  return session.families.find((f) => f.id === session.currentFamilyId) ?? null
}

export function setCurrentFamily(id: string) {
  session.currentFamilyId = id
  save(id)
}

export async function refreshFamilies() {
  session.families = await api.get<Family[]>('/families')
  const preferred = session.currentFamilyId ?? readSaved()
  const pick = session.families.find((f) => f.id === preferred) ?? session.families[0] ?? null
  session.currentFamilyId = pick?.id ?? null
  save(session.currentFamilyId)
}

export function clearSession() {
  session.user = null
  session.families = []
  session.currentFamilyId = null
}

export async function loadSession() {
  try {
    session.user = await api.get<User>('/auth/me')
    await refreshFamilies()
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401)) throw e
    clearSession()
  }
  session.loaded = true
}
```

`frontend/src/ui.ts`：

```ts
import { showFailToast } from 'vant'
import type { Router } from 'vue-router'
import { ApiError } from './api'

export function toastError(e: unknown) {
  showFailToast(e instanceof ApiError ? e.message : '网络错误，请重试')
}

export function pathText(path: { name: string }[]): string {
  return path.map((p) => p.name).join(' › ')
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

/** 只接受站内路径，防止 ?redirect= 被拿来跳到外站 */
export function safeRedirect(value: unknown): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/'
}

/** 有站内历史就返回上一页，否则去 fallback（例如扫码直接打开的页面） */
export function goBack(router: Router, fallback: string) {
  if (window.history.state?.back) router.back()
  else router.replace(fallback)
}
```

`frontend/src/router.ts`：

```ts
import { createRouter, createWebHistory } from 'vue-router'
import { loadSession, session } from './session'
import { safeRedirect } from './ui'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean // 不需要登录
    noFamily?: boolean // 没有家庭也能访问
    tab?: boolean // 显示底部标签栏
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
    { path: '/register', component: () => import('./views/RegisterView.vue'), meta: { public: true } },
    { path: '/onboarding', component: () => import('./views/OnboardingView.vue'), meta: { noFamily: true } },
    { path: '/join/:code', component: () => import('./views/JoinView.vue'), meta: { noFamily: true } },
    { path: '/', component: () => import('./views/SearchView.vue'), meta: { tab: true } },
    { path: '/scan', component: () => import('./views/ScanView.vue') },
    { path: '/locations', component: () => import('./views/LocationsView.vue'), meta: { tab: true } },
    { path: '/locations/new', component: () => import('./views/LocationEditView.vue') },
    { path: '/l/:id', component: () => import('./views/LocationView.vue') },
    { path: '/l/:id/edit', component: () => import('./views/LocationEditView.vue') },
    { path: '/items/new', component: () => import('./views/ItemEditView.vue') },
    { path: '/items/:id', component: () => import('./views/ItemView.vue') },
    { path: '/items/:id/edit', component: () => import('./views/ItemEditView.vue') },
    { path: '/family', component: () => import('./views/FamilyView.vue'), meta: { tab: true } },
    { path: '/print', component: () => import('./views/PrintView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (!session.loaded) await loadSession()
  if (to.meta.public) return session.user ? safeRedirect(to.query.redirect) : true
  if (!session.user) return { path: '/login', query: { redirect: to.fullPath } }
  if (!to.meta.noFamily && session.families.length === 0) return '/onboarding'
  return true
})

export default router
```

`frontend/src/App.vue`：

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const showTabbar = computed(() => route.meta.tab === true)
const active = computed(() =>
  route.path.startsWith('/locations') ? 1 : route.path.startsWith('/family') ? 2 : 0,
)
</script>

<template>
  <router-view />
  <van-tabbar v-if="showTabbar" :model-value="active" placeholder safe-area-inset-bottom>
    <van-tabbar-item to="/" icon="search">找东西</van-tabbar-item>
    <van-tabbar-item to="/locations" icon="location-o">位置</van-tabbar-item>
    <van-tabbar-item to="/family" icon="friends-o">家庭与我</van-tabbar-item>
  </van-tabbar>
</template>
```

`frontend/src/style.css`：

```css
body {
  margin: 0;
  background: #f7f8fa;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
}

.hint {
  color: #969799;
  font-size: 13px;
  padding: 8px 16px;
  margin: 0;
}

.center {
  text-align: center;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px;
}

.block-button {
  margin: 16px;
}

@media print {
  body {
    background: #fff;
  }
}
```

`frontend/src/main.ts`：

```ts
import { createApp } from 'vue'
import Vant from 'vant'
import 'vant/lib/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { onUnauthorized } from './api'
import { clearSession } from './session'

onUnauthorized(() => {
  clearSession()
  router.replace({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
})

createApp(App).use(Vant).use(router).mount('#app')
```

**Step 4: 先放占位页面，让构建能通过**

对下面每个文件，先写入相同的占位内容（后面的任务会逐个替换）：
`LoginView.vue`、`RegisterView.vue`、`OnboardingView.vue`、`JoinView.vue`、`SearchView.vue`、`ScanView.vue`、`LocationsView.vue`、`LocationView.vue`、`LocationEditView.vue`、`ItemView.vue`、`ItemEditView.vue`、`FamilyView.vue`、`PrintView.vue`，都放在 `frontend/src/views/` 下：

```vue
<template>
  <van-empty description="开发中" />
</template>
```

**Step 5: 类型检查和构建**

Run: `npm --prefix frontend run build`
Expected: 成功，输出 `✓ built in ...`，生成 `frontend/dist/index.html`。

**Step 6: Commit**

```bash
git add frontend
git commit -m "feat: scaffold Vue frontend with router and session"
```

---

### Task 11: 登录、注册、引导、加入家庭

**Files:**
- Modify: `frontend/src/views/LoginView.vue`, `RegisterView.vue`, `OnboardingView.vue`, `JoinView.vue`

**Step 1: 登录页**

`frontend/src/views/LoginView.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { loadSession } from '../session'
import { safeRedirect, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    await api.post('/auth/login', { username: username.value, password: password.value })
    await loadSession()
    router.replace(safeRedirect(route.query.redirect))
  } catch (e) {
    toastError(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <van-nav-bar title="登录" />
  <van-form @submit="submit">
    <van-cell-group inset style="margin-top: 16px">
      <van-field
        v-model="username"
        label="用户名"
        placeholder="用户名"
        autocomplete="username"
        :rules="[{ required: true, message: '请输入用户名' }]"
      />
      <van-field
        v-model="password"
        type="password"
        label="密码"
        placeholder="密码"
        autocomplete="current-password"
        :rules="[{ required: true, message: '请输入密码' }]"
      />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="loading">登录</van-button>
    </div>
  </van-form>
  <p class="hint center">
    还没有账号？<router-link :to="{ path: '/register', query: route.query }">注册</router-link>
  </p>
</template>
```

**Step 2: 注册页**

`frontend/src/views/RegisterView.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { loadSession } from '../session'
import { safeRedirect, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)

const usernameRule = {
  validator: (v: string) => /^[\p{L}\p{N}_]{3,50}$/u.test(v.trim()),
  message: '3-50 个字符，只能用中文、字母、数字或下划线',
}

async function submit() {
  loading.value = true
  try {
    await api.post('/auth/register', { username: username.value.trim(), password: password.value })
    await loadSession()
    router.replace(safeRedirect(route.query.redirect))
  } catch (e) {
    toastError(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <van-nav-bar title="注册" />
  <van-form @submit="submit">
    <van-cell-group inset style="margin-top: 16px">
      <van-field
        v-model="username"
        label="用户名"
        placeholder="3-50 个字符"
        autocomplete="username"
        :rules="[{ required: true, message: '请输入用户名' }, usernameRule]"
      />
      <van-field
        v-model="password"
        type="password"
        label="密码"
        placeholder="至少 8 位"
        autocomplete="new-password"
        :rules="[{ validator: (v: string) => v.length >= 8, message: '密码至少 8 位' }]"
      />
      <van-field
        v-model="confirm"
        type="password"
        label="确认密码"
        placeholder="再输入一次"
        autocomplete="new-password"
        :rules="[{ validator: (v: string) => v === password, message: '两次输入的密码不一致' }]"
      />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="loading">注册</van-button>
    </div>
  </van-form>
  <p class="hint center">
    已有账号？<router-link :to="{ path: '/login', query: route.query }">登录</router-link>
  </p>
</template>
```

**Step 3: 引导页（创建或加入家庭）**

`frontend/src/views/OnboardingView.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { api } from '../api'
import { clearSession, refreshFamilies, session, setCurrentFamily } from '../session'
import type { Family } from '../types'
import { toastError } from '../ui'

const router = useRouter()
const familyName = ref('')
const inviteInput = ref('')
const creating = ref(false)

async function create() {
  creating.value = true
  try {
    const family = await api.post<Family>('/families', { name: familyName.value })
    await refreshFamilies()
    setCurrentFamily(family.id)
    router.replace('/')
  } catch (e) {
    toastError(e)
  } finally {
    creating.value = false
  }
}

function join() {
  // 支持粘贴完整链接 https://xxx/join/<code>，也支持只填邀请码
  const match = inviteInput.value.trim().match(/([A-Za-z0-9_-]{8,})\/?$/)
  if (!match) {
    showFailToast('请粘贴邀请链接或邀请码')
    return
  }
  router.push(`/join/${match[1]}`)
}

async function logout() {
  await api.post('/auth/logout')
  clearSession()
  router.replace('/login')
}
</script>

<template>
  <van-nav-bar
    title="开始使用"
    :left-arrow="session.families.length > 0"
    @click-left="router.back()"
  />
  <p class="hint">你好，{{ session.user?.username }}。先创建一个家庭，或者加入家人的家庭。</p>

  <van-form @submit="create">
    <van-cell-group inset title="创建新家庭">
      <van-field
        v-model="familyName"
        label="家庭名称"
        placeholder="例如：我家"
        :rules="[{ required: true, message: '请输入家庭名称' }]"
      />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="creating">创建</van-button>
    </div>
  </van-form>

  <van-cell-group inset title="加入家人的家庭">
    <van-field v-model="inviteInput" label="邀请" placeholder="粘贴邀请链接或邀请码" />
  </van-cell-group>
  <div class="block-button">
    <van-button round block @click="join">加入</van-button>
  </div>

  <p class="hint center"><a href="#" @click.prevent="logout">退出登录</a></p>
</template>
```

**Step 4: 加入家庭页**

`frontend/src/views/JoinView.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { refreshFamilies, setCurrentFamily } from '../session'
import type { InvitePreview } from '../types'
import { toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const code = String(route.params.code)
const preview = ref<InvitePreview | null>(null)
const invalid = ref(false)
const joining = ref(false)

onMounted(async () => {
  try {
    preview.value = await api.get<InvitePreview>(`/invites/${encodeURIComponent(code)}`)
  } catch {
    invalid.value = true
  }
})

async function accept() {
  joining.value = true
  try {
    const family = await api.post<{ id: string }>(`/invites/${encodeURIComponent(code)}/accept`)
    await refreshFamilies()
    setCurrentFamily(family.id)
    router.replace('/')
  } catch (e) {
    toastError(e)
  } finally {
    joining.value = false
  }
}
</script>

<template>
  <van-nav-bar title="加入家庭" />
  <van-empty v-if="invalid" image="error" description="邀请无效或已过期">
    <van-button round type="primary" @click="router.replace('/')">返回首页</van-button>
  </van-empty>
  <van-empty v-else-if="preview" image="default" :description="`邀请你加入「${preview.family_name}」`">
    <van-button round type="primary" :loading="joining" @click="accept">
      {{ preview.already_member ? '你已经是成员，进入家庭' : '加入' }}
    </van-button>
  </van-empty>
  <van-loading v-else class="center" style="margin-top: 40px" />
</template>
```

**Step 5: 类型检查**

Run: `npm --prefix frontend run typecheck`
Expected: 没有输出，退出码 0。

**Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: add login, register, onboarding and join pages"
```

---

### Task 12: 位置选择器和位置页面

**Files:**
- Create: `frontend/src/components/LocationPicker.vue`
- Modify: `frontend/src/views/LocationsView.vue`, `LocationView.vue`, `LocationEditView.vue`

**Step 1: 位置选择器**

Vant 的级联选择器只能选到最末一级，所以给每个有下级的位置加一个“就放在这里”的选项。

`frontend/src/components/LocationPicker.vue`：

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CascaderOption } from 'vant'
import type { Location } from '../types'
import { pathText } from '../ui'

const props = defineProps<{
  modelValue: string | null
  locations: Location[]
  label: string
  allowRoot?: boolean // 允许选“顶层”（新建/移动位置时用）
  excludeId?: string // 排除某个位置及其所有下级（移动位置时防止形成循环）
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()

const show = ref(false)
const HERE = 'here:'
const ROOT = 'root'

const options = computed<CascaderOption[]>(() => {
  const visible = props.locations.filter(
    (l) => !props.excludeId || !l.path.some((p) => p.id === props.excludeId),
  )
  const byParent = new Map<string | null, Location[]>()
  for (const l of visible) {
    const siblings = byParent.get(l.parent_id) ?? []
    siblings.push(l)
    byParent.set(l.parent_id, siblings)
  }
  const build = (parentId: string | null): CascaderOption[] =>
    (byParent.get(parentId) ?? []).map((l) => {
      const children = build(l.id)
      return children.length
        ? { text: l.name, value: l.id, children: [{ text: `就放在「${l.name}」`, value: HERE + l.id }, ...children] }
        : { text: l.name, value: l.id }
    })
  const tree = build(null)
  return props.allowRoot ? [{ text: '顶层（不放在任何位置里）', value: ROOT }, ...tree] : tree
})

const display = computed(() => {
  if (props.modelValue === null) return props.allowRoot ? '顶层' : ''
  const loc = props.locations.find((l) => l.id === props.modelValue)
  return loc ? pathText(loc.path) : ''
})

function onFinish({ selectedOptions }: { selectedOptions: CascaderOption[] }) {
  const value = String(selectedOptions[selectedOptions.length - 1].value)
  emit('update:modelValue', value === ROOT ? null : value.startsWith(HERE) ? value.slice(HERE.length) : value)
  show.value = false
}
</script>

<template>
  <van-field :model-value="display" :label="label" placeholder="请选择" readonly is-link @click="show = true" />
  <van-popup v-model:show="show" round position="bottom">
    <van-cascader :title="`选择${label}`" :options="options" @close="show = false" @finish="onFinish" />
  </van-popup>
</template>
```

**Step 2: 位置首页（顶层位置列表）**

`frontend/src/views/LocationsView.vue`：

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { session } from '../session'
import type { Location } from '../types'
import { toastError } from '../ui'

const router = useRouter()
const locations = ref<Location[]>([])
const loaded = ref(false)

const roots = computed(() => locations.value.filter((l) => l.parent_id === null))
const childCount = computed(() => {
  const counts = new Map<string, number>()
  for (const l of locations.value) if (l.parent_id) counts.set(l.parent_id, (counts.get(l.parent_id) ?? 0) + 1)
  return counts
})

async function load() {
  if (!session.currentFamilyId) return
  try {
    locations.value = await api.get<Location[]>(`/families/${session.currentFamilyId}/locations`)
  } catch (e) {
    toastError(e)
  } finally {
    loaded.value = true
  }
}
watch(() => session.currentFamilyId, load, { immediate: true })
</script>

<template>
  <van-nav-bar title="位置" right-text="打印标签" @click-right="router.push('/print')" />
  <van-cell-group v-if="roots.length" inset style="margin-top: 12px">
    <van-cell
      v-for="loc in roots"
      :key="loc.id"
      :title="loc.name"
      :value="childCount.get(loc.id) ? `${childCount.get(loc.id)} 个子位置` : ''"
      is-link
      :to="`/l/${loc.id}`"
    />
  </van-cell-group>
  <van-empty v-else-if="loaded" description="还没有位置，先建一个房间吧" />
  <div class="block-button">
    <van-button round block type="primary" icon="plus" @click="router.push('/locations/new')">新建位置</van-button>
  </div>
</template>
```

**Step 3: 位置详情页（二维码打开的页面）**

`frontend/src/views/LocationView.vue`：

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { api, ApiError } from '../api'
import { refreshFamilies, session, setCurrentFamily } from '../session'
import type { LocationDetail } from '../types'
import { goBack, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const detail = ref<LocationDetail | null>(null)
const notFound = ref(false)

async function load() {
  const id = String(route.params.id)
  detail.value = null
  notFound.value = false
  try {
    // 先问这个位置属于哪个家庭：扫别的家庭的二维码时自动切换过去
    const { family_id } = await api.get<{ family_id: string }>(`/locations/${id}`)
    if (!session.families.some((f) => f.id === family_id)) await refreshFamilies()
    if (session.currentFamilyId !== family_id) setCurrentFamily(family_id)
    detail.value = await api.get<LocationDetail>(`/families/${family_id}/locations/${id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound.value = true
    else toastError(e)
  }
}
watch(() => route.params.id, load, { immediate: true })

async function remove() {
  const loc = detail.value
  if (!loc) return
  try {
    await showConfirmDialog({ title: '删除位置', message: `确定删除「${loc.name}」吗？` })
  } catch {
    return
  }
  try {
    await api.del(`/families/${session.currentFamilyId}/locations/${loc.id}`)
    router.replace(loc.parent_id ? `/l/${loc.parent_id}` : '/locations')
  } catch (e) {
    toastError(e)
  }
}
</script>

<template>
  <template v-if="detail">
    <van-nav-bar
      :title="detail.name"
      left-arrow
      right-text="编辑"
      @click-left="goBack(router, detail.parent_id ? `/l/${detail.parent_id}` : '/locations')"
      @click-right="router.push(`/l/${detail.id}/edit`)"
    />
    <p class="hint crumbs">
      <template v-for="(node, i) in detail.path" :key="node.id">
        <span v-if="i > 0"> › </span>
        <router-link v-if="i < detail.path.length - 1" :to="`/l/${node.id}`">{{ node.name }}</router-link>
        <span v-else>{{ node.name }}</span>
      </template>
    </p>
    <p v-if="detail.note" class="hint">{{ detail.note }}</p>

    <van-cell-group inset :title="`子位置（${detail.children.length}）`">
      <van-cell v-for="c in detail.children" :key="c.id" :title="c.name" is-link :to="`/l/${c.id}`" />
      <van-cell v-if="!detail.children.length" title="没有子位置" />
    </van-cell-group>

    <van-cell-group inset :title="`物品（${detail.items.length}）`">
      <van-cell
        v-for="item in detail.items"
        :key="item.id"
        :title="item.name"
        :label="item.note"
        is-link
        :to="`/items/${item.id}`"
      />
      <van-cell v-if="!detail.items.length" title="这里还没有物品" />
    </van-cell-group>

    <div class="actions">
      <van-button size="small" type="primary" icon="plus" @click="router.push({ path: '/items/new', query: { location: detail.id } })">
        放入物品
      </van-button>
      <van-button size="small" icon="cluster-o" @click="router.push({ path: '/locations/new', query: { parent: detail.id } })">
        新建子位置
      </van-button>
      <van-button size="small" icon="qr" @click="router.push({ path: '/print', query: { ids: detail.id } })">
        打印二维码
      </van-button>
      <van-button size="small" type="danger" plain icon="delete-o" @click="remove">删除</van-button>
    </div>
  </template>

  <template v-else-if="notFound">
    <van-nav-bar title="位置" left-arrow @click-left="router.replace('/')" />
    <van-empty image="search" description="找不到这个位置，或者你不是它所在家庭的成员">
      <van-button round type="primary" @click="router.replace('/')">回到首页</van-button>
    </van-empty>
  </template>

  <van-loading v-else class="center" style="margin-top: 40px" />
</template>
```

**Step 4: 新建 / 编辑位置**

`frontend/src/views/LocationEditView.vue`：

```vue
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import LocationPicker from '../components/LocationPicker.vue'
import { session } from '../session'
import type { Location } from '../types'
import { goBack, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const editingId = computed(() => (route.params.id ? String(route.params.id) : undefined))
const fid = session.currentFamilyId!
const locations = ref<Location[]>([])
const form = reactive({ name: '', note: '', parent_id: null as string | null })
const saving = ref(false)

onMounted(async () => {
  try {
    locations.value = await api.get<Location[]>(`/families/${fid}/locations`)
    if (editingId.value) {
      const loc = locations.value.find((l) => l.id === editingId.value)
      if (loc) Object.assign(form, { name: loc.name, note: loc.note, parent_id: loc.parent_id })
    } else if (typeof route.query.parent === 'string') {
      form.parent_id = route.query.parent
    }
  } catch (e) {
    toastError(e)
  }
})

async function save() {
  saving.value = true
  try {
    const body = { name: form.name, note: form.note, parent_id: form.parent_id }
    const loc = editingId.value
      ? await api.patch<Location>(`/families/${fid}/locations/${editingId.value}`, body)
      : await api.post<Location>(`/families/${fid}/locations`, body)
    router.replace(`/l/${loc.id}`)
  } catch (e) {
    toastError(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <van-nav-bar
    :title="editingId ? '编辑位置' : '新建位置'"
    left-arrow
    @click-left="goBack(router, editingId ? `/l/${editingId}` : '/locations')"
  />
  <van-form @submit="save">
    <van-cell-group inset style="margin-top: 12px">
      <van-field
        v-model="form.name"
        label="名称"
        placeholder="例如：主卧、衣柜、蓝色收纳盒"
        maxlength="100"
        :rules="[{ required: true, message: '请输入名称' }]"
      />
      <LocationPicker
        v-model="form.parent_id"
        :locations="locations"
        label="上级位置"
        allow-root
        :exclude-id="editingId"
      />
      <van-field v-model="form.note" label="备注" type="textarea" rows="2" autosize maxlength="1000" />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="saving">保存</van-button>
    </div>
  </van-form>
</template>
```

**Step 5: 类型检查**

Run: `npm --prefix frontend run typecheck`
Expected: 退出码 0。

**Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: add location pages and picker"
```

---

### Task 13: 扫码组件、物品页面、搜索首页

**Files:**
- Create: `frontend/src/components/BarcodeScanner.vue`
- Modify: `frontend/src/views/SearchView.vue`, `ScanView.vue`, `ItemView.vue`, `ItemEditView.vue`

**Step 1: 扫码组件**

`vue-qrcode-reader` 在支持原生 BarcodeDetector 的浏览器上直接用原生能力；不支持时（例如 iPhone Safari）会从 jsDelivr CDN 加载 ZXing 的 wasm 文件。摄像头只有在 HTTPS 或 localhost 下可用。

`frontend/src/components/BarcodeScanner.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { QrcodeStream } from 'vue-qrcode-reader'

type Formats = NonNullable<InstanceType<typeof QrcodeStream>['$props']['formats']>

defineProps<{ paused?: boolean }>()
const emit = defineEmits<{ detected: [text: string] }>()

const formats: Formats = ['qr_code', 'ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39']
const error = ref('')

function onDetect(codes: { rawValue: string }[]) {
  const text = codes[0]?.rawValue?.trim()
  if (text) emit('detected', text)
}

function onError(err: Error) {
  const messages: Record<string, string> = {
    NotAllowedError: '没有摄像头权限，请在浏览器设置里允许访问摄像头',
    NotFoundError: '没有找到摄像头',
    NotReadableError: '摄像头被其他应用占用',
    InsecureContextError: '需要通过 HTTPS 访问才能使用摄像头',
    StreamApiNotSupportedError: '当前浏览器不支持摄像头',
  }
  error.value = messages[err.name] ?? `无法打开摄像头：${err.message}`
}
</script>

<template>
  <div class="scanner">
    <qrcode-stream :formats="formats" :paused="paused" @detect="onDetect" @error="onError" />
  </div>
  <p class="hint center">{{ error || '把条码或二维码放进取景框' }}</p>
</template>

<style scoped>
.scanner {
  width: 100%;
  max-width: 480px;
  aspect-ratio: 1;
  margin: 0 auto;
  background: #000;
  overflow: hidden;
}
</style>
```

如果 `vue-tsc` 对 `Formats` 那一行报错（不同版本的组件类型导出不一样），把这两行改成：
`const formats = ['qr_code', 'ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39'] as never[]`。

**Step 2: 扫码页**

`frontend/src/views/ScanView.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import BarcodeScanner from '../components/BarcodeScanner.vue'
import { session } from '../session'
import type { Item } from '../types'
import { goBack, pathText, toastError } from '../ui'

const router = useRouter()
const busy = ref(false)
const scanned = ref('')
const manual = ref('')
const matches = ref<Item[]>([])

/** 本系统生成的位置二维码：https://<当前域名>/l/<uuid> */
function locationIdFromQr(text: string): string | null {
  try {
    const url = new URL(text)
    if (url.origin !== window.location.origin) return null
    return url.pathname.match(/^\/l\/([0-9a-f-]{36})\/?$/i)?.[1] ?? null
  } catch {
    return null
  }
}

async function handle(text: string) {
  if (busy.value) return
  busy.value = true
  const locationId = locationIdFromQr(text)
  if (locationId) {
    router.replace(`/l/${locationId}`)
    return
  }
  scanned.value = text
  try {
    const items = await api.get<Item[]>(
      `/families/${session.currentFamilyId}/items?barcode=${encodeURIComponent(text)}`,
    )
    if (items.length === 0) router.replace({ path: '/items/new', query: { barcode: text } })
    else if (items.length === 1) router.replace(`/items/${items[0].id}`)
    else matches.value = items
  } catch (e) {
    toastError(e)
    busy.value = false
  }
}

function rescan() {
  matches.value = []
  busy.value = false
}
</script>

<template>
  <van-nav-bar title="扫码" left-arrow @click-left="goBack(router, '/')" />

  <template v-if="matches.length">
    <van-cell-group inset :title="`条码 ${scanned} 对应 ${matches.length} 个物品`" style="margin-top: 12px">
      <van-cell
        v-for="item in matches"
        :key="item.id"
        :title="item.name"
        :label="pathText(item.path)"
        is-link
        :to="`/items/${item.id}`"
      />
    </van-cell-group>
    <div class="actions">
      <van-button size="small" type="primary" @click="router.push({ path: '/items/new', query: { barcode: scanned } })">
        再添加一个
      </van-button>
      <van-button size="small" @click="rescan">重新扫码</van-button>
    </div>
  </template>

  <template v-else>
    <BarcodeScanner :paused="busy" @detected="handle" />
    <van-cell-group inset title="扫不出来？手动输入条码">
      <van-field v-model="manual" placeholder="条码数字" type="text" inputmode="numeric">
        <template #button>
          <van-button size="small" type="primary" :disabled="!manual.trim()" @click="handle(manual.trim())">
            查找
          </van-button>
        </template>
      </van-field>
    </van-cell-group>
  </template>
</template>
```

**Step 3: 物品详情页**

`frontend/src/views/ItemView.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { api, ApiError } from '../api'
import { session } from '../session'
import type { Item } from '../types'
import { formatTime, goBack, pathText, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const fid = session.currentFamilyId!
const item = ref<Item | null>(null)
const notFound = ref(false)

onMounted(async () => {
  try {
    item.value = await api.get<Item>(`/families/${fid}/items/${route.params.id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound.value = true
    else toastError(e)
  }
})

async function remove() {
  if (!item.value) return
  try {
    await showConfirmDialog({ title: '删除物品', message: `确定删除「${item.value.name}」吗？` })
  } catch {
    return
  }
  try {
    await api.del(`/families/${fid}/items/${item.value.id}`)
    router.replace(`/l/${item.value.location_id}`)
  } catch (e) {
    toastError(e)
  }
}
</script>

<template>
  <template v-if="item">
    <van-nav-bar
      title="物品"
      left-arrow
      right-text="编辑"
      @click-left="goBack(router, '/')"
      @click-right="router.push(`/items/${item.id}/edit`)"
    />
    <van-cell-group inset style="margin-top: 12px">
      <van-cell title="名称" :value="item.name" />
      <van-cell title="放在" :label="pathText(item.path)" is-link :to="`/l/${item.location_id}`" />
      <van-cell v-if="item.barcode" title="条码" :value="item.barcode" />
      <van-cell v-if="item.note" title="备注" :label="item.note" />
      <van-cell title="最后修改" :label="`${item.updated_by_name ?? '—'} · ${formatTime(item.updated_at)}`" />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="danger" plain @click="remove">删除物品</van-button>
    </div>
  </template>
  <template v-else-if="notFound">
    <van-nav-bar title="物品" left-arrow @click-left="router.replace('/')" />
    <van-empty image="search" description="找不到这个物品" />
  </template>
  <van-loading v-else class="center" style="margin-top: 40px" />
</template>
```

**Step 4: 新建 / 编辑物品**

`frontend/src/views/ItemEditView.vue`：

```vue
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { api } from '../api'
import BarcodeScanner from '../components/BarcodeScanner.vue'
import LocationPicker from '../components/LocationPicker.vue'
import { session } from '../session'
import type { Item, Location } from '../types'
import { goBack, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const editingId = computed(() => (route.params.id ? String(route.params.id) : undefined))
const fid = session.currentFamilyId!
const locations = ref<Location[]>([])
const loaded = ref(false)
const form = reactive({ name: '', barcode: '', note: '', location_id: null as string | null })
const scanning = ref(false)
const saving = ref(false)

onMounted(async () => {
  try {
    locations.value = await api.get<Location[]>(`/families/${fid}/locations`)
    if (editingId.value) {
      const item = await api.get<Item>(`/families/${fid}/items/${editingId.value}`)
      Object.assign(form, {
        name: item.name,
        barcode: item.barcode ?? '',
        note: item.note,
        location_id: item.location_id,
      })
    } else {
      if (typeof route.query.barcode === 'string') form.barcode = route.query.barcode
      if (typeof route.query.location === 'string') form.location_id = route.query.location
    }
  } catch (e) {
    toastError(e)
  } finally {
    loaded.value = true
  }
})

function onScanned(text: string) {
  form.barcode = text
  scanning.value = false
}

async function save() {
  if (!form.location_id) {
    showFailToast('请选择存放位置')
    return
  }
  saving.value = true
  try {
    const body = {
      name: form.name,
      barcode: form.barcode.trim() || null,
      note: form.note,
      location_id: form.location_id,
    }
    const item = editingId.value
      ? await api.patch<Item>(`/families/${fid}/items/${editingId.value}`, body)
      : await api.post<Item>(`/families/${fid}/items`, body)
    router.replace(`/items/${item.id}`)
  } catch (e) {
    toastError(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <van-nav-bar
    :title="editingId ? '编辑物品' : '添加物品'"
    left-arrow
    @click-left="goBack(router, editingId ? `/items/${editingId}` : '/')"
  />

  <van-empty v-if="loaded && !locations.length" description="还没有任何位置，先建一个位置才能放物品">
    <van-button round type="primary" @click="router.push('/locations/new')">新建位置</van-button>
  </van-empty>

  <van-form v-else @submit="save">
    <van-cell-group inset style="margin-top: 12px">
      <van-field
        v-model="form.name"
        label="名称"
        placeholder="例如：护照、螺丝刀"
        maxlength="200"
        :rules="[{ required: true, message: '请输入名称' }]"
      />
      <LocationPicker v-model="form.location_id" :locations="locations" label="存放位置" />
      <van-field v-model="form.barcode" label="条码" placeholder="可选" maxlength="64">
        <template #right-icon>
          <van-icon name="scan" size="20" @click="scanning = true" />
        </template>
      </van-field>
      <van-field v-model="form.note" label="备注" type="textarea" rows="2" autosize maxlength="1000" />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="saving">保存</van-button>
    </div>
  </van-form>

  <van-popup v-model:show="scanning" position="bottom" round destroy-on-close>
    <van-nav-bar title="扫描条码" right-text="关闭" @click-right="scanning = false" />
    <BarcodeScanner v-if="scanning" @detected="onScanned" />
  </van-popup>
</template>
```

**Step 5: 搜索首页**

`frontend/src/views/SearchView.vue`：

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { currentFamily, session } from '../session'
import type { Item } from '../types'
import { pathText, toastError } from '../ui'

const router = useRouter()
const q = ref('')
const items = ref<Item[]>([])
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function search() {
  const fid = session.currentFamilyId
  if (!fid) return
  loading.value = true
  try {
    const query = q.value.trim()
    items.value = await api.get<Item[]>(
      `/families/${fid}/items${query ? `?q=${encodeURIComponent(query)}` : ''}`,
    )
  } catch (e) {
    toastError(e)
  } finally {
    loading.value = false
  }
}

watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(search, 300)
})
watch(() => session.currentFamilyId, search, { immediate: true })
</script>

<template>
  <van-nav-bar :title="currentFamily()?.name ?? '找东西'">
    <template #right>
      <van-icon name="scan" size="22" @click="router.push('/scan')" />
      <van-icon name="plus" size="22" style="margin-left: 16px" @click="router.push('/items/new')" />
    </template>
  </van-nav-bar>
  <van-search v-model="q" placeholder="搜索物品名称、条码或备注" />
  <van-cell-group v-if="items.length" :title="q.trim() ? '搜索结果' : '最近更新'" inset>
    <van-cell
      v-for="item in items"
      :key="item.id"
      :title="item.name"
      :label="pathText(item.path)"
      is-link
      :to="`/items/${item.id}`"
    />
  </van-cell-group>
  <van-empty v-else-if="!loading" :description="q.trim() ? '没有找到' : '还没有物品，点右上角 + 添加'" />
</template>
```

**Step 6: 类型检查**

Run: `npm --prefix frontend run typecheck`
Expected: 退出码 0。如果 `BarcodeScanner.vue` 的 `Formats` 报错，按 Step 1 末尾的说明改，然后重跑。

**Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat: add search, scanning and item pages"
```

---

### Task 14: 家庭与我

**Files:**
- Modify: `frontend/src/views/FamilyView.vue`

**Step 1: 写页面**

`frontend/src/views/FamilyView.vue`：

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import { api } from '../api'
import { clearSession, currentFamily, refreshFamilies, session, setCurrentFamily } from '../session'
import type { FamilyDetail, Invite } from '../types'
import { formatTime, toastError } from '../ui'

const router = useRouter()
const detail = ref<FamilyDetail | null>(null)
const invites = ref<Invite[]>([])
const switchShow = ref(false)
const renameShow = ref(false)
const renameValue = ref('')
const dissolveShow = ref(false)
const dissolveValue = ref('')
const passwordShow = ref(false)
const oldPassword = ref('')
const newPassword = ref('')

const fid = () => session.currentFamilyId!
const switchActions = computed(() =>
  session.families.map((f) => ({
    name: f.name,
    id: f.id,
    color: f.id === session.currentFamilyId ? '#1989fa' : undefined,
  })),
)

async function load() {
  if (!session.currentFamilyId) return
  try {
    const [d, i] = await Promise.all([
      api.get<FamilyDetail>(`/families/${fid()}`),
      api.get<Invite[]>(`/families/${fid()}/invites`),
    ])
    detail.value = d
    invites.value = i
  } catch (e) {
    toastError(e)
  }
}
watch(() => session.currentFamilyId, load, { immediate: true })

function inviteLink(code: string) {
  return `${window.location.origin}/join/${code}`
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    showSuccessToast('已复制')
  } catch {
    showFailToast('复制失败，请长按手动复制')
  }
}

async function createInvite() {
  try {
    const invite = await api.post<Invite>(`/families/${fid()}/invites`)
    await load()
    await copy(inviteLink(invite.code))
  } catch (e) {
    toastError(e)
  }
}

async function revokeInvite(id: string) {
  try {
    await api.del(`/families/${fid()}/invites/${id}`)
    await load()
  } catch (e) {
    toastError(e)
  }
}

async function afterLeaving() {
  session.currentFamilyId = null
  await refreshFamilies()
  router.replace(session.families.length ? '/' : '/onboarding')
}

async function removeMember(id: string, username: string) {
  const isSelf = id === session.user?.id
  try {
    await showConfirmDialog({
      title: isSelf ? '退出家庭' : '移除成员',
      message: isSelf
        ? `确定退出「${detail.value?.name}」吗？如果你是最后一个成员，家庭里的所有数据都会被删除。`
        : `确定把 ${username} 移出这个家庭吗？`,
    })
  } catch {
    return
  }
  try {
    await api.del(`/families/${fid()}/members/${id}`)
    if (isSelf) await afterLeaving()
    else await load()
  } catch (e) {
    toastError(e)
  }
}

async function rename() {
  const name = renameValue.value.trim()
  if (!name) {
    showFailToast('请输入家庭名称')
    return
  }
  try {
    await api.patch(`/families/${fid()}`, { name })
    await refreshFamilies()
    await load()
  } catch (e) {
    toastError(e)
  }
}

async function dissolve() {
  if (dissolveValue.value.trim() !== detail.value?.name) {
    showFailToast('家庭名称不一致，没有解散')
    return
  }
  try {
    await api.del(`/families/${fid()}`)
    await afterLeaving()
  } catch (e) {
    toastError(e)
  }
}

async function changePassword() {
  if (newPassword.value.length < 8) {
    showFailToast('新密码至少 8 位')
    return
  }
  try {
    await api.post('/auth/password', { old_password: oldPassword.value, new_password: newPassword.value })
    showSuccessToast('密码已修改')
    oldPassword.value = ''
    newPassword.value = ''
  } catch (e) {
    toastError(e)
  }
}

async function logout() {
  await api.post('/auth/logout')
  clearSession()
  router.replace('/login')
}
</script>

<template>
  <van-nav-bar title="家庭与我" />

  <van-cell-group inset title="当前家庭" style="margin-top: 4px">
    <van-cell
      :title="currentFamily()?.name"
      :value="session.families.length > 1 ? '切换' : ''"
      :is-link="session.families.length > 1"
      @click="session.families.length > 1 && (switchShow = true)"
    />
    <van-cell title="修改家庭名称" is-link @click="(renameValue = detail?.name ?? ''), (renameShow = true)" />
    <van-cell title="创建或加入其他家庭" is-link to="/onboarding" />
  </van-cell-group>

  <van-cell-group v-if="detail" inset :title="`成员（${detail.members.length}）`">
    <van-cell v-for="m in detail.members" :key="m.id" :title="m.username" :label="`加入于 ${formatTime(m.joined_at)}`">
      <template #right-icon>
        <van-button size="mini" :type="m.id === session.user?.id ? 'warning' : 'default'" @click="removeMember(m.id, m.username)">
          {{ m.id === session.user?.id ? '退出' : '移除' }}
        </van-button>
      </template>
    </van-cell>
  </van-cell-group>

  <van-cell-group inset title="邀请家人（链接 7 天内有效）">
    <van-cell v-for="inv in invites" :key="inv.id" :title="inviteLink(inv.code)" :label="`有效期至 ${formatTime(inv.expires_at)}`">
      <template #right-icon>
        <van-button size="mini" style="margin-right: 6px" @click="copy(inviteLink(inv.code))">复制</van-button>
        <van-button size="mini" type="danger" plain @click="revokeInvite(inv.id)">作废</van-button>
      </template>
    </van-cell>
    <van-cell title="生成新的邀请链接" icon="plus" is-link @click="createInvite" />
  </van-cell-group>

  <van-cell-group inset :title="`我（${session.user?.username}）`">
    <van-cell title="修改密码" is-link @click="passwordShow = true" />
    <van-cell title="退出登录" is-link @click="logout" />
  </van-cell-group>

  <div class="block-button">
    <van-button round block type="danger" plain @click="(dissolveValue = ''), (dissolveShow = true)">解散家庭</van-button>
  </div>

  <van-action-sheet
    v-model:show="switchShow"
    title="切换家庭"
    :actions="switchActions"
    cancel-text="取消"
    close-on-click-action
    @select="(a: { id: string }) => setCurrentFamily(a.id)"
  />

  <van-dialog v-model:show="renameShow" title="修改家庭名称" show-cancel-button @confirm="rename">
    <van-field v-model="renameValue" placeholder="家庭名称" maxlength="100" />
  </van-dialog>

  <van-dialog v-model:show="dissolveShow" title="解散家庭" show-cancel-button confirm-button-color="#ee0a24" @confirm="dissolve">
    <p class="hint">解散后，这个家庭的所有位置和物品都会被永久删除，所有成员都会被移出。请输入家庭名称「{{ detail?.name }}」确认：</p>
    <van-field v-model="dissolveValue" placeholder="家庭名称" />
  </van-dialog>

  <van-dialog v-model:show="passwordShow" title="修改密码" show-cancel-button @confirm="changePassword">
    <van-field v-model="oldPassword" type="password" label="原密码" autocomplete="current-password" />
    <van-field v-model="newPassword" type="password" label="新密码" placeholder="至少 8 位" autocomplete="new-password" />
  </van-dialog>
</template>
```

**Step 2: 类型检查**

Run: `npm --prefix frontend run typecheck`
Expected: 退出码 0。

**Step 3: Commit**

```bash
git add frontend/src
git commit -m "feat: add family and account page"
```

---

### Task 15: 打印二维码标签

**Files:**
- Modify: `frontend/src/views/PrintView.vue`

**Step 1: 写页面**

`frontend/src/views/PrintView.vue`：

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toDataURL } from 'qrcode'
import { api } from '../api'
import { session } from '../session'
import type { Location } from '../types'
import { goBack, pathText, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const all = ref<Location[]>([])
const selected = ref<string[]>([])
const qr = ref<Record<string, string>>({})

onMounted(async () => {
  try {
    all.value = await api.get<Location[]>(`/families/${session.currentFamilyId}/locations`)
    const ids = String(route.query.ids ?? '').split(',').filter(Boolean)
    selected.value = ids.filter((id) => all.value.some((l) => l.id === id))
  } catch (e) {
    toastError(e)
  }
})

const labels = computed(() => all.value.filter((l) => selected.value.includes(l.id)))

watch(labels, async (list) => {
  const entries = await Promise.all(
    list.map(async (l): Promise<[string, string]> => [
      l.id,
      qr.value[l.id] ??
        (await toDataURL(`${window.location.origin}/l/${l.id}`, { margin: 1, width: 300, errorCorrectionLevel: 'M' })),
    ]),
  )
  qr.value = Object.fromEntries(entries)
})

function toggleAll() {
  selected.value = selected.value.length === all.value.length ? [] : all.value.map((l) => l.id)
}

function print() {
  window.print()
}
</script>

<template>
  <div class="no-print">
    <van-nav-bar title="打印二维码标签" left-arrow @click-left="goBack(router, '/locations')" />
    <p class="hint">勾选要打印的位置。打印后贴在收纳箱上，用手机相机扫一下就能看到里面放了什么。</p>
    <van-checkbox-group v-model="selected">
      <van-cell-group inset>
        <van-cell v-for="l in all" :key="l.id" :title="pathText(l.path)">
          <template #right-icon>
            <van-checkbox :name="l.id" />
          </template>
        </van-cell>
      </van-cell-group>
    </van-checkbox-group>
    <div class="actions">
      <van-button size="small" @click="toggleAll">
        {{ selected.length === all.length && all.length ? '全不选' : '全选' }}
      </van-button>
      <van-button size="small" type="primary" icon="printer" :disabled="!labels.length" @click="print">
        打印 {{ labels.length }} 张
      </van-button>
    </div>
  </div>

  <div class="labels">
    <div v-for="l in labels" :key="l.id" class="label">
      <img v-if="qr[l.id]" :src="qr[l.id]" :alt="l.name" />
      <div class="label-name">{{ l.name }}</div>
      <div class="label-path">{{ pathText(l.path) }}</div>
    </div>
  </div>
</template>

<style scoped>
.labels {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  padding: 16px;
}
.label {
  background: #fff;
  border: 1px dashed #c8c9cc;
  border-radius: 6px;
  padding: 8px;
  text-align: center;
  break-inside: avoid;
}
.label img {
  width: 100%;
  max-width: 160px;
}
.label-name {
  font-size: 15px;
  font-weight: 600;
}
.label-path {
  color: #646566;
  font-size: 11px;
  word-break: break-all;
}
@media print {
  .no-print {
    display: none !important;
  }
  .labels {
    grid-template-columns: repeat(3, 1fr);
    gap: 4mm;
    padding: 0;
  }
  .label {
    border-color: #999;
  }
}
</style>
```

**Step 2: 构建**

Run: `npm --prefix frontend run build`
Expected: 成功，`✓ built in ...`。

**Step 3: Commit**

```bash
git add frontend/src
git commit -m "feat: add printable QR labels"
```

---

### Task 16: README 和端到端验证

**Files:**
- Create: `README.md`, `.env.example`

**Step 1: 写 `.env.example`**

```
# 本地默认用 SQLite，不需要设置。线上由 Vercel 的 Neon 集成自动注入。
DATABASE_URL=sqlite:///./dev.db
# 线上必须设置：python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=
# 本地默认 false；在 Vercel 上默认 true
COOKIE_SECURE=false
```

**Step 2: 写 `README.md`**

````markdown
# 家庭物品管理

记录家里每样东西放在哪。支持多个家庭、多层级位置（房间 › 柜子 › 收纳盒）、扫物品条码录入、给收纳箱打印二维码。

- 后端：FastAPI + SQLAlchemy（`backend/`），Vercel 入口是 `api/index.py`
- 前端：Vue 3 + Vite + Vant（`frontend/`）
- 设计文档：`docs/plans/2026-11-12-home-inventory-design.md`

## 本地开发

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/alembic -c backend/alembic.ini upgrade head
npm --prefix frontend install
```

开两个终端：

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

```bash
npm --prefix frontend run dev
```

打开 http://localhost:5173 。摄像头扫码只在 localhost 或 HTTPS 下可用。

## 测试

```bash
.venv/bin/pytest -q
npm --prefix frontend run build
```

## 部署到 Vercel

1. 把仓库推到 GitHub，在 Vercel 里 Import 这个仓库（Framework Preset 选 Other，其余用 `vercel.json` 里的配置）。
2. 在 Vercel 项目的 Storage / Marketplace 里添加 **Neon** 数据库并连接到项目，它会自动注入 `DATABASE_URL`。
3. 在项目的 Environment Variables 里添加 `SECRET_KEY`（用上面 `.env.example` 里的命令生成）。
4. 在本地对 Neon 执行迁移（用 Neon 控制台里的 **直连**（unpooled）连接串）：

   ```bash
   DATABASE_URL='postgresql://...' .venv/bin/alembic -c backend/alembic.ini upgrade head
   ```

5. 重新部署。以后每次修改模型，都要先生成迁移（`alembic revision --autogenerate`），并在部署前对 Neon 执行 `upgrade head`。
````

**Step 3: 跑全部测试和构建**

Run: `.venv/bin/pytest -q && npm --prefix frontend run build`
Expected: 后端全部通过，前端构建成功。

**Step 4: 在浏览器里走一遍主要流程**

用 `.claude/launch.json` 里的 `backend` 和 `frontend` 两个配置启动服务（`preview_start`），把视口设成手机尺寸（375×812），依次确认：

1. 打开 `/`，跳到 `/login`；去注册 `alice`，注册后进入引导页。
2. 创建家庭“我家”，进入首页，标题是“我家”。
3. 位置 → 新建“主卧”；进入主卧 → 新建子位置“衣柜”；进入衣柜 → 新建子位置“蓝色收纳盒”。路径显示“主卧 › 衣柜 › 蓝色收纳盒”。
4. 在“蓝色收纳盒”里放入物品“护照”，条码填 `6901234567890`。物品页显示的位置路径正确。
5. 首页搜索“护照”和“1234567”，都能搜到，并显示完整路径。
6. 扫码页手动输入 `6901234567890` → 跳到“护照”；输入 `000` → 跳到新建物品，条码已预填。
7. 编辑“衣柜”，把上级位置改成顶层；选择器里不出现“衣柜”自己和“蓝色收纳盒”。
8. 删除“主卧”（现在是空的）成功；删除“衣柜”提示“位置里还有子位置或物品，请先移走”。
9. 打印页勾选“蓝色收纳盒”，出现带二维码的标签。
10. 家庭与我 → 生成邀请链接。新开一个无痕标签页注册 `bob`，打开邀请链接加入；bob 能看到“护照”。
11. bob 创建第二个家庭“爸妈家”，切换家庭后首页没有“护照”；直接打开 `/l/<蓝色收纳盒 ID>` 会自动切回“我家”。
12. 浏览器控制台没有报错。

记录每一项是否通过。发现问题先修，再重跑测试。

**Step 5: Commit**

```bash
git add README.md .env.example
git commit -m "docs: add README with local dev and Vercel deploy steps"
```

---

## 部署后需要用户在手机上确认的事

这些在本地无法验证：

- 手机 Safari / Chrome 打开 HTTPS 地址后，扫码页能调起后置摄像头，并识别商品条码（EAN-13）。
- 用手机系统相机扫打印出来的位置二维码，能直接打开对应位置页面；未登录时先登录，再跳回该位置。
- 打印页在 A4 纸上的排版和二维码大小合适。
