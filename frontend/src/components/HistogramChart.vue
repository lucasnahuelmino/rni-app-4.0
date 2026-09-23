<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Chart, BarController, BarElement, LinearScale, CategoryScale, Tooltip } from 'chart.js'
import { token } from '../assets/tokens'

Chart.register(BarController, BarElement, LinearScale, CategoryScale, Tooltip)

const props = defineProps({
  bins: { type: Array, required: true }, // [{desde, hasta, n}]
})

const canvasRef = ref(null)
let chart = null

function render() {
  if (!canvasRef.value) return
  if (chart) chart.destroy()
  chart = new Chart(canvasRef.value, {
    type: 'bar',
    data: {
      labels: props.bins.map((b) => `${b.desde.toFixed(1)}–${b.hasta.toFixed(1)}`),
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
