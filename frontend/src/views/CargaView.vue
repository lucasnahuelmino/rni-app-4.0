<script setup>
import { ref } from 'vue'
import { importsApi } from '../services/domains'
import { CCTE_FIJOS } from '../ccte'
import { PROVINCIAS } from '../provincias'
import Combobox from '../components/Combobox.vue'

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
  // El combobox de CCTE y Provincia revierte lo escrito a mano cuando se
  // pierde el foco, así que con el mouse el `required` nativo ya corta el
  // submit. Con Enter no hay blur: el input sigue con "sant" puesto y el
  // navegador lo da por válido, mientras que `provincia` sigue en ''. Acá
  // se chequea el VALOR ELEGIDO y no lo que se ve en el campo.
  const faltantes = []
  if (!ccte.value) faltantes.push('CCTE')
  if (!provincia.value) faltantes.push('Provincia')
  if (!localidad.value) faltantes.push('Localidad')
  if (archivos.value.length === 0) faltantes.push('al menos un archivo Excel')
  if (faltantes.length) {
    errorEnvio.value = `Falta completar: ${faltantes.join(', ')}. Elegí las opciones de la lista en vez de escribirlas.`
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
      <Combobox
        v-model="ccte"
        :opciones="CCTE_FIJOS"
        label="CCTE"
        placeholder="Escribí para buscar…"
        required
      />
      <Combobox
        v-model="provincia"
        :opciones="PROVINCIAS"
        label="Provincia"
        placeholder="Escribí para buscar…"
        required
      />
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

/* input/select del formulario: los estilaba la vista con tres paddings
   distintos, ahora lo unifica el global de tokens.css. */

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
