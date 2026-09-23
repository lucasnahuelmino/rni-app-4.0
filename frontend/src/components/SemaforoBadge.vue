<script setup>
import { computed } from 'vue'
import { getColorPorPct, getRangoPorPct } from '../constants'

const props = defineProps({
  pct: { type: Number, default: null },
})

const nivel = computed(() => {
  if (props.pct == null) return null

  const rango = getRangoPorPct(props.pct)

  return {
    texto: rango.label,
    color: rango.color,
  }
})
</script>

<template>
  <span
    v-if="nivel"
    class="badge"
    :style="{ backgroundColor: nivel.color }"
  >
    <span class="badge__dot" aria-hidden="true"></span>
    {{ nivel.texto }}
    <span class="num">({{ pct.toFixed(2) }}%)</span>
  </span>
  <span v-else class="badge">Sin dato</span>
</template>
