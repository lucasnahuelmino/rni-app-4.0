import { ref, watch } from 'vue'
import { useFiltrosStore } from '../stores/filtros'

/**
 * Ejecuta `fetchFn(filtros)` cada vez que cambian los filtros globales.
 * `fetchFn` debe devolver una promesa que resuelve al array/objeto de datos
 * (ya extraído de `response.data`).
 */
export function useFetchOnFiltros(fetchFn, { immediate = true, watchFiltros = true } = {}) {
  const filtros = useFiltrosStore()
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function cargar() {
    loading.value = true
    error.value = null
    try {
      data.value = await fetchFn(filtros)
    } catch (e) {
      error.value = e
    } finally {
      loading.value = false
    }
  }

  if (watchFiltros) {
    watch(
      () => [filtros.ccte.slice(), filtros.provincia.slice(), filtros.anio.slice()],
      cargar,
      { deep: true },
    )
  }

  if (immediate) cargar()

  return { data, loading, error, reload: cargar }
}
