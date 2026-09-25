<script setup>
import { computed, onMounted } from 'vue'
import { useColorScaleStore } from '../stores/colorScale'
import { fmtPct } from '../format'

const props = defineProps({
  pct: { type: Number, default: null },
})

const escala = useColorScaleStore()
onMounted(() => escala.asegurarCargado())

const color = computed(() => escala.colorPorPct(props.pct))

// El texto es el valor REAL (% del límite normativo), no el rango al que
// pertenece. En la tabla de Resumen, en el detalle de Gestión y en el pico
// máximo del Dashboard se comparan filas entre sí, y "35–50 %" no se puede
// ordenar ni distinguir de "20–35 %" de un vistazo: todos los valores caían
// agrupados en 10 etiquetas repetidas. El color del borde y del punto sigue
// siendo el semáforo, que es el que dice el tramo; el rango se conserva en
// el `title` para quien quiera verlo al pasar el mouse.
//
// Va con la precisión exacta de la base (fmtPct, hasta 4 decimales) y no
// con `.toFixed(1)`: con un decimal los valores chicos se veían "0,0 %", lo
// mismo que un resultado en cero.
const valor = computed(() => {
  const v = fmtPct(props.pct)
  return v == null ? null : `${v}%`
})
const rango = computed(() => escala.etiquetaPorPct(props.pct))
</script>

<template>
  <span
    class="badge-color"
    :style="{ '--badge-color': color }"
    :title="valor != null ? `${valor} del límite normativo · rango ${rango}` : undefined"
  >
    <span class="badge-color__dot" aria-hidden="true"></span>
    <span v-if="valor != null" class="num">{{ valor }}</span>
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
