// Debe coincidir con app/core/config.py::CCTE_FIJOS del backend -- única
// fuente "visual" de los 7 CCTE fijos en el frontend.
export const CCTE_FIJOS = [
  'Córdoba',
  'Comodoro Rivadavia',
  'Neuquén',
  'Posadas',
  'Salta',
  'Buenos Aires',
  'CABA',
]
// Escala histórica RNI (Streamlit)
// Fuente única de colores para:
// - mapa
// - gestión
// - semáforos
// - leyenda
// - tooltips

export const RNI_COLOR_SCALE = [
  { min: 0, max: 1, color: '#84C2F5', label: '0-1 %' },
  { min: 1, max: 2, color: '#489DFF', label: '1-2 %' },
  { min: 2, max: 4, color: '#006BD6', label: '2-4 %' },
  { min: 4, max: 8, color: '#A9E7A9', label: '4-8 %' },
  { min: 8, max: 15, color: '#89DD89', label: '8-15 %' },
  { min: 15, max: 20, color: '#4D9623', label: '15-20 %' },
  { min: 20, max: 35, color: '#D9FF00', label: '20-35 %' },
  { min: 35, max: 50, color: '#F39A6D', label: '35-50 %' },
  { min: 50, max: 100, color: '#E68200', label: '50-100 %' },
  {
    min: 100,
    max: Number.POSITIVE_INFINITY,
    color: '#CC0000',
    label: '≥100 %'
  },
]

export function getColorPorPct(pct) {
  const valor = Number(pct ?? 0)

  const rango =
    RNI_COLOR_SCALE.find(
      r => valor >= r.min && valor < r.max
    ) || RNI_COLOR_SCALE[RNI_COLOR_SCALE.length - 1]

  return rango.color
}

export function getRangoPorPct(pct) {
  const valor = Number(pct ?? 0)

  return (
    RNI_COLOR_SCALE.find(
      r => valor >= r.min && valor < r.max
    ) || RNI_COLOR_SCALE[RNI_COLOR_SCALE.length - 1]
  )
}