<script setup>
import { ref, computed } from 'vue'
import { localitiesApi, reportsApi, tiemposApi } from '../services/domains'
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

const tabTiempo = ref('diario') // 'diario' | 'mensual'
const tiempoDiario = ref(null)
const tiempoMensual = ref(null)
const loadingTiempo = ref(false)
const errorTiempo = ref(null)

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
  cargarTiempos()
}

async function cargarTiempos() {
  if (!seleccionada.value) return
  loadingTiempo.value = true
  errorTiempo.value = null
  try {
    const { ccte, provincia, localidad } = seleccionada.value
    const [diario, mensual] = await Promise.all([
      tiemposApi.getDiario(ccte, provincia, localidad),
      tiemposApi.getMensual({ ccte, provincia, localidad }),
    ])
    tiempoDiario.value = diario.data
    tiempoMensual.value = mensual.data
  } catch (e) {
    errorTiempo.value = e
  } finally {
    loadingTiempo.value = false
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
            <p class="gestion__meta-lista">
              <strong>Expediente(s):</strong>
              <span v-if="seleccionada.expedientes_lista?.length">{{ seleccionada.expedientes_lista.join(', ') }}</span>
              <span v-else class="gestion__sin-dato">Sin expediente registrado</span>
            </p>
            <p class="gestion__meta-lista">
              <strong>Sonda(s):</strong>
              <span v-if="seleccionada.sondas_lista?.length">{{ seleccionada.sondas_lista.join(', ') }}</span>
              <span v-else class="gestion__sin-dato">—</span>
            </p>
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
          <div><dt>Fecha inicial</dt><dd>{{ seleccionada.fecha_inicio?.slice(0, 10) ?? '—' }}</dd></div>
          <div><dt>Fecha final</dt><dd>{{ seleccionada.fecha_fin?.slice(0, 10) ?? '—' }}</dd></div>
          <div><dt>Tiempo trabajado</dt><dd class="num">{{ seleccionada.tiempo_trabajado_fmt ?? '0 s' }}</dd></div>
          <div><dt>Días con medición</dt><dd class="num">{{ seleccionada.dias_con_medicion ?? 0 }}</dd></div>
        </dl>

        <div class="gestion__tiempos">
          <div class="gestion__tabs" role="tablist" aria-label="Desglose de tiempo trabajado">
            <button
              class="chip"
              :class="{ 'chip--active': tabTiempo === 'diario' }"
              role="tab"
              :aria-selected="tabTiempo === 'diario'"
              @click="tabTiempo = 'diario'"
            >
              Diario
            </button>
            <button
              class="chip"
              :class="{ 'chip--active': tabTiempo === 'mensual' }"
              role="tab"
              :aria-selected="tabTiempo === 'mensual'"
              @click="tabTiempo = 'mensual'"
            >
              Mensual
            </button>
          </div>

          <ErrorState v-if="errorTiempo" @reintentar="cargarTiempos" />
          <LoadingState v-else-if="loadingTiempo" mensaje="Calculando tiempo trabajado…" />
          <template v-else>
            <EmptyState v-if="tabTiempo === 'diario' && !tiempoDiario?.length" mensaje="Sin jornadas registradas." />
            <table v-else-if="tabTiempo === 'diario'">
              <thead>
                <tr><th>Fecha</th><th>Inicio</th><th>Fin</th><th>Duración</th></tr>
              </thead>
              <tbody>
                <tr v-for="d in tiempoDiario" :key="`${d.fecha}-${d.nombre_archivo}`">
                  <td>{{ d.fecha }}</td>
                  <td class="num">{{ d.inicio }}</td>
                  <td class="num">{{ d.fin }}</td>
                  <td class="num">{{ d.duracion_fmt }}</td>
                </tr>
              </tbody>
            </table>

            <EmptyState v-if="tabTiempo === 'mensual' && !tiempoMensual?.length" mensaje="Sin datos mensuales." />
            <table v-else-if="tabTiempo === 'mensual'">
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
          </template>
        </div>

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

.gestion__meta-lista {
  font-size: 0.8rem;
  margin: 0.15rem 0 0;
}

.gestion__sin-dato {
  color: var(--ink-soft);
}

.gestion__acciones {
  display: flex;
  gap: 0.5rem;
}

.gestion__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
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

.gestion__tiempos {
  border-top: 1px solid var(--line);
  padding-top: 1rem;
}

.gestion__tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
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

/* input del formulario: ahora lo unifica el global de tokens.css */

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
