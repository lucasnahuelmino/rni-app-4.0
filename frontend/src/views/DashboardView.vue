<script setup>
import { computed } from 'vue'
import { kpisApi, localitiesApi, chartsApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import KpiCard from '../components/KpiCard.vue'
import CcteCard from '../components/CcteCard.vue'
import SemaforoBadge from '../components/SemaforoBadge.vue'
import DataPanel from '../components/DataPanel.vue'
import MonthlyTrendChart from '../components/MonthlyTrendChart.vue'

const { data: kpis, loading: loadingKpis, error: errorKpis, reload: reloadKpis } = useFetchOnFiltros(
  async (filtros) => (await kpisApi.getKpis(filtros)).data,
)

const { data: ccteSummary, loading: loadingCcte, error: errorCcte, reload: reloadCcte } = useFetchOnFiltros(
  async () => (await kpisApi.getCcteSummary()).data,
  { watchFiltros: false },
)

const { data: topLocalidades, loading: loadingTop, error: errorTop, reload: reloadTop } = useFetchOnFiltros(
  async () => (await localitiesApi.getTopLocalities('resultado_max_vm', 5)).data,
  { watchFiltros: false },
)

const { data: tendencia, loading: loadingTendencia, error: errorTendencia, reload: reloadTendencia } = useFetchOnFiltros(
  async () => (await chartsApi.getMonthlyTrend()).data,
  { watchFiltros: false },
)

const picoTexto = computed(() => {
  const pico = kpis.value?.pico_maximo
  if (!pico) return null
  return `${pico.localidad}, ${pico.provincia} (CCTE ${pico.ccte})`
})
</script>

<template>
  <div class="dashboard">
    <section aria-labelledby="kpis-titulo">
      <h2 id="kpis-titulo" class="sr-only">KPIs principales</h2>
      <DataPanel :loading="loadingKpis" :error="errorKpis" @reintentar="reloadKpis">
        <div class="kpi-grid">
          <KpiCard label="Registros totales" :value="kpis.registros_totales" />
          <KpiCard label="Localidades" :value="kpis.localidades" />
          <KpiCard label="Provincias" :value="kpis.provincias" />
          <KpiCard label="Centros (CCTE)" :value="kpis.cctes" />
          <KpiCard
            label="Promedio del límite"
            :value="kpis.promedio_pct != null ? kpis.promedio_pct.toFixed(1) : '—'"
            unidad="%"
          />
        </div>
      </DataPanel>

      <div v-if="!loadingKpis && !errorKpis && kpis?.pico_maximo" class="panel pico-maximo">
        <h3>Pico máximo registrado</h3>
        <p>
          <strong class="num">{{ kpis.pico_maximo.resultado_vm?.toFixed(2) }} V/m</strong>
          en {{ picoTexto }}
          <SemaforoBadge :pct="kpis.pico_maximo.resultado_pct" />
        </p>
      </div>
    </section>

    <section aria-labelledby="ccte-titulo">
      <h2 id="ccte-titulo">Mediciones por Centro de Comprobación Técnica de Emisiones</h2>
      <DataPanel :loading="loadingCcte" :error="errorCcte" @reintentar="reloadCcte">
        <div class="ccte-grid">
          <CcteCard v-for="c in ccteSummary" :key="c.ccte" :ccte="c" />
        </div>
      </DataPanel>
    </section>

    <div class="dashboard__cols">
      <section aria-labelledby="top-titulo" class="panel">
        <h2 id="top-titulo">Top 5 localidades (máximo V/m)</h2>
        <DataPanel
          :loading="loadingTop"
          :error="errorTop"
          :empty="!topLocalidades?.length"
          @reintentar="reloadTop"
        >
          <table>
            <thead>
              <tr>
                <th>Localidad</th>
                <th>Provincia</th>
                <th>CCTE</th>
                <th>Máximo V/m</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in topLocalidades" :key="`${row.ccte}-${row.provincia}-${row.localidad}`">
                <td>{{ row.localidad }}</td>
                <td>{{ row.provincia }}</td>
                <td>{{ row.ccte }}</td>
                <td class="num">{{ row.valor?.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </DataPanel>
      </section>

      <section aria-labelledby="tendencia-titulo" class="panel">
        <h2 id="tendencia-titulo">Tendencia mensual</h2>
        <DataPanel
          :loading="loadingTendencia"
          :error="errorTendencia"
          :empty="!tendencia?.length"
          @reintentar="reloadTendencia"
        >
          <MonthlyTrendChart :datos="tendencia" />
        </DataPanel>
      </section>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

/* Era una copia propia de .sr-only (tokens.css); el h2 sigue siendo el
   target de aria-labelledby de la section. */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.pico-maximo p {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 0;
}

.ccte-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.dashboard__cols {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .dashboard__cols {
    grid-template-columns: 1fr;
  }
}
</style>
