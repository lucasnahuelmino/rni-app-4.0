"""Acceso a las tablas de resumen (resumen_localidad, resumen_ccte, ...,
resumen_global) y de la tabla derivada `punto_max`."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from app.db.repositories.mediciones_repo import construir_where


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


def listar_resumen_localidad(conn: sqlite3.Connection, ccte=None, provincia=None,
                             localidad=None, anio=None) -> list[dict]:
    """Resumen por localidad con los filtros del panel global.

    Es la puerta única de `/localities`, `/top-localities` y el Excel de
    Resumen, y por eso el año entra ACÁ: `resumen_localidad` se guarda por
    clave (ccte, provincia, localidad) sin columna de año, así que con un
    filtro de año puesto esta función devolvía exactamente los mismos
    renglones que sin filtro. La tabla responde a ccte/provincia/localidad;
    cuando hay año hay que recalcular sobre `mediciones`
    (`listar_resumen_localidad_en_vivo`), y centralizarlo acá hace que ninguno
    de los tres consumidores vuelva a olvidarse.
    """
    if anio:
        return listar_resumen_localidad_en_vivo(
            conn, ccte=ccte, provincia=provincia, localidad=localidad, anio=anio,
        )

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


def _set_ordenado(valor: str | None) -> str:
    """Set ordenado de valores unido por coma: el criterio de
    `services/statistics.recalcular` (que arma `sorted(set(...))`).

    En la base no hay ni un expediente ni una sonda con coma (medido sobre
    las 219.818 filas), así que separar lo que devuelve `group_concat` da
    exactamente el mismo set que arma Python.
    """
    if not valor:
        return ""
    return ",".join(sorted(v for v in valor.split(",") if v))


def grupos_tiempo_trabajado(conn: sqlite3.Connection, where: str, params: list) -> list[dict]:
    """MIN/MAX de `fecha_hora` por localidad, archivo y día.

    Es el dato crudo del que sale `tiempo_trabajado_seg`: el mismo
    agrupamiento que usa `calculations/statistics.agregar_mediciones` (por
    `nombre_archivo` y por día, sumando max-min de cada grupo), corrido en
    SQL -- 241 grupos en vez de 219.818 filas. `where`/`params` salen de
    `mediciones_repo.construir_where`, así que el tiempo respeta el mismo
    filtro que el resto de la fila.
    """
    cur = conn.execute(
        f"""SELECT ccte, provincia, localidad, a.nombre_archivo,
                   substr(fecha_hora, 1, 10) AS dia,
                   MIN(fecha_hora) AS desde, MAX(fecha_hora) AS hasta
            FROM mediciones m
            LEFT JOIN archivos a ON a.id = m.archivo_id
            {where} {"AND" if where else "WHERE"} fecha_hora IS NOT NULL
            GROUP BY ccte, provincia, localidad, a.nombre_archivo, substr(fecha_hora, 1, 10)""",
        params,
    )
    return [dict(r) for r in cur.fetchall()]


def listar_resumen_localidad_en_vivo(conn: sqlite3.Connection, ccte=None, provincia=None,
                                     localidad=None, anio=None) -> list[dict]:
    """`resumen_localidad` calculado EN VIVO con filtros que la tabla no puede
    responder.

    La tabla se guarda por clave (ccte, provincia, localidad) y resume toda la
    historia: no tiene columna de año, así que `GET /localities?anio=2025`
    devolvía los mismos 61 renglones y los mismos 34.303 bytes que sin filtro
    (medido). Con el año activo hay que agregar de nuevo sobre `mediciones`.

    Se corre en SQL y no cargando las filas a pandas (el camino de
    `services/statistics.recalcular`) porque 2026 tiene 202.296 filas: en vivo
    eso sería cerca de un segundo por consulta contra un scan de ~100 ms.

    Los criterios son los de `calculations/statistics.agregar_mediciones`, que
    es el que pobla la tabla:

      * máximo de V/m y de %, promedio de %, primera y última fecha;
      * `resultado_prom_pct` = promedio de `resultado_pct`, que es lo que hace
        `promedio_pct_de_valores` con los valores de V/m fila por fila;
      * expedientes y sondas: set ordenado unido por coma;
      * `tiempo_trabajado_seg`: suma de max-min por archivo y por día
        (`grupos_tiempo_trabajado`);
      * `dias_con_medicion`: fechas COMPLETAS distintas -- un solo registro a
        las 00:00 y otro a las 23:00 son dos días, no uno.

    El orden es el de la tabla (`ccte, provincia, localidad`, que es su clave
    primaria): con y sin año la lista arranca igual.
    """
    where, params = construir_where(ccte, provincia, anio, localidad)

    filas = [
        dict(r)
        for r in conn.execute(
            f"""SELECT ccte, provincia, localidad,
                       COUNT(*) AS mediciones,
                       MAX(resultado_vm) AS resultado_max_vm,
                       MAX(resultado_pct) AS resultado_max_pct,
                       AVG(resultado_pct) AS resultado_prom_pct,
                       MIN(fecha_hora) AS fecha_inicio,
                       MAX(fecha_hora) AS fecha_fin,
                       COUNT(DISTINCT substr(fecha_hora, 1, 10)) AS dias_con_medicion,
                       group_concat(DISTINCT e.expediente) AS expedientes,
                       group_concat(DISTINCT sonda) AS sondas
                FROM mediciones m
                LEFT JOIN expedientes e ON e.id = m.expediente_id
                {where}
                GROUP BY ccte, provincia, localidad
                ORDER BY ccte, provincia, localidad""",
            params,
        )
    ]

    # timedelta y no segundos sueltos: la suma queda exacta (microsegundos
    # enteros) y el `int()` final trunca igual que en pandas.
    tiempos: dict[tuple, timedelta] = {}
    for grupo in grupos_tiempo_trabajado(conn, where, params):
        clave = (grupo["ccte"], grupo["provincia"], grupo["localidad"])
        duracion = datetime.fromisoformat(grupo["hasta"]) - datetime.fromisoformat(grupo["desde"])
        tiempos[clave] = tiempos.get(clave, timedelta()) + duracion

    for fila in filas:
        clave = (fila["ccte"], fila["provincia"], fila["localidad"])
        fila["expedientes"] = _set_ordenado(fila["expedientes"])
        fila["sondas"] = _set_ordenado(fila["sondas"])
        fila["tiempo_trabajado_seg"] = int(tiempos.get(clave, timedelta()).total_seconds())
        # `actualizado_en` es la marca del recálculo que persistió la fila.
        # Ésta no se persistió (es un cálculo del pedido), así que no hay
        # marca que mostrar: null y no una fecha inventada.
        fila["actualizado_en"] = None
    return filas
