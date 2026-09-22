<script setup>
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
        <dd class="num">{{ ccte.resultado_max_vm != null ? ccte.resultado_max_vm.toFixed(2) : '—' }}</dd>
      </div>
      <div class="ccte-card__row">
        <dt>Pico %</dt>
        <dd class="num">{{ ccte.resultado_max_pct != null ? ccte.resultado_max_pct.toFixed(1) : '—' }}</dd>
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
  padding: 0.85rem 1rem;
}

.ccte-card__row {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.2rem 0;
  font-size: 0.8rem;
}

dt {
  color: var(--ink-soft);
}

dd {
  margin: 0;
}
</style>
