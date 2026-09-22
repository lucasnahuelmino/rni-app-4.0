"""CRUD de mediciones. Toda escritura pasa por acá y dispara el recálculo
acotado correspondiente (ver services/statistics.py)."""
from __future__ import annotations

import sqlite3

from app.db.repositories import mediciones_repo
from app.services import statistics as statistics_service


def eliminar_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> int:
    filas_borradas = mediciones_repo.eliminar_por_localidad(conn, ccte, provincia, localidad)
    statistics_service.recalcular(conn, {(ccte, provincia, localidad)})
    return filas_borradas


def editar_metadata_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str,
                               nuevos: dict) -> int:
    """UPDATE dirigido -- reemplaza el patrón 'reescribir toda la tabla' del
    sistema actual (Auditoría Fase 1, hallazgo A8)."""
    filas_afectadas = mediciones_repo.actualizar_metadata_localidad(conn, ccte, provincia, localidad, nuevos)

    claves = {(ccte, provincia, localidad)}
    nueva_ccte = nuevos.get("ccte", ccte)
    nueva_provincia = nuevos.get("provincia", provincia)
    nueva_localidad = nuevos.get("localidad", localidad)
    claves.add((nueva_ccte, nueva_provincia, nueva_localidad))

    statistics_service.recalcular(conn, claves)
    return filas_afectadas
