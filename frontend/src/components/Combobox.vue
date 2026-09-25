<script setup>
import { computed, ref, useId, watch } from 'vue'

import { normalizar } from '../texto.js'

/**
 * Combobox con búsqueda (tipo "escribí y filtrá"), para los campos que antes
 * se cargaban a mano: Provincia y CCTE.
 *
 * El problema que resuelve es que un error de tipeo NO falla. "Cordoba" sin
 * acento entra igual a la base y a partir de ahí hay DOS provincias en
 * Resumen, en el KPI "Provincias" y en el mapa. Este control solo admite
 * valores de `opciones`, que salen de src/provincias.js y src/ccte.js.
 *
 * La búsqueda no distingue mayúsculas ni acentos, así que "sant" encuentra
 * "Santiago del Estero" y "rio negro" encuentra "Río Negro". Coincide por
 * subcadena dentro del catálogo, que ya viene ordenado alfabéticamente, así
 * que el orden de los resultados es el del catálogo y no cambia de una
 * tipeada a otra.
 *
 * Accesibilidad: es un combobox ARIA de verdad (role=combobox +
 * aria-expanded + aria-controls + aria-activedescendant sobre un listbox de
 * options), no un input con un div flotando abajo. Solo se resalta una
 * opción con las flechas, nunca sola al tipear -- ver `activo` abajo.
 */
const props = defineProps({
  /** Valor elegido. Solo puede ser '' o una de `opciones`. */
  modelValue: { type: String, default: '' },
  /** Catálogo completo, sin filtrar: lo filtra el propio componente. */
  opciones: { type: Array, required: true },
  label: { type: String, required: true },
  /**
   * Deja el `<label>` solo para lectores de pantalla. Para cuando el campo
   * ya está rotulado por encima (el panel de Filtros tiene un `<h3>` con el
   * nombre del grupo): el label sigue asociado al input por `for`/`id`, que
   * es lo que hace falta para accesibilidad, pero no se ve dos veces.
   */
  labelOculto: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Elegir…' },
  required: { type: Boolean, default: false },
})

/** `seleccionado` existe aparte de `update:modelValue` para los casos en
 *  que el valor no se guarda sino que dispara algo (el filtro de
 *  Provincia: al elegir, se agrega el chip y el campo se vacía). */
const emit = defineEmits(['update:modelValue', 'seleccionado'])

const uid = useId()
const idCampo = `${uid}-campo`
const idLista = `${uid}-lista`
const idOpcion = (i) => `${uid}-op-${i}`

const texto = ref(props.modelValue)
const abierto = ref(false)

/**
 * Índice resaltado, o -1 si no hay ninguno. Que arranque en -1 y no en 0 es
 * deliberado: si al tipear quedara marcada la primera coincidencia, "sant" +
 * Enter confirmaría "Santa Cruz" sin que nadie lo haya elegido, que es
 * exactamente el error de tipeo que este control existe para evitar. Con -1,
 * Enter sin flechas no elige nada y el campo se resuelve al perder el foco.
 */
const activo = ref(-1)

/** El padre puede vaciar o cambiar el valor desde afuera (filtro, reset). */
watch(
  () => props.modelValue,
  (v) => {
    texto.value = v ?? ''
  },
)

/** Minúsculas, sin acentos, sin espacios sobrantes: ver src/texto.js. */

const coincidencias = computed(() => {
  const q = normalizar(texto.value)
  if (!q) return props.opciones
  return props.opciones.filter((o) => normalizar(o).includes(q))
})

function abrir() {
  abierto.value = true
  activo.value = -1
}

function alEscribir(e) {
  texto.value = e.target.value
  abierto.value = true
  activo.value = -1
}

function elegir(op) {
  texto.value = op
  abierto.value = false
  activo.value = -1
  if (op !== props.modelValue) {
    emit('update:modelValue', op)
    emit('seleccionado', op)
  }
}

/**
 * Al salir del campo, lo escrito se resuelve solo:
 *
 *   - identifica a UNA sola opción  -> se adopta. Tipear el nombre completo
 *     a mano tiene que servir, y de paso lo normaliza ("santiago del estero"
 *     queda "Santiago del Estero").
 *   - cualquier otra cosa           -> se repone el último valor elegido.
 *     "sant" escrito a mano no es una provincia: si no se revertiera, el
 *     input mostraría algo que no está elegido, el `required` nativo del
 *     formulario lo dejaría pasar y el valor en la base sería el que
 *     venía de antes. Con la reversión el campo queda vacío y el submit
 *     avisa.
 */
function alPerderFoco() {
  abierto.value = false
  activo.value = -1
  const c = coincidencias.value
  if (c.length === 1) elegir(c[0])
  else texto.value = props.modelValue
}

function alTeclar(e) {
  const n = coincidencias.value.length

  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    abierto.value = true
    if (!n) return
    activo.value =
      e.key === 'ArrowDown'
        ? Math.min(activo.value + 1, n - 1)
        : Math.max(activo.value - 1, 0)
    return
  }

  if (e.key === 'Enter') {
    if (!abierto.value) return // lista cerrada: que el formulario haga lo suyo
    // Con una opción resaltada se elige esa. Sin resaltar, solo si el texto
    // identifica a UNA: ahí sí conviene adoptarla, así "santa cruz" +
    // Enter sirve sin tener que bajar con la flecha. Con varias o con
    // ninguna NO se frena el submit: el formulario avisa qué falta, que es
    // un mensaje más útil que una tecla que no hace nada.
    const elegible =
      activo.value >= 0 && activo.value < n
        ? coincidencias.value[activo.value]
        : n === 1
          ? coincidencias.value[0]
          : null
    if (elegible) {
      e.preventDefault()
      elegir(elegible)
    }
    return
  }

  if (e.key === 'Escape' && abierto.value) {
    e.preventDefault()
    abierto.value = false
    activo.value = -1
    texto.value = props.modelValue
  }
}
</script>

<template>
  <div class="combobox">
    <label :for="idCampo" :class="{ 'sr-only': labelOculto }">
      {{ label }}<span v-if="required" class="combobox__marca" aria-hidden="true"> *</span>
    </label>

    <div class="combobox__campo">
      <input
        :id="idCampo"
        :value="texto"
        type="text"
        role="combobox"
        class="combobox__input"
        :placeholder="placeholder"
        :required="required"
        autocomplete="off"
        :aria-expanded="abierto ? 'true' : 'false'"
        aria-autocomplete="list"
        :aria-controls="idLista"
        :aria-activedescendant="abierto && activo >= 0 ? idOpcion(activo) : undefined"
        @focus="abrir"
        @input="alEscribir"
        @keydown="alTeclar"
        @blur="alPerderFoco"
      />
      <span class="combobox__flecha" aria-hidden="true">▾</span>
    </div>

    <!-- v-show y no v-if: el `<ul>` tiene que existir siempre en el DOM
         aunque esté cerrado, si no aria-controls apunta a un id que no
         existe. Con display:none el listbox queda igual oculto para los
         lectores de pantalla.
         mousedown.prevent en la lista: sin eso, apretar una opción hace
         blur en el input, el blur cierra la lista y el click se pierde. -->
    <ul
      v-show="abierto"
      :id="idLista"
      role="listbox"
      class="combobox__lista"
      :aria-label="label"
      @mousedown.prevent
    >
      <li
        v-for="(o, i) in coincidencias"
        :id="idOpcion(i)"
        :key="o"
        role="option"
        :aria-selected="o === modelValue"
        class="combobox__opcion"
        :class="{ 'combobox__opcion--activa': i === activo }"
        @click="elegir(o)"
        @mouseenter="activo = i"
      >
        {{ o }}
      </li>
      <li v-if="!coincidencias.length" class="combobox__sin-coincidencias" role="presentation">
        Sin coincidencias
      </li>
    </ul>
  </div>
</template>

<style scoped>
.combobox {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.combobox__marca {
  color: var(--risk-high);
}

.combobox__campo {
  position: relative;
  display: flex;
}

/* El borde, el fondo y el padding del input vienen del global de
   tokens.css (input[type=text]): acá solo va lo que es propio de este
   control, que es dejar lugar a la flecha. */
.combobox__input {
  width: 100%;
  padding-right: var(--space-8);
}

.combobox__flecha {
  position: absolute;
  right: var(--space-4);
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.7rem;
  color: var(--ink-soft);
  pointer-events: none;
}

.combobox__lista {
  position: absolute;
  z-index: 40;
  top: calc(100% - 1px);
  left: 0;
  right: 0;
  max-height: 14rem;
  overflow-y: auto;
  margin: 0;
  padding: var(--space-1);
  list-style: none;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-xs);
  /* No hay --shadow-* en el sistema a propósito (DESIGN.md): el menú se
     separa del contenido de abajo con el mismo borde que usa un input. */
}

.combobox__opcion {
  padding: var(--space-2) var(--space-4);
  cursor: pointer;
  font-size: 0.85rem;
}

.combobox__opcion--activa {
  background: color-mix(in srgb, var(--signal) 16%, var(--surface));
}

.combobox__sin-coincidencias {
  padding: var(--space-2) var(--space-4);
  font-size: 0.85rem;
  color: var(--ink-soft);
  font-style: italic;
}
</style>
