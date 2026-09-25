<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Chart, BarController, BarElement, LinearScale, CategoryScale, Tooltip } from 'chart.js'
import { token } from '../assets/tokens'
import { fmtPct, fmtVm } from '../format'

Chart.register(BarController, BarElement, LinearScale, CategoryScale, Tooltip)

const props = defineProps({
  bins: { type: Array, required: true }, // [{desde, hasta, n}]
  // Los límites de los intervalos salen de MIN/MAX de UNA columna, así que
  // se formatean con la precisión de esa columna y no con un .toFixed(1)
  // fijo: un bin de V/m tiene 3 decimales en la base y uno de % se calcula.
  campo: { type: String, default: 'resultado_pct' },
})

const canvasRef = ref(null)
let chart = null

function formato() {
  return props.campo === 'resultado_vm' ? fmtVm : fmtPct
}

function render() {
  if (!canvasRef.value) return
  if (chart) chart.destroy()
  const fmt = formato()
  chart = new Chart(canvasRef.value, {
    type: 'bar',
    data: {
      labels: props.bins.map((b) => `${fmt(b.desde)}–${fmt(b.hasta)}`),
      datasets: [{ label: 'Frecuencia', data: props.bins.map((b) => b.n), backgroundColor: token('--signal', '#1a4fbf') }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  })
}

onMounted(render)
onBeforeUnmount(() => chart?.destroy())
watch(() => props.bins, render)
</script>

<template>
  <canvas ref="canvasRef" role="img" aria-label="Histograma de distribución"></canvas>
</template>
