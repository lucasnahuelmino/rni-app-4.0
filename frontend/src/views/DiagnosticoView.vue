<script setup>
import { diagnosticsApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import DataPanel from '../components/DataPanel.vue'
import KpiCard from '../components/KpiCard.vue'

const { data: diag, loading, error, reload } = useFetchOnFiltros(
  async () => (await diagnosticsApi.getDiagnostics()).data,
  { watchFiltros: false },
)
</script>

<template>
  <section class="panel">
    <h2>Diagnóstico de calidad de datos</h2>
    <p class="diag-nota">
      Estos indicadores se calculan sobre toda la base (no aplican los filtros globales).
      El criterio de "valores sospechosos" todavía no está definido -- ver nota en
      <code>app/services/diagnostics.py</code> del backend.
    </p>
    <DataPanel :loading="loading" :error="error" @reintentar="reload">
      <div class="diag-grid">
        <KpiCard label="Total de registros" :value="diag.total_registros" />
        <KpiCard label="Fechas vacías" :value="diag.fechas_vacias" />
        <KpiCard label="Fechas no parseables" :value="diag.fechas_no_parseables" />
        <KpiCard label="Horas vacías" :value="diag.horas_vacias" />
        <KpiCard label="Coordenadas faltantes" :value="diag.coordenadas_faltantes" />
        <KpiCard label="Coordenadas fuera de rango" :value="diag.coordenadas_fuera_de_rango" />
        <KpiCard label="Resultados faltantes" :value="diag.resultados_faltantes" />
        <KpiCard label="Duplicados probables" :value="diag.duplicados_probables" />
      </div>
    </DataPanel>
  </section>
</template>

<style scoped>
.diag-nota {
  color: var(--ink-soft);
  font-size: 0.85rem;
  max-width: 640px;
}

.diag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-top: 0.75rem;
}
</style>
