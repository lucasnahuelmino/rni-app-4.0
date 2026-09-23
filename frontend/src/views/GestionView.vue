<script setup>
import { ref, nextTick } from 'vue'
import { localitiesApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import EmptyState from '../components/EmptyState.vue'
import GestionLista from '../components/gestion/GestionLista.vue'
import GestionDetalle from '../components/gestion/GestionDetalle.vue'
import GestionTiempos from '../components/gestion/GestionTiempos.vue'
import GestionEditor from '../components/gestion/GestionEditor.vue'
import GestionEliminar from '../components/gestion/GestionEliminar.vue'

// La vista quedó como orquestadora: trae el listado, cuál está seleccionada
// y qué hacer después de una mutación. Cada bloque del detalle vive en
// components/gestion/ con su propio estado y sus propios estilos.
const { data: localidades, loading, error, reload } = useFetchOnFiltros(
  async (filtros) => (await localitiesApi.getLocalities(filtros)).data,
)

const seleccionada = ref(null)
const detalle = ref(null)

function seleccionar(row) {
  seleccionada.value = row
}

// Guardar o eliminar vuelven al estado inicial: se deselecciona (lo que
// además remonta Editor/Eliminar vía :key) y se refresca el resumen.
async function despuesDeCambiar() {
  seleccionada.value = null
  await reload()
  // El botón que tenía el foco ya no existe (la localidad se quitó de la
  // selección y puede haber salido de la lista), así que sin esto el foco
  // se pierde en <body>. Va al contenedor del detalle, que es lo que acaba
  // de cambiar: anuncia el estado vacío "Elegí una localidad".
  await nextTick()
  detalle.value?.focus()
}
</script>

<template>
  <div class="gestion">
    <GestionLista
      :localidades="localidades"
      :loading="loading"
      :error="error"
      :seleccionada="seleccionada"
      @seleccionar="seleccionar"
      @reintentar="reload"
    />

    <section ref="detalle" class="panel gestion__detalle" tabindex="-1">
      <EmptyState
        v-if="!seleccionada"
        mensaje="Elegí una localidad de la lista para ver el detalle."
      />
      <template v-else>
        <GestionDetalle :localidad="seleccionada" />

        <!-- Sin key: recarga observando la prop, y el tab activo tiene que
             sobrevivir al cambio de localidad (así era antes). -->
        <GestionTiempos :localidad="seleccionada" />

        <!-- Con key: al cambiar de localidad se remontan y el formulario y
             el diálogo de confirmación vuelven a su estado inicial, igual
             que lo que antes hacía seleccionar(). -->
        <GestionEditor
          :key="`editor-${seleccionada.ccte}-${seleccionada.localidad}`"
          :localidad="seleccionada"
          @guardado="despuesDeCambiar"
        />
        <GestionEliminar
          :key="`eliminar-${seleccionada.ccte}-${seleccionada.localidad}`"
          :localidad="seleccionada"
          @eliminado="despuesDeCambiar"
        />
      </template>
    </section>
  </div>
</template>

<style scoped>
.gestion {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1rem;
  align-items: start;
}
</style>
