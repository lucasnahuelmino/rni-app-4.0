import { defineStore } from 'pinia'

export const useFiltrosStore = defineStore('filtros', {
  state: () => ({
    ccte: [],
    provincia: [],
    anio: [],
  }),
  getters: {
    hayFiltrosActivos: (state) => state.ccte.length > 0 || state.provincia.length > 0 || state.anio.length > 0,
    resumenFiltros: (state) => {
      const partes = []
      if (state.ccte.length) partes.push(`CCTE: ${state.ccte.join(', ')}`)
      if (state.provincia.length) partes.push(`Provincia: ${state.provincia.join(', ')}`)
      if (state.anio.length) partes.push(`Año: ${state.anio.join(', ')}`)
      return partes
    },
  },
  actions: {
    limpiar() {
      this.ccte = []
      this.provincia = []
      this.anio = []
    },
    toggleCcte(valor) {
      this._toggle('ccte', valor)
    },
    toggleProvincia(valor) {
      this._toggle('provincia', valor)
    },
    toggleAnio(valor) {
      this._toggle('anio', valor)
    },
    _toggle(campo, valor) {
      const idx = this[campo].indexOf(valor)
      if (idx >= 0) this[campo].splice(idx, 1)
      else this[campo].push(valor)
    },
  },
})
