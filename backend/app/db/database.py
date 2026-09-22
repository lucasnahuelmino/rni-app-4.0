"""Capa de conexión a SQLite.

Toda la aplicación pasa por acá para abrir una conexión. Nadie por fuera
de app/db/repositories/ debería importar sqlite3 directamente (evita repetir
el problema de la Auditoría Fase 1, hallazgo A10: el mapa leyendo la base
por un camino paralelo al oficial).
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.core.config import DB_PATH, SCHEMA_PATH


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # `check_same_thread=False`: FastAPI corre los endpoints síncronos en un
    # threadpool, así que una request puede caer en un hilo distinto al que
    # abrió la conexión. Es seguro acá porque cada request abre y cierra su
    # propia conexión (ver get_connection) -- nunca se comparte una misma
    # conexión entre threads concurrentes. Sin este flag, sqlite3 tira
    # `ProgrammingError: SQLite objects created in a thread can only be used
    # in that same thread` (encontrado en el smoke test de integración de
    # Fase 4, no lo detectaban los tests con pytest porque ahí todo corre en
    # un solo hilo).
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection(db_path: Path = DB_PATH):
    """Conexión con auto-commit al salir del bloque `with`, rollback si hay excepción."""
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH) -> None:
    """Crea el esquema si no existe. Es idempotente (todo el DDL usa IF NOT EXISTS)."""
    ddl = schema_path.read_text(encoding="utf-8")
    with get_connection(db_path) as conn:
        conn.executescript(ddl)
