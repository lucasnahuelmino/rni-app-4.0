import { defineStore } from 'pinia'
import { colorsApi } from '../services/domains'

// Única fuente de verdad de los 10 rangos de color: se pide una sola vez al
// backend (GET /api/color-scale) y la comparten SemaforoBadge.vue y
// MapaView.vue, para que la leyenda y los colores de los puntos nunca
// queden desincronizados (Auditoría Fase 1, hallazgo A11).
export const useColorScaleStore = defineStore('colorScale', {
  state: () => ({
    rangos: [],
    cargando: false,
    cargado: false,
  }),
  actions: {
    async asegurarCargado() {
      if (this.cargado || this.cargando) return
      this.cargando = true
      try {
        const { data } = await colorsApi.getColorScale()
        this.rangos = data
        this.cargado = true
      } finally {
        this.cargando = false
      }
    },
    colorPorPct(pct) {
      if (pct == null) return '#9aa5ab'
      const rango = this.rangos.find((r) => pct >= r.desde && (r.hasta == null || pct < r.hasta))
      return rango ? rango.color : (this.rangos.at(-1)?.color ?? '#9aa5ab')
    },
    etiquetaPorPct(pct) {
      if (pct == null) return 'Sin dato'
      const rango = this.rangos.find((r) => pct >= r.desde && (r.hasta == null || pct < r.hasta))
      return rango ? rango.etiqueta : '—'
    },
  },
})
