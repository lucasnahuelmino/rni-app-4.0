/* ==========================================================================
   ccte.js — los 7 Centros de Comprobación Técnica de Emisiones.

   Espejo de `CCTE_FIJOS` y `CCTE_SIEMPRE_VISIBLES` de
   `backend/app/core/config.py`: la base sólo tiene datos de 5 (Comodoro
   Rivadavia, Neuquén, Córdoba, Salta y Posadas), pero Buenos Aires y CABA se
   muestran SIEMPRE, aunque tengan 0 mediciones — requisito de negocio
   confirmado en la Auditoría Fase 1.

   El orden lo copia `kpis_service.obtener_ccte_summary`: los que tienen
   datos, de mayor a menor cantidad de mediciones, y al final los dos que
   siempre aparecen.
   ========================================================================== */

export const CCTE_FIJOS = [
  'Córdoba',
  'Comodoro Rivadavia',
  'Neuquén',
  'Posadas',
  'Salta',
  'Buenos Aires',
  'CABA',
]

const SIEMPRE_VISIBLES = new Set(['Buenos Aires', 'CABA'])

function ccteVacio(ccte) {
  return {
    ccte,
    mediciones: 0,
    localidades: 0,
    provincias: 0,
    resultado_max_vm: null,
    resultado_max_pct: null,
    localidad_max: null,
    tiempo_trabajado_seg: null,
    dias_con_medicion: null,
    actualizado_en: null,
    sin_datos: true,
  }
}

/**
 * Recibe las filas que trajo la base (`resumen_ccte` o el agregado en vivo)
 * y devuelve SIEMPRE los 7 CCTE, completando con una fila vacía los que no
 * tienen mediciones.
 *
 * @param {object[]} filas filas con la clave `ccte`
 * @returns {object[]} 7 filas ordenadas
 */
export function completarCcte(filas = []) {
  const porNombre = new Map(filas.map((f) => [f.ccte, f]))
  const completas = CCTE_FIJOS.map((nombre) => porNombre.get(nombre) || ccteVacio(nombre))

  const siempre = completas.filter((f) => SIEMPRE_VISIBLES.has(f.ccte))
  const resto = completas.filter((f) => !SIEMPRE_VISIBLES.has(f.ccte))
  resto.sort((a, b) => (b.mediciones || 0) - (a.mediciones || 0))

  return resto.concat(siempre)
}
