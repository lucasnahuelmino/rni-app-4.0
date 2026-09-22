"""Diagnóstico de calidad de datos -- vía SQL agregado, sin cargar la tabla
completa a pandas (Auditoría Fase 1, requisito explícito).

`duplicados_probables` y las demás métricas están definidas según lo
discutido en la Fase 2, §6. El umbral de "valores sospechosos" quedó
pendiente de confirmación con el equipo y NO está implementado todavía --
se agrega cuando se defina un criterio concreto.
"""
from __future__ import annotations

import sqlite3

from app.core.config import ARGENTINA_BBOX


def obtener_diagnostico(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) AS n FROM mediciones").fetchone()["n"]

    fechas_vacias = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE fecha_raw IS NULL OR fecha_raw = ''"
    ).fetchone()["n"]

    fechas_no_parseables = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones "
        "WHERE (fecha_raw IS NOT NULL AND fecha_raw != '') AND fecha_hora IS NULL"
    ).fetchone()["n"]

    horas_vacias = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE hora_raw IS NULL OR hora_raw = ''"
    ).fetchone()["n"]

    coordenadas_faltantes = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE lat IS NULL OR lon IS NULL"
    ).fetchone()["n"]

    coordenadas_fuera_de_rango = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE lat IS NOT NULL AND lon IS NOT NULL "
        "AND (lat < ? OR lat > ? OR lon < ? OR lon > ?)",
        (ARGENTINA_BBOX["lat_min"], ARGENTINA_BBOX["lat_max"],
         ARGENTINA_BBOX["lon_min"], ARGENTINA_BBOX["lon_max"]),
    ).fetchone()["n"]

    resultados_faltantes = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE resultado_vm IS NULL"
    ).fetchone()["n"]

    duplicados_probables = conn.execute(
        """SELECT COALESCE(SUM(cnt - 1), 0) AS n FROM (
             SELECT COUNT(*) AS cnt FROM mediciones
             GROUP BY ccte, localidad, fecha_hora, resultado_vm
             HAVING COUNT(*) > 1
           )"""
    ).fetchone()["n"]

    return {
        "total_registros": total,
        "fechas_vacias": fechas_vacias,
        "fechas_no_parseables": fechas_no_parseables,
        "horas_vacias": horas_vacias,
        "coordenadas_faltantes": coordenadas_faltantes,
        "coordenadas_fuera_de_rango": coordenadas_fuera_de_rango,
        "resultados_faltantes": resultados_faltantes,
        "duplicados_probables": duplicados_probables,
    }
