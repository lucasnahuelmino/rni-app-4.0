/* ==========================================================================
   vistas/inicio.js — Inicio: las tarjetas de la app original.

   Repite el orden del dashboard principal:

     1. KPIs: registros totales, localidades, provincias, centros (CCTE) y
        promedio del límite;
     2. pico máximo registrado (V/m + lugar + sello del % con el color del
        semáforo);
     3. mediciones por Centro de Comprobación Técnica de Emisiones, con todos
        los datos de `resumen_ccte`.

   Fuentes: `resumen_global` y `resumen_ccte` cuando existen (son las mismas
   precalculadas que usa el backend); si no, se agregan en vivo sobre
   `mediciones` con el mismo criterio que la app.

   Detalle de las localidades: hay DOS "San Pedro", así que se cuenta la tupla
   ccte + provincia + localidad (char(31) es el separador ASCII de unidad) y no
   el nombre solo. Contar solo `localidad` daría 60 en vez de 61.
   ========================================================================== */

import { primero, select, tieneTabla } from '../base.js'
import { completarCcte } from '../ccte.js'
import { entero, pct, vm, fecha, duracion } from '../formato.js'
import { $, vaciar, error, distintivoValor } from '../ui.js'
import { exportarXLSX } from '../exportar.js'

const TABLA_LOCALIDADES =
  "ccte || char(31) || provincia || char(31) || localidad"

let kpis = null      // { registros, localidades, provincias, cctes, promedio }
let pico = null      // fila de mediciones del pico máximo
let cctes = []       // filas de resumen_ccte (o su equivalente)
let listo = false

/* ------------------------------- datos -------------------------------- */

function consultarKpis() {
  if (tieneTabla('resumen_global')) {
    const g = primero('SELECT * FROM resumen_global WHERE id = 1')
    if (g) {
      return {
        registros: g.registros_totales,
        localidades: g.localidades,
        provincias: g.provincias,
        cctes: g.cctes,
        promedio: g.promedio_pct,
        picoVm: g.pico_vm,
        picoId: g.pico_id,
      }
    }
  }

  if (!tieneTabla('mediciones')) {
    throw new Error('Esta base no tiene la tabla "resumen_global" ni ' +
      '"mediciones": no hay nada para resumir.')
  }

  const f = primero(`
    SELECT COUNT(*)                                        AS registros,
           COUNT(DISTINCT ${TABLA_LOCALIDADES})             AS localidades,
           COUNT(DISTINCT provincia)                        AS provincias,
           COUNT(DISTINCT ccte)                             AS cctes,
           AVG(resultado_pct)                               AS promedio,
           MAX(resultado_vm)                                AS picoVm
      FROM mediciones`)

  return {
    registros: f.registros,
    localidades: f.localidades,
    provincias: f.provincias,
    cctes: f.cctes,
    promedio: f.promedio,
    picoVm: f.picoVm,
    picoId: null,
  }
}

/** Detalle del pico: por id si lo trae el resumen, si no por valor máximo. */
function consultarPico() {
  if (kpis.picoVm === null || kpis.picoVm === undefined) return null

  if (kpis.picoId !== null && kpis.picoId !== undefined) {
    const fila = primero(`
      SELECT localidad, provincia, ccte, resultado_vm, resultado_pct,
             fecha_hora, expediente
        FROM mediciones WHERE id = ?`, [kpis.picoId])
    if (fila) return fila
  }

  return primero(`
    SELECT localidad, provincia, ccte, resultado_vm, resultado_pct,
           fecha_hora, expediente
      FROM mediciones WHERE resultado_vm = ?
     ORDER BY id ASC LIMIT 1`, [kpis.picoVm])
}

function consultarCctes() {
  let filas = []

  if (tieneTabla('resumen_ccte')) {
    filas = select('SELECT * FROM resumen_ccte')
  } else if (tieneTabla('mediciones')) {
    filas = select(`
      SELECT ccte,
             COUNT(*)                                     AS mediciones,
             COUNT(DISTINCT provincia || char(31) || localidad) AS localidades,
             COUNT(DISTINCT provincia)                    AS provincias,
             MAX(resultado_vm)                            AS resultado_max_vm,
             MAX(resultado_pct)                           AS resultado_max_pct,
             COUNT(DISTINCT substr(fecha_hora, 1, 10))    AS dias_con_medicion
        FROM mediciones GROUP BY ccte`)

    for (const f of filas) {
      const p = primero(
        'SELECT localidad FROM mediciones WHERE ccte = ? ' +
        'ORDER BY resultado_vm DESC, id ASC LIMIT 1', [f.ccte])
      f.localidad_max = p ? p.localidad : null
      f.tiempo_trabajado_seg = null
      f.actualizado_en = null
    }
  } else {
    throw new Error('Esta base no tiene la tabla "resumen_ccte" ni ' +
      '"mediciones": no hay nada para resumir.')
  }

  // siempre los 7 CCTE (ver js/ccte.js): Buenos Aires y CABA con fila vacía
  return completarCcte(filas)
}

/** Carga (o recarga) todo lo que muestra el Inicio. */
export function cargar() {
  try {
    kpis = consultarKpis()
    pico = consultarPico()
    cctes = consultarCctes()
  } catch (e) {
    kpis = null; pico = null; cctes = []
    pintarError(e.message)
    error(e.message)
    return false
  }
  refrescar()
  return true
}

/* ------------------------------ pintado ------------------------------ */

function pintarError(mensaje) {
  const zona = $('#ini-error')
  zona.textContent = mensaje
  zona.hidden = false
}

function pintarKpis() {
  $('#ini-registros').textContent = entero(kpis.registros)
  $('#ini-localidades').textContent = entero(kpis.localidades)
  $('#ini-provincias').textContent = entero(kpis.provincias)
  $('#ini-centros').textContent = entero(kpis.cctes)

  const unidad = $('#ini-promedio-unidad')
  const valor = $('#ini-promedio')
  if (kpis.promedio === null || kpis.promedio === undefined) {
    valor.textContent = '—'
    unidad.textContent = ''
  } else {
    valor.textContent = pct(kpis.promedio)
    unidad.textContent = '%'
  }
}

function pintarPico() {
  const tarjeta = $('#tarjeta-pico')
  if (!pico) { tarjeta.hidden = true; return }
  tarjeta.hidden = false

  $('#pico-valor').textContent = vm(pico.resultado_vm)
  $('#pico-lugar').textContent = `${pico.localidad}, ${pico.provincia}`
  $('#pico-ccte').textContent = `CCTE ${pico.ccte}`
  $('#pico-fecha').textContent =
    `${fecha(pico.fecha_hora)} · ${pico.expediente || 'sin expediente'}`

  const sello = $('#pico-sello')
  vaciar(sello)
  sello.appendChild(distintivoValor(pico.resultado_pct))
}

function pintarCctes() {
  const grilla = $('#ini-ccte')
  vaciar(grilla)

  if (!cctes.length) {
    const aviso = document.createElement('p')
    aviso.className = 'vacio'
    aviso.textContent = 'No hay datos por centro en esta base.'
    grilla.appendChild(aviso)
    return
  }

  for (const c of cctes) {
    const tarjeta = document.createElement('article')
    tarjeta.className = 'ccte-card'
    tarjeta.innerHTML = `
      <h3></h3>
      <dl>
        <div class="ccte-card__fila"><dt>Mediciones</dt><dd class="num"></dd></div>
        <div class="ccte-card__fila"><dt>Localidades</dt><dd class="num"></dd></div>
        <div class="ccte-card__fila"><dt>Provincias</dt><dd class="num"></dd></div>
        <div class="ccte-card__fila"><dt>Pico V/m</dt><dd class="num"></dd></div>
        <div class="ccte-card__fila"><dt>Pico % RNI</dt><dd class="num"></dd></div>
        <div class="ccte-card__fila"><dt>Localidad del pico</dt><dd></dd></div>
        <div class="ccte-card__fila"><dt>Días con medición</dt><dd class="num"></dd></div>
        <div class="ccte-card__fila"><dt>Tiempo trabajado</dt><dd class="num"></dd></div>
      </dl>`

    const dd = tarjeta.querySelectorAll('dd')
    tarjeta.querySelector('h3').textContent = c.ccte
    dd[0].textContent = entero(c.mediciones)
    dd[1].textContent = entero(c.localidades)
    dd[2].textContent = entero(c.provincias)
    dd[3].textContent = vm(c.resultado_max_vm)
    dd[4].textContent = pct(c.resultado_max_pct)
    dd[5].textContent = c.localidad_max || '—'
    dd[6].textContent = entero(c.dias_con_medicion)
    dd[7].textContent = duracion(c.tiempo_trabajado_seg)

    grilla.appendChild(tarjeta)
  }
}

function pintar() {
  if (!kpis) return
  $('#ini-error').hidden = true
  pintarKpis()
  pintarPico()
  pintarCctes()

  // se muestran siempre los 7 CCTE; aclaro cuántos tienen datos
  const conDatos = cctes.filter((c) => c.mediciones > 0).length
  $('#ini-contador').textContent =
    `${entero(cctes.length)} centro${cctes.length === 1 ? '' : 's'}` +
    (conDatos < cctes.length ? ` · ${entero(conDatos)} con mediciones` : '')
}

export function refrescar() { if (listo) pintar() }

/* ---------------------------- exportación ---------------------------- */

function exportar() {
  if (!kpis) return

  const filas = [
    ['Registros totales', kpis.registros],
    ['Localidades', kpis.localidades],
    ['Provincias', kpis.provincias],
    ['Centros (CCTE)', kpis.cctes],
    ['Promedio del límite (%)', kpis.promedio],
    [],
    ['Pico máximo (V/m)', pico ? pico.resultado_vm : null],
    ['Pico máximo (%)', pico ? pico.resultado_pct : null],
    ['Localidad del pico', pico ? pico.localidad : null],
    ['Provincia del pico', pico ? pico.provincia : null],
    ['CCTE del pico', pico ? pico.ccte : null],
    ['Fecha del pico', pico ? pico.fecha_hora : null],
    ['Expediente del pico', pico ? pico.expediente : null],
    [],
    ['CCTE', 'Mediciones', 'Localidades', 'Provincias',
     'Pico V/m', 'Pico % RNI', 'Localidad del pico',
     'Días con medición', 'Tiempo trabajado (seg)'],
    ...cctes.map((c) => [
      c.ccte, c.mediciones, c.localidades, c.provincias,
      c.resultado_max_vm, c.resultado_max_pct, c.localidad_max,
      c.dias_con_medicion, c.tiempo_trabajado_seg,
    ]),
  ]

  exportarXLSX({
    nombre: 'inicio',
    hoja: 'Inicio',
    encabezados: ['Indicador', 'Valor'],
    filas,
    formatos: [null, '0.####'],
    anchos: [34, 46],
  })
}

/* ----------------------------- montaje ------------------------------ */

export function montar() {
  if (listo) return
  listo = true
  $('#ini-exportar').addEventListener('click', exportar)
}
