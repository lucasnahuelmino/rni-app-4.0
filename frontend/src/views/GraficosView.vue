<script setup>
import { ref, watch } from 'vue'
import { chartsApi, kpisApi, localitiesApi, tiemposApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import { useFiltrosStore } from '../stores/filtros'
import LoadingState from '../components/LoadingState.vue'
import ErrorState from '../components/ErrorState.vue'
import EmptyState from '../components/EmptyState.vue'
import HistogramChart from '../components/HistogramChart.vue'
import MonthlyTrendChart from '../components/MonthlyTrendChart.vue'

const campoHistograma = ref('resultado_pct')
const filtros = useFiltrosStore()

const { data: histograma, loading: loadingHist, error: errorHist, reload: reloadHist } = useFetchOnFiltros(
  async (f) => (await chartsApi.getHistogram(campoHistograma.value, 20, f)).data,
)
watch(campoHistograma, reloadHist)

const { data: tendencia, loading: loadingTendencia, error: errorTendencia, reload: reloadTendencia } = useFetchOnFiltros(
  async () => (await chartsApi.getMonthlyTrend()).data,
  { watchFiltros: false },
)

const metricaRanking = ref('resultado_prom_pct')
const { data: ranking, loading: loadingRanking, error: errorRanking, reload: reloadRanking } = useFetchOnFiltros(
  async () => (await localitiesApi.getTopLocalities(metricaRanking.value, 10)).data,
  { watchFiltros: false },
)
watch(metricaRanking, reloadRanking)

// Horas trabajadas y días con medición por CCTE -- ya vienen precalculados
// en resumen_ccte (services/statistics.py los mantiene actualizados en cada
// import), así que esto solo los muestra, no recalcula nada en el navegador.
const { data: ccteSummary, loading: loadingCcte, error: errorCcte, reload: reloadCcte } = useFetchOnFiltros(
  async () => (await kpisApi.getCcteSummary()).data,
  { watchFiltros: false },
)

// Tiempo trabajado mensual (nuevo -- antes no existía este desglose en
// ningún lado, ni siquiera en el sistema Streamlit anterior a nivel
// agregado nacional). Respeta los filtros globales.
const { data: tiempoMensual, loading: loadingTiempoMensual, error: errorTiempoMensual, reload: reloadTiempoMensual } = useFetchOnFiltros(
  async (f) => (await tiemposApi.getMensual({ filtros: f })).data,
)
</script>

<template>
  <div class="graficos">
    <section class="panel">
      <div class="panel__header">
        <h2>Distribución de resultados</h2>
        <select v-model="campoHistograma" aria-label="Campo del histograma">
          <option value="resultado_pct">% del límite</option>
          <option value="resultado_vm">V/m</option>
        </select>
      </div>
      <ErrorState v-if="errorHist" @reintentar="reloadHist" />
      <LoadingState v-else-if="loadingHist" />
      <EmptyState v-else-if="!histograma?.bins?.length" />
      <HistogramChart v-else :bins="histograma.bins" />
    </section>

    <section class="panel">
      <h2>Tendencia mensual (mediciones)</h2>
      <ErrorState v-if="errorTendencia" @reintentar="reloadTendencia" />
      <LoadingState v-else-if="loadingTendencia" />
      <EmptyState v-else-if="!tendencia?.length" />
      <MonthlyTrendChart v-else :datos="tendencia" />
    </section>

    <section class="panel">
      <h2>Tiempo trabajado mensual</h2>
      <ErrorState v-if="errorTiempoMensual" @reintentar="reloadTiempoMensual" />
      <LoadingState v-else-if="loadingTiempoMensual" />
      <EmptyState v-else-if="!tiempoMensual?.length" />
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
    </section>

    <section class="panel">
      <h2>Horas trabajadas y días con medición por CCTE</h2>
      <ErrorState v-if="errorCcte" @reintentar="reloadCcte" />
      <LoadingState v-else-if="loadingCcte" />
      <EmptyState v-else-if="!ccteSummary?.length" />
      <table v-else>
        <thead>
          <tr><th>CCTE</th><th>Localidades</th><th>Tiempo trabajado</th><th>Días con medición</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in ccteSummary" :key="c.ccte">
            <td>{{ c.ccte }}</td>
            <td class="num">{{ c.localidades }}</td>
            <td class="num">{{ c.tiempo_trabajado_fmt }}</td>
            <td class="num">{{ c.dias_con_medicion }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <div class="panel__header">
        <h2>Top 10 localidades</h2>
        <select v-model="metricaRanking" aria-label="Métrica del ranking">
          <option value="resultado_prom_pct">Promedio %</option>
          <option value="resultado_max_vm">Máximo V/m</option>
          <option value="resultado_max_pct">Máximo %</option>
          <option value="mediciones">Cantidad de mediciones</option>
        </select>
      </div>
      <ErrorState v-if="errorRanking" @reintentar="reloadRanking" />
      <LoadingState v-else-if="loadingRanking" />
      <EmptyState v-else-if="!ranking?.length" />
      <table v-else>
        <thead>
          <tr><th>Localidad</th><th>Provincia</th><th>CCTE</th><th>Valor</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in ranking" :key="`${row.ccte}-${row.localidad}`">
            <td>{{ row.localidad }}</td>
            <td>{{ row.provincia }}</td>
            <td>{{ row.ccte }}</td>
            <td class="num">{{ row.valor?.toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.graficos {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

select {
  border: 1px solid var(--line);
  padding: 0.35rem 0.5rem;
}
</style>
