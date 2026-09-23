<script setup>
import { ref } from 'vue'
import { useFiltrosStore } from '../stores/filtros'
import { CCTE_FIJOS } from '../constants'

const filtros = useFiltrosStore()
const abierto = ref(false)
const provinciaInput = ref('')
const anioInput = ref('')

function agregarProvincia() {
  const valor = provinciaInput.value.trim()
  if (valor) {
    filtros.toggleProvincia(valor)
    provinciaInput.value = ''
  }
}

function agregarAnio() {
  const valor = parseInt(anioInput.value, 10)
  if (valor) {
    filtros.toggleAnio(valor)
    anioInput.value = ''
  }
}
</script>

<template>
  <div class="filtros">
    <button class="btn btn--ghost" @click="abierto = !abierto" :aria-expanded="abierto" aria-controls="panel-filtros">
      Filtros
      <span v-if="filtros.hayFiltrosActivos" class="filtros__contador">{{
        filtros.ccte.length + filtros.provincia.length + filtros.anio.length
      }}</span>
    </button>

    <div class="filtros__activos" aria-live="polite">
      <span v-if="!filtros.hayFiltrosActivos" class="filtros__vacio">Sin filtros activos</span>
      <span v-for="texto in filtros.resumenFiltros" :key="texto" class="chip chip--active">{{ texto }}</span>
      <button v-if="filtros.hayFiltrosActivos" class="filtros__limpiar" @click="filtros.limpiar()">
        Limpiar filtros
      </button>
    </div>

    <div v-if="abierto" id="panel-filtros" class="filtros__panel panel">
      <div class="filtros__grupo">
        <h3>CCTE</h3>
        <div class="filtros__opciones">
          <button
            v-for="c in CCTE_FIJOS"
            :key="c"
            class="chip"
            :class="{ 'chip--active': filtros.ccte.includes(c) }"
            @click="filtros.toggleCcte(c)"
          >
            {{ c }}
          </button>
        </div>
      </div>

      <div class="filtros__grupo">
        <h3>Provincia</h3>
        <div class="filtros__opciones">
          <span v-for="p in filtros.provincia" :key="p" class="chip chip--active" @click="filtros.toggleProvincia(p)">
            {{ p }} ✕
          </span>
        </div>
        <div class="filtros__input-row">
          <input
            v-model="provinciaInput"
            type="text"
            placeholder="Agregar provincia…"
            aria-label="Agregar provincia al filtro"
            @keyup.enter="agregarProvincia"
          />
          <button class="btn btn--ghost" @click="agregarProvincia">Agregar</button>
        </div>
      </div>

      <div class="filtros__grupo">
        <h3>Año</h3>
        <div class="filtros__opciones">
          <span v-for="a in filtros.anio" :key="a" class="chip chip--active" @click="filtros.toggleAnio(a)">
            {{ a }} ✕
          </span>
        </div>
        <div class="filtros__input-row">
          <input
            v-model="anioInput"
            type="number"
            placeholder="Agregar año…"
            aria-label="Agregar año al filtro"
            @keyup.enter="agregarAnio"
          />
          <button class="btn btn--ghost" @click="agregarAnio">Agregar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filtros {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.filtros__contador {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.1rem;
  height: 1.1rem;
  background: var(--signal);
  color: var(--on-ink);
  /* era 0.65rem (~10px): ilegible. El mínimo del sistema es --fs-2xs. */
  font-size: var(--fs-2xs);
  margin-left: var(--space-4);
  padding: 0 var(--space-3);
}

.filtros__activos {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.filtros__vacio {
  font-size: 0.8rem;
  color: var(--ink-soft);
}

.filtros__limpiar {
  background: none;
  border: none;
  color: var(--signal-deep);
  text-decoration: underline;
  font-size: 0.8rem;
  padding: 0;
}

.filtros__panel {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.5rem;
  width: 340px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.filtros__grupo h3 {
  margin-bottom: 0.4rem;
}

.filtros__opciones {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.4rem;
}

.filtros__input-row {
  display: flex;
  gap: 0.4rem;
}

.filtros__input-row input {
  flex: 1;
  /* border/padding/color los pone el global de tokens.css -- acá solo va lo
     que es propio de esta fila. */
}
</style>
