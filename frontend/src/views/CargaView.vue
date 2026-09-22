<script setup>
import { ref } from 'vue'
import { importsApi } from '../services/domains'
import { CCTE_FIJOS } from '../constants'

const ccte = ref('')
const provincia = ref('')
const localidad = ref('')
const expediente = ref('')
const archivos = ref([])
const enviando = ref(false)
const reporte = ref(null)
const errorEnvio = ref(null)

function onArchivosChange(e) {
  archivos.value = Array.from(e.target.files || [])
}

async function enviar() {
  if (!ccte.value || !provincia.value || !localidad.value || archivos.value.length === 0) {
    errorEnvio.value = 'Completá CCTE, Provincia, Localidad y al menos un archivo.'
    return
  }
  enviando.value = true
  errorEnvio.value = null
  reporte.value = null

  const formData = new FormData()
  formData.append('ccte', ccte.value)
  formData.append('provincia', provincia.value)
  formData.append('localidad', localidad.value)
  if (expediente.value) formData.append('expediente', expediente.value)
  archivos.value.forEach((f) => formData.append('archivos', f))

  try {
    const { data } = await importsApi.postImport(formData)
    reporte.value = data
  } catch (e) {
    errorEnvio.value = e?.response?.data?.detail || 'No se pudo procesar la importación.'
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <section class="panel carga">
    <h2>Carga de Excel</h2>
    <form class="carga__form" @submit.prevent="enviar">
      <label>
        CCTE
        <select v-model="ccte" required>
          <option value="" disabled>Elegir…</option>
          <option v-for="c in CCTE_FIJOS" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <label>
        Provincia
        <input v-model="provincia" type="text" required />
      </label>
      <label>
        Localidad
        <input v-model="localidad" type="text" required />
      </label>
      <label>
        Expediente (opcional)
        <input v-model="expediente" type="text" />
      </label>
      <label class="carga__archivos">
        Archivos Excel
        <input type="file" accept=".xlsx,.xls" multiple @change="onArchivosChange" required />
      </label>

      <div class="carga__acciones">
        <button class="btn" type="submit" :disabled="enviando">
          {{ enviando ? 'Procesando…' : 'Importar' }}
        </button>
      </div>

      <p v-if="errorEnvio" role="alert" class="carga__error">{{ errorEnvio }}</p>
    </form>

    <div v-if="reporte" class="carga__reporte panel" role="status">
      <h3>Reporte de importación (lote #{{ reporte.id }})</h3>
      <dl class="carga__reporte-grid">
        <div><dt>Archivos procesados</dt><dd class="num">{{ reporte.archivos_procesados }}</dd></div>
        <div><dt>Registros nuevos</dt><dd class="num">{{ reporte.registros_nuevos }}</dd></div>
        <div><dt>Duplicados</dt><dd class="num">{{ reporte.registros_duplicados }}</dd></div>
        <div><dt>Rechazados</dt><dd class="num">{{ reporte.registros_rechazados }}</dd></div>
      </dl>

      <div v-if="reporte.advertencias?.length" class="carga__lista">
        <h4>Advertencias</h4>
        <ul>
          <li v-for="(a, i) in reporte.advertencias" :key="i">{{ a.archivo }}: {{ a.advertencia }}</li>
        </ul>
      </div>

      <div v-if="reporte.errores?.length" class="carga__lista carga__lista--error">
        <h4>Errores</h4>
        <ul>
          <li v-for="(err, i) in reporte.errores" :key="i">{{ err.archivo }}: {{ err.error }}</li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.carga__form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  max-width: 720px;
}

.carga__form label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--ink-soft);
}

.carga__form input,
.carga__form select {
  border: 1px solid var(--line);
  padding: 0.45rem 0.5rem;
  color: var(--ink);
}

.carga__archivos {
  grid-column: 1 / -1;
}

.carga__acciones {
  grid-column: 1 / -1;
}

.carga__error {
  grid-column: 1 / -1;
  color: var(--risk-high);
}

.carga__reporte {
  margin-top: 1.5rem;
  max-width: 720px;
}

.carga__reporte-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.75rem;
  margin: 0.75rem 0;
}

.carga__reporte-grid dt {
  font-size: 0.75rem;
  color: var(--ink-soft);
}

.carga__reporte-grid dd {
  margin: 0;
}

.carga__lista--error {
  color: var(--risk-high);
}
</style>
