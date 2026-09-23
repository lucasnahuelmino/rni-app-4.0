<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import { mapApi } from '../services/domains'
import { useFiltrosStore } from '../stores/filtros'
import LoadingState from '../components/LoadingState.vue'
import ErrorState from '../components/ErrorState.vue'

import {
  RNI_COLOR_SCALE,
  getColorPorPct,
} from '../constants'

const filtros = useFiltrosStore()

const aplicarFiltros = ref(false)
const modoMapa = ref('all')

const loading = ref(false)
const error = ref(null)

const truncado = ref(false)
const totalDisponible = ref(0)

const mapContainer = ref(null)

let mapa = null
let capaMarcadores = null

async function cargarPuntos() {
  loading.value = true
  error.value = null

  try {
    const filtrosAEnviar = aplicarFiltros.value
      ? filtros
      : {
          ccte: [],
          provincia: [],
          anio: [],
        }

    const { data } = await mapApi.getMap(
      filtrosAEnviar,
      {
        modo: modoMapa.value,
      },
    )

    truncado.value = data.truncado
    totalDisponible.value = data.total_disponible

    capaMarcadores.clearLayers()

    data.puntos.forEach((p) => {
      L.circleMarker(
        [p.lat, p.lon],
        {
          radius: 5,
          color: getColorPorPct(p.resultado_pct),
          fillColor: getColorPorPct(p.resultado_pct),
          fillOpacity: 0.8,
          weight: 1,
        },
      )
        .bindPopup(
          `<strong>${p.localidad}</strong> (${p.ccte})<br/>
          ${p.resultado_vm?.toFixed(2) ?? '—'} V/m
          ${
            p.resultado_pct != null
              ? ` · ${p.resultado_pct.toFixed(1)}%`
              : ''
          }`,
        )
        .addTo(capaMarcadores)
    })
  }
  catch (e) {
    error.value = e
  }
  finally {
    loading.value = false
  }
}

onMounted(() => {
  mapa = L.map(mapContainer.value)
    .setView([-38.4, -63.6], 4)

  L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
      attribution: '&copy; OpenStreetMap contributors',
    },
  ).addTo(mapa)

  capaMarcadores = L.layerGroup().addTo(mapa)

  cargarPuntos()
})

onBeforeUnmount(() => {
  mapa?.remove()
})

watch(aplicarFiltros, cargarPuntos)

watch(modoMapa, cargarPuntos)

watch(
  () => [
    filtros.ccte.slice(),
    filtros.provincia.slice(),
    filtros.anio.slice(),
  ],
  () => {
    if (aplicarFiltros.value) {
      cargarPuntos()
    }
  },
  { deep: true },
)
</script>

<template>
  <div class="mapa-vista">
    <div class="mapa-controles panel">

      <label class="mapa-toggle">
        <input
          v-model="aplicarFiltros"
          type="checkbox"
        />
        Aplicar los filtros globales al mapa
      </label>

      <label class="mapa-selector">
        Modo de visualización

        <select v-model="modoMapa">
          <option value="all">
            🌎 Todos los puntos
          </option>

          <option value="max_localidad">
            📍 Máximo por localidad
          </option>

          <option value="relevantes">
            🎯 Puntos relevantes
          </option>
        </select>
      </label>

      <p
        v-if="!aplicarFiltros"
        class="mapa-nota"
      >
        El mapa está mostrando
        <strong>todos los puntos</strong>
        sin aplicar filtros globales.
      </p>

      <p
        v-if="truncado"
        class="mapa-nota mapa-nota--aviso"
      >
        Mostrando una muestra de los puntos disponibles
        ({{ totalDisponible }} registros).
      </p>

      <div
        class="mapa-leyenda"
        aria-label="Escala histórica RNI"
      >
        <span
          v-for="item in RNI_COLOR_SCALE"
          :key="item.label"
          class="mapa-leyenda__item"
        >
          <span
            class="mapa-leyenda__dot"
            :style="{ backgroundColor: item.color }"
          />

          {{ item.label }}
        </span>
      </div>
    </div>

    <ErrorState
      v-if="error"
      @reintentar="cargarPuntos"
    />

    <LoadingState
      v-else-if="loading"
      mensaje="Cargando puntos del mapa…"
    />

    <div
      ref="mapContainer"
      class="mapa-canvas"
      role="application"
      aria-label="Mapa de mediciones RNI"
    />
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
  gap: 0.75rem;
}

.mapa-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.mapa-selector {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.mapa-selector select {
  min-width: 220px;
}

.mapa-nota {
  font-size: 0.85rem;
  color: var(--ink-soft);
  margin: 0;
}

.mapa-nota--aviso {
  color: var(--risk-mid);
}

.mapa-leyenda {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.5rem;
  font-size: 0.8rem;
}

.mapa-leyenda__item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.mapa-leyenda__dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
  border: 1px solid rgba(0,0,0,.25);
}

.mapa-canvas {
  height: 60vh;
  min-height: 400px;
  border: 1px solid var(--line);
}
</style>