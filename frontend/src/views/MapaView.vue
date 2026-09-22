<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { mapApi } from '../services/domains'
import { useFiltrosStore } from '../stores/filtros'
import LoadingState from '../components/LoadingState.vue'
import ErrorState from '../components/ErrorState.vue'

const filtros = useFiltrosStore()
const aplicarFiltros = ref(false)
const loading = ref(false)
const error = ref(null)
const truncado = ref(false)
const totalDisponible = ref(0)

const mapContainer = ref(null)
let mapa = null
let capaMarcadores = null

// Mismos umbrales que SemaforoBadge.vue -- una sola fuente para que la
// leyenda del mapa y el badge de la tabla nunca queden desincronizados
// (Auditoría Fase 1, hallazgo A11).
function colorPorPct(pct) {
  if (pct == null) return '#9aa5ab'
  if (pct < 25) return '#2f8f5b'
  if (pct < 80) return '#c98a1f'
  return '#b23a3a'
}

async function cargarPuntos() {
  loading.value = true
  error.value = null
  try {
    const filtrosAEnviar = aplicarFiltros.value ? filtros : { ccte: [], provincia: [], anio: [] }
    const { data } = await mapApi.getMap(filtrosAEnviar)
    truncado.value = data.truncado
    totalDisponible.value = data.total_disponible

    capaMarcadores.clearLayers()
    data.puntos.forEach((p) => {
      L.circleMarker([p.lat, p.lon], {
        radius: 5,
        color: colorPorPct(p.resultado_pct),
        fillColor: colorPorPct(p.resultado_pct),
        fillOpacity: 0.8,
        weight: 1,
      })
        .bindPopup(
          `<strong>${p.localidad}</strong> (${p.ccte})<br/>${p.resultado_vm?.toFixed(2) ?? '—'} V/m` +
            (p.resultado_pct != null ? ` · ${p.resultado_pct.toFixed(1)}%` : ''),
        )
        .addTo(capaMarcadores)
    })
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  mapa = L.map(mapContainer.value).setView([-38.4, -63.6], 4) // centro aproximado de Argentina
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(mapa)
  capaMarcadores = L.layerGroup().addTo(mapa)
  cargarPuntos()
})

onBeforeUnmount(() => {
  mapa?.remove()
})

watch(aplicarFiltros, cargarPuntos)
watch(
  () => [filtros.ccte.slice(), filtros.provincia.slice(), filtros.anio.slice()],
  () => {
    if (aplicarFiltros.value) cargarPuntos()
  },
  { deep: true },
)
</script>

<template>
  <div class="mapa-vista">
    <div class="mapa-controles panel">
      <label class="mapa-toggle">
        <input type="checkbox" v-model="aplicarFiltros" />
        Aplicar los filtros globales al mapa
      </label>
      <p v-if="!aplicarFiltros" class="mapa-nota">
        El mapa está mostrando <strong>todos</strong> los puntos, sin los filtros globales activos.
      </p>
      <p v-if="truncado" class="mapa-nota mapa-nota--aviso">
        Mostrando una muestra de los puntos disponibles ({{ totalDisponible }} en total). Acercá el zoom o agregá
        filtros para ver el detalle completo de una zona.
      </p>

      <div class="mapa-leyenda" aria-label="Referencia de niveles">
        <span class="mapa-leyenda__item"><span class="mapa-leyenda__dot" style="background:#2f8f5b"></span>Bajo (&lt;25%)</span>
        <span class="mapa-leyenda__item"><span class="mapa-leyenda__dot" style="background:#c98a1f"></span>Moderado (25–80%)</span>
        <span class="mapa-leyenda__item"><span class="mapa-leyenda__dot" style="background:#b23a3a"></span>Alto (≥80%)</span>
        <span class="mapa-leyenda__item"><span class="mapa-leyenda__dot" style="background:#9aa5ab"></span>Sin dato</span>
      </div>
    </div>

    <ErrorState v-if="error" @reintentar="cargarPuntos" />
    <LoadingState v-else-if="loading" mensaje="Cargando puntos del mapa…" />
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
  gap: 0.5rem;
}

.mapa-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
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
  gap: 1rem;
  flex-wrap: wrap;
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.mapa-leyenda__item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.mapa-leyenda__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.mapa-canvas {
  height: 60vh;
  min-height: 400px;
  border: 1px solid var(--line);
}
</style>
