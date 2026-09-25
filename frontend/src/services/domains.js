import api from './api'

// IMPORTANTE: se arma un URLSearchParams y se pasa TAL CUAL a axios (que lo
// soporta nativamente) en vez de convertirlo con Object.fromEntries(). Un
// objeto plano no puede tener dos entradas con la misma key, así que
// Object.fromEntries() sobre params repetidos (ccte=A&ccte=B) se quedaba
// solo con el último valor -- un filtro multi-select silenciosamente
// perdía todos los valores salvo el último. Bug encontrado al revisar este
// archivo para el pedido de filtros del mapa/tiempos (punto 11 y 2).
function filtrosParams(filtros, extra = {}) {
  const params = new URLSearchParams()
  ;(filtros?.ccte || []).forEach((v) => params.append('ccte', v))
  ;(filtros?.provincia || []).forEach((v) => params.append('provincia', v))
  ;(filtros?.anio || []).forEach((v) => params.append('anio', v))
  ;(filtros?.localidad || []).forEach((v) => params.append('localidad', v))
  Object.entries(extra).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.append(k, v)
  })
  return params
}

export const kpisApi = {
  getKpis: (filtros) => api.get('/kpis', { params: filtrosParams(filtros) }),
  getCcteSummary: (orden = 'mediciones') => api.get('/ccte-summary', { params: { orden } }),
}

export const localitiesApi = {
  getLocalities: (filtros) => api.get('/localities', { params: filtrosParams(filtros) }),
  getLocalityDetail: (localidad, ccte, provincia) =>
    api.get(`/localities/${encodeURIComponent(localidad)}`, { params: { ccte, provincia } }),
  // `metric` y `limit` van como extra para no perder los filtros: el top
  // del Centro operativo tiene que ser el del CCTE elegido, no el del país.
  getTopLocalities: (metric = 'resultado_max_vm', limit = 5, filtros) =>
    api.get('/top-localities', { params: filtrosParams(filtros, { metric, limit }) }),
  editLocality: (localidad, ccte, provincia, cambios) =>
    api.put(`/localities/${encodeURIComponent(localidad)}`, cambios, { params: { ccte, provincia } }),
  deleteLocality: (localidad, ccte, provincia) =>
    api.delete(`/localities/${encodeURIComponent(localidad)}`, { params: { ccte, provincia } }),
}

export const chartsApi = {
  // El histograma (distribución de resultados) quedó sin consumidor cuando
  // Gráficos se fusionó en el Centro operativo: esa sección se sacó a
  // pedido. El endpoint `/histogram` sigue en el backend por si vuelve --
  // solo se fue el método de acá, que era tres líneas que nadie llamaba.
  // Sin filtros devuelve la serie global; con filtros, la del CCTE o la
  // provincia elegida (es lo que hace que la tendencia se actualice al
  // apretar un botón de CCTE en el Centro operativo).
  getMonthlyTrend: (filtros) => api.get('/monthly-trend', { params: filtrosParams(filtros) }),
}

export const mapApi = {
  getMap: (filtros, { bbox, pctMin, modo = 'todos' } = {}) =>
    api.get('/map', { params: filtrosParams(filtros, { bbox, pct_min: pctMin, modo }) }),
}

export const tiemposApi = {
  getDiario: (ccte, provincia, localidad) => api.get('/tiempos/diario', { params: { ccte, provincia, localidad } }),
  // Desglose día por día de un centro entero, de varios, o de todo si no
  // se pasa ninguno (vista General). `filtrosParams` repite la key
  // (?ccte=A&ccte=B) porque el filtro es multi-select.
  getDiarioCcte: (ccte = []) => api.get('/tiempos/diario-ccte', { params: filtrosParams({ ccte }) }),
  getMensual: ({ ccte, provincia, localidad, filtros } = {}) =>
    api.get('/tiempos/mensual', { params: filtrosParams(filtros, { ccte, provincia, localidad }) }),
}

export const colorsApi = {
  getColorScale: () => api.get('/color-scale'),
}

export const diagnosticsApi = {
  getDiagnostics: () => api.get('/diagnostics'),
}

export const importsApi = {
  postImport: (formData) =>
    api.post('/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  getBatch: (batchId) => api.get(`/import/${batchId}`),
}

export const reportsApi = {
  wordUrl: (ccte, provincia, localidad, ambito) =>
    `${api.defaults.baseURL}/reports/word?${new URLSearchParams({ ccte, provincia, localidad, ambito }).toString()}`,
  pdfUrl: (ccte, provincia, localidad, ambito) =>
    `${api.defaults.baseURL}/reports/pdf?${new URLSearchParams({ ccte, provincia, localidad, ambito }).toString()}`,
}
