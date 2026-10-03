/* ==========================================================================
   vistas/localidades.js — Vista 1: resumen por localidad.

   Fuente: `resumen_localidad` si existe (61 filas ya agregadas); si la tabla
   no está, se arma el mismo resumen agrupando `mediciones` con SQL. En ambos
   casos el resultado son ~60 filas, así que filtrar, ordenar y buscar se hace
   en memoria, al instante.
   ========================================================================== */

import { select, tieneTabla } from '../base.js'
import { vm, pct, entero, fecha, duracion, normalizar } from '../formato.js'
import { $, celda, vaciar, error } from '../ui.js'
import { exportarXLSX } from '../exportar.js'

let datos = []
let orden = { col: 'localidad', dir: 'asc' }
let busqueda = ''
let listo = false

/* ------------------------------- datos ------------------------------- */

function consultarLocalidades() {
  if (tieneTabla('resumen_localidad')) {
    return select(`
      SELECT ccte, provincia, localidad, mediciones,
             resultado_max_vm, resultado_max_pct, resultado_prom_pct,
             fecha_inicio, fecha_fin, expedientes, sondas,
             tiempo_trabajado_seg, dias_con_medicion
        FROM resumen_localidad`)
  }

  if (tieneTabla('mediciones')) {
    // la tabla de resumen no existe: se recalcula igual que la app
    return select(`
      SELECT ccte, provincia, localidad,
             COUNT(*)                              AS mediciones,
             MAX(resultado_vm)                     AS resultado_max_vm,
             MAX(resultado_pct)                    AS resultado_max_pct,
             AVG(resultado_pct)                    AS resultado_prom_pct,
             MIN(fecha_hora)                       AS fecha_inicio,
             MAX(fecha_hora)                       AS fecha_fin,
             GROUP_CONCAT(DISTINCT e.expediente)   AS expedientes,
             GROUP_CONCAT(DISTINCT sonda)          AS sondas,
             0                                     AS tiempo_trabajado_seg,
             COUNT(DISTINCT substr(fecha_hora, 1, 10)) AS dias_con_medicion
        FROM mediciones
        LEFT JOIN expedientes e ON e.id = mediciones.expediente_id
       GROUP BY ccte, provincia, localidad
       ORDER BY ccte, provincia, localidad`)
  }

  throw new Error('Esta base no tiene la tabla "resumen_localidad" ni ' +
    '"mediciones": no hay nada para resumir.')
}

/** Carga (o recarga) las filas. Devuelve false si no había qué cargar. */
export function cargar() {
  const vacio = $('#loc-vacio')
  try {
    datos = consultarLocalidades()
  } catch (e) {
    datos = []
    vacio.textContent = e.message
    vacio.hidden = false
    error(e.message)
    return false
  }
  vacio.hidden = true
  refrescar()
  return true
}

/* ------------------------- filtro y orden -------------------------- */

function visibles() {
  const q = normalizar(busqueda)
  let salida = datos
  if (q) {
    salida = datos.filter((f) =>
      normalizar(f.ccte).includes(q) ||
      normalizar(f.provincia).includes(q) ||
      normalizar(f.localidad).includes(q))
  }
  return salida.sort(comparar)
}

function comparar(a, b) {
  const va = a[orden.col]
  const vb = b[orden.col]
  const na = va === null || va === undefined || va === ''
  const nb = vb === null || vb === undefined || vb === ''
  // los vacíos quedan al final en cualquier sentido
  if (na || nb) return na && nb ? 0 : na ? 1 : -1

  let cmp
  if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb
  else cmp = String(va).localeCompare(String(vb), 'es')

  return orden.dir === 'asc' ? cmp : -cmp
}

/* ------------------------------ pintado ------------------------------ */

function pintar() {
  const cuerpo = $('#loc-cuerpo')
  const vacio = $('#loc-vacio')
  const filas = visibles()

  vaciar(cuerpo)
  for (const f of filas) {
    const tr = document.createElement('tr')
    tr.appendChild(celda(f.ccte))
    tr.appendChild(celda(f.provincia))
    tr.appendChild(celda(f.localidad))
    tr.appendChild(celda(entero(f.mediciones), { num: true }))
    tr.appendChild(celda(pct(f.resultado_max_pct), { num: true }))
    tr.appendChild(celda(vm(f.resultado_max_vm), { num: true }))
    tr.appendChild(celda(pct(f.resultado_prom_pct), { num: true }))
    tr.appendChild(celda(fecha(f.fecha_inicio), { num: true }))
    tr.appendChild(celda(fecha(f.fecha_fin), { num: true }))
    tr.appendChild(celda(entero(f.dias_con_medicion), { num: true }))
    tr.appendChild(celda(duracion(f.tiempo_trabajado_seg), { num: true }))
    tr.appendChild(celda(f.expedientes, { clase: 'corto' }))
    tr.appendChild(celda(f.sondas))
    cuerpo.appendChild(tr)
  }

  vacio.hidden = filas.length > 0
  $('#loc-contador').textContent = filas.length === datos.length
    ? `${entero(filas.length)} localidades`
    : `${entero(filas.length)} de ${entero(datos.length)}`
}

export function refrescar() { if (listo) pintar() }

/* ---------------------------- exportación ---------------------------- */

function exportar() {
  const filas = visibles().map((f) => [
    f.ccte,
    f.provincia,
    f.localidad,
    f.mediciones,
    f.resultado_max_pct,
    f.resultado_max_vm,
    f.resultado_prom_pct,
    f.fecha_inicio,
    f.fecha_fin,
    f.dias_con_medicion,
    f.tiempo_trabajado_seg,
    f.expedientes,
    f.sondas,
  ])

  exportarXLSX({
    nombre: 'localidades',
    hoja: 'Localidades',
    encabezados: [
      'CCTE', 'Provincia', 'Localidad', 'Mediciones',
      'Máximo % RNI', 'Máximo V/m', 'Promedio % RNI',
      'Primer día', 'Último día', 'Días con medición',
      'Tiempo trabajado (seg)', 'Expediente(s)', 'Sonda(s)',
    ],
    filas,
    formatos: [null, null, null, '0', '0.####', '0.###', '0.####',
      null, null, '0', '0', null, null],
    anchos: [22, 22, 30, 12, 14, 12, 14, 20, 20, 10, 18, 44, 16],
  })
}

/* ----------------------------- montaje ------------------------------ */

export function montar() {
  if (listo) return
  listo = true

  const entrada = $('#loc-busqueda')
  let espera = null
  entrada.addEventListener('input', () => {
    clearTimeout(espera)
    espera = setTimeout(() => { busqueda = entrada.value; refrescar() }, 180)
  })

  document.querySelectorAll('#loc-tabla th.ordenar').forEach((th) => {
    th.addEventListener('click', () => {
      const col = th.dataset.col
      orden = { col, dir: orden.col === col && orden.dir === 'asc' ? 'desc' : 'asc' }
      document.querySelectorAll('#loc-tabla th.ordenar').forEach((otro) => {
        otro.classList.toggle('ordenar--asc', otro === th && orden.dir === 'asc')
        otro.classList.toggle('ordenar--desc', otro === th && orden.dir === 'desc')
      })
      refrescar()
    })
  })

  $('#loc-exportar').addEventListener('click', exportar)
}
