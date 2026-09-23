"""Acceso a las tablas de resumen (resumen_localidad, resumen_ccte, ...,
resumen_global) y de la tabla derivada `punto_max`."""
from __future__ import annotations

import sqlite3


def upsert_resumen_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str,
                              agregados: dict, ahora: str) -> None:
    conn.execute(
        """INSERT INTO resumen_localidad
             (ccte, provincia, localidad, mediciones, resultado_max_vm, resultado_max_pct,
              resultado_prom_pct, fecha_inicio, fecha_fin, expedientes, sondas,
              tiempo_trabajado_seg, dias_con_medicion, actualizado_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(ccte, provincia, localidad) DO UPDATE SET
             mediciones=excluded.mediciones,
             resultado_max_vm=excluded.resultado_max_vm,
             resultado_max_pct=excluded.resultado_max_pct,
             resultado_prom_pct=excluded.resultado_prom_pct,
             fecha_inicio=excluded.fecha_inicio,
             fecha_fin=excluded.fecha_fin,
             expedientes=excluded.expedientes,
             sondas=excluded.sondas,
             tiempo_trabajado_seg=excluded.tiempo_trabajado_seg,
             dias_con_medicion=excluded.dias_con_medicion,
             actualizado_en=excluded.actualizado_en
        """,
        (
            ccte, provincia, localidad,
            agregados["mediciones"], agregados["resultado_max_vm"], agregados["resultado_max_pct"],
            agregados["resultado_prom_pct"], agregados["fecha_inicio"], agregados["fecha_fin"],
            agregados.get("expedientes"), agregados.get("sondas"),
            agregados["tiempo_trabajado_seg"], agregados["dias_con_medicion"], ahora,
        ),
    )


def eliminar_resumen_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> None:
    conn.execute(
        "DELETE FROM resumen_localidad WHERE ccte = ? AND provincia = ? AND localidad = ?",
        (ccte, provincia, localidad),
    )


def recalcular_resumen_ccte(conn: sqlite3.Connection, ccte: str, ahora: str) -> None:
    cur = conn.execute(
        # `ccte` ya está fijo por el WHERE, así que dentro de un CCTE la
        # identidad de una localidad es (provincia, localidad). Contar solo
        # `localidad` fusionaba los dos "San Pedro" (Catamarca y Santiago del
        # Estero, ambas en el CCTE Salta): 20 en vez de 21. char(31) es el
        # unit separator de ASCII, no puede aparecer en un nombre real.
        # Ver el mismo criterio en obtener_kpis y en recalcular_resumen_anual.
        """SELECT SUM(mediciones) AS mediciones,
                  COUNT(DISTINCT provincia || char(31) || localidad) AS localidades,
                  COUNT(DISTINCT provincia) AS provincias,
                  MAX(resultado_max_vm) AS resultado_max_vm,
                  MAX(resultado_max_pct) AS resultado_max_pct,
                  SUM(tiempo_trabajado_seg) AS tiempo_trabajado_seg,
                  SUM(dias_con_medicion) AS dias_con_medicion
           FROM resumen_localidad WHERE ccte = ?""",
        (ccte,),
    )
    row = cur.fetchone()
    if row is None or row["mediciones"] in (0, None):
        conn.execute("DELETE FROM resumen_ccte WHERE ccte = ?", (ccte,))
        return

    loc_cur = conn.execute(
        "SELECT localidad FROM resumen_localidad WHERE ccte = ? ORDER BY resultado_max_vm DESC LIMIT 1",
        (ccte,),
    )
    loc_row = loc_cur.fetchone()
    localidad_max = loc_row["localidad"] if loc_row else None

    conn.execute(
        """INSERT INTO resumen_ccte
             (ccte, mediciones, localidades, provincias, resultado_max_vm, resultado_max_pct,
              localidad_max, tiempo_trabajado_seg, dias_con_medicion, actualizado_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(ccte) DO UPDATE SET
             mediciones=excluded.mediciones, localidades=excluded.localidades,
             provincias=excluded.provincias, resultado_max_vm=excluded.resultado_max_vm,
             resultado_max_pct=excluded.resultado_max_pct, localidad_max=excluded.localidad_max,
             tiempo_trabajado_seg=excluded.tiempo_trabajado_seg,
             dias_con_medicion=excluded.dias_con_medicion, actualizado_en=excluded.actualizado_en
        """,
        (ccte, row["mediciones"], row["localidades"], row["provincias"], row["resultado_max_vm"],
         row["resultado_max_pct"], localidad_max, row["tiempo_trabajado_seg"] or 0,
         row["dias_con_medicion"] or 0, ahora),
    )


def recalcular_resumen_provincia(conn: sqlite3.Connection, provincia: str, ahora: str) -> None:
    cur = conn.execute(
        # `provincia` está fija por el WHERE: dentro de una provincia la
        # identidad es (ccte, localidad), porque el mismo nombre en dos CCTE
        # distintos son dos lugares. Hoy no colisiona ninguna, pero el
        # criterio tiene que ser el mismo que en el resto de los resúmenes.
        """SELECT SUM(mediciones) AS mediciones,
                  COUNT(DISTINCT ccte || char(31) || localidad) AS localidades,
                  COUNT(DISTINCT ccte) AS cctes, MAX(resultado_max_vm) AS resultado_max_vm,
                  MAX(resultado_max_pct) AS resultado_max_pct
           FROM resumen_localidad WHERE provincia = ?""",
        (provincia,),
    )
    row = cur.fetchone()
    if row is None or row["mediciones"] in (0, None):
        conn.execute("DELETE FROM resumen_provincia WHERE provincia = ?", (provincia,))
        return
    loc_row = conn.execute(
        "SELECT localidad FROM resumen_localidad WHERE provincia = ? ORDER BY resultado_max_vm DESC LIMIT 1",
        (provincia,),
    ).fetchone()
    conn.execute(
        """INSERT INTO resumen_provincia (provincia, mediciones, localidades, cctes,
             resultado_max_vm, resultado_max_pct, localidad_max, actualizado_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(provincia) DO UPDATE SET
             mediciones=excluded.mediciones, localidades=excluded.localidades, cctes=excluded.cctes,
             resultado_max_vm=excluded.resultado_max_vm, resultado_max_pct=excluded.resultado_max_pct,
             localidad_max=excluded.localidad_max, actualizado_en=excluded.actualizado_en
        """,
        (provincia, row["mediciones"], row["localidades"], row["cctes"], row["resultado_max_vm"],
         row["resultado_max_pct"], loc_row["localidad"] if loc_row else None, ahora),
    )


def recalcular_resumen_anual(conn: sqlite3.Connection, anio: int, ahora: str) -> None:
    cur = conn.execute(
        # Solo `anio` está fijo, así que hace falta la clave completa:
        # contar solo `localidad` daba 57 en vez de 58 (mismo caso de los dos
        # "San Pedro"). char(31) = unit separator de ASCII, ver obtener_kpis.
        """SELECT COUNT(*) AS mediciones,
                  COUNT(DISTINCT ccte || char(31) || provincia || char(31) || localidad) AS localidades,
                  COUNT(DISTINCT provincia) AS provincias, COUNT(DISTINCT ccte) AS cctes,
                  MAX(resultado_vm) AS resultado_max_vm, MAX(resultado_pct) AS resultado_max_pct
           FROM mediciones WHERE anio = ?""",
        (anio,),
    )
    row = cur.fetchone()
    if row is None or row["mediciones"] in (0, None):
        conn.execute("DELETE FROM resumen_anual WHERE anio = ?", (anio,))
        return
    conn.execute(
        """INSERT INTO resumen_anual (anio, mediciones, localidades, provincias, cctes,
             resultado_max_vm, resultado_max_pct, actualizado_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(anio) DO UPDATE SET
             mediciones=excluded.mediciones, localidades=excluded.localidades,
             provincias=excluded.provincias, cctes=excluded.cctes,
             resultado_max_vm=excluded.resultado_max_vm, resultado_max_pct=excluded.resultado_max_pct,
             actualizado_en=excluded.actualizado_en
        """,
        (anio, row["mediciones"], row["localidades"], row["provincias"], row["cctes"],
         row["resultado_max_vm"], row["resultado_max_pct"], ahora),
    )


def recalcular_resumen_provincia_ccte(conn: sqlite3.Connection, provincia: str, ccte: str, ahora: str) -> None:
    cur = conn.execute(
        "SELECT COUNT(DISTINCT localidad) AS localidades, COUNT(*) AS mediciones "
        "FROM mediciones WHERE provincia = ? AND ccte = ?",
        (provincia, ccte),
    )
    row = cur.fetchone()
    if row is None or row["mediciones"] in (0, None):
        conn.execute("DELETE FROM resumen_provincia_ccte WHERE provincia = ? AND ccte = ?", (provincia, ccte))
        return
    conn.execute(
        """INSERT INTO resumen_provincia_ccte (provincia, ccte, localidades, mediciones, actualizado_en)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(provincia, ccte) DO UPDATE SET
             localidades=excluded.localidades, mediciones=excluded.mediciones,
             actualizado_en=excluded.actualizado_en
        """,
        (provincia, ccte, row["localidades"], row["mediciones"], ahora),
    )


def recalcular_resumen_mensual(conn: sqlite3.Connection, mes: str, ahora: str) -> None:
    cur = conn.execute(
        "SELECT COUNT(*) AS mediciones FROM mediciones WHERE substr(fecha_hora, 1, 7) = ?",
        (mes,),
    )
    row = cur.fetchone()
    if row is None or row["mediciones"] in (0, None):
        conn.execute("DELETE FROM resumen_mensual WHERE mes = ?", (mes,))
        return
    conn.execute(
        """INSERT INTO resumen_mensual (mes, mediciones, actualizado_en) VALUES (?, ?, ?)
           ON CONFLICT(mes) DO UPDATE SET mediciones=excluded.mediciones, actualizado_en=excluded.actualizado_en
        """,
        (mes, row["mediciones"], ahora),
    )


def recalcular_resumen_global(conn: sqlite3.Connection, ahora: str) -> None:
    """Reconstruye la única fila de `resumen_global`.

    El agregado sobre `mediciones` no se puede incrementalizar por localidad:
    `COUNT(DISTINCT ...)` y `AVG` dependen de TODAS las filas, no de las que
    se tocaron, así que se recalcula entero en cada import (medido: ~590 ms,
    contra los ~0,01 ms de leer la fila ya hecha).

    El detalle del pico se guarda como `pico_id` en vez de copiar los campos:
    así no puede quedar desincronizado, se busca por clave primaria, y el
    criterio (`resultado_vm` máximo, empate -> menor `id`) es exactamente el
    mismo que usa el agregado en vivo cuando hay filtros, lo que permite
    comparar los dos caminos en los tests.
    """
    # Fila única: DELETE + INSERT es más corto que repetir los 8 campos en un
    # ON CONFLICT DO UPDATE, y el DELETE queda cubierto por la transacción de
    # la conexión (get_connection hace rollback si el INSERT falla).
    conn.execute("DELETE FROM resumen_global")
    conn.execute(
        """INSERT INTO resumen_global
             (id, registros_totales, localidades, provincias, cctes,
              promedio_pct, pico_vm, pico_id, actualizado_en)
           SELECT 1, g.registros_totales, g.localidades, g.provincias, g.cctes,
                  g.promedio_pct, g.pico_vm,
                  (SELECT m.id FROM mediciones m
                   WHERE m.resultado_vm = g.pico_vm
                   ORDER BY m.id ASC LIMIT 1),
                  ?
           FROM (
               SELECT COUNT(*) AS registros_totales,
                      -- La identidad de una localidad es su clave COMPLETA:
                      -- hay dos "San Pedro" (Catamarca y Santiago del
                      -- Estero) y contar solo `localidad` daba 60 en vez de
                      -- 61. char(31) es el unit separator de ASCII, no puede
                      -- aparecer en un nombre real. Ver obtener_kpis.
                      COUNT(DISTINCT ccte || char(31) || provincia || char(31) || localidad) AS localidades,
                      COUNT(DISTINCT provincia) AS provincias,
                      COUNT(DISTINCT ccte) AS cctes,
                      AVG(resultado_pct) AS promedio_pct,
                      MAX(resultado_vm) AS pico_vm
               FROM mediciones
           ) AS g""",
        (ahora,),
    )


def recalcular_punto_max(conn: sqlite3.Connection, ccte: str, provincia: str,
                         localidad: str) -> None:
    """Reconstruye los puntos máximos de UNA localidad (camino incremental).

    Es el que se ejecuta en cada import; el total se hace en cascada desde
    `statistics.recalcular_todo`. La query corre con el índice de
    `idx_mediciones_ccte_prov_loc` por las tres igualdades del WHERE, así que
    solo recorre las filas de ESTA localidad: 0,8 ms para una de 160 filas y
    384 ms para Neuquén (40.716), la más pesada de la base.

    El ORDER BY es `resultado_pct DESC, id ASC` y el `id` no es cosmético:
    Las Heras tiene 8 filas con exactamente el mismo `resultado_pct` (Río
    Gallegos 4, Río Primero y Choele Choel 2), así que sin desempate el punto
    que pinta el mapa podía cambiar entre renders.

    Se borra la localidad entera antes de insertar: si pasara a no tener
    ninguna fila con coordenadas, no debe quedar ningún punto viejo.
    """
    conn.execute(
        "DELETE FROM punto_max WHERE ccte = ? AND provincia = ? AND localidad = ?",
        (ccte, provincia, localidad),
    )
    conn.execute(
        """INSERT INTO punto_max
             (anio, ccte, provincia, localidad, id, lat, lon, resultado_vm, resultado_pct)
           SELECT anio, ccte, provincia, localidad, id, lat, lon, resultado_vm, resultado_pct
           FROM (
               SELECT anio, ccte, provincia, localidad, id, lat, lon, resultado_vm, resultado_pct,
                      ROW_NUMBER() OVER (PARTITION BY anio
                                         ORDER BY resultado_pct DESC, id ASC) AS rn
               FROM mediciones
               WHERE ccte = ? AND provincia = ? AND localidad = ?
                 AND lat IS NOT NULL AND lon IS NOT NULL
           )
           WHERE rn = 1""",
        (ccte, provincia, localidad),
    )


def listar_resumen_localidad(conn: sqlite3.Connection, ccte=None, provincia=None, localidad=None) -> list[dict]:
    condiciones, params = [], []
    if ccte:
        condiciones.append(f"ccte IN ({','.join('?' for _ in ccte)})")
        params += list(ccte)
    if provincia:
        condiciones.append(f"provincia IN ({','.join('?' for _ in provincia)})")
        params += list(provincia)
    if localidad:
        condiciones.append(f"localidad IN ({','.join('?' for _ in localidad)})")
        params += list(localidad)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    cur = conn.execute(f"SELECT * FROM resumen_localidad {where}", params)
    return [dict(r) for r in cur.fetchall()]


def listar_resumen_ccte(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM resumen_ccte")
    return [dict(r) for r in cur.fetchall()]
