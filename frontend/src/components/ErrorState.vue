<script setup>
defineProps({
  mensaje: { type: String, default: 'No se pudo cargar la información. Reintentá en unos segundos.' },
})
defineEmits(['reintentar'])
</script>

<template>
  <div class="empty-state" role="alert">
    <p>{{ mensaje }}</p>
    <button class="btn btn--ghost" @click="$emit('reintentar')">Reintentar</button>
  </div>
</template>
