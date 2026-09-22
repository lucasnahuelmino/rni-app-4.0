<script setup>
import { localitiesApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import LoadingState from '../components/LoadingState.vue'
import ErrorState from '../components/ErrorState.vue'
import EmptyState from '../components/EmptyState.vue'
import SemaforoBadge from '../components/SemaforoBadge.vue'

const { data: localidades, loading, error, reload } = useFetchOnFiltros(
  async (filtros) => (await localitiesApi.getLocalities(filtros)).data,
)
</script>

<template>
  <section class="panel">
    <h2>Resumen por localidad</h2>
    <ErrorState v-if="error" @reintentar="reload" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!localidades?.length" />
    <div v-else class="tabla-scroll">
      <table>
        <thead>
          <tr>
            <th>CCTE</th>
            <th>Provincia</th>
            <th>Localidad</th>
            <th>Mediciones</th>
            <th>Máx. V/m</th>
            <th>Nivel</th>
            <th>Inicio</th>
            <th>Fin</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in localidades" :key="`${row.ccte}-${row.provincia}-${row.localidad}`">
            <td>{{ row.ccte }}</td>
            <td>{{ row.provincia }}</td>
            <td>{{ row.localidad }}</td>
            <td class="num">{{ row.mediciones }}</td>
            <td class="num">{{ row.resultado_max_vm != null ? row.resultado_max_vm.toFixed(2) : '—' }}</td>
            <td><SemaforoBadge :pct="row.resultado_max_pct" /></td>
            <td>{{ row.fecha_inicio ? row.fecha_inicio.slice(0, 10) : '—' }}</td>
            <td>{{ row.fecha_fin ? row.fecha_fin.slice(0, 10) : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.tabla-scroll {
  overflow-x: auto;
}
</style>
