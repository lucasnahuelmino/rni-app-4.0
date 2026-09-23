<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler } from 'chart.js'
import { token, tokenConAlfa } from '../assets/tokens'

// Filler hace falta: Chart.js tree-shakea los plugins, y sin registrar este
// `fill: true` no pinta nada (el área del gráfico desaparecía en silencio).
Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler)

const props = defineProps({
  datos: { type: Array, required: true }, // [{mes, mediciones}]
})

const canvasRef = ref(null)
let chart = null

function render() {
  if (!canvasRef.value) return
  if (chart) chart.destroy()
  chart = new Chart(canvasRef.value, {
    type: 'line',
    data: {
      labels: props.datos.map((d) => d.mes),
      datasets: [
        {
          label: 'Mediciones',
          data: props.datos.map((d) => d.mediciones),
          borderColor: token('--signal', '#1a4fbf'),
          backgroundColor: tokenConAlfa('--signal', 0.15, '#1a4fbf'),
          fill: true,
          tension: 0.25,
        },
      ],
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
watch(() => props.datos, render)
</script>

<template>
  <div class="chart-wrap">
    <canvas ref="canvasRef" role="img" aria-label="Tendencia mensual de mediciones"></canvas>
    <table class="sr-only-table">
      <caption>Datos de tendencia mensual (tabla equivalente al gráfico)</caption>
      <thead>
        <tr><th>Mes</th><th>Mediciones</th></tr>
      </thead>
      <tbody>
        <tr v-for="d in datos" :key="d.mes"><td>{{ d.mes }}</td><td>{{ d.mediciones }}</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
}

.sr-only-table {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
