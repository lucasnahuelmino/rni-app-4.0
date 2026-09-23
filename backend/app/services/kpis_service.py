"""KPIs agregados a nivel nacional (con filtros opcionales).

Cuando no hay filtros, se sirve directamente desde resumen_ccte/resumen_anual
(pre-calculado). Cuando hay filtros que no coinciden 1:1 con esas tablas, se
recurre a un agregado SQL directo sobre `mediciones` (nunca se carga la tabla
completa a pandas)."""
from __future__ import annotations

import sqlite3

from app.calculations.dates import format_timedelta_long
from app.core.config import CCTE_FIJOS, CCTE_SIEMPRE_VISIBLES
from app.db.repositories.mediciones_repo import construir_where
from app.schemas.filters import FiltrosQuery


def obtener_kpis(conn: sqlite3.Connection, filtros: FiltrosQuery) -> dict:
    where, params = construir_where(filtros.ccte, filtros.provincia, filtros.anio)

    row = conn.execute(
        f"""SELECT COUNT(*) AS registros_totales,
                   COUNT(DISTINCT localidad) AS localidades,
                   COUNT(DISTINCT provincia) AS provincias,
                   COUNT(DISTINCT ccte) AS cctes,
                   AVG(resultado_pct) AS promedio_pct,
                   MAX(resultado_vm) AS pico_vm
            FROM mediciones {where}""",
        params,
    ).fetchone()

    pico_maximo = None
    if row["pico_vm"] is not None:
        detalle = conn.execute(
            f"""SELECT localidad, provincia, ccte, resultado_vm, resultado_pct, expediente
                FROM mediciones {where} {"AND" if where else "WHERE"} resultado_vm = ?
                LIMIT 1""",
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
