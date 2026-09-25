<script setup>
import { computed } from 'vue'
import { reportsApi } from '../../services/domains'
import { fmtVm } from '../../format'
import SemaforoBadge from '../SemaforoBadge.vue'

/**
 * Cabecera del detalle: identificación de la localidad, enlaces a los
 * informes y la grilla de KPIs. Es puramente presentacional -- no tiene
 * estado propio, todo sale de la prop.
 */
const props = defineProps({
  localidad: { type: Object, required: true },
})

const urlWord = computed(() =>
  reportsApi.wordUrl(props.localidad.ccte, props.localidad.provincia, props.localidad.localidad, 'Localidad'),
)
const urlPdf = computed(() =>
  reportsApi.pdfUrl(props.localidad.ccte, props.localidad.provincia, props.localidad.localidad, 'Localidad'),
)
</script>

<template>
  <div class="gestion__header">
    <div>
      <h2>{{ localidad.localidad }}</h2>
      <p class="gestion__subtitulo">{{ localidad.provincia }} · CCTE {{ localidad.ccte }}</p>
      <p class="gestion__meta-lista">
        <strong>Expediente(s):</strong>
        <span v-if="localidad.expedientes_lista?.length">{{ localidad.expedientes_lista.join(', ') }}</span>
        <span v-else class="gestion__sin-dato">Sin expediente registrado</span>
      </p>
      <p class="gestion__meta-lista">
        <strong>Sonda(s):</strong>
        <span v-if="localidad.sondas_lista?.length">{{ localidad.sondas_lista.join(', ') }}</span>
        <span v-else class="gestion__sin-dato">—</span>
      </p>
    </div>
    <div class="gestion__acciones">
      <a class="btn btn--ghost" :href="urlWord">Exportar Word</a>
      <a class="btn btn--ghost" :href="urlPdf">Exportar PDF</a>
    </div>
  </div>

  <dl class="gestion__stats">
    <div><dt>Mediciones</dt><dd class="num">{{ localidad.mediciones }}</dd></div>
    <div><dt>Máx. V/m</dt><dd class="num">{{ fmtVm(localidad.resultado_max_vm) ?? '—' }}</dd></div>
    <div><dt>Nivel</dt><dd><SemaforoBadge :pct="localidad.resultado_max_pct" /></dd></div>
    <div><dt>Fecha inicial</dt><dd>{{ localidad.fecha_inicio?.slice(0, 10) ?? '—' }}</dd></div>
    <div><dt>Fecha final</dt><dd>{{ localidad.fecha_fin?.slice(0, 10) ?? '—' }}</dd></div>
    <div><dt>Tiempo trabajado</dt><dd class="num">{{ localidad.tiempo_trabajado_fmt ?? '0 s' }}</dd></div>
    <div><dt>Días con medición</dt><dd class="num">{{ localidad.dias_con_medicion ?? 0 }}</dd></div>
  </dl>
</template>

<style scoped>
.gestion__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.gestion__subtitulo {
  color: var(--ink-soft);
  margin: 0.2rem 0 0;
}

.gestion__meta-lista {
  font-size: 0.8rem;
  margin: 0.15rem 0 0;
}

.gestion__sin-dato {
  color: var(--ink-soft);
}

.gestion__acciones {
  display: flex;
  gap: 0.5rem;
}

.gestion__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.75rem;
  margin: 0 0 1.25rem;
}

.gestion__stats dt {
  font-size: 0.75rem;
  color: var(--ink-soft);
}

.gestion__stats dd {
  margin: 0;
}
</style>
