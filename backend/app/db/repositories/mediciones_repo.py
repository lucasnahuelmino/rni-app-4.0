"""Acceso a datos de la tabla `mediciones`.

Único punto de la aplicación que arma SQL sobre esta tabla (evita repetir
el problema de la Auditoría Fase 1, hallazgo A10: el mapa leyendo la tabla
por un camino paralelo).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable


def insertar_mediciones(conn: sqlite3.Connection, filas: list[dict]) -> list[int]:
    """Inserta filas nuevas y devuelve los ids generados."""
    if not filas:
        return []

    columnas = [
        "ccte", "provincia", "localidad",
        "resultado_vm", "resultado_pct",
        "fecha_raw", "hora_raw", "fecha_hora", "anio",
        "lat", "lon", "lat_raw", "lon_raw",
        "expediente", "sonda", "nombre_archivo",
        "import_batch_id", "fecha_carga",
    ]
    placeholders = ",".join("?" for _ in columnas)
    sql = f"INSERT INTO mediciones ({','.join(columnas)}) VALUES ({placeholders})"

    ids = []
    cur = conn.cursor()
    for fila in filas:
        valores = [fila.get(c) for c in columnas]
        cur.execute(sql, valores)
        ids.append(cur.lastrowid)
    return ids


def existe_medicion(conn: sqlite3.Connection, ccte: str, localidad: str,
                     fecha_hora: str | None, resultado_vm: float | None) -> bool:
    """Detección de duplicados por contenido (no solo por nombre de archivo,
    a diferencia del sistema Streamlit actual -- Auditoría Fase 1, hallazgo
    sobre `carga_excel.py`)."""
    cur = conn.execute(
        """SELECT 1 FROM mediciones
           WHERE ccte = ? AND localidad = ?
             AND fecha_hora IS ? AND resultado_vm IS ?
           LIMIT 1""",
        (ccte, localidad, fecha_hora, resultado_vm),
    )
    return cur.fetchone() is not None


def claves_por_batch(conn: sqlite3.Connection, batch_id: int) -> list[tuple[str, str, str]]:
    """(ccte, provincia, localidad) distintos insertados por un lote -- usado
    para saber qué resúmenes recalcular tras un import."""
    cur = conn.execute(
        """SELECT DISTINCT ccte, provincia, localidad FROM mediciones
           WHERE import_batch_id = ?""",
        (batch_id,),
    )
    return [(r["ccte"], r["provincia"], r["localidad"]) for r in cur.fetchall()]


def filas_por_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> list[dict]:
    cur = conn.execute(
        """SELECT * FROM mediciones WHERE ccte = ? AND provincia = ? AND localidad = ?""",
        (ccte, provincia, localidad),
    )
    return [dict(r) for r in cur.fetchall()]


def eliminar_por_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> int:
    cur = conn.execute(
        "DELETE FROM mediciones WHERE ccte = ? AND provincia = ? AND localidad = ?",
        (ccte, provincia, localidad),
    )
    return cur.rowcount


def actualizar_metadata_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str,
                                   nuevos: dict) -> int:
    """UPDATE dirigido sobre las filas de una localidad (reemplaza el patrón
    'borrar+reinsertar toda la tabla' del sistema actual -- Auditoría Fase 1,
    hallazgo A8)."""
    campos_permitidos = {"ccte", "provincia", "localidad", "expediente"}
    sets = {k: v for k, v in nuevos.items() if k in campos_permitidos}
    if not sets:
        return 0
    set_clause = ", ".join(f"{k} = ?" for k in sets)
    valores = list(sets.values()) + [ccte, provincia, localidad]
    cur = conn.execute(
        f"UPDATE mediciones SET {set_clause} WHERE ccte = ? AND provincia = ? AND localidad = ?",
        valores,
    )
    return cur.rowcount


def query_filtrada(conn: sqlite3.Connection, ccte: Iterable[str] | None = None,
                    provincia: Iterable[str] | None = None, anio: Iterable[int] | None = None,
                    limit: int | None = None) -> list[dict]:
    """SELECT genérico con filtros opcionales -- usado por endpoints que
    necesitan filas individuales (mapa, histograma)."""
    where, params = construir_where(ccte, provincia, anio)
    sql = f"SELECT * FROM mediciones {where}"
    if limit:
        sql += " LIMIT ?"
        params = params + [limit]
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def construir_where(ccte, provincia, anio) -> tuple[str, list[Any]]:
    condiciones = []
    params: list[Any] = []
    if ccte:
        ccte = list(ccte)
        condiciones.append(f"ccte IN ({','.join('?' for _ in ccte)})")
        params += ccte
    if provincia:
        provincia = list(provincia)
        condiciones.append(f"provincia IN ({','.join('?' for _ in provincia)})")
        params += provincia
    if anio:
        anio = list(anio)
        condiciones.append(f"anio IN ({','.join('?' for _ in anio)})")
        params += anio
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return where, params
