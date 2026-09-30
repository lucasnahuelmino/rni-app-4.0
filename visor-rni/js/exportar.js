/* ==========================================================================
   exportar.js — exportación a Excel (.xlsx) con SheetJS.

   Se exporta SIEMPRE lo que la vista está mostrando en ese momento (con la
   búsqueda y los filtros aplicados), con encabezados en español y nombre de
   archivo que lleva la fecha.

   Los números van crudos a la celda (sin formato de texto) y el formato se
   aplica por `z`, igual que en las exportaciones de la app principal: así en
   Excel se puede seguir ordenando y sumando.
   ========================================================================== */

import { error } from './ui.js'

/**
 * @param {object}   opciones
 * @param {string}   opciones.nombre      archivo de salida (sin extensión)
 * @param {string}   opciones.hoja        nombre de la hoja
 * @param {string[]} opciones.encabezados títulos de columna
 * @param {any[][]}  opciones.filas       filas (arrays); los números, crudos
 * @param {string[]} [opciones.formatos]  formato por columna ('0.###', …)
 * @param {number[]} [opciones.anchos]    ancho sugerido de columna
 */
export function exportarXLSX({ nombre, hoja, encabezados, filas, formatos = [], anchos = [] }) {
  if (typeof XLSX === 'undefined') {
    error('No se pudo cargar vendor/xlsx.full.min.js: la exportación a Excel no está disponible.')
    return false
  }

  const datos = [encabezados, ...filas]
  const hojaXLSX = XLSX.utils.aoa_to_sheet(datos)

  // ancho de columnas
  if (anchos.length) {
    hojaXLSX['!cols'] = anchos.map((w) => ({ wch: w }))
  }

  // formato numérico por columna (los valores quedan crudos)
  formatos.forEach((formato, indice) => {
    if (!formato) return
    for (let f = 1; f <= filas.length; f++) {
      const ref = XLSX.utils.encode_cell({ r: f, c: indice })
      const celda = hojaXLSX[ref]
      if (celda && typeof celda.v === 'number') celda.z = formato
    }
  })

  const libro = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(libro, hojaXLSX, hoja.slice(0, 31))

  const fecha = new Date().toISOString().slice(0, 10)
  const archivo = `${nombre}_${fecha}.xlsx`
  XLSX.writeFile(libro, archivo)
  return archivo
}
