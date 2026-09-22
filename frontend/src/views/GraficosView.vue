<script setup>
import { ref, watch } from 'vue'
import { chartsApi, localitiesApi } from '../services/domains'
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

const { data: tendencia, loading: loadingTendencia } = useFetchOnFiltros(
  async () => (await chartsApi.getMonthlyTrend()).data,
  { watchFiltros: false },
)

const metricaRanking = ref('resultado_prom_pct')
const { data: ranking, loading: loadingRanking, reload: reloadRanking } = useFetchOnFiltros(
  async () => (await localitiesApi.getTopLocalities(metricaRanking.value, 10)).data,
  { watchFiltros: false },
)
watch(metricaRanking, reloadRanking)
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
      <h2>Tendencia mensual</h2>
      <LoadingState v-if="loadingTendencia" />
      <EmptyState v-else-if="!tendencia?.length" />
      <MonthlyTrendChart v-else :datos="tendencia" />
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
      <LoadingState v-if="loadingRanking" />
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
