<script setup>
import ErrorState from './ErrorState.vue'
import LoadingState from './LoadingState.vue'
import EmptyState from './EmptyState.vue'

/**
 * La tripletas Error → Loading → Vacío → contenido estaba escrita a mano 14
 * veces en 6 vistas, y en 5 de ellas faltaba alguno de los estados (un fallo
 * de red se caía a EmptyState, que además ahora tiene estilo propio y ya no
 * se confunde). Acá vive una sola vez.
 *
 * El orden importa y es el mismo que tenían los `v-if`/`v-else-if` originales:
 * el error tiene prioridad sobre el loading, porque `useFetchOnFiltros` setea
 * `error` dentro del `try` y `loading = false` en el `finally`.
 *
 * Los slots no se evalúan mientras no se rendericen, así que el contenido
 * puede referirse a `data` sabiendo que llega después de pasar los tres
 * estados (mismo motivo por el que los `v-else` originales eran seguros).
 */
defineProps({
  loading: { type: Boolean, default: false },
  // El composable guarda la excepción tal cual, así que el tipo es abierto:
  // cualquier truthy cuenta como error.
  error: { default: null },
  // `false` (default) = la sección no tiene estado vacío propio, igual que
  // los bloques que antes eran solo Error → Loading → contenido.
  empty: { type: Boolean, default: false },
  // undefined deja el default de LoadingState/EmptyState, así que las secciones
  // que no customizaban el mensaje siguen diciendo exactamente lo mismo.
  mensajeCargando: { type: String, default: undefined },
  mensajeVacio: { type: String, default: undefined },
})

defineEmits(['reintentar'])
</script>

<template>
  <ErrorState v-if="error" @reintentar="$emit('reintentar')" />
  <LoadingState v-else-if="loading" :mensaje="mensajeCargando" />
  <EmptyState v-else-if="empty" :mensaje="mensajeVacio" />
  <slot v-else />
</template>
