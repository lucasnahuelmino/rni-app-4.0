<script setup>
import { ref, computed, createApp, h, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { mapApi } from '../services/domains'
import { useFiltrosStore } from '../stores/filtros'
import { useColorScaleStore } from '../stores/colorScale'
import { tokenConAlfa } from '../assets/tokens'
import DataPanel from '../components/DataPanel.vue'
import MapPopup from '../components/mapa/MapPopup.vue'

const filtros = useFiltrosStore()
const escala = useColorScaleStore()

const aplicarFiltros = ref(false)
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
        title="Los filtros globales de CCTE/Provincia/Año del topbar no afectan al mapa a menos que actives esta casilla."
      >
        <input v-model="aplicarFiltros" type="checkbox" />
        Usar filtros globales
      </label>

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
        <span
          v-for="r in escala.rangos"
          :key="r.etiqueta"
          class="mapa-leyenda__item"
          :class="{ 'mapa-leyenda__item--alerta': r.hasta == null }"
          role="listitem"
        >
          <span class="mapa-leyenda__dot" :style="{ background: r.color }"></span>{{ r.etiqueta }}
          <!-- El único rango abierto (hasta == null) no es "un escalón más
               de la escala" sino una excedencia de la MEP: puntos que el
               área técnica revisa después y en detalle. Se marca con texto
               y no solo con color, que es la regla del semáforo de la UI
               (ver DESIGN.md, --risk-high). -->
          <span v-if="r.hasta == null" class="mapa-leyenda__aviso">excede la MEP</span>
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
  display: flex;
  gap: var(--space-6);
  flex-wrap: wrap;
  font-size: var(--fs-2xs);
  padding: var(--space-3) var(--space-4);
  /* deja libre la columna derecha para las notas, para que no se pisen */
  max-width: calc(100% - 340px);
}

.mapa-leyenda__item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  white-space: nowrap;
}

/* El rango abierto (≥100 %) no es "el último escalón de la escala": es una
   excedencia de la MEP, que el área técnica revisa después y en detalle. Se
   le agrega texto propio en forma de pastilla -- --risk-high pasa WCAG AA
   sobre --surface, y la regla del semáforo de la UI es que NUNCA haya
   información solo por color (ver DESIGN.md). Así la leyenda no puede
   presentar un límite normativo como si fuera simplemente "el rojo más
   fuerte". */
.mapa-leyenda__aviso {
  font-weight: 600;
  color: var(--risk-high);
  padding: 1px var(--space-3);
  border: 1px solid color-mix(in srgb, var(--risk-high) 35%, transparent);
  background: color-mix(in srgb, var(--risk-high) 7%, var(--surface));
  border-radius: var(--radius-full);
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
