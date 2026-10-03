/* ==========================================================================
   vistas/horarios.js — Vista 2: medición por medida, con fecha y hora.

   Fuente: `mediciones` (219.818 filas). Nada de esto se trae entero a la
   memoria: el filtrado, el conteo y la página se resuelven con SQL con
   LIMIT/OFFSET, y sólo se cargan las filas visibles.

   ========================================================================== */

import { select, contar, tieneTabla, base } from '../base.js'
import { vm, pct, entero, fecha, hora } from '../formato.js'
import { $, celda, vaciar, distintivoNivel, error, aviso } from '../ui.js'
import { exportarXLSX } from '../exportar.js'

const COLS = `fecha_hora, ccte, provincia, localidad,
              resultado_vm, resultado_pct, sonda, lat, lon`

let filtro = { localidad: '', desde: '', hasta: '', busqueda: '' }
let pagina = 1
let porPagina = 100
let total = 0
let listo = false
let esperando = null

/* ------------------------------- cláusulas ------------------------------ */

function clausula() {
  const partes = []
  const params = []

  if (filtro.localidad) {
    partes.push('localidad = ?')
    params.push(filtro.localidad)
  }
  if (filtro.desde) {
    partes.push('fecha_hora >= ?')
    params.push(filtro.desde + 'T00:00:00')
  }
  if (filtro.hasta) {
    partes.push('fecha_hora <= ?')
    params.push(filtro.hasta + 'T23:59:59')
  }
  if (filtro.busqueda) {
    const like = '%' + filtro.busqueda + '%'
    partes.push(`(localidad LIKE ? OR provincia LIKE ? OR ccte LIKE ?
                  OR sonda LIKE ? OR IFNULL(e.expediente, '') LIKE ?)`)
    params.push(like, like, like, like, like)
  }

  // `expediente` hoy vive en la tabla expedientes, no en mediciones. El
  // join entra SOLO cuando el filtro lo necesita, asi las consultas de la
  // pagina no lo arrastran de arriba. Ojo: con el join, `id` pasa a ser
  // ambiguo (lo tienen las dos tablas), por eso los ORDER BY lo escriben
  // como `mediciones.id`.
  const join = filtro.busqueda
    ? ' LEFT JOIN expedientes e ON e.id = mediciones.expediente_id'
    : ''

  return { sql: partes.length ? 'WHERE ' + partes.join(' AND ') : '', params, join }
}

const hayFiltros = () =>
  filtro.localidad || filtro.desde || filtro.hasta || filtro.busqueda

/* ------------------------------- carga --------------------------------- */

/** Pobla el select de localidades. Devuelve false si falta la tabla. */
export function cargar() {
  const vacio = $('#hor-vacio')

  if (!tieneTabla('mediciones')) {
    datos = []
    total = 0
    vacio.textContent = 'Esta base no tiene la tabla "mediciones": ' +
      'no hay mediciones por horario para consultar.'
    vacio.hidden = false
    error(vacio.textContent)
    pintarPaginacion()
    return false
  }

  const select_ = $('#hor-localidad')
  select_.innerHTML = '<option value="">Todas</option>'
  for (const fila of select(
    'SELECT DISTINCT localidad FROM mediciones ORDER BY localidad')) {
    const opcion = document.createElement('option')
    opcion.value = fila.localidad
    opcion.textContent = fila.localidad
    select_.appendChild(opcion)
  }

  // rango disponible en la base, para no filtrar contra un vacío
  const rango = select(
    'SELECT MIN(fecha_hora) AS desde, MAX(fecha_hora) AS hasta FROM mediciones')[0]
  $('#hor-desde').min = (rango?.desde || '').slice(0, 10)
  $('#hor-hasta').max = (rango?.hasta || '').slice(0, 10)

  filtro = { localidad: '', desde: '', hasta: '', busqueda: '' }
  pagina = 1
  $('#hor-busqueda').value = ''
  $('#hor-desde').value = ''
  $('#hor-hasta').value = ''
  refrescar()
  return true
}

/* ------------------------------ refresco -------------------------------- */

export function refrescar() {
  if (!listo || !tieneTabla('mediciones')) return

  const { sql, params, join } = clausula()

  total = contar('SELECT COUNT(*) AS n FROM mediciones' + join + ' ' + sql, params)

  const ultima = Math.max(1, Math.ceil(total / porPagina))
  if (pagina > ultima) pagina = ultima

  const filas = select(
    `SELECT ${COLS} FROM mediciones${join} ${sql}
      ORDER BY fecha_hora DESC, mediciones.id DESC
      LIMIT ? OFFSET ?`,
    [...params, porPagina, (pagina - 1) * porPagina])

  pintar(filas)
  pintarPaginacion()
}

let datos = []

function pintar(filas) {
  datos = filas
  const cuerpo = $('#hor-cuerpo')
  const vacio = $('#hor-vacio')
  vaciar(cuerpo)

  for (const f of filas) {
    const tr = document.createElement('tr')
    tr.appendChild(celda(fecha(f.fecha_hora), { num: true }))
    tr.appendChild(celda(hora(f.fecha_hora), { num: true }))
    tr.appendChild(celda(f.ccte))
    tr.appendChild(celda(f.provincia))
    tr.appendChild(celda(f.localidad))
    tr.appendChild(celda(vm(f.resultado_vm), { num: true }))
    tr.appendChild(celda(pct(f.resultado_pct), { num: true }))

    const tdNivel = document.createElement('td')
    tdNivel.appendChild(distintivoNivel(f.resultado_pct))
    tr.appendChild(tdNivel)

    tr.appendChild(celda(f.sonda))
    tr.appendChild(celda(f.lat === null ? null : Number(f.lat).toFixed(5), { num: true }))
    tr.appendChild(celda(f.lon === null ? null : Number(f.lon).toFixed(5), { num: true }))
    cuerpo.appendChild(tr)
  }

  vacio.hidden = filas.length > 0
  $('#hor-contador').textContent = hayFiltros()
    ? `${entero(total)} de ${entero(base.mediciones)} mediciones`
    : `${entero(total)} mediciones`
}

function pintarPaginacion() {
  const ultima = Math.max(1, Math.ceil(total / porPagina))
  $('#hor-estado').textContent = total === 0
    ? '0 de 0'
    : `Página ${entero(pagina)} de ${entero(ultima)} · filas ${entero((pagina - 1) * porPagina + 1)}–${entero(Math.min(pagina * porPagina, total))}`

  const botones = document.querySelectorAll('#hor-paginacion button[data-pag]')
  botones.forEach((b) => {
    const p = b.dataset.pag
    b.disabled =
      (total === 0) ||
      ((p === 'primera' || p === 'anterior') && pagina <= 1) ||
      ((p === 'siguiente' || p === 'ultima') && pagina >= ultima)
  })
}

/* ----------------------------- exportación ------------------------------ */

function exportar() {
  if (!tieneTabla('mediciones')) return

  const { sql, params, join } = clausula()
  aviso('Exportando las mediciones filtradas… esto puede tardar unos segundos.')

  setTimeout(() => {
    try {
      const filas = select(
        `SELECT ${COLS} FROM mediciones${join} ${sql}
          ORDER BY fecha_hora DESC, mediciones.id DESC`,
        params
      ).map((f) => [
        f.fecha_hora, f.ccte, f.provincia, f.localidad,
        f.resultado_vm, f.resultado_pct, f.sonda, f.lat, f.lon,
      ])

      exportarXLSX({
        nombre: 'mediciones_por_horario',
        hoja: 'Por horarios',
        encabezados: ['Fecha y hora', 'CCTE', 'Provincia', 'Localidad',
          'V/m', '% RNI', 'Sonda', 'Latitud', 'Longitud'],
        filas,
        formatos: [null, null, null, null, '0.###', '0.####', null, '0.00000', '0.00000'],
        anchos: [20, 24, 20, 28, 11, 12, 11, 12, 12],
      })
    } catch (e) {
      error('No se pudo exportar: ' + e.message)
    }
  }, 50)
}

/* ------------------------------ montaje --------------------------------- */

export function montar() {
  if (listo) return
  listo = true

  $('#hor-localidad').addEventListener('change', (e) => {
    filtro.localidad = e.target.value
    pagina = 1
    refrescar()
  })

  for (const id of ['#hor-desde', '#hor-hasta']) {
    $(id).addEventListener('change', () => {
      filtro.desde = $('#hor-desde').value
      filtro.hasta = $('#hor-hasta').value
      pagina = 1
      refrescar()
    })
  }

  const entrada = $('#hor-busqueda')
  entrada.addEventListener('input', () => {
    clearTimeout(esperando)
    esperando = setTimeout(() => {
      filtro.busqueda = entrada.value.trim()
      pagina = 1
      refrescar()
    }, 300)
  })

  $('#hor-limpiar').addEventListener('click', () => {
    filtro = { localidad: '', desde: '', hasta: '', busqueda: '' }
    $('#hor-localidad').value = ''
    $('#hor-desde').value = ''
    $('#hor-hasta').value = ''
    entrada.value = ''
    pagina = 1
    refrescar()
  })

  $('#hor-porpagina').addEventListener('change', (e) => {
    porPagina = Number(e.target.value)
    pagina = 1
    refrescar()
  })

  document.querySelectorAll('#hor-paginacion button[data-pag]').forEach((b) => {
    b.addEventListener('click', () => {
      const ultima = Math.max(1, Math.ceil(total / porPagina))
      const p = b.dataset.pag
      if (p === 'primera') pagina = 1
      if (p === 'anterior') pagina = Math.max(1, pagina - 1)
      if (p === 'siguiente') pagina = Math.min(ultima, pagina + 1)
      if (p === 'ultima') pagina = ultima
      refrescar()
      $('#vista-horarios').scrollIntoView({ block: 'start' })
    })
  })

  $('#hor-exportar').addEventListener('click', exportar)
}
