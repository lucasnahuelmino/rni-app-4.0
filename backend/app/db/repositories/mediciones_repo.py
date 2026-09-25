"""Acceso a datos de la tabla `mediciones`.

Único punto de la aplicación que arma SQL sobre esta tabla (evita repetir
el problema de la Auditoría Fase 1, hallazgo A10: el mapa leyendo la tabla
por un camino paralelo).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable


def insertar_mediciones(conn: sqlite3.Connection, filas: list[dict]) -> list[int]:
    """Inserta filas nuevas y devuelve los ids generados."""
    if not filas:
        return []

    columnas = [
        "ccte", "provincia", "localidad",
        "resultado_vm", "resultado_pct",
        "fecha_raw", "hora_raw", "fecha_hora", "anio",
        "lat", "lon", "lat_raw", "lon_raw",
        "expediente", "sonda", "nombre_archivo",
        "import_batch_id", "fecha_carga",
    ]
    placeholders = ",".join("?" for _ in columnas)
    sql = f"INSERT INTO mediciones ({','.join(columnas)}) VALUES ({placeholders})"

    ids = []
    cur = conn.cursor()
    for fila in filas:
        valores = [fila.get(c) for c in columnas]
        cur.execute(sql, valores)
        ids.append(cur.lastrowid)
    return ids


def existe_medicion(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str,
                     fecha_hora: str | None, resultado_vm: float | None) -> bool:
    """Detección de duplicados por contenido (no solo por nombre de archivo,
    a diferencia del sistema Streamlit actual -- Auditoría Fase 1, hallazgo
    sobre `carga_excel.py`).

    La clave es la identidad COMPLETA (ccte, provincia, localidad), la misma
    que usan todas las demás funciones de este módulo. Sin `provincia`, dos
    localidades homónimas del mismo CCTE se pisaban: en la base real hay dos
    "San Pedro" (Catamarca y Santiago del Estero), ambas bajo el CCTE Salta,
    y cargar la segunda hacía que todas sus mediciones contaran como
    duplicados de la primera y se descartaran en silencio.
    """
    cur = conn.execute(
        """SELECT 1 FROM mediciones
           WHERE ccte = ? AND provincia = ? AND localidad = ?
             AND fecha_hora IS ? AND resultado_vm IS ?
           LIMIT 1""",
        (ccte, provincia, localidad, fecha_hora, resultado_vm),
    )
    return cur.fetchone() is not None


def claves_por_batch(conn: sqlite3.Connection, batch_id: int) -> list[tuple[str, str, str]]:
    """(ccte, provincia, localidad) distintos insertados por un lote -- usado
    para saber qué resúmenes recalcular tras un import."""
    cur = conn.execute(
        """SELECT DISTINCT ccte, provincia, localidad FROM mediciones
           WHERE import_batch_id = ?""",
        (batch_id,),
    )
    return [(r["ccte"], r["provincia"], r["localidad"]) for r in cur.fetchall()]


def filas_por_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> list[dict]:
    cur = conn.execute(
        """SELECT * FROM mediciones WHERE ccte = ? AND provincia = ? AND localidad = ?""",
        (ccte, provincia, localidad),
    )
    return [dict(r) for r in cur.fetchall()]


def periodos_por_localidad(conn: sqlite3.Connection, ccte: str, provincia: str,
                           localidad: str) -> tuple[set[int], set[str]]:
    """(años, meses "YYYY-MM") que ocupa esta localidad.

    Se tiene que leer ANTES de un DELETE: una vez borradas las filas no hay
    forma de saber qué filas de `resumen_anual`/`resumen_mensual` quedaron
    desactualizadas. Ver `services/measurements.eliminar_localidad`.
    """
    cur = conn.execute(
        """SELECT DISTINCT anio FROM mediciones
           WHERE ccte = ? AND provincia = ? AND localidad = ? AND anio IS NOT NULL""",
        (ccte, provincia, localidad),
    )
    anios = {int(r["anio"]) for r in cur.fetchall()}

    cur = conn.execute(
        """SELECT DISTINCT substr(fecha_hora, 1, 7) AS mes FROM mediciones
           WHERE ccte = ? AND provincia = ? AND localidad = ?
             AND fecha_hora IS NOT NULL AND fecha_hora <> ''""",
        (ccte, provincia, localidad),
    )
    meses = {r["mes"] for r in cur.fetchall() if r["mes"]}
    return anios, meses


def eliminar_por_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> int:
    cur = conn.execute(
        "DELETE FROM mediciones WHERE ccte = ? AND provincia = ? AND localidad = ?",
        (ccte, provincia, localidad),
    )
    return cur.rowcount


def actualizar_metadata_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str,
                                   nuevos: dict) -> int:
    """UPDATE dirigido sobre las filas de una localidad (reemplaza el patrón
    'borrar+reinsertar toda la tabla' del sistema actual -- Auditoría Fase 1,
    hallazgo A8)."""
    campos_permitidos = {"ccte", "provincia", "localidad", "expediente"}
    sets = {k: v for k, v in nuevos.items() if k in campos_permitidos}
    if not sets:
        return 0
    set_clause = ", ".join(f"{k} = ?" for k in sets)
    valores = list(sets.values()) + [ccte, provincia, localidad]
    cur = conn.execute(
        f"UPDATE mediciones SET {set_clause} WHERE ccte = ? AND provincia = ? AND localidad = ?",
        valores,
    )
    return cur.rowcount


def query_filtrada(conn: sqlite3.Connection, ccte: Iterable[str] | None = None,
                    provincia: Iterable[str] | None = None, anio: Iterable[int] | None = None,
                    localidad: Iterable[str] | None = None, limit: int | None = None,
                    columnas: str = "*") -> list[dict]:
    """SELECT genérico con filtros opcionales -- usado por endpoints que
    necesitan filas individuales (mapa, histograma, tiempos trabajados).
    `columnas` permite pedir solo las columnas necesarias (ej. tiempos
    trabajados no necesita traer lat/lon/resultado)."""
    where, params = construir_where(ccte, provincia, anio, localidad)
    sql = f"SELECT {columnas} FROM mediciones {where}"
    if limit:
        sql += " LIMIT ?"
        params = params + [limit]
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def agrupar_min_max_por_archivo_dia(conn: sqlite3.Connection, ccte=None, provincia=None,
                                    anio=None, localidad=None) -> list[dict]:
    """MIN/MAX de `fecha_hora` por (nombre_archivo, dia), agrupado en SQL.

    Devuelve exactamente la salida de `_agrupar_por_archivo_dia` de
    `calculations/dates.py` (nombre_archivo, _dia, min, max) pero dejando la
    agregación en SQLite en vez de arrastrar todas las filas a Python.

    Motivo: el desglose diario/mensual del Centro operativo necesita
    `fecha_hora` + `nombre_archivo` de TODAS las mediciones para quedarse con
    241 grupos. Medido en la base real (219 818 filas) el camino anterior era
    0,78 s de fetch + construir un DataFrame de 219 818 filas + parsear 219
    818 datetime + agrupar en pandas: ~2,8 s solo en la vista General, y 17-21
    s cuando la vista dispara sus cinco pedidos a la vez (CPU puro, el GIL
    los serializa y ninguno termina a tiempo). El agregado en SQL son 0,43 s
    y 241 filas.

    Comparar `fecha_hora` como texto es legible porque es ISO de longitud
    fija (`2025-12-03T09:13:15`): lexicográficamente ordena igual que
    cronológicamente, `substr(fecha_hora, 1, 10)` es el día y
    `substr(fecha_hora, 12, 8)` la hora en el mismo formato que daba
    `strftime("%H:%M:%S")`. Verificado contra los 241 grupos reales:
    igualdad exacta con pandas. Lo cubre
    `test_tiempos.py::test_agrupado_en_sql_igual_que_en_pandas`, que es lo
    que avisa si alguien cambia uno de los dos lados.

    El `fecha_hora IS NOT NULL` es el mismo `dropna` que hace pandas: la
    columna es nullable (hoy tiene 0 nulos, pero nada la obliga a serlo).
    """
    where, params = construir_where(ccte, provincia, anio, localidad)
    condicion = "fecha_hora IS NOT NULL"
    where = f"{where} AND {condicion}" if where else f"WHERE {condicion}"
    sql = (
        "SELECT nombre_archivo, substr(fecha_hora, 1, 10) AS _dia, "
        "MIN(fecha_hora) AS min, MAX(fecha_hora) AS max "
        f"FROM mediciones {where} "
        "GROUP BY nombre_archivo, substr(fecha_hora, 1, 10)"
    )
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _a_lista(valor: Any) -> list[Any]:
    """Un valor suelto o varios -> lista, para los IN () de `construir_where`.

    Sin esto, `list("Córdoba")` da `['C', 'ó', 'r', 'd', 'o', 'b', 'a']`: la
    query queda `ccte IN ('C','ó',...)`, no matchea ninguna fila y el
    endpoint devuelve una lista VACÍA sin fallar. Es el peor tipo de bug que
    puede dejar acá un `list()` a secas, porque nadie se entera -- el dato no
    aparece y parece que no había datos.

    Un número solo (un `anio=2025`) entra por el mismo camino: antes tiraba
    `TypeError: 'int' object is not iterable`, que al menos explotaba.
    """
    if valor is None:
        return []
    if isinstance(valor, (str, int, float)):
        return [valor]
    return list(valor)


def construir_where(ccte, provincia, anio, localidad=None) -> tuple[str, list[Any]]:
    condiciones = []
    params: list[Any] = []
    if ccte:
        ccte = _a_lista(ccte)
        condiciones.append(f"ccte IN ({','.join('?' for _ in ccte)})")
        params += ccte
    if provincia:
        provincia = _a_lista(provincia)
        condiciones.append(f"provincia IN ({','.join('?' for _ in provincia)})")
        params += provincia
    if anio:
        anio = _a_lista(anio)
        condiciones.append(f"anio IN ({','.join('?' for _ in anio)})")
        params += anio
    if localidad:
        localidad = _a_lista(localidad)
        condiciones.append(f"localidad IN ({','.join('?' for _ in localidad)})")
        params += localidad
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return where, params
