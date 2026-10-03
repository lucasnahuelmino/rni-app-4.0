"""Acceso a datos de la tabla `mediciones`.

Único punto de la aplicación que arma SQL sobre esta tabla (evita repetir
el problema de la Auditoría Fase 1, hallazgo A10: el mapa leyendo la tabla
por un camino paralelo).
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Iterable

# Procedencia: cómo se llama en el dict que recibe el código (texto) y cómo
# queda en `mediciones` (id a la tabla de lookup). Ver schema.sql.
_PROCEDENCIA = {
    "expediente": ("expedientes", "expediente", "expediente_id"),
    "nombre_archivo": ("archivos", "nombre_archivo", "archivo_id"),
    "fecha_carga": ("cargas", "fecha_carga", "fecha_carga_id"),
}

# Los tres LEFT JOIN que resuelven id -> texto, con alias `m` para mediciones.
_JOINS = (
    "LEFT JOIN expedientes e ON e.id = m.expediente_id "
    "LEFT JOIN archivos    a ON a.id = m.archivo_id "
    "LEFT JOIN cargas      c ON c.id = m.fecha_carga_id"
)
_EXPRESION = {
    "expediente": "e.expediente",
    "nombre_archivo": "a.nombre_archivo",
    "fecha_carga": "c.fecha_carga",
}

# Las filas COMPLETAS con la procedencia ya resuelta a texto. Compartido con
# `services/reports.py`: un `SELECT *` a secas devolvería los `*_id` y los
# informes perderían `expediente` (agrupado por expediente) y `nombre_archivo`
# (por el que se mide el tiempo trabajado), que es la clase de cambio que no
# rompe un test pero sí cambia lo que se ve.
#
# Las 19 columnas de SIEMPRE, una por una y en el orden del esquema viejo:
# cada `*_id` entra por su join (texto) en el mismo lugar que ocupaba el
# texto, y los ids quedan FUERA porque no los lee nadie. Medido: con `m.*`
# las filas traían 22 columnas y el payload de los informes (que incluye
# `filas` enteras) crecía 12 %, de 304 a 341 MB -- misma cantidad de filas,
# sólo más ancho. Listarlas a mano también inmuniza contra una columna nueva
# que aparezca en `mediciones` y se cuelen sin querer en los DataFrames.
FILAS_COMPLETAS = (
    "m.id, m.ccte, m.provincia, m.localidad, m.resultado_vm, m.resultado_pct, "
    "m.fecha_raw, m.hora_raw, m.fecha_hora, m.anio, "
    "m.lat, m.lon, m.lat_raw, m.lon_raw, "
    "e.expediente, m.sonda, a.nombre_archivo, m.import_batch_id, c.fecha_carga "
    f"FROM mediciones m {_JOINS}"
)


def id_de_procedencia(conn: sqlite3.Connection, campo: str, valor,
                      cache: dict | None = None) -> int | None:
    """Texto -> id, dando de alta el valor si es el primero que aparece.

    `cache` es por lote: en una carga hay un solo expediente y un solo
    archivo, así que después de la primera fila todo es un lookup en memoria
    en vez de dos queries por fila.
    """
    if valor is None:
        return None
    tabla, columna, _ = _PROCEDENCIA[campo]
    clave = (tabla, valor)
    if cache is not None and clave in cache:
        return cache[clave]
    conn.execute(f"INSERT OR IGNORE INTO {tabla} ({columna}) VALUES (?)", (valor,))
    fila = conn.execute(f"SELECT id FROM {tabla} WHERE {columna} = ?", (valor,)).fetchone()
    if fila is None:
        raise RuntimeError(f"{campo}={valor!r} no quedó en la tabla {tabla}")
    if cache is not None:
        cache[clave] = fila[0]
    return fila[0]


def insertar_mediciones(conn: sqlite3.Connection, filas: list[dict]) -> list[int]:
    """Inserta filas nuevas y devuelve los ids generados.

    `filas` trae la procedencia como TEXTO (`expediente`, `nombre_archivo`,
    `fecha_carga`), como siempre: la traducción a id pasa acá, así el
    importador y la migración del esquema Streamlit no cambian.
    """
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
    columnas_sql = [_PROCEDENCIA[c][2] if c in _PROCEDENCIA else c for c in columnas]
    placeholders = ",".join("?" for _ in columnas)
    sql = f"INSERT INTO mediciones ({','.join(columnas_sql)}) VALUES ({placeholders})"

    ids = []
    cache: dict = {}
    cur = conn.cursor()
    for fila in filas:
        valores = []
        for c in columnas:
            valor = fila.get(c)
            if c in _PROCEDENCIA:
                valor = id_de_procedencia(conn, c, valor, cache)
            valores.append(valor)
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
    """Todas las filas de una localidad, con la procedencia ya como texto.

    Un `SELECT *` a secas ya no alcanza: `expediente`, `nombre_archivo` y
    `fecha_carga` ahora son ids. Los tres nombres de siempre siguen en el
    dict, porque de acá salen los expedientes del resumen y -- esto es lo que
    no se puede perder -- `agregar_mediciones`, que mide el tiempo trabajado
    agrupando por `nombre_archivo` SI la columna está presente
    (calculations/dates.py:106). Sin el join, `tiempo_trabajado_seg` cambiaría
    en silencio: dejaría de separar por archivo y sumaría max-min cruzando
    archivos distintos. `FILAS_COMPLETAS` trae sólo las 19 columnas de siempre
    (los `*_id` quedan afuera: no los lee nadie y sólo engordarían el dict).
    """
    cur = conn.execute(
        f"""SELECT {FILAS_COMPLETAS}
            WHERE m.ccte = ? AND m.provincia = ? AND m.localidad = ?""",
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
    partes: list[str] = []
    valores: list = []
    for campo, valor in sets.items():
        if campo == "expediente":
            # El texto vive en `expedientes`: si es un expediente nuevo hay
            # que darlo de alta primero, y el UPDATE se apunta al id.
            id_de_procedencia(conn, "expediente", valor)
            partes.append("expediente_id = (SELECT id FROM expedientes WHERE expediente = ?)")
        else:
            partes.append(f"{campo} = ?")
        valores.append(valor)
    valores += [ccte, provincia, localidad]
    cur = conn.execute(
        f"UPDATE mediciones SET {', '.join(partes)} WHERE ccte = ? AND provincia = ? AND localidad = ?",
        valores,
    )
    return cur.rowcount


def _columnas_resueltas(columnas: str) -> tuple[str, bool]:
    """`columnas` como la escribe el llamador -> SELECT con la procedencia ya
    resuelta. Devuelve (seleccion, hace_falta_join).

    El nombre que pidió el llamador queda EXACTAMENTE igual en la salida --
    sólo por dentro va al JOIN -- porque es la clave con la que después se
    busca en el dict: `test_agrupado_sql` pide `fecha_hora, nombre_archivo`
    y agrupa en pandas por `nombre_archivo`.
    """
    if columnas.strip() == "*":
        extra = ", ".join(f"{expr} AS {nombre}" for nombre, expr in _EXPRESION.items())
        return f"m.*, {extra}", True
    sql = columnas
    hace_join = False
    for nombre, expr in _EXPRESION.items():
        # El `(?<![\w.])` evita pisar `expediente_id`: si alguien lo pide
        # tal cual, el id NO se resuelve y hay que devolverlo como está.
        patron = rf"(?<![\w.]){re.escape(nombre)}(?![\w])"
        if re.search(patron, sql):
            hace_join = True
            sql = re.sub(patron, f"{expr} AS {nombre}", sql)
    return sql, hace_join


def query_filtrada(conn: sqlite3.Connection, ccte: Iterable[str] | None = None,
                    provincia: Iterable[str] | None = None, anio: Iterable[int] | None = None,
                    localidad: Iterable[str] | None = None, limit: int | None = None,
                    columnas: str = "*") -> list[dict]:
    """SELECT genérico con filtros opcionales -- usado por endpoints que
    necesitan filas individuales (mapa, histograma, tiempos trabajados).
    `columnas` permite pedir solo las columnas necesarias (ej. tiempos
    trabajados no necesita traer lat/lon/resultado)."""
    where, params = construir_where(ccte, provincia, anio, localidad)
    seleccion, con_join = _columnas_resueltas(columnas)
    desde = f"mediciones m {_JOINS}" if con_join else "mediciones m"
    sql = f"SELECT {seleccion} FROM {desde} {where}"
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
        "SELECT a.nombre_archivo, substr(m.fecha_hora, 1, 10) AS _dia, "
        "MIN(m.fecha_hora) AS min, MAX(m.fecha_hora) AS max "
        "FROM mediciones m "
        "LEFT JOIN archivos a ON a.id = m.archivo_id "
        f"{where} "
        "GROUP BY a.nombre_archivo, substr(m.fecha_hora, 1, 10)"
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
