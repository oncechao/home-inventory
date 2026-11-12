import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("VERCEL", "SECRET_KEY", "DATABASE_URL", "COOKIE_SECURE"):
        monkeypatch.delenv(name, raising=False)


def test_vercel_requires_database_url(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("SECRET_KEY", "prod-secret")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_settings()


def test_vercel_requires_secret_key(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_settings()


def test_vercel_settings(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("SECRET_KEY", "prod-secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    s = get_settings()
    assert s.cookie_secure is True
    assert s.secret_key == "prod-secret"
    assert s.database_url == "postgresql+psycopg://u:p@h/db"


def test_local_defaults():
    s = get_settings()
    assert s.database_url == "sqlite:///./dev.db"
    assert s.cookie_secure is False
