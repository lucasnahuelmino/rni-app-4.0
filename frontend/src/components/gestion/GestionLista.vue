<script setup>
import DataPanel from '../DataPanel.vue'

/**
 * Panel izquierdo: el listado de localidades y cuál está seleccionada.
 * Toda la carga vive en GestionView; acá solo se pinta y se emite.
 */
defineProps({
  localidades: { type: Array, default: null },
  loading: { type: Boolean, default: false },
  // El composable guarda la excepción tal cual, así que el tipo es abierto.
  error: { default: null },
  seleccionada: { type: Object, default: null },
})

defineEmits(['seleccionar', 'reintentar'])
</script>

<template>
  <section class="panel gestion__lista">
    <h2>Localidades</h2>
    <DataPanel
      :loading="loading"
      :error="error"
      :empty="!localidades?.length"
      @reintentar="$emit('reintentar')"
    >
      <ul class="gestion__ul">
        <li v-for="row in localidades" :key="`${row.ccte}-${row.localidad}`">
          <button
            type="button"
            class="gestion__item"
            :class="{
              'gestion__item--activo':
                seleccionada?.localidad === row.localidad && seleccionada?.ccte === row.ccte,
            }"
            @click="$emit('seleccionar', row)"
          >
            <span>{{ row.localidad }}</span>
            <span class="gestion__item-meta">{{ row.provincia }} · {{ row.ccte }}</span>
          </button>
        </li>
      </ul>
    </DataPanel>
  </section>
</template>

<style scoped>
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

.gestion__item-meta {
  font-size: 0.75rem;
  color: var(--ink-soft);
}
</style>
