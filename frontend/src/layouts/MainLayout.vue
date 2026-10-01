<script setup>
import { useRoute } from 'vue-router'
import { nextTick, ref, watch } from 'vue'
import FiltrosBar from '../components/FiltrosBar.vue'
// Logo institucional tal cual está en assets: Vite lo copia al build y
// devuelve la URL resuelta. El PNG es monocromático azul marino (#0B1742,
// el mismo valor que --ink), así que sobre la barra oscura se lo pasa a
// blanco con un filtro que no toca el alfa (ver .topbar__logo).
import logoEnacom from '../assets/logoenacom.png'

const route = useRoute()

// El scroll de la página vive dentro de <main class="content">: el shell,
// la barra superior y el pie quedan fijos. El scrollBehavior del router
// sólo sabe rebobinar la VENTANA, así que al cambiar de sección hay que
// llevar el contenido al principio a mano.
const contenido = ref(null)
watch(
  () => route.fullPath,
  () => nextTick(() => { if (contenido.value) contenido.value.scrollTop = 0 }),
)

// Cinco entradas: Diagnóstico dejó de ser una sección propia y quedó
// dentro de Carga de Excel (misma base cruda), ver router/index.js.
const nav = [
  { to: '/', label: 'Inicio', icon: '◆' },
  { to: '/resumen', label: 'Resumen', icon: '▤' },
  // Gráficos dejó de existir como sección: pasó a ser parte del Centro
  // operativo (antes "Gestión"), junto con la lista y el detalle.
  { to: '/gestion', label: 'Centro operativo', icon: '⚙' },
  { to: '/mapa', label: 'Mapa', icon: '⬢' },
  { to: '/carga', label: 'Carga de Excel', icon: '↑' },
]
</script>

<template>
  <div class="shell">
    <!-- UNA barra oscura arriba (--ink, el mismo azul que tenía el sidebar):
         marca a la izquierda, menú de secciones CENTRADO y filtros a la
         derecha. El menú va horizontal porque la navegación en columna
         lateral le robaba 220 px de ancho a todo el contenido (la tabla de
         Resumen no entraba sin barra horizontal). -->
    <header class="topbar">
      <div class="topbar__marca">
        <img
          class="topbar__logo"
          :src="logoEnacom"
          alt="ENACOM"
          width="112"
          height="29"
        />
        <p class="topbar__claim">Base de datos de Radiaciones no Ionizantes</p>
      </div>

      <nav class="topnav" aria-label="Navegación principal">
        <router-link
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="topnav__link"
          active-class="topnav__link--active"
        >
          <span class="topnav__icon" aria-hidden="true">{{ item.icon }}</span>
          {{ item.label }}
        </router-link>
      </nav>

      <!-- El título de la sección se sacó de la barra: con el menú centrado
           y los filtros a la derecha quedaba apretado, y el link activo ya
           dice dónde estás. Sigue siendo el <h1> de la página, sólo que
           oculto: sin él, el encabezado más alto de cada vista sería un h2. -->
      <h1 class="sr-only">{{ route.meta.titulo }}</h1>

      <!-- .sobre-oscuro le avisa a FiltrosBar que pinte sus controles con la
           paleta clara (los mismos --on-ink que usaba el sidebar). -->
      <div class="topbar__filtros">
        <FiltrosBar class="sobre-oscuro" />
      </div>
    </header>

    <!-- La vista del mapa ocupa TODO el alto que queda: sin este modo el
         contenido tiene 1.5rem de padding en los cuatro costados y el mapa
         queda en 60vh con un montón de aire alrededor, que era justo lo que
         sobraba. -->
    <main ref="contenido" class="content" :class="{ 'content--mapa': route.name === 'mapa' }">
      <slot />
    </main>

    <!-- Pie institucional: filete azul (--signal), logo de ENACOM y el
         organismo responsable. Siempre visible al fondo de la derecha: el
         scroll vive dentro de .content, así que este pie no le roba alto a
         la ventana. -->
    <footer class="pie">
      <img class="pie__logo" :src="logoEnacom" alt="ENACOM" width="80" height="21" />
      <p class="pie__texto">Dirección Nacional de Control y Fiscalización</p>
    </footer>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  /* Altura exacta del viewport y sin scroll: la página nunca crece, así que
     la barra superior y el pie quedan siempre a la vista. El exceso de
     contenido lo absorbe .content con su propio scroll. Antes valía
     min-height y el contenido se desbordaba POR FUERA del shell: esos px de
     sobra no tenían fondo detrás, que era exactamente lo que se veía al
     bajar (fondo vacío sin barra). */
  height: 100%;
  overflow: hidden;
}

/* ---------------------------- barra superior ---------------------------- */

.topbar {
  background: var(--ink);
  /* 0.5rem en vertical: con el menú dentro el renglón mide ~53 px, menos
     que la barra clara que había (título + 1rem de padding). */
  padding: var(--space-4) var(--space-7);
  display: flex;
  align-items: center;
  gap: var(--space-3) var(--space-6);
  flex-wrap: wrap;
  flex-shrink: 0;
}

/* Los dos costados con flex-basis 0 y crecimiento 1: quedan con el MISMO
   ancho, y eso es lo que centra el menú exactamente a mitad de la barra
   (con anchos naturales distintos el menú quedaba corrido hacia un lado). */
.topbar__marca {
  flex: 1 1 0;
  display: flex;
  align-items: center;
  gap: var(--space-5);
  min-width: 0;
}

.topbar__logo {
  width: 112px;
  height: auto;
  display: block;
  /* El PNG es #0B1742, exactamente el fondo de la barra: sin esto el logo
     era invisible. brightness(0) lo deja en negro y invert(1) en blanco, y
     como no toca el alfa no queda ningún rectángulo detrás. */
  filter: brightness(0) invert(1);
}

/* El claim ocupa ~250 px y con él puesto el menú se iba a otro renglón en
   1366, que era el ancho que veníamos midiendo: se muestra recién cuando la
   barra tiene lugar de sobra. */
.topbar__claim {
  display: none;
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  line-height: 1.35;
  color: var(--on-ink-soft);
}

@media (min-width: 1500px) {
  .topbar__claim {
    display: block;
  }
}

/* Sólo lo que necesita y se achica si no entra: entre los dos costados que
   crecen por igual queda centrado. flex-wrap es la red de seguridad en
   pantallas angostas (el menú pasa a otro renglón en vez de desbordar). */
.topnav {
  flex: 0 1 auto;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: var(--space-1);
}

.topnav__link {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  color: var(--on-ink-soft);
  text-decoration: none;
  font-size: var(--fs-md);
  white-space: nowrap;
  /* Filete ABAJO y no a la izquierda: en una barra horizontal es lo que
     marca la sección activa sin ensanchar la fila (en el sidebar era
     border-left, que servía porque las filas estaban apiladas). */
  border-bottom: 3px solid transparent;
}

.topnav__link:hover {
  color: var(--on-ink);
  background: var(--on-ink-wash);
}

.topnav__link--active {
  color: var(--on-ink);
  font-weight: 600;
  border-bottom-color: var(--signal-on-ink);
  background: var(--on-ink-wash);
}

/* --signal (el acento de toda la interfaz) sobre --ink da 2.52:1 y no
   llega al 3:1 mínimo de WCAG para elementos gráficos: sobre la barra
   oscura corresponde --signal-on-ink (6.15:1). Igual motivo tiene el
   anillo de foco acá abajo: el global es --signal y sobre --ink no se ve. */
.topnav__icon {
  color: var(--signal-on-ink);
}

.topnav__link:focus-visible {
  outline-color: var(--signal-on-ink);
}

.topbar__filtros {
  flex: 1 1 0;
  display: flex;
  justify-content: flex-end;
  min-width: 0;
}

.content {
  padding: 1.5rem;
  flex: 1;
  /* El scroll de cada sección vive acá y no en la ventana: el documento
     mide exactamente la pantalla, así que la barra nunca se queda sin
     fondo detrás. min-height: 0 es lo que permite que el hijo desborde y
     aparezca la barra. */
  min-height: 0;
  overflow: auto;
}

.content--mapa {
  /* Sin padding ni margen: el mapa llega a los bordes y aprovecha todo el
     alto que deja la barra superior. overflow: hidden y no auto: Leaflet
     mide su lienzo con el del contenedor y un scroll interno en vez de
     recortar le dejaría un canvas de tamaño viejo. */
  padding: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* Pie institucional: la línea azul es el filete de arriba (--signal), y
   debajo van el logo y el organismo responsable. */
.pie {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-3) var(--space-6);
  background: var(--surface);
  border-top: 2px solid var(--signal);
}

.pie__logo {
  width: 80px;
  height: auto;
  display: block;
}

.pie__texto {
  margin: 0;
  font-size: var(--fs-2xs);
  line-height: 1.3;
  color: var(--ink-soft);
}
</style>
