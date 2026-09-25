<script setup>
import { nextTick, ref, watch } from 'vue'

import { localitiesApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import { useFiltrosStore } from '../stores/filtros'
import CcteSelector from '../components/centro/CcteSelector.vue'
import CentroResumen from '../components/centro/CentroResumen.vue'
import GestionLista from '../components/gestion/GestionLista.vue'
import GestionDetalle from '../components/gestion/GestionDetalle.vue'
import GestionTiempos from '../components/gestion/GestionTiempos.vue'
import GestionEditor from '../components/gestion/GestionEditor.vue'
import GestionEliminar from '../components/gestion/GestionEliminar.vue'

/**
 * Centro operativo: lo que antes eran "Gestión" y "Gráficos" en dos
 * secciones, ahora una sola.
 *
 * Dos estados y nada más:
 *
 *   - SIN localidad seleccionada  -> CentroResumen: la info de todo el
 *     centro (resumen, tendencia, tiempos mensual y diario, top 10).
 *   - CON localidad seleccionada  -> el detalle de esa localidad, con un
 *     botón para volver.
 *
 * El CCTE se elige con botones arriba de todo (CcteSelector) y escribe en
 * `filtros.ccte`, el mismo estado del panel "Filtros" global -- así la
 * lista, el resumen y los gráficos se enteran todos juntos y no hay un
 * estado paralelo que pueda quedar desfasado respecto de otro.
 */
const filtros = useFiltrosStore()

const { data: localidades, loading, error, reload } = useFetchOnFiltros(
  async (f) => (await localitiesApi.getLocalities(f)).data,
)

const seleccionada = ref(null)
const detalle = ref(null)

function seleccionar(row) {
  seleccionada.value = row
}

/**
 * Vuelve a la vista del centro. Es también lo que pasa después de guardar o
 * eliminar (que además refresca el resumen): dos motivos distintos, mismo
 * estado final, así que es una sola función.
 *
 * El foco va al panel del detalle, que es lo que acaba de cambiar: sin esto
 * se perdería en <body>, porque el botón que lo tenía ya no existe.
 */
async function irAlCentro(recargar = false) {
  seleccionada.value = null
  if (recargar) await reload()
  await nextTick()
  detalle.value?.focus()
}

// Elegir otro CCTE vuelve a la vista del centro: al apretar un botón de CCTE
// tiene que verse la info de ese centro (o de todos), no la localidad que
// estaba abierta de antes -- que además puede ni siquiera pertenecerle.
//
// El foco NO se mueve acá: queda en el radio que se apretó, que es donde
// sigue trabajando quien lo usó. Dejarlo en el panel habría arrancado al
// usuario del selector en medio de que está eligiendo.
watch(
  () => filtros.ccte.slice(),
  () => {
    seleccionada.value = null
  },
)
</script>

<template>
  <div class="gestion">
    <div class="gestion__barra">
      <CcteSelector />
    </div>

    <GestionLista
      :localidades="localidades"
      :loading="loading"
      :error="error"
      :seleccionada="seleccionada"
      @seleccionar="seleccionar"
      @reintentar="reload"
    />

    <section ref="detalle" class="panel gestion__detalle" tabindex="-1">
      <template v-if="seleccionada">
        <button type="button" class="btn btn--ghost gestion__volver" @click="irAlCentro()">
          ← Volver al centro
        </button>

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
          @guardado="irAlCentro(true)"
        />
        <GestionEliminar
          :key="`eliminar-${seleccionada.ccte}-${seleccionada.localidad}`"
          :localidad="seleccionada"
          @eliminado="irAlCentro(true)"
        />
      </template>

      <CentroResumen v-else />
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

/* El selector va sobre las dos columnas: es una elección sobre TODO el
   centro, no sobre la lista ni sobre el detalle. */
.gestion__barra {
  grid-column: 1 / -1;
}

.gestion__volver {
  align-self: flex-start;
  margin-bottom: 0.75rem;
}
</style>
