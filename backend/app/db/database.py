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
        escribio = conn.total_changes > 0
        conn.commit()
        if escribio:
            _mantenimiento_pos_escritura(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _mantenimiento_pos_escritura(conn: sqlite3.Connection) -> None:
    """WAL y páginas libres, sólo cuando la conexión escribió de verdad.

    Dos pragmas, ambas medidas sobre `data/rni.db` (118.5 MiB, 359.414 filas):

    * `wal_checkpoint(TRUNCATE)` vuelca el diario al archivo principal y lo
      deja EN CERO. Sin esto, después de cada escritura `rni.db` queda
      incompleto hasta que alguien haga el checkpoint: el visor abre el
      `.db` arrastrándolo a mano, `restore_db` lo restaura con un
      `shutil.copy2` crudo y la sincronización de OneDrive sube sólo ese
      archivo -- los tres se comerían una base vieja o partida. Con el
      checkpoint en cero, `rni.db` siempre está completo en reposo.
    * `incremental_vacuum` devuelve al sistema las páginas libres de a
      poco, en vez de esperar un `VACUUM` de 16 s sobre la base cerrada.
      Hace falta `auto_vacuum=INCREMENTAL`, que se pide en `init_schema`.

    Mejor esfuerzo: una pragma que no pudo correr nunca rompe el request
    que la llamó.
    """
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        if conn.execute("PRAGMA freelist_count").fetchone()[0]:
            conn.execute("PRAGMA incremental_vacuum")
    except sqlite3.Error:
        pass


def init_schema(db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH) -> None:
    """Crea el esquema si no existe. Es idempotente (todo el DDL usa IF NOT EXISTS)."""
    ddl = schema_path.read_text(encoding="utf-8")
    with get_connection(db_path) as conn:
        # ANTES del DDL, que es lo único que funciona sin VACUUM: en una base
        # recién creada (vacía) el pragma se aplica de entrada; sobre una con
        # contenido SQLite lo ignora en silencio. Por eso `data/rni.db` se
        # convirtió una vez a mano con `PRAGMA auto_vacuum=INCREMENTAL` +
        # `VACUUM`, y recién después se le pidió a `_mantenimiento_pos_escritura`.
        conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
        # Lo mismo con WAL: queda grabado en el encabezado, así toda base nueva
        # (tests, restauraciones, la que traiga mañana) nace igual que la actual
        # en vez de volver al diario de rollback, que en cada carga escribe una
        # copia completa de la base al lado.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(ddl)
