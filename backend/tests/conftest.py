import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture()
def client(db_path, monkeypatch):
    """App real con TestClient, apuntando a una DB temporal (via env var,
    ver app/core/config.py) -- nunca toca data/rni.db.

    Vive en conftest y no en test_api_integration.py porque lo usan los tests
    de ese archivo y los de test_exports.py: una sola fuente, para que nadie
    termine con dos fixtures distintas que responden al mismo nombre.
    """
    monkeypatch.setenv("RNI_DB_PATH", str(db_path))
    # Los modulos ya pueden estar importados de tests anteriores con el
    # DB_PATH viejo "horneado" -- se recargan para que tomen el nuevo path.
    import importlib

    import app.core.config as config_module
    import app.core.deps as deps_module
    import app.db.database as database_module
    import app.main as main_module

    importlib.reload(config_module)
    importlib.reload(database_module)
    importlib.reload(deps_module)
    importlib.reload(main_module)

    with TestClient(main_module.app) as c:
        yield c
