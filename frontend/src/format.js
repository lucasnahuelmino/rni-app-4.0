// Formateo de los dos valores que se muestran en casi toda la app.
//
// La regla es NO redondear lo que la base guarda, porque hasta ahora se
// estaba tirando información real en pantalla:
//
//   resultado_vm   el instrumento mide en pasos de 0,001 y el 83,32 % de los
//                  valores (183.160 de 219.818) tiene 3 decimales. Con
//                  .toFixed(2) salía "0.942 -> 0.94" y, peor,
//                  "0.001 -> 0.00": un cero en pantalla para un valor que
//                  no es cero (y "0.005 -> 0.01", redondeando hacia arriba).
//
//   resultado_pct  es un valor CALCULADO (vm^2 / 3770 / limite * 100) y la
//                  base guarda el float completo, 17 dígitos. Ahí sí hace
//                  falta acotar, pero hasta 4 decimales: con .toFixed(1)
//                  salía "0,04022315030756169 -> 0,0 %", que además se
//                  confunde con el contador de "resultados en cero" del
//                  Diagnóstico (215.212 de 219.818 filas cambiaban).
//
// El backend NO redondea: estas funciones son la única capa que acota, y
// lo hacen sobre los decimales que la base realmente tiene.
//
// Las dos devuelven NÚMEROS, no strings. En el template Vue se imprimen con
// la representación más corta que los reproduce exacto, así que no quedan
// ceros de relleno: 19.260 -> "19.26", 0.000 -> "0".

/**
 * V/m tal cual está en la base: sin redondear y sin ceros de relleno.
 *
 * 3 decimales es la precisión del instrumento y es el máximo que existe en
 * la base, así que `toFixed(3)` no puede perder ningún dígito real: solo
 * limpia ruido de punto flotante en el caso (hoy inexistente) de que un V/m
 * salga de un cálculo en vez de venir leído del Excel.
 */
export function fmtVm(valor) {
  if (valor == null) return null
  return parseFloat(valor.toFixed(3))
}

/**
 * % del límite con hasta 4 decimales y sin ceros sobrantes.
 *
 *   49.14569145368187 -> 49.1457
 *    0.04022315030756169 -> 0.0402
 *    0                  -> 0
 *
 * Los enteros (conteos de mediciones, de localidades, etc.) no pasan por
 * acá: vienen de COUNT(*) como enteros y se muestran tal cual.
 */
export function fmtPct(valor) {
  if (valor == null) return null
  return parseFloat(valor.toFixed(4))
}
