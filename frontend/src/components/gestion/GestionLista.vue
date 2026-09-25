<script setup>
import { computed, ref, useId } from 'vue'

import DataPanel from '../DataPanel.vue'
import { fmtPct, fmtVm } from '../../format'
import { normalizar } from '../../texto.js'

/**
 * Panel izquierdo: el listado de localidades y cuál está seleccionada.
 * Toda la carga vive en GestionView; acá solo se pinta, filtra y emite.
 *
 * El buscador filtra SOBRE lo que ya vino del servidor y no arma un query
 * param: son 61 filas en memoria, así que tipear responde sin ida y vuelta
 * y sin pisar la caché que comparte useFetchOnFiltros con el resto de la
 * app. Cubre localidad, expediente y provincia -- los tres campos que se
 * usan para reconocer una medición.
 */
const props = defineProps({
  localidades: { type: Array, default: null },
  loading: { type: Boolean, default: false },
  // El composable guarda la excepción tal cual, así que el tipo es abierto.
  error: { default: null },
  seleccionada: { type: Object, default: null },
})

const emit = defineEmits(['seleccionar', 'reintentar'])

const idBusqueda = useId()
const busqueda = ref('')

/** `row.expedientes` puede venir vacío o nulo; `normalizar` ya lo baja a ''. */
const filtradas = computed(() => {
  const q = normalizar(busqueda.value)
  const filas = props.localidades ?? []
  if (!q) return filas
  return filas.filter((row) =>
    [row.localidad, row.expedientes, row.provincia].some((v) => normalizar(v).includes(q)),
  )
})

const contador = computed(() => {
  const total = props.localidades?.length ?? 0
  if (!busqueda.value.trim()) return `${total} localidades`
  return `${filtradas.value.length} de ${total}`
})
</script>

<template>
  <section class="panel gestion__lista">
    <h2>Localidades</h2>

    <!-- Solo con datos cargados: mientras no haya filas, DataPanel muestra su
         propio estado vacío y un campo que no filtra nada sería ruido. -->
    <div v-if="localidades?.length" class="gestion__buscador">
      <label class="gestion__buscador-label" :for="idBusqueda">Buscar</label>
      <input
        :id="idBusqueda"
        v-model="busqueda"
        type="search"
        class="gestion__buscador-input"
        placeholder="Localidad, expediente o provincia…"
        autocomplete="off"
      />
      <!-- role=status hace que un lector de pantalla anuncie el cambio de
           conteo sin robarle el foco a quien está tipeando. -->
      <p class="gestion__buscador-contador" role="status">{{ contador }}</p>
    </div>

    <DataPanel
      :loading="loading"
      :error="error"
      :empty="!localidades?.length"
      @reintentar="emit('reintentar')"
    >
      <p v-if="!filtradas.length" class="gestion__sin-resultados">
        Ninguna localidad coincide con «{{ busqueda }}».
      </p>
      <ul v-else class="gestion__ul">
        <li v-for="row in filtradas" :key="`${row.ccte}-${row.localidad}`">
          <button
            type="button"
            class="gestion__item"
            :class="{
              'gestion__item--activo':
                seleccionada?.localidad === row.localidad && seleccionada?.ccte === row.ccte,
            }"
            @click="emit('seleccionar', row)"
          >
            <span class="gestion__item-nombre">{{ row.localidad }}</span>
            <span class="gestion__item-meta">{{ row.provincia }} · {{ row.ccte }}</span>
            <!-- Los números con los que se reconoce una localidad: sus
                 máximos y cuántos puntos tiene. fmtVm/fmtPct son los mismos
                 formateadores del resto de la app -- decimales exactos de la
                 base, sin redondear (DESIGN.md, "Decimales"). -->
            <span class="gestion__item-datos">
              <span>Máx {{ fmtVm(row.resultado_max_vm) }} V/m</span>
              <span>{{ fmtPct(row.resultado_max_pct) }} %</span>
              <span :title="`${row.mediciones} mediciones`">{{ row.mediciones }} pts</span>
            </span>
            <!-- El expediente es largo y a veces hay más de uno: en la
                 columna angosta se corta con puntos suspensivos y el texto
                 completo queda en el tooltip del navegador. -->
            <span
              v-if="row.expedientes"
              class="gestion__item-exp"
              :title="row.expedientes"
            >{{ row.expedientes }}</span>
          </button>
        </li>
      </ul>
    </DataPanel>
  </section>
</template>

<style scoped>
.gestion__buscador {
  margin-bottom: 0.75rem;
}

.gestion__buscador-label {
  display: block;
  font-size: 0.75rem;
  color: var(--ink-soft);
  margin-bottom: 0.25rem;
}

.gestion__buscador-input {
  width: 100%;
  padding: 0.4rem 0.5rem;
  font: inherit;
  font-size: 0.875rem;
  color: inherit;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 4px;
}

.gestion__buscador-input:focus-visible {
  outline: 2px solid var(--signal);
  outline-offset: 1px;
}

.gestion__buscador-contador {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: var(--ink-soft);
}

.gestion__sin-resultados {
  margin: 0;
  padding: 0.75rem 0.25rem;
  font-size: 0.875rem;
  color: var(--ink-soft);
}

.gestion__ul {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 70vh;
  overflow-y: auto;
}

.gestion__item {
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  border-bottom: 1px solid var(--line);
  padding: 0.5rem 0.25rem;
  display: flex;
  flex-direction: column;
}

.gestion__item--activo {
  border-left: 3px solid var(--signal);
  background: var(--paper);
}

.gestion__item-nombre {
  font-weight: 500;
}

.gestion__item-meta {
  font-size: 0.75rem;
  color: var(--ink-soft);
}

.gestion__item-datos {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 0.6rem;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

/* El expediente puede ocupar dos líneas de la pantalla: se corta en una y
   el texto entero vive en el tooltip. */
.gestion__item-exp {
  font-size: 0.6875rem;
  color: var(--ink-soft);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
