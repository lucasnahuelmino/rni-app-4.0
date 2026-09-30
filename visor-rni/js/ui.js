/* ==========================================================================
   ui.js — utilidades mínimas de interfaz: selectores, toast, tooltip,
   construcción de celdas y el distintivo de nivel (color + etiqueta).
   ========================================================================== */

import { rangoPorPct } from './escala.js'
import { pct } from './formato.js'

export const $ = (selector, raiz = document) => raiz.querySelector(selector)
export const $$ = (selector, raiz = document) => Array.from(raiz.querySelectorAll(selector))

let temporizadorToast = null

/** Aviso flotante abajo al centro. `tipo`: 'info' | 'error'. */
export function toast(mensaje, tipo = 'info') {
  const el = $('#toast')
  if (!el) return
  el.textContent = mensaje
  el.classList.toggle('toast--error', tipo === 'error')
  el.hidden = false
  clearTimeout(temporizadorToast)
  temporizadorToast = setTimeout(() => { el.hidden = true }, 7000)
}

export function aviso(mensaje) { toast(mensaje, 'info') }
export function error(mensaje) { toast(mensaje, 'error') }

/** Tooltip compartido: lo usan los puntos del mapa (Leaflet y canvas). */
export function mostrarTooltip(evento, html) {
  const el = $('#tooltip')
  if (!el) return
  el.innerHTML = html
  el.hidden = false
  moverTooltip(evento)
}

export function moverTooltip(evento) {
  const el = $('#tooltip')
  if (!el || el.hidden) return
  const margen = 14
  const caja = el.getBoundingClientRect()
  let x = evento.clientX + margen
  let y = evento.clientY + margen
  if (x + caja.width > window.innerWidth - 8) x = evento.clientX - caja.width - margen
  if (y + caja.height > window.innerHeight - 8) y = evento.clientY - caja.height - margen
  el.style.left = Math.max(8, x) + 'px'
  el.style.top = Math.max(8, y) + 'px'
}

export function ocultarTooltip() {
  const el = $('#tooltip')
  if (el) el.hidden = true
}

/** Celda de tabla: acepta texto y arma el <td> con las clases de estilo. */
export function celda(valor, { num = false, clase = '' } = {}) {
  const td = document.createElement('td')
  td.textContent = valor === null || valor === undefined || valor === '' ? '—' : String(valor)
  if (num) td.classList.add('num')
  if (clase) td.classList.add(clase)
  return td
}

export function vaciar(elemento) {
  while (elemento.firstChild) elemento.removeChild(elemento.firstChild)
}

/**
 * Distintivo de nivel: color de fondo ETIQUETA de texto. Va en la tabla de
 * "Por horarios" para que el nivel se lea aunque no se distingan los colores.
 */
export function distintivoNivel(pct) {
  const rango = rangoPorPct(pct)
  const span = document.createElement('span')
  span.className = 'nivel'
  span.style.background = rango.color
  span.textContent = rango.etiqueta
  return span
}

/**
 * Distintivo con el VALOR (no el tramo), pintado con el color del semáforo:
 * es el sello que muestra la app original al lado del pico máximo registrado.
 */
export function distintivoValor(pctValor) {
  const span = document.createElement('span')
  span.className = 'nivel'
  span.style.background = rangoPorPct(pctValor).color
  span.textContent = pct(pctValor) + ' %'
  return span
}
