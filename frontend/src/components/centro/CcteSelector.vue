<script setup>
import { computed } from 'vue'

import { CCTE_FIJOS } from '../../ccte'
import { useFiltrosStore } from '../../stores/filtros'

/**
 * Selector de CCTE con botones (nunca desplegable): "General" con todo, y
 * después cada uno de los centros. Al cambiarlo se actualiza TODO lo de la
 * sección: lista, resumen, tendencia, top y tiempos.
 *
 * Escribe en el MISMO estado que los chips del panel "Filtros" global
 * (`filtros.ccte`), así que no hay dos controles de CCTE que se contradicen:
 * si apretás "Córdoba" acá, el chip "CCTE: Córdoba" aparece en la barra, y
 * si lo quitás desde la barra, este botón vuelve a "General".
 *
 * Es selección única y los chips son multi-selección, así que hay un caso
 * intermedio: con dos chips puestos no hay botón que pueda estar activo
 * (ninguno es "el único elegido"). En vez de resaltar uno y mentir, no se
 * resalta ninguno y se avisa arriba cuáles están puestos. La opción para
 * volver es apretar cualquiera, que colapsa la selección a uno solo.
 *
 * Por ser selección exclusiva usa `<fieldset>` + radios nativos y no botones
 * con aria-pressed, según la regla de DESIGN.md "Accesibilidad": el radio
 * trae solo el rol, la exclusividad y el teclado (flechas) sin escribir una
 * línea de JS. Solo se le cambia la apariencia para que se vea como botones,
 * que es lo que se pidió.
 */
const filtros = useFiltrosStore()

/** Sin ningún CCTE elegido = vista General (todo el sistema). */
const ninguno = computed(() => filtros.ccte.length === 0)
/** Uno solo elegido = ese botón es el que está activo. */
const unico = computed(() => (filtros.ccte.length === 1 ? filtros.ccte[0] : null))
/** Varios a la vez: solo posible desde los chips del panel "Filtros". */
const varios = computed(() => filtros.ccte.length > 1)

function activo(ccte) {
  return unico.value === ccte
}
</script>

<template>
  <div class="selector">
    <fieldset class="selector__set">
      <legend class="sr-only">Centro de trabajo a mostrar</legend>

      <label class="selector__btn" :class="{ 'selector__btn--activo': ninguno }">
        <input
          class="selector__input"
          type="radio"
          name="centro-operativo-ccte"
          :checked="ninguno"
          @change="filtros.ccte = []"
        />
        <span>General</span>
      </label>

      <label
        v-for="c in CCTE_FIJOS"
        :key="c"
        class="selector__btn"
        :class="{ 'selector__btn--activo': activo(c) }"
      >
        <input
          class="selector__input"
          type="radio"
          name="centro-operativo-ccte"
          :checked="activo(c)"
          @change="filtros.ccte = [c]"
        />
        <span>{{ c }}</span>
      </label>
    </fieldset>

    <!-- Si hay más de un chip, ningún botón queda activo. Se dice en vez de
         esconderlo: no poder explicar por qué no se marca ninguno es peor
         que una línea de texto. role=status lo anuncia sin robar el foco. -->
    <p v-if="varios" class="selector__aviso" role="status">
      Hay {{ filtros.ccte.length }} CCTE activos en el panel de filtros
      ({{ filtros.ccte.join(', ') }}). Apretá uno para verlo solo, o General
      para verlos todos.
    </p>
  </div>
</template>

<style scoped>
.selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.selector__set {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin: 0;
  padding: 0;
  border: none;
}

/* Se ve como botón, pero el control es el radio de adentro: todo el
   comportamiento (exclusividad, flechas del teclado, foco) es nativo. */
.selector__btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  font-size: 0.8125rem;
  line-height: 1.2;
  color: var(--ink-soft);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 4px;
  cursor: pointer;
}

.selector__btn:hover {
  border-color: var(--signal);
}

.selector__btn--activo {
  color: var(--ink);
  font-weight: 600;
  background: var(--signal-bg, transparent);
  border-color: var(--signal);
}

/* El radio se oculta visualmente pero sigue siendo el control real: no se
   pone display:none porque entonces sale del árbol de accesibilidad y el
   grupo deja de ser un grupo de radios. */
.selector__input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.selector__btn:focus-within {
  outline: 2px solid var(--signal);
  outline-offset: 1px;
}

.selector__aviso {
  margin: 0;
  font-size: 0.75rem;
  color: var(--ink-soft);
}
</style>
