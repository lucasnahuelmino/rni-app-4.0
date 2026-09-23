<script setup>
import { computed, onMounted } from 'vue'
import { useColorScaleStore } from '../stores/colorScale'

const props = defineProps({
  pct: { type: Number, default: null },
})

const escala = useColorScaleStore()
onMounted(() => escala.asegurarCargado())

const color = computed(() => escala.colorPorPct(props.pct))
const etiqueta = computed(() => escala.etiquetaPorPct(props.pct))
</script>

<template>
  <span class="badge-color" :style="{ '--badge-color': color }">
    <span class="badge-color__dot" aria-hidden="true"></span>
    <span v-if="pct != null" class="num">{{ etiqueta }}</span>
    <span v-else>Sin dato</span>
  </span>
</template>

<style scoped>
.badge-color {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  border: 1px solid var(--badge-color, var(--line));
  padding: 0.15rem 0.5rem;
}

.badge-color__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--badge-color, var(--ink-soft));
  flex-shrink: 0;
}
</style>
