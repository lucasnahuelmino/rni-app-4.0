/**
 * Lee los design tokens de `assets/tokens.css` desde JS.
 *
 * Chart.js y Leaflet necesitan el color como string: no pueden resolver
 * `var(--signal)`. Antes cada gráfico tenía el hex escrito a mano, así que
 * cambiar `--signal` en tokens.css dejaba los gráficos desincronizados del
 * resto de la app.
 *
 * Los valores se cachean: los tokens son constantes de diseño y no cambian
 * en runtime (no hay theming). La cache importa sobre todo en el mapa, donde
 * `colorPorPct` se llama una vez por marcador.
 */
const cache = new Map()

export function token(nombre, fallback = '') {
  if (cache.has(nombre)) return cache.get(nombre)
  const valor =
    getComputedStyle(document.documentElement).getPropertyValue(nombre).trim() || fallback
  cache.set(nombre, valor)
  return valor
}

/** `token()` con alfa -- para el relleno de Chart.js, que espera `rgba(...)`. */
export function tokenConAlfa(nombre, alfa, fallback = '') {
  const color = token(nombre, fallback)
  const hex = color.match(/^#([0-9a-f]{6})$/i)
  if (!hex) return color
  const n = parseInt(hex[1], 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`
}
