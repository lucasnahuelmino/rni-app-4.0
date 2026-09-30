<script setup>
import { ref, computed, createApp, h, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { mapApi, reportsApi } from '../services/domains'
import { useFiltrosStore } from '../stores/filtros'
import { useColorScaleStore } from '../stores/colorScale'
import { tokenConAlfa } from '../assets/tokens'
import DataPanel from '../components/DataPanel.vue'
import MapPopup from '../components/mapa/MapPopup.vue'

const filtros = useFiltrosStore()
const escala = useColorScaleStore()

// Arranca en true: apretar un CCTE en el panel de filtros tiene que filtrar
// los puntos, que es lo primero que se espera al usarlo. Sigue siendo una
// casilla, así que quien quiera ver todos los centros juntos la desmarca y
// listo. (Antes arrancaba en false: el mapa ignoraba los filtros del topbar
// y, encima, el panel quedaba tapado por el mapa -- motivo por el que parecía
// que "apretar un CCTE no filtraba nada".)
const aplicarFiltros = ref(true)
const localidadBusqueda = ref('')
const loading = ref(false)
const error = ref(null)
const truncado = ref(false)
const totalDisponible = ref(0)
const puntosMostrados = ref(0)
const zoomActual = ref(null)

const mapContainer = ref(null)
let mapa = null
let capaMarcadores = null

/**
 * El modo pasa a ser automático según el zoom y reemplaza al selector manual
 * "Todos los puntos / Máximo por localidad".
 *
 * Por debajo de ZOOM_DETALLE se muestra UN punto por localidad: el de mayor
 * % del límite. Desde ese zoom en adelante, todos los puntos del área
 * visible.
 *
 * El motivo es de lectura y no de rendimiento: a la vista nacional hay 4.968
 * puntos concentrados en prácticamente cinco zonas (Comodoro Rivadavia,
 * Neuquén, Córdoba, Salta, Posadas), así que dentro de cada zona se apilan en
 * unos pocos píxeles y las localidades chicas -- que en la muestra tienen
 * entre 3 y 9 puntos -- quedan tapadas por las grandes. Con un representante
 * por localidad, la vista general muestra las 61 localidades separadas, que
 * es lo que importa mirar de lejos; al acercar a una zona entran todos los
 * puntos del rectángulo que se está mirando.
 *
 * ZOOM_DETALLE = 7 es una escala provincial (~2.8° de alto): ahí ya se mira
 * una zona concreta y tiene sentido pedir todo lo que hay en ella.
 */
const ZOOM_DETALLE = 7

const modo = computed(() => {
  // La búsqueda por localidad tiene prioridad sobre todo lo demás: si estás
  // buscando una ciudad, tiene que traer sus puntos aunque el mapa esté en
  // la otra punta del país (el backend aplica bbox y localidad con AND, así
  // que mandar bbox aquí devolvería 0 puntos para algo que sí existe).
  if (localidadBusqueda.value.trim()) return 'todos'
  if (zoomActual.value == null) return 'max_localidad'
  return zoomActual.value < ZOOM_DETALLE ? 'max_localidad' : 'todos'
})

// Una sola línea en la barra, que explica lo que el selector manual dejaba
// de decir. Cambia con el zoom, así que hay que leer el estado reactivamente.
const modoNota = computed(() => {
  const buscando = localidadBusqueda.value.trim()
  if (buscando) return `Mostrando "${buscando}" en todo el país, sin importar el viewport.`
  if (modo.value === 'max_localidad') {
    return 'Vista general: 1 punto por localidad (el de mayor % del límite). Acercá para ver todos los puntos.'
  }
  return 'Zoom de detalle: todos los puntos del área visible.'
})

// La primera carga sí merece un estado grande en pantalla; las refetch que
// dispara cada pan/zoom solo muestran un aviso chico, porque tapar el mapa
// entero cada vez que se mueve sería insoportable.
const primeraCarga = computed(() => loading.value && puntosMostrados.value === 0)

// El viewport actual en el formato que espera el backend:
// "lat_min,lat_max,lon_min,lon_max".
function bboxActual() {
  if (!mapa) return undefined
  const b = mapa.getBounds()
  return `${b.getSouth()},${b.getNorth()},${b.getWest()},${b.getEast()}`
}

// Clave de todo lo que cambia la respuesta. Leaflet dispara moveend en
// varios momentos en los que el viewport no varió, y sin esta guarda cada
// pan o zoom volvería a pedir exactamente lo mismo.
let ultimaClave = null
let debounceMovimiento = null
let debounceBusqueda = null

async function cargarPuntos() {
  const base = aplicarFiltros.value ? filtros : { ccte: [], provincia: [], anio: [] }
  const buscando = localidadBusqueda.value.trim()

  const solicitud = {
    ccte: [...base.ccte],
    provincia: [...base.provincia],
    anio: [...base.anio],
    localidad: buscando ? [buscando] : [],
    modo: modo.value,
    bbox: buscando ? undefined : bboxActual(),
  }

  const clave = JSON.stringify(solicitud)
  if (clave === ultimaClave) return
  ultimaClave = clave

  loading.value = true
  error.value = null
  try {
    const filtrosAEnviar = {
      ccte: solicitud.ccte,
      provincia: solicitud.provincia,
      anio: solicitud.anio,
      localidad: solicitud.localidad,
    }
    const { data } = await mapApi.getMap(filtrosAEnviar, {
      modo: solicitud.modo,
      bbox: solicitud.bbox,
    })
    truncado.value = data.truncado
    totalDisponible.value = data.total_disponible
    puntosMostrados.value = data.puntos.length
    pintar(data.puntos)
  } catch (e) {
    error.value = e
    // Si no se limpia, "Reintentar" chocaría con la misma clave y el botón
    // no haría nada.
    ultimaClave = null
  } finally {
    loading.value = false
  }
}

/* --- Popup ---------------------------------------------------------------
   Una única app de Vue para TODOS los marcadores: montar una por punto
   serían miles de instancias con la vista cargada. El componente vive en
   components/mapa/MapPopup.vue y recibe el punto y el store de la escala por
   props, así que no necesita Pinia propio. */
const puntoActivo = ref(null)
let elPopup = null
let appPopup = null

function prepararPopup() {
  elPopup = document.createElement('div')
  appPopup = createApp({
    render: () => (puntoActivo.value ? h(MapPopup, { punto: puntoActivo.value, escala }) : null),
  })
  appPopup.mount(elPopup)
}

function pintar(puntos) {
  capaMarcadores.clearLayers()

  // Borde marino sobre el relleno del semáforo. No es cosmético: cuatro de
  // los diez rangos (#84C2F5, #A9E7A9, #89DD89, #D9FF00) miden entre 1.15 y
  // 1.91:1 contra el fondo blanco y, con borde del mismo color que el
  // relleno, casi no se recortaban. El borde va a --ink al 55%, que contra
  // blanco da doble dígito siempre; el color sigue siendo el del dato.
  const borde = tokenConAlfa('--ink', 0.55, '#0b1742')

  for (const p of puntos) {
    L.circleMarker([p.lat, p.lon], {
      radius: 5,
      color: borde,
      weight: 1,
      fillColor: escala.colorPorPct(p.resultado_pct),
      fillOpacity: 0.9,
    })
      // El mismo elemento va como contenido de todos los popups: solo hay
      // uno abierto a la vez, así que nunca está en dos lugares. Vue escapa
      // {{ }} solo, así que no hay HTML armado a mano que sanitizar.
      .bindPopup(elPopup, {
        className: 'popup-rni',
        maxWidth: 320,
        minWidth: 200,
        autoClose: true,
        closeButton: true,
      })
      .on('click', () => {
        puntoActivo.value = p
      })
      .addTo(capaMarcadores)
  }
}

onMounted(async () => {
  await escala.asegurarCargado()
  prepararPopup()

  mapa = L.map(mapContainer.value, {
    // Teselas de OpenStreetMap. Es un mapa POLÍTICO: no trae alturas ni
    // sombreado (lo que pide el usuario es "sin relieve"), y el filtro del
    // CSS sobre el tile pane (`grayscale(1) brightness(1.08)`) lo deja en
    // blanco y negro y tirado hacia el blanco, así los colores del semáforo
    // siguen siendo la única información cromática de la pantalla.
    //
    // La atribución es obligatoria: OpenStreetMap la exige, así que el
    // control vuelve a estar encendido.
    attributionControl: true,
  }).setView([-38.4, -63.6], 4) // centro aproximado de Argentina

  // Se probó primero CARTO Positron, que es más limpio (solo bordes y
  // etiquetas, sin calles), pero desde que pasó a pedir API key devuelve un
  // placeholder con el texto "API key required" dibujado DENTRO de la tesela
  // -- ni siquiera tira un HTTP error, así que no se detecta de otro modo que
  // mirando los bytes. El servidor de OpenStreetMap no pide clave y el
  // pedido era justamente "los mapas de OpenStreetMap".
  //
  // Sin conexión no cargan las teselas y queda el fondo `--surface` que ya
  // tiene el contenedor: el mapa se sigue pudiendo usar igual.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(mapa)

  capaMarcadores = L.layerGroup().addTo(mapa)
  zoomActual.value = mapa.getZoom()

  // moveend también dispara al hacer zoom, que es cuando hay que pedir los
  // puntos del área que se está mirando en vez de una muestra nacional, y
  // además recién ahí cambia el modo. Se registra DESPUÉS del setView
  // inicial para que no dispare un segundo fetch junto con el de abajo; la
  // clave de dedupe es una red de seguridad más.
  mapa.on('moveend', () => {
    zoomActual.value = mapa.getZoom()
    clearTimeout(debounceMovimiento)
    debounceMovimiento = setTimeout(cargarPuntos, 250)
  })

  // Si el contenedor todavía no tenía tamaño al montar, el primer bbox sale
  // degenerado y el backend devuelve casi nada. Se acomoda el tamaño y recién
  // ahí se pide el primer load.
  await nextTick()
  mapa.invalidateSize()
  cargarPuntos()
})

onBeforeUnmount(() => {
  clearTimeout(debounceMovimiento)
  clearTimeout(debounceBusqueda)
  mapa?.remove()
  mapa = null
  appPopup?.unmount()
  elPopup?.remove()
  appPopup = null
  elPopup = null
})

watch(aplicarFiltros, cargarPuntos)
watch(
  () => [filtros.ccte.slice(), filtros.provincia.slice(), filtros.anio.slice()],
  () => {
    if (aplicarFiltros.value) cargarPuntos()
  },
  { deep: true },
)

function onLocalidadInput() {
  clearTimeout(debounceBusqueda)
  debounceBusqueda = setTimeout(cargarPuntos, 400)
}

// --- salida impresa del mapa -------------------------------------------------

// Leaflet pinta con tiles + SVG, que no se pueden copiar a un archivo: para
// descargar una imagen o mandarla a la impresora hay que repintar todo en un
// canvas. La posicion de cada tesela se calcula con la proyeccion Web Mercator
// del estandar XYZ (la que usa OpenStreetMap) y no con APIs internas de
// Leaflet, para que no se rompa si se actualiza la libreria.
function mundoX(lon, zoom) {
  return ((lon + 180) / 360) * 256 * 2 ** zoom
}

function mundoY(lat, zoom) {
  const rad = (lat * Math.PI) / 180
  return ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * 256 * 2 ** zoom
}

function cargarTile(url) {
  return new Promise((resolve) => {
    const img = new Image()
    // crossOrigin es lo que permite leer el canvas despues: sin el, el tile
    // "contamina" el canvas y toBlob() tira un SecurityError.
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = url
  })
}

function tilesVisibles() {
  const zoom = mapa.getZoom()
  const size = mapa.getSize()
  const bounds = mapa.getBounds()
  const x0 = mundoX(bounds.getWest(), zoom)
  const y0 = mundoY(bounds.getNorth(), zoom)
  const n = 2 ** zoom

  const tiles = []
  const desdeX = Math.floor(x0 / 256)
  const hastaX = Math.floor((x0 + size.x) / 256)
  const desdeY = Math.floor(y0 / 256)
  const hastaY = Math.floor((y0 + size.y) / 256)
  for (let tx = desdeX; tx <= hastaX; tx++) {
    // Wrap horizontal: si el mapa quedo pasando el antimeridiano, el mismo tile
    // se pide de nuevo y no se deja un hueco.
    const txModulo = ((tx % n) + n) % n
    for (let ty = desdeY; ty <= hastaY; ty++) {
      if (ty < 0 || ty >= n) continue
      tiles.push({
        url: `https://tile.openstreetmap.org/${zoom}/${txModulo}/${ty}.png`,
        dx: tx * 256 - x0,
        dy: ty * 256 - y0,
      })
    }
  }
  return tiles
}

function dibujarPuntos(ctx) {
  if (!capaMarcadores) return
  capaMarcadores.eachLayer((layer) => {
    const p = mapa.latLngToContainerPoint(layer.getLatLng())
    const op = layer.options || {}
    ctx.globalAlpha = op.fillOpacity ?? 1
    ctx.beginPath()
    // getRadius() de CircleMarker devuelve pixeles (no metros como Circle).
    ctx.arc(p.x, p.y, layer.getRadius(), 0, Math.PI * 2)
    ctx.fillStyle = op.fillColor || op.color || '#006BD6'
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.lineWidth = op.weight ?? 1
    ctx.strokeStyle = op.color || '#ffffff'
    ctx.stroke()
  })
}

function dibujarLeyenda(ctx) {
  const rangos = escala.rangos || []
  if (!rangos.length) return
  const items = rangos.length + 1 // +1 por "Sin dato"
  const ancho = 130
  const alto = 30 + items * 15
  const x = 8
  const y = ctx.canvas.height - alto - 8

  ctx.save()
  ctx.globalAlpha = 0.95
  ctx.fillStyle = '#ffffff'
  ctx.strokeStyle = '#B7BFD1'
  ctx.lineWidth = 1
  ctx.beginPath()
  if (ctx.roundRect) ctx.roundRect(x, y, ancho, alto, 6)
  else ctx.rect(x, y, ancho, alto)
  ctx.fill()
  ctx.stroke()
  ctx.globalAlpha = 1

  ctx.textBaseline = 'middle'
  ctx.fillStyle = '#0B1742'
  ctx.font = '600 11px system-ui, sans-serif'
  ctx.fillText('% del límite normativo', x + 7, y + 15)

  const pintar = (cy, color, texto) => {
    ctx.beginPath()
    ctx.arc(x + 11, cy, 5, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
    ctx.fillStyle = '#0B1742'
    ctx.font = '11px system-ui, sans-serif'
    ctx.fillText(texto, x + 19, cy)
  }
  rangos.forEach((r, i) => pintar(y + 30 + i * 15, r.color, r.etiqueta))
  pintar(y + 30 + rangos.length * 15, escala.colorPorPct(null), 'Sin dato')
  ctx.restore()
}

/**
 * Repinta lo que se esta viendo en pantalla: teselas, puntos y leyenda.
 *
 * Los filtros globales NO se interpretan aca: se dibuja lo que hay
 * efectivamente en la capa de marcadores, que ya los aplico (o no) segun el
 * casillero "Usar filtros globales". Asi la imagen refleja la pantalla y no
 * una logica paralela que podria discrepar.
 */
async function capturarMapa() {
  if (!mapa) throw new Error('El mapa todavia no esta listo')
  const size = mapa.getSize()
  const canvas = document.createElement('canvas')
  canvas.width = size.x
  canvas.height = size.y
  const ctx = canvas.getContext('2d')

  // Fondo blanco: si alguna tesela no carga, queda aire y no un hueco negro.
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, size.x, size.y)

  const tiles = tilesVisibles()
  const PARALELOS = 8
  for (let i = 0; i < tiles.length; i += PARALELOS) {
    const tanda = tiles.slice(i, i + PARALELOS)
    const imgs = await Promise.all(tanda.map((t) => cargarTile(t.url)))
    // El mismo filtro que aplica el CSS al panel del mapa: tesela politica,
    // sin relieve, blanco/gris (grayscale(1) brightness(1.08)).
    ctx.filter = 'grayscale(1) brightness(1.08)'
    imgs.forEach((img, k) => {
      if (img) ctx.drawImage(img, Math.round(tanda[k].dx), Math.round(tanda[k].dy))
    })
    ctx.filter = 'none'
  }

  dibujarPuntos(ctx)
  dibujarLeyenda(ctx)
  return canvas
}

const exportando = ref(false)
const mensajeExport = ref('')

function notasDeSalida() {
  const notas = [
    aplicarFiltros.value
      ? 'Con los filtros globales del topbar aplicados.'
      : 'Sin los filtros globales del topbar: todos los centros juntos.',
    modoNota.value,
  ]
  if (localidadBusqueda.value) notas.push(`Búsqueda: ${localidadBusqueda.value}`)
  if (truncado.value) {
    notas.push(
      `${puntosMostrados.value} de ${totalDisponible.value} puntos en pantalla; hacer zoom para cargar los del área.`,
    )
  }
  return notas
}

function paraBlob(canvas) {
  return new Promise((resolve, reject) => {
    try {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('El navegador no devolvio la imagen'))),
        'image/png',
      )
    } catch (e) {
      // SecurityError: pasa si algun tile entro sin crossOrigin y el canvas
      // quedo "contaminado" (ilegible para JS).
      reject(e)
    }
  })
}

function sello() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`
}

function descargar(blob, nombre) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

async function conExportacion(tarea, mensajeFallo) {
  if (exportando.value) return
  exportando.value = true
  mensajeExport.value = ''
  try {
    await tarea()
  } catch (e) {
    console.error(e)
    mensajeExport.value = mensajeFallo
  } finally {
    exportando.value = false
  }
}

function descargarImagenMapa() {
  return conExportacion(async () => {
    const blob = await paraBlob(await capturarMapa())
    descargar(blob, `Mapa_RNI_${sello()}.png`)
  }, 'No se pudo generar la imagen del mapa.')
}

function descargarPdfMapa() {
  return conExportacion(async () => {
    const canvas = await capturarMapa()
    const resp = await reportsApi.postMapPdf({
      png: canvas.toDataURL('image/png'),
      titulo: 'Mapa de mediciones RNI',
      notas: notasDeSalida(),
    })
    descargar(resp.data, `Mapa_RNI_${sello()}.pdf`)
  }, 'No se pudo generar el PDF del mapa.')
}

function imprimirMapa() {
  // Se imprime la captura en una ventana aparte y no la pagina de la app: asi
  // el impreso es exactamente lo que se esta viendo (con sus filtros o sin
  // ellos, segun el casillero) y no hace falta desarmar el layout para que
  // entre en el papel. Desde el dialogo de impresion del navegador ademas se
  // elige "Guardar como PDF", que es la otra salida que se ofrece.
  return conExportacion(async () => {
    const canvas = await capturarMapa()
    const dataUrl = canvas.toDataURL('image/png')
    const notas = notasDeSalida()
      .map((n) => `<li>${n}</li>`)
      .join('')
    const win = window.open('', '_blank')
    if (!win) throw new Error('El navegador bloqueo la ventana de impresion')
    win.document.write(
      '<!doctype html><html lang="es"><head><meta charset="utf-8">' +
        '<title>Mapa RNI</title><style>' +
        '@page { size: landscape; margin: 10mm; }' +
        'body { font-family: system-ui, sans-serif; margin: 12px; color: #0B1742; }' +
        'h1 { font-size: 15pt; margin: 0 0 4px; }' +
        'ul { margin: 0 0 10px 18px; padding: 0; font-size: 9pt; color: #5A6478; }' +
        'li { margin: 1px 0; }' +
        'img { width: 100%; }' +
        '</style></head><body>' +
        '<h1>Mapa de mediciones RNI</h1><ul>' + notas + '</ul>' +
        `<img src="${dataUrl}" alt="Mapa de mediciones RNI" ` +
        'onload="window.focus(); window.print();">' +
        '</body></html>',
    )
    win.document.close()
  }, 'No se pudo preparar la impresion del mapa.')
}
</script>

<template>
  <div class="mapa-vista">
    <!-- Una sola fila de controles. Antes eran fieldset + dos chips + dos
         checkboxes/inputs + tres párrafos de nota, y todo eso vivía en un
         panel del alto de una tabla: el mapa quedaba en 60vh rodeado de
         aire. -->
    <div class="mapa-barra">
      <label class="mapa-barra__buscar">
        <span class="sr-only">Buscar localidad</span>
        <input
          v-model="localidadBusqueda"
          type="search"
          placeholder="Buscar localidad…"
          @input="onLocalidadInput"
        />
      </label>

      <label
        class="mapa-toggle"
        title="Filtra los puntos con el CCTE / Provincia / ño elegidos en el panel de filtros del topbar. Desmárcalo para ver todos los centros juntos."
      >
        <input v-model="aplicarFiltros" type="checkbox" />
        Usar filtros globales
      </label>

      <!-- Salidas del mapa, en la misma fila que los filtros: la barra tiene
           que seguir achiquita, el mapa es lo que importa. -->
      <div class="mapa-barra__acciones">
        <button
          type="button"
          class="btn btn--ghost mapa-accion"
          title="Abre el mapa en una ventana aparte y lo manda a la impresora. Desde el dialogo del navegador tambien se elige Guardar como PDF."
          :disabled="exportando"
          @click="imprimirMapa"
        >
          Imprimir
        </button>
        <button
          type="button"
          class="btn btn--ghost mapa-accion"
          title="Descarga el mapa tal cual se esta viendo, en PNG"
          :disabled="exportando"
          @click="descargarImagenMapa"
        >
          Imagen
        </button>
        <button
          type="button"
          class="btn btn--ghost mapa-accion"
          title="Descarga el mapa tal cual se esta viendo, en PDF"
          :disabled="exportando"
          @click="descargarPdfMapa"
        >
          PDF
        </button>
        <p v-if="mensajeExport" class="mapa-accion__fallo" role="alert">
          {{ mensajeExport }}
        </p>
      </div>

      <p class="mapa-barra__modo">
        {{ modoNota }}
        <span v-if="!aplicarFiltros" class="mapa-barra__extra">
          · Sin los filtros globales del topbar.
        </span>
      </p>
    </div>

    <div class="mapa-escena">
      <div
        ref="mapContainer"
        class="mapa-canvas"
        role="application"
        aria-label="Mapa de mediciones RNI"
      ></div>

      <!-- role=list porque aria-label sobre un div sin role no se expone como
           nombre accesible: el lector de pantalla no anunciaba la leyenda -->
      <div
        class="mapa-float mapa-leyenda"
        role="list"
        aria-label="Referencia de niveles (% del límite normativo)"
      >
        <span class="mapa-leyenda__titulo">% del límite normativo</span>
        <span
          v-for="r in escala.rangos"
          :key="r.etiqueta"
          class="mapa-leyenda__item"
          role="listitem"
        >
          <span class="mapa-leyenda__dot" :style="{ background: r.color }"></span>{{ r.etiqueta }}
        </span>
        <span class="mapa-leyenda__item" role="listitem">
          <!-- colorPorPct(null) en vez de un hex suelto: es la misma fuente
               que usan los marcadores, así la leyenda no puede divergir -->
          <span class="mapa-leyenda__dot" :style="{ background: escala.colorPorPct(null) }"></span>
          Sin dato
        </span>
      </div>

      <!-- Todo lo transitorio va a una sola columna flotante arriba a la
           derecha: no altera el alto del mapa, así que Leaflet nunca queda
           con un tamaño viejo. -->
      <div class="mapa-float mapa-notas">
        <!-- Auditoría Fase 1: un límite nunca puede presentarse como "todos
             los puntos" sin decirlo. -->
        <p v-if="truncado" class="mapa-aviso">
          <strong class="num">{{ puntosMostrados }}</strong> de
          <strong class="num">{{ totalDisponible }}</strong> puntos · hacé zoom para cargar los del
          área
        </p>

        <div v-if="error || primeraCarga" class="mapa-overlay">
          <DataPanel
            :loading="primeraCarga && !error"
            :error="error"
            mensaje-cargando="Cargando puntos del mapa…"
            @reintentar="cargarPuntos"
          />
        </div>
        <p v-else-if="loading" class="mapa-estado" role="status">Actualizando…</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mapa-vista {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* --- barra de controles --- */
.mapa-barra {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  flex-wrap: wrap;
  background: var(--surface);
  border: 1px solid var(--line);
  padding: var(--space-3) var(--space-5);
}

.mapa-barra__buscar input {
  width: 190px;
  font-size: var(--fs-sm);
  padding: var(--space-2) var(--space-4);
}

.mapa-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--fs-sm);
  color: var(--ink-soft);
  white-space: nowrap;
}

.mapa-barra__modo {
  margin: 0;
  font-size: var(--fs-2xs);
  color: var(--ink-soft);
}

.mapa-barra__extra {
  color: var(--sin-dato);
}

.mapa-barra__acciones {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

/* A escala de la barra y no del .btn de formulario: son controles de paso,
   no acciones principales. */
.mapa-accion {
  font-size: var(--fs-2xs);
  padding: var(--space-1) var(--space-3);
}

.mapa-accion:disabled {
  opacity: 0.55;
  cursor: progress;
}

.mapa-accion__fallo {
  margin: 0;
  font-size: var(--fs-2xs);
  color: var(--risk-high, #cc0000);
}

/* --- escena: el mapa ocupa todo lo que queda --- */
.mapa-escena {
  position: relative;
  flex: 1;
  min-height: 0;
}

/* absolute+inset en vez de height:60vh: el tamaño lo da el contenedor, que
   ya es el resto del viewport, y un hermano que aparezca/desaparezca no
   cambia las dimensiones (Leaflet no se entera y no hay que pedirle un
   invalidateSize). */
.mapa-canvas {
  position: absolute;
  inset: 0;
  border: 1px solid var(--line);

  /* CLAVE: Leaflet pinta sus capas con z-index 400-800 (.leaflet-pane 400,
     .leaflet-control 800, popups 700). El contenedor no tenía z-index, así
     que esas capas NO estaban confinadas: competían directamente contra el
     resto de la página en el contexto raíz. El panel de filtros del topbar
     está en z-index 20 y quedaba DEBAJO del mapa -- imposible ver los CCTE
     ni marcar "Usar filtros globales".

     `isolation: isolate` crea el contexto de apilamiento SIN mover al mapa
     de lugar (sigue con z-index auto, o sea por debajo de todo lo que tenga
     z-index real): las 400-800 de Leaflet quedan adentro y los controles de
     la app, que están arriba, vuelven a ganarle. No se sube el z-index del
     topbar a lo loco porque eso taparía otras cosas (los popups del mapa
     siguen necesitando verse por encima del mapa, y se ven: están adentro. */
  isolation: isolate;
}

/* Leaflet trae fondo gris y controles con borde grueso y sombra: el sistema
   es hairline y cuadrado y sin elevación, así que se reescriben acá. Los
   estilos viven en un chunk aparte de tokens.css, de ahí la anidación. */
.mapa-canvas.leaflet-container {
  background: var(--surface);
  font-family: var(--font-ui);
}

/* OpenStreetMap viene bastante coloreado: agua en celeste, rutas en amarillo
   y naranja, usos de suelo en verde. grayscale(1) lo deja estrictamente en
   blanco y negro, que es lo que se pidió (mapa político, "sin colorear").
   brightness(1.08) tira para el lado del blanco: sin eso el mar queda en un
   gris medio (#AAD3DF pasado a gris ≈ 200/255) y todo se ve apagado. Con el
   brillo, la tierra (#F2EFE9 ≈ 239/255) satura a blanco puro y el agua queda
   en un gris muy claro, mientras que las etiquetas --que arrancan en ~#333--
   apenas se aclaran y siguen teniendo contraste.
   Va sobre el TILE PANE y no sobre el contenedor: el contenedor también
   contiene los marcadores, y descolorearlos arruinaría el semáforo. */
.mapa-canvas .leaflet-tile-pane {
  filter: grayscale(1) brightness(1.08);
}

/* La atribución es obligatoria (OpenStreetMap exige declararla), así que hay
   que reestilurarla: Leaflet la trae con fondo blanco opaco, borde y
   tipografía chiquita sin relación con el sistema. */
.mapa-canvas .leaflet-control-attribution {
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  color: var(--ink-soft);
  font-size: var(--fs-2xs);
  border-radius: 0;
  box-shadow: none;
}

.mapa-canvas .leaflet-control-attribution a {
  color: var(--signal-deep);
}

.mapa-canvas .leaflet-bar {
  border: 1px solid var(--line);
  border-radius: var(--radius-xs);
  box-shadow: none;
}

.mapa-canvas .leaflet-bar a {
  width: 26px;
  height: 26px;
  line-height: 26px;
  background: var(--surface);
  color: var(--ink);
  border-bottom-color: var(--line);
  border-radius: 0;
}

.mapa-canvas .leaflet-bar a:hover {
  background: var(--paper);
  color: var(--signal-deep);
}

.mapa-canvas .leaflet-bar a.leaflet-disabled {
  background: var(--surface);
  color: var(--sin-dato);
}

/* --- flotantes ---
   z-index 500 = por encima del fondo, por debajo del panel de marcadores
   (600) y de las ventanas (700): la leyenda no tapa puntos ni popups, y al
   no recibir clics tampoco los bloquea. */
.mapa-float {
  position: absolute;
  z-index: 500;
  pointer-events: none;
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  border: 1px solid var(--line);
}

.mapa-leyenda {
  left: var(--space-4);
  bottom: var(--space-4);
  /* Una columna y no una franja: tapa mucho menos mapa y es la misma
     disposicion que lleva la captura impresa, asi la imagen exportada
     coincide con lo que se ve en pantalla. */
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  line-height: 1.15;
  font-size: var(--fs-2xs);
  padding: var(--space-2) var(--space-3);
  /* ancho acotado: con la columna no hace falta dejar libre la derecha
     (las notas flotan arriba y no se pisan), pero no debe crecer */
  max-width: min(230px, calc(100% - 2 * var(--space-4)));
}

.mapa-leyenda__titulo {
  font-weight: 600;
  color: var(--ink);
  margin-bottom: var(--space-1);
}

.mapa-leyenda__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  white-space: nowrap;
}

.mapa-leyenda__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  /* igual que el borde de los marcadores: los tramos claros del semáforo
     sobre blanco casi no se recortan solos */
  border: 1px solid color-mix(in srgb, var(--ink) 55%, transparent);
  display: inline-block;
}

.mapa-notas {
  top: var(--space-4);
  right: var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-3);
  max-width: min(340px, calc(100% - 2 * var(--space-4)));
  /* el botón "Reintentar" del ErrorState tiene que seguir clickeable */
  background: none;
  border: 0;
}

.mapa-notas > * {
  pointer-events: auto;
}

.mapa-aviso {
  margin: 0;
  font-size: var(--fs-2xs);
  color: var(--risk-mid);
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  border: 1px solid var(--line);
  padding: var(--space-3) var(--space-4);
}

.mapa-overlay {
  background: var(--surface);
  border: 1px solid var(--line);
}

.mapa-estado {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--fs-2xs);
  color: var(--ink-soft);
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  border: 1px solid var(--line);
  padding: var(--space-2) var(--space-4);
}
</style>
