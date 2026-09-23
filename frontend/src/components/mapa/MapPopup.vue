<script setup>
import { computed, onMounted } from 'vue'
import { useColorScaleStore } from '../../stores/colorScale'

/**
 * Popup del mapa como componente Vue.
 *
 * Antes el popup era una cadena de HTML armada a mano dentro de MapaView,
 * con `escaparHtml()` aplicado a mano en cada interpolación. Vue escapa solo
 * al interpolar (`{{ }}`), así que acá no hay superficie de XSS que defender
 * y el markup, los tokens y los tipos se escriben como en cualquier otro
 * componente de la app.
 *
 * Recibe `punto` y `escala` por props en vez de llamar a
 * `useColorScaleStore()` adentro: el popup se monta en su propia app de
 * Vue (una sola, reutilizada para los N marcadores), que no tiene el Pinia
 * raíz. Pasar la instancia del store es lo que mantiene el popup en la MISMA
 * escala que la leyenda y los marcadores.
 */
const props = defineProps({
  punto: { type: Object, required: true },
  escala: { type: Object, required: true },
})

onMounted(() => props.escala.asegurarCargado?.())

// El color y el rango salen del mismo store que usan la leyenda y los
// marcadores: no hay una segunda fuente de verdad que pueda divergir.
const color = computed(() => props.escala.colorPorPct(props.punto.resultado_pct))
const rango = computed(() => props.escala.etiquetaPorPct(props.punto.resultado_pct))

const vm = computed(() =>
  props.punto.resultado_vm != null ? props.punto.resultado_vm.toFixed(2) : null,
)
const pct = computed(() =>
  props.punto.resultado_pct != null ? `${props.punto.resultado_pct.toFixed(1)}%` : null,
)

// Hay DOS "San Pedro" (Catamarca y Santiago del Estero): sin provincia los
// dos popups eran idénticos. Va en una línea aparte y en tono suave.
const lugar = computed(() => props.punto.localidad)
const jurisdiccion = computed(() =>
  [props.punto.provincia, props.punto.ccte && `CCTE ${props.punto.ccte}`]
    .filter(Boolean)
    .join(' · '),
)
</script>

<template>
  <div class="popup">
    <p class="popup__lugar">
      <strong class="popup__nombre">{{ lugar }}</strong>
      <span v-if="jurisdiccion" class="popup__jur">{{ jurisdiccion }}</span>
    </p>

    <div class="popup__dato">
      <span class="popup__dot" :style="{ background: color }" aria-hidden="true"></span>
      <span class="popup__vm num">{{ vm ?? '—' }}<small class="popup__unidad"> V/m</small></span>
      <span v-if="pct" class="popup__pct num">{{ pct }}</span>
    </div>

    <p class="popup__rango">{{ rango }} del límite normativo</p>
  </div>
</template>

<style scoped>
.popup {
  min-width: 190px;
  font-size: var(--fs-md);
  line-height: 1.4;
}

.popup__lugar {
  margin: 0 0 var(--space-4);
}

.popup__nombre {
  display: block;
  font-family: var(--font-display);
  font-size: var(--fs-lg);
  color: var(--ink);
}

.popup__jur {
  display: block;
  font-size: var(--fs-2xs);
  color: var(--ink-soft);
}

.popup__dato {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}

.popup__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  /* Borde marino sobre cualquier color del semáforo: los tramos claros
     (#84C2F5, #A9E7A9, #D9FF00) sobre fondo blanco casi no se recortan solos. */
  border: 1px solid color-mix(in srgb, var(--ink) 55%, transparent);
  flex-shrink: 0;
}

.popup__vm {
  font-weight: 600;
}

.popup__unidad {
  font-weight: 400;
  color: var(--ink-soft);
}

.popup__pct {
  margin-left: auto;
  color: var(--ink-soft);
}

.popup__rango {
  margin: var(--space-3) 0 0;
  font-size: var(--fs-2xs);
  color: var(--ink-soft);
}
</style>
