<script setup>
import { computed, ref, watch } from 'vue'

import { chartsApi, kpisApi, localitiesApi, tiemposApi } from '../../services/domains'
import { fmtPct, fmtVm } from '../../format'
import { useFetchOnFiltros } from '../../composables/useFetchOnFiltros'
import { useFiltrosStore } from '../../stores/filtros'
import DataPanel from '../DataPanel.vue'
import MonthlyTrendChart from '../MonthlyTrendChart.vue'

/**
 * Lo que se ve cuando NO hay una localidad seleccionada: la info de todo el
 * centro. Al apretar una localidad de la lista se reemplaza por su detalle,
 * y al volver (o al apretar otro CCTE) vuelve a aparecer esto.
 *
 * Todo lo de acá se refresca solo cuando cambia el CCTE, porque todos estos
 * fetches bajan `filtros` del store -- el mismo estado en el que escribe el
 * botón. No hay un estado paralelo que pueda quedar desincronizado.
 *
 * Lo único que NO se filtra es la tabla "Resumen por CCTE": es una tabla de
 * comparación entre centros, así que siempre muestra todos los que estén
 * activos en el filtro (todos si no hay ninguno, solo el elegido si hay
 * uno, los elegidos si hay varios).
 */
const filtros = useFiltrosStore()

/** Título de cada bloque: "…", o "… — Córdoba" si hay un solo CCTE. */
const sufijo = computed(() => (filtros.ccte.length === 1 ? ` — ${filtros.ccte[0]}` : ''))

const { data: ccteSummary, loading: loadingCcte, error: errorCcte, reload: reloadCcte } = useFetchOnFiltros(
  // watchFiltros: false porque igual lo re-filtra abajo en cliente: es una
  // tabla de 7 filas ya cargada, no vale la pena un viaje al servidor por
  // cada tecla del panel de filtros.
  async () => (await kpisApi.getCcteSummary()).data,
  { watchFiltros: false },
)

const filasResumen = computed(() => {
  const datos = ccteSummary.value ?? []
  if (!filtros.ccte.length) return datos
  return datos.filter((c) => filtros.ccte.includes(c.ccte))
})

const { data: tendencia, loading: loadingTendencia, error: errorTendencia, reload: reloadTendencia } = useFetchOnFiltros(
  async (f) => (await chartsApi.getMonthlyTrend(f)).data,
)

const { data: tiempoMensual, loading: loadingTiempoMensual, error: errorTiempoMensual, reload: reloadTiempoMensual } = useFetchOnFiltros(
  async (f) => (await tiemposApi.getMensual({ filtros: f })).data,
)

// El desglose diario va aparte del mensual en el backend, pero los dos
// parten del mismo agrupamiento, así que la suma de las filas de acá da
// exactamente lo que da la tabla de arriba. Ese es el invariante que cubre
// el test; si un día no cuadra, se rompió ahí y no en la vista.
const { data: tiempoDiario, loading: loadingTiempoDiario, error: errorTiempoDiario, reload: reloadTiempoDiario } = useFetchOnFiltros(
  async (f) => (await tiemposApi.getDiarioCcte(f.ccte)).data,
)

const metricaRanking = ref('resultado_prom_pct')
const { data: ranking, loading: loadingRanking, error: errorRanking, reload: reloadRanking } = useFetchOnFiltros(
  async (f) => (await localitiesApi.getTopLocalities(metricaRanking.value, 10, f)).data,
)
watch(metricaRanking, reloadRanking)

// El ranking devuelve SIEMPRE una columna `valor`, pero qué es depende de la
// métrica elegida: un %, un V/m o una cantidad. Cada métrica trae su
// formateador, que es el de la precisión real de la base (ver DESIGN.md
// "Decimales") -- un .toFixed(2) fijo mostraba "123.00" para un conteo.
const METRICAS = {
  resultado_prom_pct: { fmt: fmtPct, etiqueta: 'Promedio %' },
  resultado_max_vm: { fmt: fmtVm, etiqueta: 'Máximo V/m' },
  resultado_max_pct: { fmt: fmtPct, etiqueta: 'Máximo %' },
  mediciones: { fmt: (v) => v, etiqueta: 'Cantidad de mediciones' },
}
const metrica = computed(() => METRICAS[metricaRanking.value] ?? METRICAS.resultado_prom_pct)
</script>

<template>
  <div class="resumen">
    <section class="resumen__bloque">
      <h3>Resumen{{ sufijo }}</h3>
      <DataPanel :loading="loadingCcte" :error="errorCcte" :empty="!filasResumen?.length" @reintentar="reloadCcte">
        <table>
          <thead>
            <tr>
              <th>CCTE</th>
              <th>Mediciones</th>
              <th>Localidades</th>
              <th>Provincias</th>
              <th>Tiempo trabajado</th>
              <th>Días con medición</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in filasResumen" :key="c.ccte">
              <td>{{ c.ccte }}</td>
              <td class="num">{{ c.mediciones }}</td>
              <td class="num">{{ c.localidades }}</td>
              <td class="num">{{ c.provincias }}</td>
              <td class="num">{{ c.tiempo_trabajado_fmt }}</td>
              <td class="num">{{ c.dias_con_medicion }}</td>
            </tr>
          </tbody>
        </table>
      </DataPanel>
    </section>

    <section class="resumen__bloque">
      <h3>Tendencia mensual (mediciones){{ sufijo }}</h3>
      <DataPanel
        :loading="loadingTendencia"
        :error="errorTendencia"
        :empty="!tendencia?.length"
        @reintentar="reloadTendencia"
      >
        <MonthlyTrendChart :datos="tendencia" />
      </DataPanel>
    </section>

    <section class="resumen__bloque">
      <h3>Tiempo trabajado mensual{{ sufijo }}</h3>
      <DataPanel
        :loading="loadingTiempoMensual"
        :error="errorTiempoMensual"
        :empty="!tiempoMensual?.length"
        @reintentar="reloadTiempoMensual"
      >
        <table>
          <thead>
            <tr><th>Mes</th><th>Tiempo trabajado</th><th>Días con medición</th></tr>
          </thead>
          <tbody>
            <tr v-for="m in tiempoMensual" :key="m.mes">
              <td>{{ m.mes }}</td>
              <td class="num">{{ m.tiempo_trabajado_fmt }}</td>
              <td class="num">{{ m.dias_con_medicion }}</td>
            </tr>
          </tbody>
        </table>
      </DataPanel>
    </section>

    <section class="resumen__bloque">
      <h3>Tiempo trabajado diario{{ sufijo }}</h3>
      <DataPanel
        :loading="loadingTiempoDiario"
        :error="errorTiempoDiario"
        :empty="!tiempoDiario?.length"
        @reintentar="reloadTiempoDiario"
      >
        <!-- En la vista General son todas las jornadas del sistema (241 en la
             base real), así que la tabla va con su propio scroll: la ve el
             que la busca, no tapa lo de abajo. -->
        <div class="resumen__tabla-scroll">
          <table>
            <thead>
              <tr><th>Fecha</th><th>Tiempo trabajado</th><th>Archivo</th></tr>
            </thead>
            <tbody>
              <tr v-for="(d, i) in tiempoDiario" :key="`${d.fecha}-${d.nombre_archivo}-${i}`">
                <td>{{ d.fecha }}</td>
                <td class="num">{{ d.duracion_fmt }}</td>
                <td class="resumen__archivo" :title="d.nombre_archivo">{{ d.nombre_archivo }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </DataPanel>
    </section>

    <section class="resumen__bloque">
      <div class="resumen__header">
        <h3>Top 10 localidades{{ sufijo }}</h3>
        <select v-model="metricaRanking" aria-label="Métrica del ranking">
          <option value="resultado_prom_pct">Promedio %</option>
          <option value="resultado_max_vm">Máximo V/m</option>
          <option value="resultado_max_pct">Máximo %</option>
          <option value="mediciones">Cantidad de mediciones</option>
        </select>
      </div>
      <DataPanel
        :loading="loadingRanking"
        :error="errorRanking"
        :empty="!ranking?.length"
        @reintentar="reloadRanking"
      >
        <table>
          <thead>
            <tr><th>Localidad</th><th>Provincia</th><th>CCTE</th><th>{{ metrica.etiqueta }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in ranking" :key="`${row.ccte}-${row.localidad}`">
              <td>{{ row.localidad }}</td>
              <td>{{ row.provincia }}</td>
              <td>{{ row.ccte }}</td>
              <td class="num">{{ metrica.fmt(row.valor) }}</td>
            </tr>
          </tbody>
        </table>
      </DataPanel>
    </section>
  </div>
</template>

<style scoped>
.resumen {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.resumen__bloque > h3 {
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
}

.resumen__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.resumen__header > h3 {
  margin: 0;
}

.resumen__tabla-scroll {
  max-height: 60vh;
  overflow-y: auto;
}

.resumen__archivo {
  max-width: 22ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.75rem;
  color: var(--ink-soft);
}
</style>
