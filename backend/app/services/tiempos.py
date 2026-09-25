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

from app.calculations.dates import desglose_diario_desde_agrupado, desglose_mensual
from app.db.repositories import mediciones_repo
from app.schemas.filters import FiltrosQuery


def tiempo_diario_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> list[dict]:
    agg = mediciones_repo.agrupar_min_max_por_archivo_dia(
        conn, ccte=[ccte], provincia=[provincia], localidad=[localidad],
    )
    return desglose_diario_desde_agrupado(pd.DataFrame(agg))


def tiempo_diario_ccte(conn: sqlite3.Connection, ccte: list[str] | None = None) -> list[dict]:
    """Desglose día por día de UN centro de trabajo, o de todos juntos.

    `ccte=None` trae todo el sistema, que es lo que muestra la vista
    General del Centro operativo; con CCTE es la vista de ese centro. La
    lista puede traer varios centros a la vez porque el filtro de CCTE es
    multi-select en la barra global: los botones de la sección son
    selección única, pero si alguien armó dos chips a mano, la lista, la
    tendencia y este desglose tienen que cubrir los mismos dos centros.
    Mismo camino que `/tiempos/mensual`.

    Usa la MISMA función de agrupamiento que `/tiempos/mensual`
    (`desglose_diario`: por archivo + día sobre todas las filas del CCTE),
    así que la suma de este desglose da exactamente lo que da el mensual:
    dos niveles distintos del mismo criterio, no dos fórmulas. Ese es el
    invariant que cubre el test.

    NO coincide con `resumen_ccte.tiempo_trabajado_seg`, y no es un bug de
    este endpoint: ese total es `SUM(tiempo_trabajado_seg) FROM
    resumen_localidad`, que agrupa por archivo+día DENTRO de cada localidad
    y recién después suma. Si un mismo archivo cubre dos localidades, el
    criterio por localidad lo cuenta dos veces y el global una. Medido en la
    base real: 1 383 472 s (global) vs 1 379 651 s (por localidad), 0,28 %
    en total y concentrado solo en Córdoba (3821 s, 1,9 %); los otros cuatro
    CCTE dan idéntico en los dos criterios. Acá se eligió el del mensual
    porque es el que ya existía y el que está al lado en la misma pantalla:
    cambiar uno de los dos habría inventado una tercera discrepancia. Si
    algún día se quiere unificar, el cambio es en `_agrupar_por_archivo_dia`
    (agregar `provincia`/`localidad` a las claves) y debe aplicarse a
    `resumen_*` y a `tiempo_mensual` a la vez, no a uno solo.

    El desglose por archivo se conserva en vez de agregar por fecha: son
    jornadas distintas y sumarlas escondería que fueron varias. Se midió
    antes de elegirlo, porque con archivos sueltos la tabla se podía ir a
    miles de filas: en la base real el máximo por CCTE es 135 (Comodoro
    Rivadavia) y todos los demás quedan por debajo de 40.
    """
    agg = mediciones_repo.agrupar_min_max_por_archivo_dia(conn, ccte=ccte)
    return desglose_diario_desde_agrupado(pd.DataFrame(agg))


def tiempo_mensual_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> list[dict]:
    diario = tiempo_diario_localidad(conn, ccte, provincia, localidad)
    return desglose_mensual(diario)


def tiempo_mensual(conn: sqlite3.Connection, filtros: FiltrosQuery) -> list[dict]:
    """Desglose mensual global (o filtrado por ccte/provincia/año/localidad),
    para el panel de Gráficos > Operativo. Solo trae las columnas que hacen
    falta (fecha_hora, nombre_archivo), no la tabla completa."""
    agg = mediciones_repo.agrupar_min_max_por_archivo_dia(
        conn, ccte=filtros.ccte, provincia=filtros.provincia, anio=filtros.anio,
        localidad=filtros.localidad,
    )
    diario = desglose_diario_desde_agrupado(pd.DataFrame(agg))
    return desglose_mensual(diario)
