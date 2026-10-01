<script setup>
import { fmtPct, fmtVm } from '../format'

defineProps({
  ccte: { type: Object, required: true },
})
</script>

<template>
  <div class="ccte-card">
    <h3>{{ ccte.ccte }}</h3>
    <dl>
      <div class="ccte-card__row">
        <dt>Puntos</dt>
        <dd class="num">{{ ccte.mediciones }}</dd>
      </div>
      <div class="ccte-card__row">
        <dt>Pico V/m</dt>
        <dd class="num">{{ ccte.resultado_max_vm != null ? fmtVm(ccte.resultado_max_vm) : '—' }}</dd>
      </div>
      <div class="ccte-card__row">
        <dt>Pico %</dt>
        <dd class="num">{{ ccte.resultado_max_pct != null ? fmtPct(ccte.resultado_max_pct) : '—' }}</dd>
      </div>
      <div class="ccte-card__row" v-if="ccte.localidad_max">
        <dt>Localidad</dt>
        <dd>{{ ccte.localidad_max }}</dd>
      </div>
    </dl>
  </div>
</template>

<style scoped>
.ccte-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-top: 3px solid var(--signal);
  /* Siete en una fila: el padding baja de 0.85/1rem para que el nombre del
     centro y sus datos entren en una columna angosta sin desbordar. */
  padding: 0.5rem 0.6rem;
}

.ccte-card h3 {
  font-size: 0.78rem;
  line-height: 1.2;
  margin-bottom: 0.35rem;
  overflow-wrap: anywhere;
}

.ccte-card__row {
  display: flex;
  /* Wrap como red de seguridad: "Localidad" y "Río Gallegos" no entran juntos
     en una columna angosta, y en ese caso el valor baja a su propia línea en
     vez de pisarse con la etiqueta. */
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0 0.35rem;
  padding: 0.12rem 0;
  font-size: 0.7rem;
}

dt {
  color: var(--ink-soft);
}

dd {
  margin: 0;
  text-align: right;
  overflow-wrap: anywhere;
}
</style>
