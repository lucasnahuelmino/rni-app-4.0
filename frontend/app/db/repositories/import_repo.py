"""Acceso a datos de `import_batches` -- historial y trazabilidad de cargas."""
from __future__ import annotations

import sqlite3


def crear_batch(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str,
                 expediente: str | None, fecha_carga: str) -> int:
    cur = conn.execute(
        """INSERT INTO import_batches (fecha_carga, ccte, provincia, localidad, expediente)
           VALUES (?, ?, ?, ?, ?)""",
        (fecha_carga, ccte, provincia, localidad, expediente),
    )
    return cur.lastrowid


def cerrar_batch(conn: sqlite3.Connection, batch_id: int, *, archivos_procesados: int,
                  registros_nuevos: int, registros_duplicados: int, registros_rechazados: int,
                  errores_json: str | None, advertencias_json: str | None) -> None:
    conn.execute(
        """UPDATE import_batches SET
             archivos_procesados = ?, registros_nuevos = ?, registros_duplicados = ?,
             registros_rechazados = ?, errores_json = ?, advertencias_json = ?
           WHERE id = ?""",
        (archivos_procesados, registros_nuevos, registros_duplicados, registros_rechazados,
         errores_json, advertencias_json, batch_id),
    )


def obtener_batch(conn: sqlite3.Connection, batch_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,))
    row = cur.fetchone()
    return dict(row) if row else None
