import api from './api'

function filtrosParams(filtros) {
  const params = new URLSearchParams()
  ;(filtros.ccte || []).forEach((v) => params.append('ccte', v))
  ;(filtros.provincia || []).forEach((v) => params.append('provincia', v))
  ;(filtros.anio || []).forEach((v) => params.append('anio', v))
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
  getTopLocalities: (metric = 'resultado_max_vm', limit = 5) =>
    api.get('/top-localities', { params: { metric, limit } }),
  editLocality: (localidad, ccte, provincia, cambios) =>
    api.put(`/localities/${encodeURIComponent(localidad)}`, cambios, { params: { ccte, provincia } }),
  deleteLocality: (localidad, ccte, provincia) =>
    api.delete(`/localities/${encodeURIComponent(localidad)}`, { params: { ccte, provincia } }),
}

export const chartsApi = {
  getHistogram: (campo = 'resultado_pct', bins = 20, filtros = {}) =>
    api.get('/histogram', { params: { campo, bins, ...Object.fromEntries(filtrosParams(filtros)) } }),
  getMonthlyTrend: () => api.get('/monthly-trend'),
}

export const mapApi = {
  getMap: (filtros, { bbox, pctMin } = {}) =>
    api.get('/map', { params: { bbox, pct_min: pctMin, ...Object.fromEntries(filtrosParams(filtros)) } }),
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
