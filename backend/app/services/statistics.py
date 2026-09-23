"""Recalculo de tablas de resumen -- acotado a las claves afectadas, no full
rebuild (ver Fase 2, §1.5)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.calculations.statistics import agregar_mediciones
from app.db.repositories import mediciones_repo, resumen_repo


def recalcular(conn: sqlite3.Connection, claves: set[tuple[str, str, str]],
               periodos_afectados: tuple[set[int], set[str]] | None = None) -> None:
    """`claves` es un set de (ccte, provincia, localidad) a recalcular.

    `periodos_afectados` = (años, meses "YYYY-MM") que hay que recalcular
    aunque `claves` no aporte filas. Hace falta cuando se BORRAN filas: el
    bucle de abajo solo puede leer años/meses de las filas que siguen vivas,
    así que sin este dato `resumen_anual`/`resumen_mensual` quedarían
    contando mediciones que ya no existen. Ver
    `services/measurements.eliminar_localidad`.
    """
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

        # Se hace SIEMPRE, también en la rama `not filas`: la función ya
        # borra la localidad entera antes de insertar, así que si la
        # localidad dejó de existir (o de tener filas con coordenadas) no
        # queda ningún punto viejo en el mapa.
        resumen_repo.recalcular_punto_max(conn, ccte, provincia, localidad)

        cctes_tocados.add(ccte)
        provincias_tocadas.add(provincia)
        pares_provincia_ccte.add((provincia, ccte))

    if periodos_afectados:
        anios_tocados |= periodos_afectados[0]
        meses_tocados |= periodos_afectados[1]

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

    if claves or periodos_afectados:
        # Cambió la base, así que cambian también los KPIs nacionales, que no
        # dependen de ninguna clave en particular. Se recalcula entero en vez
        # de por localidad porque COUNT(DISTINCT)/AVG no se pueden
        # incrementalizar (ver recalcular_resumen_global).
        resumen_repo.recalcular_resumen_global(conn, ahora)


def poblar_tablas_derivadas(conn: sqlite3.Connection) -> None:
    """Construye `punto_max` y `resumen_global` si están sin filas.

    Las dos nacen vacías cuando a una base EXISTENTE solo se le aplica el DDL
    nuevo: schema.sql usa `IF NOT EXISTS`, así que crea la tabla pero no llena
    nada. Sin este pase, /api/map?modo=max_localidad y /api/kpis seguirían
    yendo a las queries lentas (2,8 s y 0,6 s) para siempre y sin ningún
    aviso -- la app funcionaría, solo que lenta, que es la peor manera de
    romper algo.

    Corre en el arranque desde `main.on_startup`. Cuando ya hay filas el
    costo son dos COUNT sobre tablas de 62 y 1 filas; el pase completo solo
    ocurre una vez, porque después el import las mantiene al día.
    """
    if conn.execute("SELECT COUNT(*) FROM resumen_global").fetchone()[0] == 0:
        resumen_repo.recalcular_resumen_global(conn, datetime.now(timezone.utc).isoformat())

    if conn.execute("SELECT COUNT(*) FROM punto_max").fetchone()[0] == 0:
        # ¿Hay algo que valga la pena construir? Sin este corte, una base
        # sin ninguna fila con coordenadas re-correría todas sus localidades
        # en cada arranque para terminar insertando cero filas -- y la tabla
        # seguiría vacía, con lo cual el corte anterior jamás se cumpliría.
        con_coordenadas = conn.execute(
            "SELECT 1 FROM mediciones WHERE lat IS NOT NULL AND lon IS NOT NULL LIMIT 1"
        ).fetchone()
        if con_coordenadas:
            for r in conn.execute(
                "SELECT DISTINCT ccte, provincia, localidad FROM mediciones"
            ).fetchall():
                resumen_repo.recalcular_punto_max(conn, r["ccte"], r["provincia"], r["localidad"])


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
    # `punto_max` y `resumen_global` también: recalcular() los vuelve a crear
    # por cada clave, pero sin este DELETE sobrevivirían las localidades que
    # ya no existan en `mediciones` (claves solo trae las que siguen vivas).
    conn.execute("DELETE FROM punto_max")
    conn.execute("DELETE FROM resumen_global")
    if claves:
        recalcular(conn, claves)
