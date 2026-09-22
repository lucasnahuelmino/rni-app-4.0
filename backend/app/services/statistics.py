"""Recalculo de tablas de resumen -- acotado a las claves afectadas, no full
rebuild (ver Fase 2, §1.5)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.calculations.statistics import agregar_mediciones
from app.db.repositories import mediciones_repo, resumen_repo


def recalcular(conn: sqlite3.Connection, claves: set[tuple[str, str, str]]) -> None:
    """`claves` es un set de (ccte, provincia, localidad) a recalcular."""
    ahora = datetime.now(timezone.utc).isoformat()
    cctes_tocados: set[str] = set()
    provincias_tocadas: set[str] = set()
    anios_tocados: set[int] = set()
    pares_provincia_ccte: set[tuple[str, str]] = set()
    meses_tocados: set[str] = set()

    for ccte, provincia, localidad in claves:
        filas = mediciones_repo.filas_por_localidad(conn, ccte, provincia, localidad)
        if not filas:
            resumen_repo.eliminar_resumen_localidad(conn, ccte, provincia, localidad)
        else:
            agregados = agregar_mediciones(filas)
            expedientes = ",".join(sorted({f["expediente"] for f in filas if f.get("expediente")}))
            sondas = ",".join(sorted({f["sonda"] for f in filas if f.get("sonda")}))
            agregados["expedientes"] = expedientes or None
            agregados["sondas"] = sondas or None
            resumen_repo.upsert_resumen_localidad(conn, ccte, provincia, localidad, agregados, ahora)

            # Se reutilizan las mismas `filas` ya traídas arriba para juntar
            # años y meses tocados, en vez de volver a consultar la
            # localidad de nuevo (optimización de Fase 5 -- la versión
            # anterior hacía esta misma consulta dos veces).
            for f in filas:
                if f.get("anio"):
                    anios_tocados.add(int(f["anio"]))
                if f.get("fecha_hora"):
                    meses_tocados.add(f["fecha_hora"][:7])

        cctes_tocados.add(ccte)
        provincias_tocadas.add(provincia)
        pares_provincia_ccte.add((provincia, ccte))

    for ccte in cctes_tocados:
        resumen_repo.recalcular_resumen_ccte(conn, ccte, ahora)
    for provincia in provincias_tocadas:
        resumen_repo.recalcular_resumen_provincia(conn, provincia, ahora)
    for anio in anios_tocados:
        resumen_repo.recalcular_resumen_anual(conn, anio, ahora)

    # Antes se recalculaba el producto cartesiano provincias x cctes
    # tocados (O(P*C) queries incluso para combinaciones que nunca
    # existieron); ahora solo los pares (provincia, ccte) que realmente
    # aparecen en las claves recalculadas.
    for provincia, ccte in pares_provincia_ccte:
        resumen_repo.recalcular_resumen_provincia_ccte(conn, provincia, ccte, ahora)

    for mes in meses_tocados:
        resumen_repo.recalcular_resumen_mensual(conn, mes, ahora)


def recalcular_todo(conn: sqlite3.Connection) -> None:
    """Recalculo completo -- solo para migración inicial o mantenimiento manual,
    NO para el flujo normal de importación (ver Fase 2, §1.5)."""
    cur = conn.execute("SELECT DISTINCT ccte, provincia, localidad FROM mediciones")
    claves = {(r["ccte"], r["provincia"], r["localidad"]) for r in cur.fetchall()}
    conn.execute("DELETE FROM resumen_localidad")
    conn.execute("DELETE FROM resumen_ccte")
    conn.execute("DELETE FROM resumen_provincia")
    conn.execute("DELETE FROM resumen_anual")
    conn.execute("DELETE FROM resumen_provincia_ccte")
    conn.execute("DELETE FROM resumen_mensual")
    if claves:
        recalcular(conn, claves)
