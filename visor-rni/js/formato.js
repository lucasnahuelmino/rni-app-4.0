/* ==========================================================================
   formato.js — todo lo que se muestra se formatea acá, en es-AR.

   Criterio de decimales (igual que la app principal): hasta 3 decimales en
   V/m y hasta 4 en %, sin redondear de más. Los valores crudos se conservan
   para la exportación a Excel.
   ========================================================================== */

const conDecimales = (dec) =>
  new Intl.NumberFormat('es-AR', { maximumFractionDigits: dec })
const enteroFmt = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 0 })

const fm3 = conDecimales(3)
const fm4 = conDecimales(4)

/** V/m: hasta 3 decimales. */
export function vm(valor) {
  return valor === null || valor === undefined ? '—' : fm3.format(Number(valor))
}

/** % de RNI: hasta 4 decimales. */
export function pct(valor) {
  return valor === null || valor === undefined ? '—' : fm4.format(Number(valor))
}

/** Enteros con separador de miles (12.345). */
export function entero(valor) {
  return valor === null || valor === undefined ? '—' : enteroFmt.format(Number(valor))
}

/** '2026-05-12T09:00:13' → '12/05/2026' (sin pasar por Date: sin zona). */
export function fecha(iso) {
  if (!iso) return '—'
  const parte = String(iso).split('T')[0]
  const [a, m, d] = parte.split('-')
  if (!a || !m || !d) return String(iso)
  return `${d}/${m}/${a}`
}

/** '2026-05-12T09:00:13' → '09:00:13'. */
export function hora(iso) {
  if (!iso) return '—'
  const partes = String(iso).split('T')
  return partes[1] ? partes[1].slice(0, 8) : '—'
}

/** Segundos → '45 min' / '3 h 12 min' / '7 d 8 h' (tiempos trabajados). */
export function duracion(segundos) {
  if (!segundos) return '—'
  const s = Number(segundos)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return h === 0 ? `${d} d` : `${d} d ${h} h`
  if (h === 0) return `${m} min`
  if (m === 0) return `${h} h`
  return `${h} h ${m} min`
}

/** '2026-05' → 'mayo 2026' (claves de mes de las tablas de resumen). */
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

export function mesLegible(clave) {
  if (!clave) return '—'
  const [a, m] = String(clave).split('-')
  const indice = Number(m) - 1
  if (!a || Number.isNaN(indice) || !MESES[indice]) return String(clave)
  return `${MESES[indice]} ${a}`
}

/** '2026-09-23T19:41:31.157201+00:00' → '23/09/2026 19:41'. */
export function momento(iso) {
  if (!iso) return '—'
  const partes = String(iso).split('T')
  const horaTxt = partes[1] ? partes[1].slice(0, 5) : ''
  return horaTxt ? `${fecha(partes[0])} ${horaTxt}` : fecha(partes[0])
}

/** Normaliza para buscar sin distinguir mayúsculas ni acentos:
    'Córdoba' y 'cordoba' se consideran iguales. */
export function normalizar(texto) {
  return String(texto ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}
