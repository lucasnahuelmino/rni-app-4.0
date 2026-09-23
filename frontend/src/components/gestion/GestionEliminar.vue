<script setup>
import { ref } from 'vue'
import { localitiesApi } from '../../services/domains'

/**
 * Zona de borrado con su confirmación.
 *
 * El padre le pasa `:key` identificando a la localidad, así que al cambiar
 * de selección el componente se remonta y el diálogo de confirmación queda
 * cerrado (antes lo hacía seleccionar() desde la vista).
 *
 * Arregla de paso un bug heredado: el error del borrado se guardaba en
 * `errorGuardado`, que la vista mostraba DENTRO del formulario de edición
 * (`v-if="editando"`). Si no estabas editando, un fallo de borrado no se
 * veía en ningún lado. Cada componente tiene ahora su propio mensaje.
 */
const props = defineProps({
  localidad: { type: Object, required: true },
})

const emit = defineEmits(['eliminado'])

const confirmando = ref(false)
const borrando = ref(false)
const error = ref(null)

function abrirConfirmacion() {
  confirmando.value = true
  error.value = null
}

function cancelar() {
  confirmando.value = false
  error.value = null
}

async function eliminar() {
  borrando.value = true
  error.value = null
  try {
    await localitiesApi.deleteLocality(
      props.localidad.localidad,
      props.localidad.ccte,
      props.localidad.provincia,
    )
    emit('eliminado')
  } catch (e) {
    error.value = e?.response?.data?.detail || 'No se pudo eliminar la localidad.'
  } finally {
    borrando.value = false
  }
}
</script>

<template>
  <div class="gestion__danger">
    <button v-if="!confirmando" type="button" class="btn btn--danger" @click="abrirConfirmacion">
      Eliminar localidad
    </button>
    <div v-else class="gestion__confirmar" role="alertdialog" aria-label="Confirmar eliminación">
      <p>
        Esto borra permanentemente las {{ localidad.mediciones }} mediciones de
        <strong>{{ localidad.localidad }}</strong>. No se puede deshacer.
      </p>
      <div class="acciones-fila">
        <button type="button" class="btn btn--danger" :disabled="borrando" @click="eliminar">
          {{ borrando ? 'Eliminando…' : 'Sí, eliminar definitivamente' }}
        </button>
        <button type="button" class="btn btn--ghost" @click="cancelar">Cancelar</button>
      </div>
    </div>

    <!-- visible tanto si falla el borrado como si el diálogo sigue abierto -->
    <p v-if="error" role="alert" class="gestion__error">{{ error }}</p>
  </div>
</template>

<style scoped>
.gestion__danger {
  border-top: 1px solid var(--line);
  padding-top: 1rem;
  margin-top: 1rem;
}

.gestion__confirmar {
  border: 1px solid var(--risk-high);
  padding: 0.85rem;
}

.gestion__error {
  color: var(--risk-high);
  margin: 0.5rem 0 0;
}
</style>
