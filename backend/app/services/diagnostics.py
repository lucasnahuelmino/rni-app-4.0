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
import time

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


# --- caché -------------------------------------------------------------
# Las 11 queries de arriba leen los 219.818 registros: 1.3 s con las páginas
# en memoria y **33 s la primera vez** después de reiniciar el backend (es el
# endpoint más lento de la API y la vista de Carga lo pide). Los números sólo
# cambian si cambian los datos, así que el resultado se guarda y se recalcula
# sólo cuando algo se movió.
#
# Tres cortapisas por si una sola no alcanzara:
#
#  * `firma`: COUNT(*) + MAX(rowid) de `mediciones` (8 ms) detecta altas,
#    bajas y reemplazos vengan de donde vengan, incluso de un script hecho a
#    mano. Además es lo que evita que dos tests con bases distintas se pisen:
#    el módulo se importa una sola vez para toda la sesión.
#  * `invalidar_cache`: lo llaman las rutas que escriben. Es el contrato
#    explícito y no depende de cómo esté armada la firma. El caso que de
#    verdad hace falta es renombrar una localidad: por sí solo un rename no
#    mueve ni el COUNT ni el rowid, pero si el nombre nuevo choca con una
#    localidad existente las filas quedan juntas en el agrupamiento de
#    `duplicados_probables` y el número cambia sin que se mueva la firma.
#  * TTL: red de seguridad por cualquier escritura que no esté en esas rutas.
#    Como máximo 60 s de datos viejos.
TTL_SEGUNDOS = 60

# (firma, momento, datos). Una sola tupla en una sola variable: se escribe de
# un pisotón, así quien la lee nunca coge una mitad con la otra (los endpoints
# corren en threadpool y puede haber dos peticiones a la vez).
_entrada: tuple | None = None


def _firma(conn: sqlite3.Connection) -> tuple[int, int]:
    fila = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(MAX(rowid), 0) AS ultima FROM mediciones"
    ).fetchone()
    return fila["n"], fila["ultima"]


def invalidar_cache() -> None:
    """Tira el diagnóstico cacheado. Lo llaman las rutas que escriben."""
    global _entrada
    _entrada = None


def obtener_diagnostico_cacheado(conn: sqlite3.Connection) -> dict:
    """`obtener_diagnostico` sin volver a calcularlo si nada cambió.

    Devuelve una copia: el que llama se puede quedar con el dict sin que la
    próxima escritura le cambie los datos de debajo.
    """
    global _entrada
    firma = _firma(conn)
    ahora = time.monotonic()
    if _entrada is not None and _entrada[0] == firma and ahora - _entrada[1] < TTL_SEGUNDOS:
        return dict(_entrada[2])
    datos = obtener_diagnostico(conn)
    _entrada = (firma, ahora, datos)
    return dict(datos)
