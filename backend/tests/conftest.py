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
