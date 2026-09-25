// Catálogo único de provincias argentinas para toda la app.
//
// Por qué existe un archivo aparte: hasta ahora la provincia se escribía a
// mano en tres lugares (la carga de Excel, la edición de Gestión y el filtro
// global) y un error de tipeo NO falla, entra igual a la base y después se
// cuenta mal. Con "Córdoba" ya alcanza con tipearlo sin acento para que
// aparezca una provincia nueva al lado de la real en Resumen, en los KPIs
// ("Provincias") y en el mapa.
//
// Se usa desde un combobox con búsqueda (components/Combobox.vue), que
// filtra sin distinguir mayúsculas ni acentos: "sant" encuentra
// "Santiago del Estero" y "rio negro" encuentra "Río Negro".
//
// El catálogo es el COMPLETO (23 provincias + CABA), aunque hoy solo 10
// tienen mediciones: Catamarca, Chubut, Córdoba, Jujuy, Mendoza, Misiones,
// Neuquén, Río Negro, Santa Cruz y Santiago del Estero. La carga tiene que
// poder recibir datos de una provincia que todavía no está en el sistema,
// y el filtro muestra vacío sin romper nada si se elige una sin datos.
//
// Los nombres son los cortos y oficiales de uso corriente, y tienen que
// coincidir con lo que ya está guardado: los valores de esta lista son los
// que se comparan contra `mediciones.provincia` tal cual están.
export const PROVINCIAS = [
  'Buenos Aires',
  'CABA',
  'Catamarca',
  'Chaco',
  'Chubut',
  'Córdoba',
  'Corrientes',
  'Entre Ríos',
  'Formosa',
  'Jujuy',
  'La Pampa',
  'La Rioja',
  'Mendoza',
  'Misiones',
  'Neuquén',
  'Río Negro',
  'Salta',
  'San Juan',
  'San Luis',
  'Santa Cruz',
  'Santa Fe',
  'Santiago del Estero',
  'Tierra del Fuego',
  'Tucumán',
]
