<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { mapApi } from '../services/domains'
import { useFiltrosStore } from '../stores/filtros'
import { useColorScaleStore } from '../stores/colorScale'
import DataPanel from '../components/DataPanel.vue'

const filtros = useFiltrosStore()
const escala = useColorScaleStore()

const aplicarFiltros = ref(false)
const modo = ref('todos') // 'todos' | 'max_localidad'
const localidadBusqueda = ref('')
const loading = ref(false)
const error = ref(null)
const truncado = ref(false)
const totalDisponible = ref(0)
const puntosMostrados = ref(0)

const mapContainer = ref(null)
let mapa = null
let capaMarcadores = null

// El popup se construye como HTML y el backend devuelve texto libre
// (localidad/CCTE), así que hay que escaparlo: sin esto cualquier dato con
// <img onerror=...> se ejecutaba en la sesión de quien abría el mapa.
const ESCAPAR = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
function escaparHtml(valor) {
  return String(valor ?? '').replace(/[&<>"']/g, (c) => ESCAPAR[c])
}

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

async function cargarPuntos() {
  const base = aplicarFiltros.value ? filtros : { ccte: [], provincia: [], anio: [] }
  const buscando = localidadBusqueda.value.trim()

  // La búsqueda por localidad tiene prioridad sobre el viewport: el backend
  // aplica bbox y localidad con AND, así que buscar una ciudad mientras el
  // mapa está en la otra punta del país devolvería 0 puntos y se vería
  // "Sin datos" para algo que sí existe.
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

    capaMarcadores.clearLayers()
    data.puntos.forEach((p) => {
      const color = escala.colorPorPct(p.resultado_pct)
      L.circleMarker([p.lat, p.lon], {
        radius: 5,
        color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: 1,
      })
        .bindPopup(
          `<strong>${escaparHtml(p.localidad)}</strong> (${escaparHtml(p.ccte)})<br/>` +
            `${p.resultado_vm != null ? escaparHtml(p.resultado_vm.toFixed(2)) : '—'} V/m` +
            (p.resultado_pct != null
              ? ` · ${escaparHtml(p.resultado_pct.toFixed(1))}% · ${escaparHtml(escala.etiquetaPorPct(p.resultado_pct))}`
              : ''),
        )
        .addTo(capaMarcadores)
    })
  } catch (e) {
    error.value = e
    // Si no se limpia, "Reintentar" chocaría con la misma clave y el botón
    // no haría nada.
    ultimaClave = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await escala.asegurarCargado()
  mapa = L.map(mapContainer.value).setView([-38.4, -63.6], 4) // centro aproximado de Argentina
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(mapa)
  capaMarcadores = L.layerGroup().addTo(mapa)

  // moveend también dispara al hacer zoom, que es cuando queremos pedir los
  // puntos del área que se está mirando en vez de una muestra nacional.
  // Se registra DESPUÉS del setView inicial para que no dispare un segundo
  // fetch junto con el de abajo; la clave es una red de seguridad más.
  mapa.on('moveend', () => {
    clearTimeout(debounceMovimiento)
    debounceMovimiento = setTimeout(cargarPuntos, 250)
  })

  cargarPuntos()
})

onBeforeUnmount(() => {
  clearTimeout(debounceMovimiento)
  mapa?.remove()
})

watch([aplicarFiltros, modo], cargarPuntos)
watch(
  () => [filtros.ccte.slice(), filtros.provincia.slice(), filtros.anio.slice()],
  () => {
    if (aplicarFiltros.value) cargarPuntos()
  },
  { deep: true },
)

let debounceId = null
function onLocalidadInput() {
  clearTimeout(debounceId)
  debounceId = setTimeout(cargarPuntos, 400)
}
</script>

<template>
  <div class="mapa-vista">
    <div class="mapa-controles panel">
      <!-- Antes era un div[role=radiogroup] con botones que usaban
           aria-pressed: el radiogroup exige hijos role=radio + aria-checked,
           y aria-pressed estaba hardcodeado en "true" en el primero (siempre
           "seleccionado") y ausente en el segundo. Radios nativos dan el
           grupo, el aria-checked y la navegacion con flechas gratis. -->
      <fieldset class="mapa-modos">
        <legend class="sr-only">Qué puntos mostrar</legend>
        <label class="chip" :class="{ 'chip--active': modo === 'todos' }">
          <input v-model="modo" class="sr-only" type="radio" name="mapa-modo" value="todos" />
          🌎 Todos los puntos
        </label>
        <label class="chip" :class="{ 'chip--active': modo === 'max_localidad' }">
          <input v-model="modo" class="sr-only" type="radio" name="mapa-modo" value="max_localidad" />
          📍 Máximo por localidad
        </label>
      </fieldset>

      <label class="mapa-toggle">
        <input type="checkbox" v-model="aplicarFiltros" />
        Aplicar filtros al mapa (CCTE / Provincia / Año)
      </label>

      <label class="mapa-localidad">
        Buscar localidad
        <input
          v-model="localidadBusqueda"
          type="text"
          placeholder="Nombre exacto de la localidad…"
          @input="onLocalidadInput"
        />
      </label>

      <p v-if="!aplicarFiltros" class="mapa-nota">
        Mostrando el mapa <strong>nacional completo</strong>, sin los filtros globales de CCTE/Provincia/Año
        (el mapa no hereda esos filtros a menos que actives la casilla de arriba).
      </p>
      <p v-if="modo === 'max_localidad'" class="mapa-nota">
        Un punto por localidad: el de mayor % del límite registrado en cada una.
      </p>
      <p v-if="truncado" class="mapa-nota mapa-nota--aviso">
        Mostrando <strong>{{ puntosMostrados }} de {{ totalDisponible }}</strong> puntos de esta vista,
        repartidos en proporción entre todas las localidades. <strong>Hacé zoom</strong> para cargar los
        puntos del área que estés mirando.
      </p>

      <!-- role=list porque aria-label sobre un div sin role no se expone como
           nombre accesible: el lector de pantalla no anunciaba la leyenda -->
      <div class="mapa-leyenda" role="list" aria-label="Referencia de niveles (% del límite normativo)">
        <span v-for="r in escala.rangos" :key="r.etiqueta" class="mapa-leyenda__item" role="listitem">
          <span class="mapa-leyenda__dot" :style="{ background: r.color }"></span>{{ r.etiqueta }}
        </span>
        <span class="mapa-leyenda__item" role="listitem">
          <!-- colorPorPct(null) en vez de un hex suelto: es la misma fuente
               que usan los marcadores, así la leyenda no puede divergir -->
          <span class="mapa-leyenda__dot" :style="{ background: escala.colorPorPct(null) }"></span>Sin dato
        </span>
      </div>
    </div>

    <DataPanel :loading="loading" :error="error" mensaje-cargando="Cargando puntos del mapa…" @reintentar="cargarPuntos" />
    <div ref="mapContainer" class="mapa-canvas" role="application" aria-label="Mapa de mediciones RNI"></div>
  </div>
</template>

<style scoped>
.mapa-vista {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mapa-controles {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.mapa-modos {
  display: flex;
  gap: 0.5rem;
  /* reset de <fieldset>: sin esto trae borde UA, margen y
     min-inline-size:min-content que rompe el flex-wrap */
  border: 0;
  margin: 0;
  padding: 0;
  min-inline-size: 0;
}

.mapa-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.mapa-localidad {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: var(--ink-soft);
  max-width: 280px;
}

.mapa-nota {
  font-size: 0.8rem;
  color: var(--ink-soft);
  margin: 0;
}

.mapa-nota--aviso {
  color: var(--risk-mid);
}

.mapa-leyenda {
  display: flex;
  gap: 0.85rem;
  flex-wrap: wrap;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}

.mapa-leyenda__item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
}

.mapa-leyenda__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  display: inline-block;
}

.mapa-canvas {
  height: 60vh;
  min-height: 400px;
  border: 1px solid var(--line);
}
</style>
