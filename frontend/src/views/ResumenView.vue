<script setup>
import { ref, computed } from 'vue'
import { localitiesApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import DataPanel from '../components/DataPanel.vue'
import SemaforoBadge from '../components/SemaforoBadge.vue'

const { data: localidades, loading, error, reload } = useFetchOnFiltros(
  async (filtros) => (await localitiesApi.getLocalities(filtros)).data,
)

// Las 8 columnas de la tabla declaradas una sola vez: `tipo` decide cómo se
// compara (num resta, texto usa localeCompare) y `etiqueta` es lo que se
// muestra, así que cabecera, orden y clase numérica no pueden desincronizarse.
const COLUMNAS = [
  { campo: 'ccte', etiqueta: 'CCTE', tipo: 'texto' },
  { campo: 'provincia', etiqueta: 'Provincia', tipo: 'texto' },
  { campo: 'localidad', etiqueta: 'Localidad', tipo: 'texto' },
  { campo: 'mediciones', etiqueta: 'Mediciones', tipo: 'num' },
  { campo: 'resultado_max_vm', etiqueta: 'Máx. V/m', tipo: 'num' },
  { campo: 'resultado_max_pct', etiqueta: 'Nivel', tipo: 'num' },
  // ISO8601 completo: comparar el string es comparar la fecha, y sigue
  // sirviendo si alguna vez tra hora; la celda solo muestra los
  // primeros 10 caracteres.
  { campo: 'fecha_inicio', etiqueta: 'Inicio', tipo: 'texto' },
  { campo: 'fecha_fin', etiqueta: 'Fin', tipo: 'texto' },
]

const columnaOrden = ref(null)
const direccion = ref(1) // 1 = ascendente, -1 = descendente

function ordenar(campo) {
  if (columnaOrden.value === campo) {
    direccion.value = -direccion.value
  } else {
    columnaOrden.value = campo
    direccion.value = 1
  }
}

const filasOrdenadas = computed(() => {
  const filas = localidades.value
  const def = COLUMNAS.find((c) => c.campo === columnaOrden.value)
  // Sin columna activa se devuelve el orden que trae el backend: la tabla
  // arranca igual que antes y el orden es una acción del usuario.
  if (!filas || !def) return filas

  const dir = direccion.value
  return [...filas].sort((a, b) => {
    const va = a[def.campo]
    const vb = b[def.campo]
    // Los vacíos quedan SIEMPRE al final, en los dos sentidos: si se
    // multiplicaran por `dir`, ordenar descendente subiría todos los "—" y
    // la columna quedaría encabezada por datos inexistentes.
    const vacioA = va == null || va === ''
    const vacioB = vb == null || vb === ''
    if (vacioA && vacioB) return 0
    if (vacioA) return 1
    if (vacioB) return -1
    const r = def.tipo === 'num' ? va - vb : String(va).localeCompare(String(vb), 'es')
    return r * dir
  })
})

function ariaSort(campo) {
  if (columnaOrden.value !== campo) return 'none'
  return direccion.value === 1 ? 'ascending' : 'descending'
}
</script>

<template>
  <section class="panel">
    <h2>Resumen por localidad</h2>
    <DataPanel :loading="loading" :error="error" :empty="!localidades?.length" @reintentar="reload">
      <div class="tabla-scroll">
        <table>
          <thead>
            <tr>
              <!-- aria-sort va en la celda (no en el botón): es la propiedad
                   de la columna, y es lo que anuncia el lector de pantalla.
                   El botón solo hace falta que se llame como la cabecera. -->
              <th
                v-for="col in COLUMNAS"
                :key="col.campo"
                scope="col"
                :class="{ num: col.tipo === 'num' }"
                :aria-sort="ariaSort(col.campo)"
              >
                <button class="th-orden" type="button" @click="ordenar(col.campo)">
                  {{ col.etiqueta }}
                  <span class="th-orden__flecha" aria-hidden="true">
                    {{ columnaOrden === col.campo ? (direccion === 1 ? '▲' : '▼') : '↕' }}
                  </span>
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filasOrdenadas" :key="`${row.ccte}-${row.provincia}-${row.localidad}`">
              <td>{{ row.ccte }}</td>
              <td>{{ row.provincia }}</td>
              <td>{{ row.localidad }}</td>
              <td class="num">{{ row.mediciones }}</td>
              <td class="num">{{ row.resultado_max_vm != null ? row.resultado_max_vm.toFixed(2) : '—' }}</td>
              <td><SemaforoBadge :pct="row.resultado_max_pct" /></td>
              <td>{{ row.fecha_inicio ? row.fecha_inicio.slice(0, 10) : '—' }}</td>
              <td>{{ row.fecha_fin ? row.fecha_fin.slice(0, 10) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </DataPanel>
  </section>
</template>

<style scoped>
.tabla-scroll {
  overflow-x: auto;
}

/* Reset del botón UA: sin esto cada cabecera traía su fondo gris y sus
   esquinas redondeadas sobre un sistema deliberadamente cuadrado. */
.th-orden {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: none;
  border: 0;
  margin: 0;
  padding: 0;
  font: inherit;
  color: inherit;
}

.th-orden:hover {
  color: var(--signal-deep);
}

/* th.num alinea a la derecha para caer exactamente sobre td.num; sin esto
   la cabecera "Mediciones" quedaba a la izquierda de su número. La flecha
   va después del texto, así que en las columnas de texto queda pegada a la
   etiqueta y en las numéricas, por herencia de text-align, al borde. */
.th-orden__flecha {
  font-size: 0.7em;
  color: var(--ink-soft);
}
</style>
