"""Tiempo trabajado -- diario, mensual, y por localidad/CCTE.

Reutiliza la MISMA lógica de agrupamiento que ya existía en
calculations/dates.py (por archivo+día, tomando min/max de fecha_hora).
No se inventa una fórmula nueva; esto solo la expone con más granularidad
de la que hoy persisten resumen_localidad/resumen_ccte (que solo guardan el
total, no el desglose diario/mensual).
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from app.calculations.dates import desglose_diario, desglose_mensual
from app.db.repositories import mediciones_repo
from app.schemas.filters import FiltrosQuery


def tiempo_diario_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> list[dict]:
    filas = mediciones_repo.filas_por_localidad(conn, ccte, provincia, localidad)
    return desglose_diario(pd.DataFrame(filas))


def tiempo_mensual_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> list[dict]:
    diario = tiempo_diario_localidad(conn, ccte, provincia, localidad)
    return desglose_mensual(diario)


def tiempo_mensual(conn: sqlite3.Connection, filtros: FiltrosQuery) -> list[dict]:
    """Desglose mensual global (o filtrado por ccte/provincia/año/localidad),
    para el panel de Gráficos > Operativo. Solo trae las columnas que hacen
    falta (fecha_hora, nombre_archivo), no la tabla completa."""
    filas = mediciones_repo.query_filtrada(
        conn, ccte=filtros.ccte, provincia=filtros.provincia, anio=filtros.anio,
        localidad=filtros.localidad, columnas="fecha_hora, nombre_archivo",
    )
    diario = desglose_diario(pd.DataFrame(filas))
    return desglose_mensual(diario)
