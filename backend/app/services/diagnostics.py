"""Diagnóstico de calidad de datos -- vía SQL agregado, sin cargar la tabla
completa a pandas (Auditoría Fase 1, requisito explícito).

`duplicados_probables` y las demás métricas están definidas según lo
discutido en la Fase 2, §6. Esa misma Fase dejó "pendiente de confirmación
con el equipo" el umbral de valores sospechosos, y quedó resuelto en el
Lote 7 dividiendo en tres casos:

  * NEGATIVO -- imposible físicamente. Ya no puede llegar a la base: el
    import fuerza el valor absoluto en `_leer_y_normalizar` y las filas que
    ya estaban cargadas las sanea `measurements.sanear_signo_resultados` en
    el arranque. Por eso NO se cuenta acá: si contara, sería una regresión,
    no una métrica.

  * CERO EXACTO -- error del equipo. La sonda no midió nada. Se conservan
    como valores reales (siguen en los promedios, en el mapa y en el
    % del límite, que también da 0), pero se cuentan acá para que se vea
    que hubo un problema de medición. Hoy: 4.606 filas.

  * >= 100% -- POSIBLE, no es un error. Es una excedencia de la MEP y se
    trata después y en detalle desde el área técnica. Va en su propio
    contador, con leyenda de alerta en la UI.

Valores faltantes, duplicados, fechas y coordenadas siguen siendo los
contadores de calidad de datos de siempre.
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

    # Ceros absolutos: error del equipo (ver docstring). Se cuentan aparte
    # de `resultados_faltantes` porque la fila NO está vacía -- tiene fecha,
    # hora, coordenadas y sonda válidos, solo que la sonda no midió.
    resultados_en_cero = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE resultado_vm = 0"
    ).fetchone()["n"]

    # Excedencias de la MEP: posibles, no son error de datos. Van con su
    # propia leyenda de alerta porque son puntos que el área técnica trata
    # después, en detalle.
    excedencias_mep = conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE resultado_pct >= 100"
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
        "resultados_en_cero": resultados_en_cero,
        "excedencias_mep": excedencias_mep,
        "duplicados_probables": duplicados_probables,
    }
