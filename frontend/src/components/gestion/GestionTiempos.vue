<script setup>
import { ref, computed, watch } from 'vue'
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
</script>

<template>
  <div class="gestion__tiempos">
    <div class="gestion__tabs" role="tablist" aria-label="Desglose de tiempo trabajado">
      <button
        id="tab-tiempo-diario"
        class="chip"
        type="button"
        :class="{ 'chip--active': tabTiempo === 'diario' }"
        role="tab"
        aria-controls="panel-tiempo"
        :aria-selected="tabTiempo === 'diario'"
        @click="tabTiempo = 'diario'"
      >
        Diario
      </button>
      <button
        id="tab-tiempo-mensual"
        class="chip"
        type="button"
        :class="{ 'chip--active': tabTiempo === 'mensual' }"
        role="tab"
        aria-controls="panel-tiempo"
        :aria-selected="tabTiempo === 'mensual'"
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
