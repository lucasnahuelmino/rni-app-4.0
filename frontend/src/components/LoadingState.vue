<script setup>
defineProps({
  mensaje: { type: String, default: 'Cargando…' },
})
</script>

<template>
  <div class="loading-state" role="status">{{ mensaje }}</div>
</template>
