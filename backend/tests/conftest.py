import sqlite3
from pathlib import Path

import pytest

from app.db.database import get_connection


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "rni_test.db"


@pytest.fixture()
def conn(db_path: Path):
    from app.core.config import SCHEMA_PATH
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(db_path) as c:
        c.executescript(ddl)
    with get_connection(db_path) as c:
        yield c
