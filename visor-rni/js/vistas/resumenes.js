/* ==========================================================================
   vistas/resumenes.js — Resúmenes: agregados de la base.

   Una pestaña por cada forma que tiene la base de expresarse:

     Por centro        `resumen_ccte`       (si no existe, se agrupa en vivo)
     Por mes           agrupado de `mediciones`
                       (`resumen_mensual` sólo guarda mes + cantidad: se usa
                        como respaldo si la base no tiene `mediciones`)
     Por año           `resumen_anual`      (si no, en vivo)
     Por provincia     `resumen_provincia`  (si no, en vivo)
     Provincia y CCTE  `resumen_provincia_ccte` (si no, en vivo)
     En general        `resumen_global` + rangos de `mediciones`

   Todo se pinta con el mismo motor de columnas, así la exportación a Excel
   refleja exactamente lo que se ve, con los valores crudos de la base.
   ========================================================================== */

import { primero, select, tieneTabla } from '../base.js'
import { completarCcte } from '../ccte.js'
import {
  entero, pct, vm, fecha, momento, duracion, mesLegible,
} from '../formato.js'
import { $, celda, vaciar, error } from '../ui.js'
import { exportarXLSX } from '../exportar.js'

/* ------------------------------ formato ------------------------------- */

/** texto → tal cual; el resto pasa por formato.js (es-AR). */
function formatear(tipo, valor) {
  if (valor === null || valor === undefined || valor === '') {
    if (tipo === 'entero' || tipo === 'vm' || tipo === 'pct' ||
        tipo === 'fecha' || tipo === 'momento' || tipo === 'duracion' ||
        tipo === 'mes') return '—'
    return '—'
  }
  switch (tipo) {
    case 'entero': return entero(valor)
    // el año es un número, no una cantidad: sin separador de miles
    case 'anio': return String(valor)
    case 'vm': return vm(valor)
    case 'pct': return pct(valor)
    case 'porcentaje': return pct(valor) + ' %'
    case 'fecha': return fecha(valor)
    case 'momento': return momento(valor)
    case 'duracion': return duracion(valor)
    case 'mes': return mesLegible(valor)
    default: return String(valor)
  }
}

/** Formato numérico de Excel por tipo (los valores van crudos a la celda). */
const FORMATO_EXCEL = {
  entero: '0',
  anio: '0',
  vm: '0.###',
  pct: '0.####',
  porcentaje: '0.####',
  duracion: '0',
  texto: null,
  fecha: null,
  momento: null,
  mes: null,
  variable: '0.####',
}

/* ------------------------------ pestañas ------------------------------ */
/* Cada columna: clave, título, tipo ('texto'…) y `num` para alinear a la
   derecha. La pestaña "general" usa tipo 'variable': formatea fila a fila. */

const COL_ACT = { clave: 'actualizado_en', titulo: 'Actualizado', tipo: 'momento' }

function columnasCcte() {
  return [
    { clave: 'ccte', titulo: 'CCTE', tipo: 'texto' },
    { clave: 'mediciones', titulo: 'Mediciones', tipo: 'entero', num: true },
    { clave: 'localidades', titulo: 'Localidades', tipo: 'entero', num: true },
    { clave: 'provincias', titulo: 'Provincias', tipo: 'entero', num: true },
    { clave: 'resultado_max_vm', titulo: 'Pico V/m', tipo: 'vm', num: true },
    { clave: 'resultado_max_pct', titulo: 'Pico % RNI', tipo: 'pct', num: true },
    { clave: 'localidad_max', titulo: 'Localidad del pico', tipo: 'texto' },
    { clave: 'dias_con_medicion', titulo: 'Días con medición', tipo: 'entero', num: true },
    { clave: 'tiempo_trabajado_seg', titulo: 'Tiempo trabajado', tipo: 'duracion', num: true },
    COL_ACT,
  ]
}

function columnasMes() {
  return [
    { clave: 'mes', titulo: 'Mes', tipo: 'mes' },
    { clave: 'mediciones', titulo: 'Mediciones', tipo: 'entero', num: true },
    { clave: 'localidades', titulo: 'Localidades', tipo: 'entero', num: true },
    { clave: 'provincias', titulo: 'Provincias', tipo: 'entero', num: true },
    { clave: 'cctes', titulo: 'Centros', tipo: 'entero', num: true },
    { clave: 'promedio_pct', titulo: 'Promedio % RNI', tipo: 'pct', num: true },
    { clave: 'resultado_max_vm', titulo: 'Pico V/m', tipo: 'vm', num: true },
    { clave: 'resultado_max_pct', titulo: 'Pico % RNI', tipo: 'pct', num: true },
    { clave: 'fecha_inicio', titulo: 'Primer día', tipo: 'fecha', num: true },
    { clave: 'fecha_fin', titulo: 'Último día', tipo: 'fecha', num: true },
    { clave: 'dias_con_medicion', titulo: 'Días', tipo: 'entero', num: true },
  ]
}

function columnasAnio() {
  return [
    { clave: 'anio', titulo: 'Año', tipo: 'anio', num: true },
    { clave: 'mediciones', titulo: 'Mediciones', tipo: 'entero', num: true },
    { clave: 'localidades', titulo: 'Localidades', tipo: 'entero', num: true },
    { clave: 'provincias', titulo: 'Provincias', tipo: 'entero', num: true },
    { clave: 'cctes', titulo: 'Centros', tipo: 'entero', num: true },
    { clave: 'resultado_max_vm', titulo: 'Pico V/m', tipo: 'vm', num: true },
    { clave: 'resultado_max_pct', titulo: 'Pico % RNI', tipo: 'pct', num: true },
    COL_ACT,
  ]
}

function columnasProvincia() {
  return [
    { clave: 'provincia', titulo: 'Provincia', tipo: 'texto' },
    { clave: 'mediciones', titulo: 'Mediciones', tipo: 'entero', num: true },
    { clave: 'localidades', titulo: 'Localidades', tipo: 'entero', num: true },
    { clave: 'cctes', titulo: 'Centros', tipo: 'entero', num: true },
    { clave: 'resultado_max_vm', titulo: 'Pico V/m', tipo: 'vm', num: true },
    { clave: 'resultado_max_pct', titulo: 'Pico % RNI', tipo: 'pct', num: true },
    { clave: 'localidad_max', titulo: 'Localidad del pico', tipo: 'texto' },
    COL_ACT,
  ]
}

function columnasProvinciaCcte() {
  return [
    { clave: 'provincia', titulo: 'Provincia', tipo: 'texto' },
    { clave: 'ccte', titulo: 'CCTE', tipo: 'texto' },
    { clave: 'localidades', titulo: 'Localidades', tipo: 'entero', num: true },
    { clave: 'mediciones', titulo: 'Mediciones', tipo: 'entero', num: true },
    COL_ACT,
  ]
}

function columnasGeneral() {
  return [
    { clave: 'indicador', titulo: 'Indicador', tipo: 'texto' },
    { clave: 'valor', titulo: 'Valor', tipo: 'variable', num: true },
  ]
}

/* ------------------------------- datos -------------------------------- */

/** Localidad = tupla completa (hay dos "San Pedro"; ver vistas/inicio.js). */
const TUPLA =
  'ccte || char(31) || provincia || char(31) || localidad'

function exigir(tablas, mensaje) {
  if (tablas.some((t) => tieneTabla(t))) return
  throw new Error(mensaje)
}

function cargarCcte() {
  exigir(['resumen_ccte', 'mediciones'], 'Esta base no tiene la tabla ' +
    '"resumen_ccte" ni "mediciones": no hay nada para resumir.')

  if (tieneTabla('resumen_ccte')) {
    return completarCcte(select('SELECT * FROM resumen_ccte'))
  }

  const filas = select(`
    SELECT ccte,
           COUNT(*)                                  AS mediciones,
           COUNT(DISTINCT provincia || char(31) || localidad) AS localidades,
           COUNT(DISTINCT provincia)                 AS provincias,
           MAX(resultado_vm)                         AS resultado_max_vm,
           MAX(resultado_pct)                        AS resultado_max_pct,
           COUNT(DISTINCT substr(fecha_hora, 1, 10)) AS dias_con_medicion
      FROM mediciones GROUP BY ccte`)

  for (const f of filas) {
    const p = primero(
      'SELECT localidad FROM mediciones WHERE ccte = ? ' +
      'ORDER BY resultado_vm DESC, id ASC LIMIT 1', [f.ccte])
    f.localidad_max = p ? p.localidad : null
    f.tiempo_trabajado_seg = null
    f.actualizado_en = null
  }

  // siempre los 7 CCTE (ver js/ccte.js)
  return completarCcte(filas)
}

function cargarMes() {
  if (tieneTabla('mediciones')) {
    return select(`
      SELECT substr(fecha_hora, 1, 7)                AS mes,
             COUNT(*)                                AS mediciones,
             COUNT(DISTINCT ${TUPLA})                AS localidades,
             COUNT(DISTINCT provincia)               AS provincias,
             COUNT(DISTINCT ccte)                    AS cctes,
             AVG(resultado_pct)                      AS promedio_pct,
             MAX(resultado_vm)                       AS resultado_max_vm,
             MAX(resultado_pct)                      AS resultado_max_pct,
             MIN(fecha_hora)                         AS fecha_inicio,
             MAX(fecha_hora)                         AS fecha_fin,
             COUNT(DISTINCT substr(fecha_hora, 1, 10)) AS dias_con_medicion
        FROM mediciones GROUP BY mes ORDER BY mes`)
  }

  exigir(['resumen_mensual'], 'Esta base no tiene la tabla "mediciones" ni ' +
    '"resumen_mensual": no hay nada para resumir.')

  return select('SELECT mes, mediciones FROM resumen_mensual ORDER BY mes')
    .map((f) => ({ ...f, actualizado_en: null }))
}

function cargarAnio() {
  exigir(['resumen_anual', 'mediciones'], 'Esta base no tiene la tabla ' +
    '"resumen_anual" ni "mediciones": no hay nada para resumir.')

  if (tieneTabla('resumen_anual')) {
    return select('SELECT * FROM resumen_anual ORDER BY anio')
  }

  return select(`
    SELECT CAST(substr(fecha_hora, 1, 4) AS INTEGER) AS anio,
           COUNT(*)                                  AS mediciones,
           COUNT(DISTINCT ${TUPLA})                  AS localidades,
           COUNT(DISTINCT provincia)                 AS provincias,
           COUNT(DISTINCT ccte)                      AS cctes,
           MAX(resultado_vm)                         AS resultado_max_vm,
           MAX(resultado_pct)                        AS resultado_max_pct
      FROM mediciones GROUP BY anio ORDER BY anio`)
    .map((f) => ({ ...f, actualizado_en: null }))
}

function cargarProvincia() {
  exigir(['resumen_provincia', 'mediciones'], 'Esta base no tiene la tabla ' +
    '"resumen_provincia" ni "mediciones": no hay nada para resumir.')

  if (tieneTabla('resumen_provincia')) {
    return select('SELECT * FROM resumen_provincia ORDER BY mediciones DESC')
  }

  const filas = select(`
    SELECT provincia,
           COUNT(*)                    AS mediciones,
           COUNT(DISTINCT ${TUPLA})    AS localidades,
           COUNT(DISTINCT ccte)        AS cctes,
           MAX(resultado_vm)           AS resultado_max_vm,
           MAX(resultado_pct)          AS resultado_max_pct
      FROM mediciones GROUP BY provincia ORDER BY mediciones DESC`)

  for (const f of filas) {
    const p = primero(
      'SELECT localidad FROM mediciones WHERE provincia = ? ' +
      'ORDER BY resultado_vm DESC, id ASC LIMIT 1', [f.provincia])
    f.localidad_max = p ? p.localidad : null
    f.actualizado_en = null
  }
  return filas
}

function cargarProvinciaCcte() {
  exigir(['resumen_provincia_ccte', 'mediciones'], 'Esta base no tiene la ' +
    'tabla "resumen_provincia_ccte" ni "mediciones": no hay nada para resumir.')

  if (tieneTabla('resumen_provincia_ccte')) {
    return select('SELECT * FROM resumen_provincia_ccte ' +
      'ORDER BY provincia, ccte')
  }

  return select(`
    SELECT provincia, ccte,
           COUNT(DISTINCT ${TUPLA}) AS localidades,
           COUNT(*)                 AS mediciones
      FROM mediciones
     GROUP BY provincia, ccte
     ORDER BY provincia, ccte`).map((f) => ({ ...f, actualizado_en: null }))
}

/**
 * La pestaña "En general" no es una tabla de filas iguales: es una lista de
 * indicador/valor con tipos mezclados, así que cada fila guarda su tipo.
 */
function cargarGeneral() {
  const global_ = tieneTabla('resumen_global')
    ? primero('SELECT * FROM resumen_global WHERE id = 1')
    : null

  const r = tieneTabla('mediciones') ? primero(`
    SELECT COUNT(*)                                   AS registros,
           COUNT(DISTINCT ${TUPLA})                   AS localidades,
           COUNT(DISTINCT provincia)                  AS provincias,
           COUNT(DISTINCT ccte)                       AS cctes,
           AVG(resultado_pct)                         AS promedio,
           MAX(resultado_vm)                          AS pico_vm,
           MIN(fecha_hora)                            AS desde,
           MAX(fecha_hora)                            AS hasta,
           COUNT(DISTINCT substr(fecha_hora, 1, 10))  AS dias,
           COUNT(DISTINCT substr(fecha_hora, 1, 7))   AS meses
      FROM mediciones`) : null

  if (!global_ && !r) {
    throw new Error('Esta base no tiene la tabla "resumen_global" ni ' +
      '"mediciones": no hay nada para resumir.')
  }

  // los totales precalculados mandan (son los que sirve el backend); el
  // escaneo en vivo aporta el rango de fechas, los días y los meses
  const registros = global_ ? global_.registros_totales : r.registros
  const localidades = global_ ? global_.localidades : r.localidades
  const provincias = global_ ? global_.provincias : r.provincias
  const cctes = global_ ? global_.cctes : r.cctes
  const promedio = global_ ? global_.promedio_pct : r.promedio

  let pico = null
  if (global_ && global_.pico_id !== null && global_.pico_id !== undefined) {
    pico = primero('SELECT localidad, provincia, ccte, resultado_vm, ' +
      'resultado_pct, fecha_hora, expediente FROM mediciones WHERE id = ?',
      [global_.pico_id])
  }
  if (!pico && r && r.pico_vm !== null && r.pico_vm !== undefined) {
    pico = primero('SELECT localidad, provincia, ccte, resultado_vm, ' +
      'resultado_pct, fecha_hora, expediente FROM mediciones ' +
      'WHERE resultado_vm = ? ORDER BY id ASC LIMIT 1', [r.pico_vm])
  }

  const tiempo = tieneTabla('resumen_ccte')
    ? primero('SELECT SUM(tiempo_trabajado_seg) AS total FROM resumen_ccte')
    : null

  const actualizado = global_
    ? global_.actualizado_en
    : (tieneTabla('resumen_ccte')
      ? primero('SELECT MAX(actualizado_en) AS total FROM resumen_ccte').total
      : null)

  const filas = []
  const add = (indicador, valor, tipo) => filas.push({ indicador, valor, tipo })

  add('Registros totales', registros, 'entero')
  add('Localidades', localidades, 'entero')
  add('Provincias', provincias, 'entero')
  add('Centros (CCTE)', cctes, 'entero')
  add('Promedio del límite', promedio, 'porcentaje')

  add('Pico máximo (V/m)', pico ? pico.resultado_vm : null, 'vm')
  add('Pico máximo (%)', pico ? pico.resultado_pct : null, 'porcentaje')
  add('Localidad del pico',
    pico ? `${pico.localidad}, ${pico.provincia}` : null, 'texto')
  add('CCTE del pico', pico ? pico.ccte : null, 'texto')
  add('Fecha del pico', pico ? pico.fecha_hora : null, 'momento')
  add('Expediente del pico', pico ? pico.expediente : null, 'texto')

  add('Primer día medido', r ? r.desde : null, 'fecha')
  add('Último día medido', r ? r.hasta : null, 'fecha')
  add('Días con medición', r ? r.dias : null, 'entero')
  add('Meses con medición', r ? r.meses : null, 'entero')

  add('Tiempo trabajado (total CCTE)',
    tiempo ? tiempo.total : null, 'duracion')
  add('Resumen actualizado', actualizado, 'momento')

  return filas
}

const PESTANAS = [
  { id: 'centro', titulo: 'Por centro', columnas: columnasCcte, cargar: cargarCcte },
  { id: 'mes', titulo: 'Por mes', columnas: columnasMes, cargar: cargarMes },
  { id: 'anio', titulo: 'Por año', columnas: columnasAnio, cargar: cargarAnio },
  { id: 'provincia', titulo: 'Por provincia', columnas: columnasProvincia, cargar: cargarProvincia },
  { id: 'provincia_ccte', titulo: 'Provincia y CCTE', columnas: columnasProvinciaCcte, cargar: cargarProvinciaCcte },
  { id: 'general', titulo: 'En general', columnas: columnasGeneral, cargar: cargarGeneral },
]

/* ------------------------------- estado ------------------------------- */

const cache = {}        // id de pestaña → filas ya cargadas
let activa = 'centro'
let listo = false

function pestañaActual() {
  return PESTANAS.find((p) => p.id === activa)
}

function filasDe(p) {
  if (!cache[p.id]) cache[p.id] = p.cargar()
  return cache[p.id]
}

/** Carga todo lo que se pueda y deja el resto para cuando se pida. */
export function cargar() {
  try {
    for (const p of PESTANAS) delete cache[p.id]
    // la primera pestaña se carga acá: si falla, el error se ve enseguida
    filasDe(pestañaActual())
  } catch (e) {
    pintarError(e.message)
    error(e.message)
    return false
  }
  refrescar()
  return true
}

function pintarError(mensaje) {
  const vacio = $('#res-vacio')
  vacio.textContent = mensaje
  vacio.hidden = false
  $('#res-contador').textContent = '—'
}

/* ------------------------------ pintado ------------------------------- */

function pintar() {
  const p = pestañaActual()
  let filas
  try {
    filas = filasDe(p)
  } catch (e) {
    vaciar($('#res-cabecera'))
    vaciar($('#res-cuerpo'))
    pintarError(e.message)
    error(e.message)
    return
  }

  const columnas = p.columnas()
  const vacio = $('#res-vacio')
  vacio.hidden = true

  // encabezado
  const cabecera = $('#res-cabecera')
  vaciar(cabecera)
  const tr = document.createElement('tr')
  for (const col of columnas) {
    const th = document.createElement('th')
    th.textContent = col.titulo
    if (col.num) th.classList.add('num')
    tr.appendChild(th)
  }
  cabecera.appendChild(tr)

  // filas
  const cuerpo = $('#res-cuerpo')
  vaciar(cuerpo)
  for (const f of filas) {
    const fila = document.createElement('tr')
    for (const col of columnas) {
      const tipo = col.tipo === 'variable' ? f.tipo : col.tipo
      const valor = col.tipo === 'variable' ? f.valor : f[col.clave]
      fila.appendChild(celda(formatear(tipo, valor), { num: !!col.num }))
    }
    cuerpo.appendChild(fila)
  }

  $('#res-contador').textContent =
    `${entero(filas.length)} fila${filas.length === 1 ? '' : 's'}`
}

export function refrescar() { if (listo) pintar() }

/* ---------------------------- exportación ---------------------------- */

function exportar() {
  const p = pestañaActual()
  let filas
  try {
    filas = filasDe(p)
  } catch (e) {
    error(e.message)
    return
  }

  const columnas = p.columnas()
  const datos = filas.map((f) => columnas.map((col) =>
    col.tipo === 'variable' ? f.valor : f[col.clave]))

  const nombre = p.id === 'provincia_ccte' ? 'provincia_por_ccte'
    : p.id === 'general' ? 'resumen_general'
      : `resumen_${p.id}`

  exportarXLSX({
    nombre,
    hoja: p.titulo,
    encabezados: columnas.map((c) => c.titulo),
    filas: datos,
    formatos: columnas.map((c) => FORMATO_EXCEL[c.tipo] ?? null),
    anchos: columnas.map((c) => (c.tipo === 'variable' ? 46 : 18)),
  })
}

/* ------------------------------ montaje ------------------------------- */

export function montar() {
  if (listo) return
  listo = true

  document.querySelectorAll('.pestania').forEach((boton) => {
    boton.addEventListener('click', () => {
      activa = boton.dataset.pestania
      document.querySelectorAll('.pestania').forEach((otro) => {
        const propio = otro === boton
        otro.classList.toggle('pestania--activa', propio)
        otro.setAttribute('aria-selected', propio ? 'true' : 'false')
      })
      refrescar()
    })
  })

  $('#res-exportar').addEventListener('click', exportar)
}
