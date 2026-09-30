/* ==========================================================================
   base.js — capa de datos.

   SQLite compilado a WebAssembly (sql.js) corriendo EN EL NAVEGADOR sobre la
   copia en memoria del archivo. Dos garantías de sólo lectura:

     1. el archivo se abre con FileReader, nunca con un sistema de archivos:
        el visor no tiene forma de escribir en el disco;
     2. apenas se conecta se ejecuta `PRAGMA query_only = ON`, así que aunque
        alguna consulta intentara un INSERT/UPDATE, SQLite la rechaza.

   Ninguna función de este módulo modifica la base.
   ========================================================================== */

let SQL = null   // espacio de nombres de sql.js (cargado una sola vez)
let db = null    // conexión a la base abierta

/** Estado global que leen las vistas y la barra lateral. */
export const base = {
  nombre: '',
  filas: 0,
  tablas: [],
  mediciones: 0,
  localidades: 0,
}

/** Carga el motor (js + wasm) desde vendor/. Una sola vez. */
export async function prepararMotor() {
  if (SQL) return SQL
  if (typeof initSqlJs !== 'function') {
    throw new Error(
      'No se pudo cargar vendor/sql-wasm.js. Revisá que la carpeta vendor/ ' +
      'esté completa y junto al index.html.')
  }
  SQL = await initSqlJs({
    // la URL se arma contra document.baseURI: funciona igual si el visor
    // queda en la raíz del servidor o en una subcarpeta
    locateFile: (archivo) => new URL('vendor/' + archivo, document.baseURI).href,
  })
  return SQL
}

/** Abre un archivo .db elegido o arrastrado. Devuelve el estado `base`. */
export async function abrirArchivo(archivo) {
  await prepararMotor()
  cerrar()

  if (!archivo) throw new Error('No se seleccionó ningún archivo.')
  if (archivo.size === 0) {
    throw new Error('El archivo "' + archivo.name + '" está vacío (0 bytes).')
  }
  if (!/\.(db|sqlite|sqlite3|db3)$/i.test(archivo.name)) {
    throw new Error('"' + archivo.name + '" no parece una base SQLite. ' +
      'Se espera un archivo .db (por ejemplo rni.db).')
  }

  const bytes = await archivo.arrayBuffer()
  let instancia
  try {
    instancia = new SQL.Database(new Uint8Array(bytes))
  } catch (e) {
    throw new Error('No se pudo abrir "' + archivo.name + '" como base SQLite: ' + e.message)
  }

  try {
    // Conexión de sólo lectura a partir de acá (ver encabezado del archivo).
    instancia.exec('PRAGMA query_only = ON')
    instancia.exec('SELECT name FROM sqlite_master LIMIT 1')
  } catch (e) {
    instancia.close()
    throw new Error('"' + archivo.name + '" no es una base SQLite válida ' +
      '(puede estar corrupta o ser otro tipo de archivo).')
  }

  db = instancia
  base.nombre = archivo.name
  base.tablas = listarTablas()

  if (base.tablas.length === 0) {
    cerrar()
    throw new Error('La base no tiene tablas: ¿será un archivo recién creado?')
  }

  const esperadas = ['mediciones', 'resumen_localidad', 'punto_max']
  if (!esperadas.some((t) => base.tablas.includes(t))) {
    const vistas = base.tablas.join(', ')
    cerrar()
    throw new Error('No parece una base RNI: faltan las tablas mediciones, ' +
      'resumen_localidad y punto_max. Tablas encontradas: ' + vistas + '.')
  }

  base.mediciones = contarFilas('mediciones')
  base.localidades = contarLocalidades()
  base.filas = base.mediciones + contarFilas('resumen_localidad') + contarFilas('punto_max')

  if (base.filas === 0) {
    const vacia = base.nombre
    cerrar()
    throw new Error('La base "' + vacia + '" está vacía: no tiene mediciones ' +
      'ni tablas de resumen.')
  }

  return base
}

/** Cierra la conexión actual (si la hay) y limpia el estado. */
export function cerrar() {
  if (db) { try { db.close() } catch (e) { /* ya cerrada */ } }
  db = null
  base.nombre = ''
  base.filas = 0
  base.tablas = []
  base.mediciones = 0
  base.localidades = 0
}

function exigirBase() {
  if (!db) throw new Error('No hay ninguna base cargada.')
  return db
}

/** ¿Existe la tabla? */
export function tieneTabla(nombre) {
  exigirBase()
  return base.tablas.includes(nombre)
}

/** Nombres de las tablas del usuario (sin las internas de SQLite). */
function listarTablas() {
  const salida = []
  for (const fila of select(
    "SELECT name FROM sqlite_master WHERE type = 'table' " +
    "AND name NOT LIKE 'sqlite_%' ORDER BY name")) {
    salida.push(fila.name)
  }
  return salida
}

function contarFilas(tabla) {
  if (!tieneTabla(tabla)) return 0
  return Number(primero('SELECT COUNT(*) AS n FROM "' + tabla + '"')?.n || 0)
}

function contarLocalidades() {
  if (tieneTabla('resumen_localidad')) {
    return contarFilas('resumen_localidad')
  }
  if (tieneTabla('mediciones')) {
    return Number(primero('SELECT COUNT(DISTINCT localidad) AS n FROM mediciones')?.n || 0)
  }
  return 0
}

/** Ejecuta un SELECT y devuelve un array de objetos (uno por fila). */
export function select(sql, params = []) {
  const conexion = exigirBase()
  const stmt = conexion.prepare(sql)
  const salida = []
  try {
    stmt.bind(params)
    while (stmt.step()) salida.push(stmt.getAsObject())
  } finally {
    stmt.free()
  }
  return salida
}

/** Primera fila de un SELECT, o undefined. */
export function primero(sql, params = []) {
  return select(sql, params)[0]
}

/** COUNT(*) de un SELECT, o 0. */
export function contar(sql, params = []) {
  const fila = primero(sql, params)
  if (!fila) return 0
  const clave = Object.keys(fila)[0]
  return Number(fila[clave] || 0)
}
