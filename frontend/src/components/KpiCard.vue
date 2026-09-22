<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: '—' },
  unidad: { type: String, default: '' },
})
</script>

<template>
  <div class="stat-block">
    <div class="stat-block__label">{{ label }}</div>
    <div class="stat-block__value">
      {{ value }}
      <span v-if="unidad" class="stat-block__unidad">{{ unidad }}</span>
    </div>
  </div>
</template>

<style scoped>
.stat-block__unidad {
  font-size: 0.85rem;
  color: var(--ink-soft);
  font-weight: 400;
}
</style>
