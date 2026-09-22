<script setup>
import { computed } from 'vue'

const props = defineProps({
  pct: { type: Number, default: null },
})

// NOTA: el sistema Streamlit actual usa una escala de 10 bandas de color
// para el mapa (get_color_por_pct) que no se pudo preservar 1:1 acá -- se
// simplificó a 3 niveles (Bajo/Moderado/Alto) con umbrales provisorios.
// Confirmar con el equipo los cortes exactos antes de usar esto para
// decisiones regulatorias.
const nivel = computed(() => {
  if (props.pct == null) return null
  if (props.pct < 25) return { clase: 'badge--ok', texto: 'Bajo' }
  if (props.pct < 80) return { clase: 'badge--mid', texto: 'Moderado' }
  return { clase: 'badge--high', texto: 'Alto' }
})
</script>

<template>
  <span v-if="nivel" class="badge" :class="nivel.clase">
    <span class="badge__dot" aria-hidden="true"></span>
    {{ nivel.texto }}
    <span class="num">({{ pct.toFixed(1) }}%)</span>
  </span>
  <span v-else class="badge">Sin dato</span>
</template>
