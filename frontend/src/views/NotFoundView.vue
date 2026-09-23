<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <section class="panel no-encontrada">
    <h2>Página no encontrada</h2>
    <p class="no-encontrada__texto">
      No existe ninguna vista en <code class="num">{{ route.fullPath }}</code>.
    </p>
    <router-link class="btn" to="/">Volver al inicio</router-link>
  </section>
</template>

<style scoped>
.no-encontrada__texto {
  color: var(--ink-soft);
  margin: 0 0 var(--space-6);
  max-width: 640px;
}
</style>
