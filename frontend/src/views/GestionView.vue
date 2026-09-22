<script setup>
import { ref, computed } from 'vue'
import { localitiesApi, reportsApi } from '../services/domains'
import { useFetchOnFiltros } from '../composables/useFetchOnFiltros'
import LoadingState from '../components/LoadingState.vue'
import ErrorState from '../components/ErrorState.vue'
import EmptyState from '../components/EmptyState.vue'
import SemaforoBadge from '../components/SemaforoBadge.vue'

const { data: localidades, loading, error, reload } = useFetchOnFiltros(
  async (filtros) => (await localitiesApi.getLocalities(filtros)).data,
)

const seleccionada = ref(null)
const editando = ref(false)
const formEdicion = ref({ ccte: '', provincia: '', localidad: '', expediente: '' })
const guardando = ref(false)
const errorGuardado = ref(null)
const confirmarBorrado = ref(false)
const borrando = ref(false)

function seleccionar(row) {
  seleccionada.value = row
  editando.value = false
  confirmarBorrado.value = false
  formEdicion.value = {
    ccte: row.ccte,
    provincia: row.provincia,
    localidad: row.localidad,
    expediente: row.expedientes || '',
  }
}

async function guardarEdicion() {
  if (!seleccionada.value) return
  guardando.value = true
  errorGuardado.value = null
  try {
    await localitiesApi.editLocality(
      seleccionada.value.localidad,
      seleccionada.value.ccte,
      seleccionada.value.provincia,
      formEdicion.value,
    )
    editando.value = false
    seleccionada.value = null
    await reload()
  } catch (e) {
    errorGuardado.value = e?.response?.data?.detail || 'No se pudo guardar el cambio.'
  } finally {
    guardando.value = false
  }
}

async function eliminarLocalidad() {
  if (!seleccionada.value) return
  borrando.value = true
  try {
    await localitiesApi.deleteLocality(seleccionada.value.localidad, seleccionada.value.ccte, seleccionada.value.provincia)
    seleccionada.value = null
    confirmarBorrado.value = false
    await reload()
  } catch (e) {
    errorGuardado.value = e?.response?.data?.detail || 'No se pudo eliminar la localidad.'
  } finally {
    borrando.value = false
  }
}

const urlWord = computed(() => {
  if (!seleccionada.value) return null
  return reportsApi.wordUrl(seleccionada.value.ccte, seleccionada.value.provincia, seleccionada.value.localidad, 'Localidad')
})
const urlPdf = computed(() => {
  if (!seleccionada.value) return null
  return reportsApi.pdfUrl(seleccionada.value.ccte, seleccionada.value.provincia, seleccionada.value.localidad, 'Localidad')
})
</script>

<template>
  <div class="gestion">
    <section class="panel gestion__lista">
      <h2>Localidades</h2>
      <ErrorState v-if="error" @reintentar="reload" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!localidades?.length" />
      <ul v-else class="gestion__ul">
        <li v-for="row in localidades" :key="`${row.ccte}-${row.localidad}`">
          <button
            class="gestion__item"
            :class="{ 'gestion__item--activo': seleccionada?.localidad === row.localidad && seleccionada?.ccte === row.ccte }"
            @click="seleccionar(row)"
          >
            <span>{{ row.localidad }}</span>
            <span class="gestion__item-meta">{{ row.provincia }} · {{ row.ccte }}</span>
          </button>
        </li>
      </ul>
    </section>

    <section class="panel gestion__detalle">
      <template v-if="!seleccionada">
        <EmptyState mensaje="Elegí una localidad de la lista para ver el detalle." />
      </template>
      <template v-else>
        <div class="gestion__header">
          <div>
            <h2>{{ seleccionada.localidad }}</h2>
            <p class="gestion__subtitulo">{{ seleccionada.provincia }} · CCTE {{ seleccionada.ccte }}</p>
          </div>
          <div class="gestion__acciones">
            <a class="btn btn--ghost" :href="urlWord">Exportar Word</a>
            <a class="btn btn--ghost" :href="urlPdf">Exportar PDF</a>
          </div>
        </div>

        <dl class="gestion__stats">
          <div><dt>Mediciones</dt><dd class="num">{{ seleccionada.mediciones }}</dd></div>
          <div><dt>Máx. V/m</dt><dd class="num">{{ seleccionada.resultado_max_vm?.toFixed(2) ?? '—' }}</dd></div>
          <div><dt>Nivel</dt><dd><SemaforoBadge :pct="seleccionada.resultado_max_pct" /></dd></div>
          <div><dt>Desde</dt><dd>{{ seleccionada.fecha_inicio?.slice(0, 10) ?? '—' }}</dd></div>
          <div><dt>Hasta</dt><dd>{{ seleccionada.fecha_fin?.slice(0, 10) ?? '—' }}</dd></div>
        </dl>

        <div class="gestion__editor">
          <button v-if="!editando" class="btn btn--ghost" @click="editando = true">Editar metadata</button>
          <form v-else class="gestion__form" @submit.prevent="guardarEdicion">
            <label>
              CCTE
              <input v-model="formEdicion.ccte" type="text" />
            </label>
            <label>
              Provincia
              <input v-model="formEdicion.provincia" type="text" />
            </label>
            <label>
              Localidad
              <input v-model="formEdicion.localidad" type="text" />
            </label>
            <label>
              Expediente
              <input v-model="formEdicion.expediente" type="text" />
            </label>
            <div class="gestion__form-acciones">
              <button type="submit" class="btn" :disabled="guardando">
                {{ guardando ? 'Guardando…' : 'Guardar cambios' }}
              </button>
              <button type="button" class="btn btn--ghost" @click="editando = false">Cancelar</button>
            </div>
            <p v-if="errorGuardado" role="alert" class="gestion__error">{{ errorGuardado }}</p>
          </form>
        </div>

        <div class="gestion__danger">
          <button v-if="!confirmarBorrado" class="btn btn--danger" @click="confirmarBorrado = true">
            Eliminar localidad
          </button>
          <div v-else class="gestion__confirmar" role="alertdialog" aria-label="Confirmar eliminación">
            <p>
              Esto borra permanentemente las {{ seleccionada.mediciones }} mediciones de
              <strong>{{ seleccionada.localidad }}</strong>. No se puede deshacer.
            </p>
            <div class="gestion__form-acciones">
              <button class="btn btn--danger" :disabled="borrando" @click="eliminarLocalidad">
                {{ borrando ? 'Eliminando…' : 'Sí, eliminar definitivamente' }}
              </button>
              <button class="btn btn--ghost" @click="confirmarBorrado = false">Cancelar</button>
            </div>
          </div>
        </div>
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

.gestion__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.gestion__subtitulo {
  color: var(--ink-soft);
  margin: 0.2rem 0 0;
}

.gestion__acciones {
  display: flex;
  gap: 0.5rem;
}

.gestion__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 0.75rem;
  margin: 0 0 1.25rem;
}

.gestion__stats dt {
  font-size: 0.75rem;
  color: var(--ink-soft);
}

.gestion__stats dd {
  margin: 0;
}

.gestion__editor,
.gestion__danger {
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

.gestion__form input {
  border: 1px solid var(--line);
  padding: 0.4rem 0.5rem;
  color: var(--ink);
}

.gestion__form-acciones {
  display: flex;
  gap: 0.5rem;
  grid-column: 1 / -1;
}

.gestion__confirmar {
  border: 1px solid var(--risk-high);
  padding: 0.85rem;
}

.gestion__error {
  color: var(--risk-high);
  grid-column: 1 / -1;
  margin: 0;
}
</style>
