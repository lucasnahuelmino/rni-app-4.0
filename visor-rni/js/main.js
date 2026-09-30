/* ==========================================================================
   main.js — punto de entrada.

   1. prepara el motor SQLite (vendor/),
   2. arma la carga del archivo (selector + arrastrar y soltar),
   3. monta las cinco vistas y maneja la navegación.

   Nunca escribe: sólo llama a base.js, que abre la conexión en modo lectura.
   ========================================================================== */

import { prepararMotor, abrirArchivo, base } from './base.js'
import { $, $$, aviso, error } from './ui.js'
import { entero } from './formato.js'
import * as inicio from './vistas/inicio.js'
import * as localidades from './vistas/localidades.js'
import * as horarios from './vistas/horarios.js'
import * as resumenes from './vistas/resumenes.js'
import * as mapa from './vistas/mapa.js'

/* Los módulos ES ya cargaron: si el aviso de file:// todavía está pendiente,
   ya no hace falta mostrarlo. */
window.__visorListo = true

const SECCIONES = {
  inicio: '#vista-inicio',
  localidades: '#vista-localidades',
  horarios: '#vista-horarios',
  resumenes: '#vista-resumenes',
  mapa: '#vista-mapa',
}

/* ------------------------------ navegación ------------------------------ */

function mostrarVista(nombre) {
  if (!SECCIONES[nombre]) return

  $$('.navitem').forEach((b) =>
    b.classList.toggle('navitem--activo', b.dataset.vista === nombre))

  for (const [clave, selector] of Object.entries(SECCIONES)) {
    $(selector).hidden = clave !== nombre
  }

  // el mapa necesita re-medirse cada vez que vuelve a hacerse visible
  if (nombre === 'mapa') mapa.refrescar()
}

function montarNavegacion() {
  $$('.navitem').forEach((boton) => {
    boton.addEventListener('click', () => mostrarVista(boton.dataset.vista))
  })
}

/* ------------------------------ logos ---------------------------------- */

/** Si falta un logo, se oculta él (y su separador) sin romper la cabecera. */
function montarLogos() {
  const revelar = (selector, ocultar) => {
    $$(selector).forEach((img) => {
      const fallo = () => $$(ocultar).forEach((el) => { el.hidden = true })
      img.addEventListener('error', fallo)
      // el error puede haber ocurrido antes de que este script corriera
      if (img.tagName === 'IMG' && img.complete && img.naturalWidth === 0) fallo()
    })
  }
  revelar('img[data-logo-dos]', '[data-logo-dos]')
  revelar('img[data-logo]:not([data-logo-dos])', '[data-logo]')
}

/* ---------------------------- carga de archivo -------------------------- */

function mensajeDeCarga(mensaje) {
  const caja = $('#error-carga')
  caja.textContent = mensaje
  caja.hidden = !mensaje
}

async function cargarBase(archivo) {
  const progreso = $('#progreso-carga')
  mensajeDeCarga('')
  progreso.hidden = false
  progreso.textContent = `Leyendo ${archivo.name} (${(archivo.size / 1048576).toFixed(1)} MB)…`

  // deja el input listo para volver a elegir el mismo archivo
  $('#input-archivo').value = ''

  try {
    await abrirArchivo(archivo)
  } catch (e) {
    progreso.hidden = true
    mensajeDeCarga(e.message)
    error(e.message)
    return
  }

  progreso.hidden = true
  pintarEstadoDeLaBase()
  $('#pantalla-carga').hidden = true
  $$('.navitem').forEach((b) => { b.disabled = false })

  inicio.montar()
  localidades.montar()
  horarios.montar()
  resumenes.montar()
  mapa.montar()

  inicio.cargar()
  localidades.cargar()
  horarios.cargar()
  resumenes.cargar()
  mapa.cargar()

  mostrarVista('inicio')
  aviso(`Base ${base.nombre} cargada: ${entero(base.mediciones)} mediciones.`)
}

function pintarEstadoDeLaBase() {
  $('#sidebar-archivo').textContent = base.nombre
  $('#sidebar-mediciones').textContent = entero(base.mediciones)
  $('#sidebar-localidades').textContent = entero(base.localidades)
  $('#sidebar-tablas').textContent = entero(base.tablas.length)

  const pastilla = $('#pastilla-base')
  pastilla.textContent = `${base.nombre} · ${entero(base.mediciones)} mediciones`
  pastilla.classList.add('pastilla--ok')
}

function montarEntradaDeArchivo() {
  const input = $('#input-archivo')
  input.addEventListener('change', () => {
    const archivo = input.files && input.files[0]
    if (archivo) cargarBase(archivo)
  })

  $('#btn-cambiar').addEventListener('click', () => input.click())

  // arrastrar y soltar sobre la pantalla de carga
  const zona = $('#zona-arrastre')
  const encender = (e) => { e.preventDefault(); zona.classList.add('carga__zona--sobre') }
  const apagar = (e) => { e.preventDefault(); zona.classList.remove('carga__zona--sobre') }
  ;['dragenter', 'dragover'].forEach((ev) => zona.addEventListener(ev, encender))
  ;['dragleave', 'drop'].forEach((ev) => zona.addEventListener(ev, apagar))
  zona.addEventListener('drop', (e) => {
    const archivo = e.dataTransfer && e.dataTransfer.files[0]
    if (archivo) cargarBase(archivo)
  })

  // que el navegador no intente abrir el archivo si se suelta en otro lado
  ;['dragover', 'drop'].forEach((ev) =>
    document.addEventListener(ev, (e) => e.preventDefault()))
}

/* ------------------------------- arranque ------------------------------- */

async function arrancar() {
  montarNavegacion()
  montarLogos()
  montarEntradaDeArchivo()

  try {
    await prepararMotor()
  } catch (e) {
    mensajeDeCarga(e.message)
    error(e.message)
  }
}

arrancar()
