/* ==========================================================================
   vistas/mapa.js — Vista 3: punto máximo de cada localidad.

   · Fuente: `punto_max` si existe; si no, se calcula el máximo de cada
     localidad sobre `mediciones` con SQL.
   · Si hay internet se usa Leaflet con teselas de OpenStreetMap; si no hay
     conexión (o las teselas fallan) se dibuja el mismo mapa en un <canvas>
     con lat/lon, sin depender de nada externo.
   · El nivel siempre se informa con color ETIQUETA de texto (leyenda y
     tooltip), nunca sólo con color.
   · Descarga el mapa como PNG: se repinta en un <canvas> propio, así que
     funciona igual en los dos modos.
   ========================================================================== */

import { select, tieneTabla } from '../base.js'
import { vm, pct, entero } from '../formato.js'
import { $, aviso, error, mostrarTooltip, moverTooltip, ocultarTooltip } from '../ui.js'
import { RANGOS, rangoPorPct } from '../escala.js'
import { exportarXLSX } from '../exportar.js'

const TESELAS = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

let puntos = []            // [{localidad, provincia, ccte, lat, lon, vm, pct}]
let sinCoordenadas = 0
let listo = false
let mapa = null            // instancia de Leaflet (null = modo canvas)
let capa = null            // capa de teselas
let modo = 'canvas'        // 'leaflet' | 'canvas'
let esperandoInternet = false

/* ------------------------------- datos --------------------------------- */

function valido(lat, lon) {
  if (lat === null || lon === null || lat === undefined || lon === undefined) return false
  const a = Number(lat)
  const o = Number(lon)
  if (Number.isNaN(a) || Number.isNaN(o)) return false
  if (a === 0 && o === 0) return false                 // coordenadas de relleno
  return a >= -90 && a <= 90 && o >= -180 && o <= 180
}

function consultarPuntos() {
  if (tieneTabla('punto_max')) {
    return select(`SELECT ccte, provincia, localidad, lat, lon,
                          resultado_vm, resultado_pct, anio
                     FROM punto_max`)
  }

  if (tieneTabla('mediciones')) {
    // sin la tabla de puntos: máximo de cada localidad (empates -> primero)
    return select(`
      SELECT m.ccte, m.provincia, m.localidad, m.lat, m.lon,
             m.resultado_vm, m.resultado_pct, m.anio
        FROM mediciones m
        JOIN (SELECT localidad, MAX(resultado_pct) AS pct
                FROM mediciones
               WHERE lat IS NOT NULL AND lon IS NOT NULL
               GROUP BY localidad) x
          ON x.localidad = m.localidad AND x.pct = m.resultado_pct`)
  }

  throw new Error('Esta base no tiene la tabla "punto_max" ni "mediciones": ' +
    'no hay coordenadas para el mapa.')
}

/** Un solo punto por localidad: el de mayor % de RNI. */
function agrupar(filas) {
  const porLocalidad = new Map()
  let nulas = 0

  for (const f of filas) {
    if (!valido(f.lat, f.lon)) { nulas++; continue }
    const clave = `${f.ccte}|${f.provincia}|${f.localidad}`
    const actual = porLocalidad.get(clave)
    const pctNuevo = Number(f.resultado_pct)
    if (!actual || pctNuevo > Number(actual.pct)) {
      porLocalidad.set(clave, {
        localidad: f.localidad,
        provincia: f.provincia,
        ccte: f.ccte,
        lat: Number(f.lat),
        lon: Number(f.lon),
        vm: f.resultado_vm,
        pct: f.resultado_pct,
      })
    }
  }

  sinCoordenadas = nulas
  return [...porLocalidad.values()]
    .sort((a, b) => a.localidad.localeCompare(b.localidad, 'es'))
}

export function cargar() {
  const nota = $('#mapa-nota')
  try {
    puntos = agrupar(consultarPuntos())
  } catch (e) {
    puntos = []
    nota.textContent = e.message
    nota.hidden = false
    error(e.message)
    return false
  }

  $('#mapa-contador').textContent = `${entero(puntos.length)} localidades`
  nota.textContent = sinCoordenadas > 0
    ? `${entero(sinCoordenadas)} registro/s sin coordenadas válidas (nulas o fuera de rango) ` +
      'se omitieron del mapa.'
    : ''
  nota.hidden = nota.textContent === ''

  pintarLeyenda()
  return true
}

/* ------------------------------- leyenda -------------------------------- */

function pintarLeyenda() {
  const lista = $('#leyenda')
  lista.innerHTML = ''

  const titulo = document.createElement('li')
  titulo.className = 'leyenda__titulo'
  titulo.textContent = '% del límite normativo'
  lista.appendChild(titulo)

  for (const rango of RANGOS) {
    const li = document.createElement('li')
    li.className = 'leyenda__item'

    const muestra = document.createElement('span')
    muestra.className = 'leyenda__muestra'
    muestra.style.background = rango.color

    const texto = document.createElement('span')
    texto.className = 'leyenda__texto'
    texto.textContent = rango.etiqueta

    li.append(muestra, texto)
    lista.appendChild(li)
  }
}

/* ------------------------------ internet -------------------------------- */

/** ¿Responden las teselas de OpenStreetMap? (5 s de tolerancia) */
function hayInternet() {
  return new Promise((resolver) => {
    const imagen = new Image()
    let respondio = false
    const tiempo = setTimeout(() => { if (!respondio) resolver(false) }, 5000)
    imagen.crossOrigin = 'anonymous'
    imagen.onload = () => { respondio = true; clearTimeout(tiempo); resolver(true) }
    imagen.onerror = () => { respondio = true; clearTimeout(tiempo); resolver(false) }
    imagen.src = 'https://tile.openstreetmap.org/2/1/1.png'
  })
}

/* ------------------------------ pintado --------------------------------- */

export async function refrescar() {
  if (!listo) return
  if (puntos.length === 0) return

  const contenedor = $('#mapa-leaflet')

  if (mapa) {
    mapa.invalidateSize()
    return                       // ya está dibujado: sólo hay que re-medir
  }
  if (modo === 'canvas' && !$('#mapa-canvas').hidden) {
    redibujarLienzo($('#mapa-canvas'))   // el bitmap viejo se estira al volver
    return
  }

  if (esperandoInternet) return
  esperandoInternet = true
  const conectado = (typeof L !== 'undefined') && await hayInternet()
  esperandoInternet = false

  if (conectado) pintarLeaflet(contenedor)
  else pintarCanvas()

  dibujarPuntos()
}

function pintarLeaflet(contenedor) {
  modo = 'leaflet'
  $('#mapa-canvas').hidden = true
  contenedor.hidden = false

  const centro = puntos.reduce(
    (acc, p) => [acc[0] + p.lat, acc[1] + p.lon], [0, 0])
  mapa = L.map(contenedor, { scrollWheelZoom: true })
    .setView([centro[0] / puntos.length, centro[1] / puntos.length], 5)

  capa = L.tileLayer(TESELAS, {
    maxZoom: 19,
    crossOrigin: true,
    attribution: '© OpenStreetMap',
  })
  capa.addTo(mapa)

  // si las teselas no llegan (se cortó internet entre el test y ahora),
  // volvemos al mapa sin conexión
  let errores = 0
  let llegoAlgo = false
  capa.on('load', () => { llegoAlgo = true })
  capa.on('tileerror', () => {
    errores++
    if (!llegoAlgo && errores >= 6) {
      destruirLeaflet()
      pintarCanvas()
      dibujarPuntos()
      aviso('Sin conexión con las teselas: el mapa se muestra sin fondo.')
    }
  })
}

function destruirLeaflet() {
  if (mapa) { try { mapa.remove() } catch (e) { /* ya borrado */ } }
  mapa = null
  capa = null
  $('#mapa-leaflet').hidden = true
  $('#mapa-leaflet').innerHTML = ''
}

function pintarCanvas() {
  modo = 'canvas'
  destruirLeaflet()
  const lienzo = $('#mapa-canvas')
  lienzo.hidden = false
  redibujarLienzo(lienzo)
}

function redibujarLienzo(lienzo) {
  const dpr = window.devicePixelRatio || 1
  const ancho = lienzo.clientWidth || lienzo.parentElement.clientWidth
  const alto = lienzo.clientHeight || lienzo.parentElement.clientHeight
  if (!ancho || !alto) return

  lienzo.width = Math.round(ancho * dpr)
  lienzo.height = Math.round(alto * dpr)
  const ctx = lienzo.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const proyeccion = proyectar(ancho, alto)
  ctx.fillStyle = '#eaf1f4'
  ctx.fillRect(0, 0, ancho, alto)
  dibujarGraticula(ctx, proyeccion, ancho, alto)
  dibujarPuntosCanvas(ctx, proyeccion)
  lienzo._proyeccion = proyeccion
}

/** Equirectangular con corrección por latitud media: sin dependencias. */
function proyectar(ancho, alto) {
  const lats = puntos.map((p) => p.lat)
  const lons = puntos.map((p) => p.lon)
  let latMin = Math.min(...lats)
  let latMax = Math.max(...lats)
  let lonMin = Math.min(...lons)
  let lonMax = Math.max(...lons)

  // un solo punto (o todos pegados): abrimos un poco la ventana
  const margenLat = Math.max((latMax - latMin) * 0.25, 0.4)
  const margenLon = Math.max((lonMax - lonMin) * 0.25, 0.5)
  latMin -= margenLat; latMax += margenLat
  lonMin -= margenLon; lonMax += margenLon

  const relLat = Math.cos(((latMin + latMax) / 2) * Math.PI / 180)
  const anchoDatos = (lonMax - lonMin) * relLat
  const altoDatos = (latMax - latMin)
  const escala = Math.min((ancho - 40) / anchoDatos, (alto - 40) / altoDatos)

  const cx = (lonMin + lonMax) / 2
  const cy = (latMin + latMax) / 2
  const px = ancho / 2
  const py = alto / 2

  return {
    aPixel: (lat, lon) => [
      px + (lon - cx) * relLat * escala,
      py - (lat - cy) * escala,
    ],
    aGrados: (x, y) => [
      cy - (y - py) / escala,
      cx + (x - px) / (escala * relLat),
    ],
  }
}

function dibujarGraticula(ctx, proyeccion, ancho, alto) {
  ctx.save()
  ctx.strokeStyle = 'rgba(18, 36, 43, 0.14)'
  ctx.fillStyle = 'rgba(18, 36, 43, 0.55)'
  ctx.lineWidth = 1
  ctx.font = '11px "IBM Plex Mono", monospace'

  const esquinas = [proyeccion.aGrados(0, 0), proyeccion.aGrados(ancho, alto)]
  const latMin = Math.min(esquinas[0][0], esquinas[1][0])
  const latMax = Math.max(esquinas[0][0], esquinas[1][0])
  const lonMin = Math.min(esquinas[0][1], esquinas[1][1])
  const lonMax = Math.max(esquinas[0][1], esquinas[1][1])
  const paso = Math.max(1, Math.round((lonMax - lonMin) / 6))

  for (let lon = Math.ceil(lonMin / paso) * paso; lon <= lonMax; lon += paso) {
    const [x] = proyeccion.aPixel(latMin, lon)
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, alto); ctx.stroke()
    ctx.fillText(`${lon}°`, x + 3, alto - 6)
  }
  for (let lat = Math.ceil(latMin / paso) * paso; lat <= latMax; lat += paso) {
    const [, y] = proyeccion.aPixel(lat, lonMin)
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(ancho, y); ctx.stroke()
    ctx.fillText(`${lat}°`, 4, y - 4)
  }
  ctx.restore()
}

function radio() { return 7.5 }

function dibujarPuntosCanvas(ctx, proyeccion) {
  for (const p of puntos) {
    const [x, y] = proyeccion.aPixel(p.lat, p.lon)
    ctx.beginPath()
    ctx.arc(x, y, radio(), 0, Math.PI * 2)
    ctx.fillStyle = rangoPorPct(p.pct).color
    ctx.fill()
    ctx.lineWidth = 1.6
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)'
    ctx.stroke()
    ctx.lineWidth = 0.8
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.5)'
    ctx.stroke()
  }
}

function dibujarPuntos() {
  if (modo === 'canvas') {
    const lienzo = $('#mapa-canvas')
    if (!lienzo.hidden) redibujarLienzo(lienzo)
    return
  }

  const bounds = L.latLngBounds(puntos.map((p) => [p.lat, p.lon]))
  for (const p of puntos) {
    const color = rangoPorPct(p.pct).color
    const marcador = L.marker([p.lat, p.lon], {
      icon: L.divIcon({
        className: '',
        html: `<div class="marcador" style="background:${color}"></div>`,
        iconSize: [15, 15],
        iconAnchor: [7, 7],
      }),
      keyboard: false,
    }).addTo(mapa)

    const html = htmlTooltip(p)
    marcador.on('mouseover', (e) => mostrarTooltip(e.originalEvent, html))
    marcador.on('mousemove', (e) => moverTooltip(e.originalEvent))
    marcador.on('mouseout', ocultarTooltip)
  }
  // animate:false es deliberado: con animación Leaflet encadena el cambio de
  // vista en requestAnimFrame, que el navegador NO ejecuta si la pestaña está
  // en segundo plano (queda en el setView inicial y el sur del país queda
  // fuera del encuadre). Sin animación el zoom se aplica en el acto.
  // El padding va en píxeles y chico: con pad(0.15) el encuadre crecía un
  // 30 % (15 % por lado) y dejaba el mapa un zoom afuera de lo justo, y con
  // 30 px el zoom 4 no entraba. 15 px cubre el radio del marcador (8 px).
  mapa.fitBounds(bounds, { padding: [15, 15], maxZoom: 9, animate: false })
}

function htmlTooltip(p) {
  const rango = rangoPorPct(p.pct)
  return `<strong>${p.localidad}</strong>` +
    `<span class="num">${p.provincia}${p.ccte ? ' · ' + p.ccte : ''}</span>` +
    `<span class="num">${pct(p.pct)} % de RNI · ${vm(p.vm)} V/m</span>` +
    `<span class="num">Nivel: ${rango.etiqueta}</span>`
}

/* --------------------------- tooltip en canvas --------------------------- */

function montarHoverCanvas() {
  const lienzo = $('#mapa-canvas')

  lienzo.addEventListener('mousemove', (evento) => {
    if (modo !== 'canvas' || !lienzo._proyeccion) return
    const rect = lienzo.getBoundingClientRect()
    const x = evento.clientX - rect.left
    const y = evento.clientY - rect.top

    let cercano = null
    let distancia = radio() + 4
    for (const p of puntos) {
      const [px, py] = lienzo._proyeccion.aPixel(p.lat, p.lon)
      const d = Math.hypot(px - x, py - y)
      if (d < distancia) { distancia = d; cercano = p }
    }

    if (cercano) {
      lienzo.style.cursor = 'pointer'
      mostrarTooltip(evento, htmlTooltip(cercano))
    } else {
      lienzo.style.cursor = ''
      ocultarTooltip()
    }
  })

  lienzo.addEventListener('mouseleave', ocultarTooltip)
}

/* ------------------------------- PNG ------------------------------------ */

function dibujarLeyenda(ctx, ancho) {
  const altoItem = 17
  const anchoCaja = 168
  const altoCaja = 26 + RANGOS.length * altoItem + 8
  const x = 12
  const y = 12

  ctx.save()
  ctx.fillStyle = 'rgba(255, 255, 255, 0.96)'
  ctx.strokeStyle = '#c6d3d8'
  ctx.lineWidth = 1
  ctx.beginPath()
  // roundRect no existe en navegadores viejos: se dibuja el rectángulo simple
  if (typeof ctx.roundRect === 'function') ctx.roundRect(x, y, anchoCaja, altoCaja, 6)
  else ctx.rect(x, y, anchoCaja, altoCaja)
  ctx.fill()
  ctx.stroke()

  ctx.fillStyle = '#12242b'
  ctx.font = '600 12.5px "Space Grotesk", sans-serif'
  ctx.fillText('% del límite normativo', x + 11, y + 19)

  ctx.font = '12px "IBM Plex Sans", sans-serif'
  RANGOS.forEach((rango, i) => {
    const cy = y + 30 + i * altoItem
    ctx.beginPath()
    ctx.arc(x + 18, cy - 4, 6.5, 0, Math.PI * 2)
    ctx.fillStyle = rango.color
    ctx.fill()
    ctx.lineWidth = 1
    ctx.strokeStyle = 'rgba(0,0,0,0.35)'
    ctx.stroke()
    ctx.fillStyle = '#4b5f68'
    ctx.fillText(rango.etiqueta, x + 32, cy)
  })
  ctx.restore()
}

function exportarPNG() {
  if (puntos.length === 0) { error('No hay puntos para descargar.'); return }

  const caja = document.querySelector('.mapa')
  const rect = caja.getBoundingClientRect()
  const escala = modo === 'canvas' ? 2 : (window.devicePixelRatio || 1)

  const salida = document.createElement('canvas')
  salida.width = Math.round(rect.width * escala)
  salida.height = Math.round(rect.height * escala)
  const ctx = salida.getContext('2d')
  ctx.scale(escala, escala)

  const ancho = rect.width
  const alto = rect.height
  ctx.fillStyle = '#eaf1f4'
  ctx.fillRect(0, 0, ancho, alto)

  if (modo === 'leaflet') {
    // se copian las teselas tal como se ven (todas con crossOrigin)
    document.querySelectorAll('#mapa-leaflet img.leaflet-tile-loaded').forEach((img) => {
      const r = img.getBoundingClientRect()
      try {
        ctx.drawImage(img, r.left - rect.left, r.top - rect.top, r.width, r.height)
      } catch (e) { /* tesela que no se pudo copiar: se queda el fondo */ }
    })
    puntos.forEach((p) => {
      const punto = mapa.latLngToContainerPoint([p.lat, p.lon])
      dibujarPunto(ctx, punto.x, punto.y, p)
    })
  } else {
    const lienzo = $('#mapa-canvas')
    const proyeccion = lienzo._proyeccion || proyectar(ancho, alto)
    dibujarGraticula(ctx, proyeccion, ancho, alto)
    for (const p of puntos) {
      const [x, y] = proyeccion.aPixel(p.lat, p.lon)
      dibujarPunto(ctx, x, y, p)
    }
  }

  dibujarLeyenda(ctx, ancho)

  const fecha = new Date().toISOString().slice(0, 10)
  salida.toBlob((blob) => {
    if (!blob) { error('No se pudo generar la imagen.'); return }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mapa_puntos_maximos_${fecha}.png`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 4000)
    aviso('Mapa descargado como PNG.')
  }, 'image/png')
}

function dibujarPunto(ctx, x, y, p) {
  ctx.beginPath()
  ctx.arc(x, y, radio(), 0, Math.PI * 2)
  ctx.fillStyle = rangoPorPct(p.pct).color
  ctx.fill()
  ctx.lineWidth = 1.6
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)'
  ctx.stroke()
  ctx.lineWidth = 0.8
  ctx.strokeStyle = 'rgba(0, 0, 0, 0.5)'
  ctx.stroke()
}

/* ----------------------------- exportación ------------------------------ */

function exportar() {
  if (puntos.length === 0) { error('No hay puntos para exportar.'); return }
  exportarXLSX({
    nombre: 'puntos_maximos',
    hoja: 'Mapa',
    encabezados: ['Localidad', 'Provincia', 'CCTE', 'Latitud', 'Longitud',
      'V/m máximo', '% RNI máximo', 'Nivel'],
    filas: puntos.map((p) => [
      p.localidad, p.provincia, p.ccte, p.lat, p.lon,
      p.vm, p.pct, rangoPorPct(p.pct).etiqueta,
    ]),
    formatos: [null, null, null, '0.00000', '0.00000', '0.###', '0.####', null],
    anchos: [30, 22, 24, 12, 12, 13, 15, 12],
  })
}

/* ------------------------------ montaje --------------------------------- */

let redimension = null

export function montar() {
  if (listo) return
  listo = true

  $('#mapa-png').addEventListener('click', exportarPNG)
  $('#mapa-exportar').addEventListener('click', exportar)
  montarHoverCanvas()

  // el mapa se acomoda si cambia el tamaño de la ventana
  redimension = () => {
    clearTimeout(redimension._t)
    redimension._t = setTimeout(() => refrescar(), 180)
  }
  window.addEventListener('resize', redimension)
}
