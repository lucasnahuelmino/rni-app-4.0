/* ==========================================================================
   escala.js — semáforo de colores.

   Copiado tal cual de backend/app/core/config.py (RANGOS_COLOR): es la única
   fuente de verdad de la app principal, así el visor pinta cada punto con el
   MISMO color y la MISMA etiqueta que el mapa de producción.

   Cada tramo trae además su etiqueta de texto ("0–1 %", "≥100 %"): el nivel
   nunca se comunica sólo con color.
   ========================================================================== */

export const RANGOS = [
  { desde: 0, hasta: 1, color: '#84C2F5', etiqueta: '0–1 %' },
  { desde: 1, hasta: 2, color: '#489DFF', etiqueta: '1–2 %' },
  { desde: 2, hasta: 4, color: '#006BD6', etiqueta: '2–4 %' },
  { desde: 4, hasta: 8, color: '#A9E7A9', etiqueta: '4–8 %' },
  { desde: 8, hasta: 15, color: '#89DD89', etiqueta: '8–15 %' },
  { desde: 15, hasta: 20, color: '#4D9623', etiqueta: '15–20 %' },
  { desde: 20, hasta: 35, color: '#D9FF00', etiqueta: '20–35 %' },
  { desde: 35, hasta: 50, color: '#F39A6D', etiqueta: '35–50 %' },
  { desde: 50, hasta: 100, color: '#E68200', etiqueta: '50–100 %' },
  { desde: 100, hasta: null, color: '#CC0000', etiqueta: '≥100 %' },
]

/** Rango que le corresponde a un % de RNI. `null`/`undefined` → sin dato. */
export function rangoPorPct(pct) {
  if (pct === null || pct === undefined || Number.isNaN(Number(pct))) {
    return { desde: null, hasta: null, color: '#9aa5ab', etiqueta: 'Sin dato' }
  }
  const valor = Number(pct)
  for (const rango of RANGOS) {
    if (valor >= rango.desde && (rango.hasta === null || valor < rango.hasta)) {
      return rango
    }
  }
  return RANGOS[RANGOS.length - 1]
}

export function colorPorPct(pct) {
  return rangoPorPct(pct).color
}

export function etiquetaPorPct(pct) {
  return rangoPorPct(pct).etiqueta
}
