"""Migra `mediciones` del layout viejo (texto repetido) al nuevo (ids).

Antes del lote de reducción de tamaño, `mediciones` guardaba `expediente`,
`nombre_archivo` y `fecha_carga` repetidos en cada fila: 132, 345 y 151
valores distintos promediando 32.7, 22.0 y 24.7 B = 27.2 MiB de payload sobre
las 359.414 filas actuales. Hoy cada uno vive en su tabla (`expedientes`,
`archivos`, `cargas`) y la medición guarda un id.

Corre sola desde `init_schema`, así que una base restaurada con `restore_db.py`
desde un respaldo anterior al cambio (`rni_20261002_2345.db` y los de antes)
termina funcionando sin pasos manuales. Si `mediciones` ya tiene el layout
nuevo no hace nada.

Se reconstruye la tabla entera en vez de `ADD COLUMN` + `DROP COLUMN` por dos
motivos: así el resultado queda idéntico al DDL de `schema.sql` (una base
recién creada y una migrada no pueden divergir), y porque `DROP COLUMN` no
puede cambiar `fecha_carga` de nullable a `NOT NULL`.

Todo corre dentro de la transacción de `get_connection`: si la verificación
falla, el `rollback` del context manager deshace la migración completa y la
base queda como estaba. La migración preserva `id` a propósito: `punto_max.id`
y `resumen_global.pico_id` apuntan a ids de `mediciones`.
"""
import sqlite3

_TABLA_TMP = "mediciones_nueva"

# De texto a id. Se resuelven por subconsulta: `init_schema` garantiza que los
# valores ya están en las tablas de lookup antes de tocar `mediciones`.
_SUB = {
    "expediente_id": "(SELECT e.id FROM expedientes e WHERE e.expediente = m.expediente)",
    "archivo_id": "(SELECT a.id FROM archivos a WHERE a.nombre_archivo = m.nombre_archivo)",
    "fecha_carga_id": "(SELECT c.id FROM cargas c WHERE c.fecha_carga = m.fecha_carga)",
}


def layout_viejo(conn: sqlite3.Connection) -> bool:
    """¿`mediciones` todavía tiene las columnas de texto?"""
    try:
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(mediciones)")}
    except sqlite3.Error:
        return False
    return "expediente" in columnas


def _sin_comentarios(sql: str) -> str:
    """Quita los `-- ...` de cada línea antes de contar paréntesis."""
    lineas = []
    for linea in sql.splitlines():
        cortado = linea.split("--", 1)[0]
        lineas.append(cortado)
    return "\n".join(lineas)


def _create_de_mediciones(schema_sql: str) -> str:
    """Extrae el `CREATE TABLE ... mediciones (...)` completo de `schema.sql`.

    Se corta por balanceo de paréntesis sobre el SQL ya sin comentarios: es la
    única forma de que la tabla migrada sea EXACTAMENTE la que define el
    esquema, sin un segundo DDL a mano que se pueda desincronizar.
    """
    marca = "CREATE TABLE IF NOT EXISTS mediciones ("
    inicio = schema_sql.find(marca)
    if inicio < 0:
        raise ValueError("schema.sql no tiene el CREATE TABLE de mediciones")
    limpio = _sin_comentarios(schema_sql)
    inicio = limpio.find(marca)
    if inicio < 0:
        raise ValueError("no se pudo leer el CREATE TABLE de mediciones")
    abierto = limpio.find("(", inicio)
    prof = 0
    for pos in range(abierto, len(limpio)):
        if limpio[pos] == "(":
            prof += 1
        elif limpio[pos] == ")":
            prof -= 1
            if prof == 0:
                bloque = limpio[inicio:pos + 1]
                return bloque.replace("CREATE TABLE IF NOT EXISTS mediciones",
                                      f"CREATE TABLE {_TABLA_TMP}", 1)
    raise ValueError("el CREATE TABLE de mediciones no cierra")


def _indices_de_mediciones(schema_sql: str) -> list[str]:
    lineas = []
    for linea in _sin_comentarios(schema_sql).splitlines():
        texto = linea.strip()
        if texto.upper().startswith("CREATE INDEX") and " ON mediciones(" in texto:
            lineas.append(texto)
    return lineas


def migrar(conn: sqlite3.Connection, schema_sql: str) -> int | None:
    """Rehace `mediciones` con el layout nuevo. `None` si no había nada que hacer.

    Devuelve cuántas filas migró. Lanza excepción (y así se revierte) si la
    verificación no da limpia.
    """
    if not layout_viejo(conn):
        return None

    # Acá todavía no hay transacción abierta (lo llama `init_schema` apenas
    # salió `executescript`) y ese es el ÚNICO momento en que esta pragma hace
    # algo: adentro de una transacción SQLite la ignora. Por lo mismo, el
    # `foreign_keys=ON` del final va después del commit de abajo.
    conn.execute("PRAGMA foreign_keys=OFF")

    filas_viejas = conn.execute("SELECT COUNT(*) FROM mediciones").fetchone()[0]
    ids_viejos = [r[0] for r in conn.execute("SELECT id FROM mediciones ORDER BY id")]

    # 1) tablas de lookup, con lo que hoy hay repetido en cada fila
    for ddl, origen, columna in (
        ("INSERT OR IGNORE INTO expedientes (expediente) "
         "SELECT DISTINCT expediente FROM mediciones WHERE expediente IS NOT NULL",
         "expedientes", "expediente"),
        ("INSERT OR IGNORE INTO archivos (nombre_archivo) "
         "SELECT DISTINCT nombre_archivo FROM mediciones WHERE nombre_archivo IS NOT NULL",
         "archivos", "nombre_archivo"),
        ("INSERT OR IGNORE INTO cargas (fecha_carga) "
         "SELECT DISTINCT fecha_carga FROM mediciones WHERE fecha_carga IS NOT NULL",
         "cargas", "fecha_carga"),
    ):
        esperado = conn.execute(
            f"SELECT COUNT(DISTINCT {columna}) FROM mediciones"
            f" WHERE {columna} IS NOT NULL").fetchone()[0]
        conn.execute(ddl)
        obtenido = conn.execute(f"SELECT COUNT(*) FROM {origen}").fetchone()[0]
        if obtenido < esperado:
            raise RuntimeError(
                f"{origen}: quedaron {esperado - obtenido} valores sin tabla propia")

    # 2) tabla nueva con el DDL de schema.sql
    conn.execute(_create_de_mediciones(schema_sql))
    nuevas = [r[1] for r in conn.execute(f"PRAGMA table_info({_TABLA_TMP})")]
    viejas = {r[1] for r in conn.execute("PRAGMA table_info(mediciones)")}
    seleccionadas = []
    for columna in nuevas:
        if columna in _SUB:
            seleccionadas.append(f"{_SUB[columna]} AS {columna}")
        elif columna in viejas:
            seleccionadas.append(f"m.{columna}")
        else:
            raise RuntimeError(f"no sé de dónde sale la columna nueva {columna}")
    conn.execute(
        f"INSERT INTO {_TABLA_TMP} ({','.join(nuevas)}) "
        f"SELECT {','.join(seleccionadas)} FROM mediciones m")

    # 3) verifico ANTES de borrar: si algo falla, el rollback devuelve la base
    #    como estaba (el DROP y el RENAME todavía no corrieron).
    filas_nuevas = conn.execute(f"SELECT COUNT(*) FROM {_TABLA_TMP}").fetchone()[0]
    if filas_nuevas != filas_viejas:
        raise RuntimeError(f"se copiaron {filas_nuevas} de {filas_viejas} filas")
    ids_nuevos = [r[0] for r in conn.execute(f"SELECT id FROM {_TABLA_TMP} ORDER BY id")]
    if ids_nuevos != ids_viejos:
        raise RuntimeError("cambiaron los ids de mediciones (punto_max apunta a ellos)")
    for columna in _SUB:
        nulos = conn.execute(
            f"SELECT COUNT(*) FROM {_TABLA_TMP} WHERE {columna} IS NULL").fetchone()[0]
        if nulos:
            raise RuntimeError(f"{columna}: {nulos} filas quedaron sin resolver")

    # 4) recambio. Sin esto el DROP se llevaría los índices, así que se vuelven
    #    a crear con el mismo nombre (map.py los cita con INDEXED BY).
    conn.execute("DROP TABLE mediciones")
    conn.execute(f"ALTER TABLE {_TABLA_TMP} RENAME TO mediciones")
    indices = _indices_de_mediciones(schema_sql)
    for ddl in indices:
        conn.execute(ddl)

    if not indices:
        raise RuntimeError("schema.sql no devolvió ningún índice de mediciones")
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("integrity_check da error después de migrar")
    if list(conn.execute("PRAGMA foreign_key_check")):
        raise RuntimeError("foreign_key_check da problemas después de migrar")

    # Punto sin retorno: hasta acá todo lo anterior era una transacción
    # abierta y una excepción deshacía el DROP y el RENAME también. Recién
    # ahora se fija, y después puede volver a habilitar las claves foráneas
    # (que de otro modo quedaría en OFF: la pragma no corre con transacción).
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    return filas_nuevas
