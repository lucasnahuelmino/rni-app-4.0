// Catálogo único de CCTE para toda la app.
//
// Antes vivía en constants.js, que solo contenía esto: se separa porque el
// equipo pidió que haya un archivo para provincias y otro para CCTE, de modo
// que todo lo que muestre o pida un CCTE lea de acá y no de una lista
// copiada en cada vista.
//
// Debe coincidir con app/core/config.py::CCTE_FIJOS del backend, que es el
// que manda. Los siete siempre existen aunque no midan: Buenos Aires y CABA
// están en CCTE_SIEMPRE_VISIBLES y aparecen con 0 mediciones.
export const CCTE_FIJOS = [
  'Córdoba',
  'Comodoro Rivadavia',
  'Neuquén',
  'Posadas',
  'Salta',
  'Buenos Aires',
  'CABA',
]
