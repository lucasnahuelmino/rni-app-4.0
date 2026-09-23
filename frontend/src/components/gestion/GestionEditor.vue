<script setup>
import { ref } from 'vue'
import { localitiesApi } from '../../services/domains'

/**
 * Formulario de edición de metadata (CCTE / Provincia / Localidad /
 * Expediente).
 *
 * El padre le pasa `:key` identificando a la localidad, así que al cambiar
 * de selección el componente se remonta y el estado vuelve a cero: cerrado
 * y con el formulario precargado de la nueva localidad. Eso reproduce lo
 * que antes hacía seleccionar() en la vista (reseteaba editando y
 * reconstruía formEdicion).
 */
const props = defineProps({
  localidad: { type: Object, required: true },
})

const emit = defineEmits(['guardado'])

const editando = ref(false)
const form = ref({
  ccte: props.localidad.ccte,
  provincia: props.localidad.provincia,
  localidad: props.localidad.localidad,
  expediente: props.localidad.expedientes || '',
})
const guardando = ref(false)
const error = ref(null)

async function guardar() {
  guardando.value = true
  error.value = null
  try {
    await localitiesApi.editLocality(
      props.localidad.localidad,
      props.localidad.ccte,
      props.localidad.provincia,
      form.value,
    )
    emit('guardado')
  } catch (e) {
    error.value = e?.response?.data?.detail || 'No se pudo guardar el cambio.'
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div class="gestion__editor">
    <button v-if="!editando" type="button" class="btn btn--ghost" @click="editando = true">
      Editar metadata
    </button>
    <form v-else class="gestion__form" @submit.prevent="guardar">
      <label>
        CCTE
        <input v-model="form.ccte" type="text" />
      </label>
      <label>
        Provincia
        <input v-model="form.provincia" type="text" />
      </label>
      <label>
        Localidad
        <input v-model="form.localidad" type="text" />
      </label>
      <label>
        Expediente
        <input v-model="form.expediente" type="text" />
      </label>
      <div class="acciones-fila">
        <button type="submit" class="btn" :disabled="guardando">
          {{ guardando ? 'Guardando…' : 'Guardar cambios' }}
        </button>
        <button type="button" class="btn btn--ghost" @click="editando = false">Cancelar</button>
      </div>
      <p v-if="error" role="alert" class="gestion__error">{{ error }}</p>
    </form>
  </div>
</template>

<style scoped>
.gestion__editor {
  border-top: 1px solid var(--line);
  padding-top: 1rem;
  margin-top: 1rem;
}

.gestion__form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
}

.gestion__form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: var(--ink-soft);
}

/* input del formulario: ahora lo unifica el global de tokens.css */

/* la fila de botones vive afuera del grid: en tokens.css, porque
   GestionEliminar la necesita igual y el scoped CSS no cruza componentes */
.acciones-fila {
  grid-column: 1 / -1;
}

.gestion__error {
  color: var(--risk-high);
  grid-column: 1 / -1;
  margin: 0;
}
</style>
