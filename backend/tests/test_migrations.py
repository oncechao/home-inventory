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
