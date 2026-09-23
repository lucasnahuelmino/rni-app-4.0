"""KPIs agregados a nivel nacional (con filtros opcionales).

Sin filtros se sirven desde `resumen_global` (UNA fila precalculada por
`resumen_repo.recalcular_resumen_global`): el agregado en vivo sobre las
219.818 filas tarda 590 ms y es la carga del dashboard (GET /api/kpis sin
parámetros medía 532 ms de HTTP).

Con filtros no hay atajo posible -- haría falta una tabla por combinación
ccte x provincia x anio, y ni siquiera una sola clave en solitario coincide
1:1 con las tablas que ya existen (resumen_ccte, por ejemplo, no guarda ni
promedio_pct ni cctes) -- así que se recurre al agregado SQL directo sobre
`mediciones`. Ese scan baja a ~94 ms cuando la clave está fija, porque usa
su índice. Nunca se carga la tabla completa a pandas.
"""
from __future__ import annotations

import sqlite3

from app.calculations.dates import format_timedelta_long
from app.core.config import CCTE_FIJOS, CCTE_SIEMPRE_VISIBLES
from app.db.repositories.mediciones_repo import construir_where
from app.schemas.filters import FiltrosQuery


def _kpis_precalculados(conn: sqlite3.Connection) -> dict | None:
    """`resumen_global`, o None si la tabla todavía no se construyó.

    El None no es cosmético: hay que caer al agregado en vivo de abajo en vez
    de romper, porque la tabla puede estar vacía en una base recién creada
    desde cero (el arranque la llena, pero un test que la vacíe a mano o una
    migración a medias no tiene por qué haberlo hecho).
    """
    fila = conn.execute("SELECT * FROM resumen_global WHERE id = 1").fetchone()
    if fila is None:
        return None

    pico_maximo = None
    if fila["pico_id"] is not None:
        detalle = conn.execute(
            """SELECT localidad, provincia, ccte, resultado_vm, resultado_pct, expediente
               FROM mediciones WHERE id = ?""",
            (fila["pico_id"],),
        ).fetchone()
        if detalle:
            pico_maximo = dict(detalle)

    return {
        "registros_totales": fila["registros_totales"] or 0,
        "localidades": fila["localidades"] or 0,
        "provincias": fila["provincias"] or 0,
        "cctes": fila["cctes"] or 0,
        "promedio_pct": fila["promedio_pct"],
        "pico_maximo": pico_maximo,
    }


def obtener_kpis(conn: sqlite3.Connection, filtros: FiltrosQuery) -> dict:
    # `filtros.localidad` no entra: construir_where acá abajo tampoco lo usa,
    # los KPIs son nacionales por diseño.
    if not (filtros.ccte or filtros.provincia or filtros.anio):
        precalculado = _kpis_precalculados(conn)
        if precalculado is not None:
            return precalculado

    where, params = construir_where(filtros.ccte, filtros.provincia, filtros.anio)

    # "Localidades" son lugares distintos, no nombres distintos: hay DOS
    # "San Pedro" (Catamarca y Santiago del Estero) y contar solo `localidad`
    # las fusionaba en una (60 en vez de 61). La identidad de una localidad es
    # su clave completa, así que se cuenta la tupla concatenada -- SQLite no
    # acepta `COUNT(DISTINCT (a, b, c))` ("row value misused"). char(31) es el
    # unit separator de ASCII: no puede aparecer en ningún nombre real.
    row = conn.execute(
        f"""SELECT COUNT(*) AS registros_totales,
                   COUNT(DISTINCT ccte || char(31) || provincia || char(31) || localidad) AS localidades,
                   COUNT(DISTINCT provincia) AS provincias,
                   COUNT(DISTINCT ccte) AS cctes,
                   AVG(resultado_pct) AS promedio_pct,
                   MAX(resultado_vm) AS pico_vm
            FROM mediciones {where}""",
        params,
    ).fetchone()

    pico_maximo = None
    if row["pico_vm"] is not None:
        # ORDER BY id ASC: el agregado vive sin filtro elige el pico con el
        # mismo criterio (ver recalcular_resumen_global), y sin este orden el
        # LIMIT 1 devolvía la primera fila que encontrara el plan -- hoy
        # coincide porque el recorrido de tabla sale en orden de rowid, pero
        # no está garantizado y no se puede comparar contra el atajo.
        detalle = conn.execute(
            f"""SELECT localidad, provincia, ccte, resultado_vm, resultado_pct, expediente
                FROM mediciones {where} {"AND" if where else "WHERE"} resultado_vm = ?
                ORDER BY id ASC LIMIT 1""",
            params + [row["pico_vm"]],
        ).fetchone()
        if detalle:
            pico_maximo = dict(detalle)

    return {
        "registros_totales": row["registros_totales"] or 0,
        "localidades": row["localidades"] or 0,
        "provincias": row["provincias"] or 0,
        "cctes": row["cctes"] or 0,
        "promedio_pct": row["promedio_pct"],
        "pico_maximo": pico_maximo,
    }


def obtener_ccte_summary(conn: sqlite3.Connection, orden: str = "mediciones") -> list[dict]:
    """Siempre devuelve los 7 CCTE fijos, con Buenos Aires/CABA presentes aunque
    tengan 0 mediciones (Auditoría Fase 1, requisito de negocio confirmado)."""
    filas = {r["ccte"]: dict(r) for r in conn.execute("SELECT * FROM resumen_ccte").fetchall()}

    resultado = []
    for ccte in CCTE_FIJOS:
        if ccte in filas:
            resultado.append(filas[ccte])
        else:
            resultado.append({
                "ccte": ccte, "mediciones": 0, "localidades": 0, "provincias": 0,
                "resultado_max_vm": None, "resultado_max_pct": None, "localidad_max": None,
                "tiempo_trabajado_seg": 0, "dias_con_medicion": 0, "actualizado_en": None,
            })

    fijos = [r for r in resultado if r["ccte"] in CCTE_SIEMPRE_VISIBLES]
    resto = [r for r in resultado if r["ccte"] not in CCTE_SIEMPRE_VISIBLES]
    resto.sort(key=lambda r: r.get(orden) or 0, reverse=True)
    ordenado = resto + fijos
    for r in ordenado:
        r["tiempo_trabajado_fmt"] = format_timedelta_long(r.get("tiempo_trabajado_seg"))
    return ordenado
