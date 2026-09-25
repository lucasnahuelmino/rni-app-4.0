// Normalización de texto para las DOS cosas de la app que se buscan
// escribiendo a mano: el Combobox de catálogos y el buscador de Gestión.
//
// La regla es la misma en los dos y está acá una sola vez: la búsqueda no
// distingue mayúsculas ni acentos. Sin eso, "cordoba" no encuentra
// "Córdoba" y "rio negro" no encuentra "Río Negro", que es justamente la
// clase de error ortográfico que los dos controles existen para evitar.
//
// Cómo funciona: NFD descompone "á" en "a" + el acento como carácter
// aparte, y `\p{M}` con el flag `u` recorta cualquier carácter combinante,
// que en español es justo el acento. Se usa `\p{M}` y no el rango
// U+0300-U+036F escrito a mano porque esos caracteres combinantes van
// invisibles en el fuente y dependen de con qué codificación se edite el
// archivo.
export function normalizar(s) {
  return (s ?? '')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .trim()
}
