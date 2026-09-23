<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { tiemposApi } from '../../services/domains'
import DataPanel from '../DataPanel.vue'

/**
 * Desglose de tiempo trabajado (tabs Diario / Mensual).
 *
 * Es el único bloque del detalle con carga propia: duerme su estado
 * (tab, datos, loading, error) y reacciona al cambio de localidad.
 *
 * OJO: NO lleva `:key` en el padre. Se observa la prop para recargar, y
 * eso deja que el tab activo se mantenga al cambiar de localidad -- que es
 * lo que hacía la versión original (seleccionar() no tocaba tabTiempo).
 * Si se le pusiera key, cada selección volvería a "Diario".
 */
const props = defineProps({
  localidad: { type: Object, required: true },
})

const tabTiempo = ref('diario') // 'diario' | 'mensual'
const tiempoDiario = ref(null)
const tiempoMensual = ref(null)
const loading = ref(false)
const error = ref(null)

async function cargar() {
  loading.value = true
  error.value = null
  try {
    const { ccte, provincia, localidad } = props.localidad
    const [diario, mensual] = await Promise.all([
      tiemposApi.getDiario(ccte, provincia, localidad),
      tiemposApi.getMensual({ ccte, provincia, localidad }),
    ])
    tiempoDiario.value = diario.data
    tiempoMensual.value = mensual.data
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}

watch(() => props.localidad, cargar, { immediate: true })

// El panel tiene dos tablas distintas según el tab activo, así que el
// estado vacío (y su mensaje) también cambian con él.
const vacio = computed(() =>
  tabTiempo.value === 'diario' ? !tiempoDiario.value?.length : !tiempoMensual.value?.length,
)
const mensajeVacio = computed(() =>
  tabTiempo.value === 'diario' ? 'Sin jornadas registradas.' : 'Sin datos mensuales.',
)

/**
 * Roving tabindex (patrón APG de Tabs).
 *
 * Antes los dos <button> eran tabulables: con el teclado había que pasar
 * por "Diario", después por "Mensual" y recién ahí llegar al panel, es
 * decir un paso extra obligado por un control que no interesaba. Con
 * roving, Tab entra una sola vez al grupo y las flechas navegan dentro.
 *
 * Se usa activación automática (la flecha ya cambia de tab): cambiar entre
 * Diario y Mensual no cuesta nada y mover solo el foco obligaría a pulsar
 * Enter después de cada flecha para ver el contenido.
 */
const ORDEN_TABS = ['diario', 'mensual']
const refTabDiario = ref(null)
const refTabMensual = ref(null)
const refPorTab = { diario: refTabDiario, mensual: refTabMensual }

function onTecladoTablist(event) {
  const actual = ORDEN_TABS.indexOf(tabTiempo.value)
  let destino = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    destino = (actual + 1) % ORDEN_TABS.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    destino = (actual - 1 + ORDEN_TABS.length) % ORDEN_TABS.length
  } else if (event.key === 'Home') {
    destino = 0
  } else if (event.key === 'End') {
    destino = ORDEN_TABS.length - 1
  }
  if (destino === null) return

  event.preventDefault()
  tabTiempo.value = ORDEN_TABS[destino]
  // El foco tiene que viajar con el tab: si no, queda en un botón que ya
  // tiene tabindex=-1 y deja de ser alcanzable.
  nextTick(() => refPorTab[ORDEN_TABS[destino]].value?.focus())
}
</script>

<template>
  <div class="gestion__tiempos">
    <div
      class="gestion__tabs"
      role="tablist"
      aria-label="Desglose de tiempo trabajado"
      @keydown="onTecladoTablist"
    >
      <button
        id="tab-tiempo-diario"
        ref="refTabDiario"
        class="chip"
        type="button"
        :class="{ 'chip--active': tabTiempo === 'diario' }"
        role="tab"
        aria-controls="panel-tiempo"
        :aria-selected="tabTiempo === 'diario'"
        :tabindex="tabTiempo === 'diario' ? 0 : -1"
        @click="tabTiempo = 'diario'"
      >
        Diario
      </button>
      <button
        id="tab-tiempo-mensual"
        ref="refTabMensual"
        class="chip"
        type="button"
        :class="{ 'chip--active': tabTiempo === 'mensual' }"
        role="tab"
        aria-controls="panel-tiempo"
        :aria-selected="tabTiempo === 'mensual'"
        :tabindex="tabTiempo === 'mensual' ? 0 : -1"
        @click="tabTiempo = 'mensual'"
      >
        Mensual
      </button>
    </div>

    <!-- El panel existía implícitamente pero no estaba declarado: los
         tabs anunciaban aria-selected sin ningún panel asociado.
         tabindex=0 porque el panel es una región que se recorre. -->
    <div
      id="panel-tiempo"
      role="tabpanel"
      tabindex="0"
      :aria-labelledby="tabTiempo === 'diario' ? 'tab-tiempo-diario' : 'tab-tiempo-mensual'"
    >
      <DataPanel
        :loading="loading"
        :error="error"
        :empty="vacio"
        mensaje-cargando="Calculando tiempo trabajado…"
        :mensaje-vacio="mensajeVacio"
        @reintentar="cargar"
      >
        <table v-if="tabTiempo === 'diario'">
          <thead>
            <tr><th>Fecha</th><th>Inicio</th><th>Fin</th><th>Duración</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in tiempoDiario" :key="`${d.fecha}-${d.nombre_archivo}`">
              <td>{{ d.fecha }}</td>
              <td class="num">{{ d.inicio }}</td>
              <td class="num">{{ d.fin }}</td>
              <td class="num">{{ d.duracion_fmt }}</td>
            </tr>
          </tbody>
        </table>

        <table v-else>
          <thead>
            <tr><th>Mes</th><th>Tiempo trabajado</th><th>Días con medición</th></tr>
          </thead>
          <tbody>
            <tr v-for="m in tiempoMensual" :key="m.mes">
              <td>{{ m.mes }}</td>
              <td class="num">{{ m.tiempo_trabajado_fmt }}</td>
              <td class="num">{{ m.dias_con_medicion }}</td>
            </tr>
          </tbody>
        </table>
      </DataPanel>
    </div>
  </div>
</template>

<style scoped>
.gestion__tiempos {
  border-top: 1px solid var(--line);
  padding-top: 1rem;
}

.gestion__tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
</style>
