<script setup>
defineProps({
  mensaje: { type: String, default: 'No hay datos para los filtros seleccionados.' },
})
</script>

<template>
  <div class="empty-state">{{ mensaje }}</div>
</template>
