<script setup>
import { useRoute } from 'vue-router'
import { nextTick, ref, watch } from 'vue'
import FiltrosBar from '../components/FiltrosBar.vue'
// Logo institucional tal cual está en assets: Vite lo copia al build y
// devuelve la URL resuelta. El PNG es monocromático azul marino (#0B1742,
// el mismo valor que --ink), por lo que en el sidebar se lo pasa a blanco
// con un filtro (ver .sidebar__logo) en vez de traer otro archivo.
import logoEnacom from '../assets/logoenacom.png'

const route = useRoute()

// El scroll de la página vive dentro de <main class="content">: el shell,
// la barra superior y el sidebar quedan fijos. El scrollBehavior del router
// sólo sabe rebobinar la VENTANA, así que al cambiar de sección hay que
// llevar el contenido al principio a mano.
const contenido = ref(null)
watch(
  () => route.fullPath,
  () => nextTick(() => { if (contenido.value) contenido.value.scrollTop = 0 }),
)

const nav = [
  { to: '/', label: 'Inicio', icon: '◆' },
  { to: '/resumen', label: 'Resumen', icon: '▤' },
  // Gráficos dejó de existir como sección: pasó a ser parte del Centro
  // operativo (antes "Gestión"), junto con la lista y el detalle.
  { to: '/gestion', label: 'Centro operativo', icon: '⚙' },
  { to: '/mapa', label: 'Mapa', icon: '⬢' },
  { to: '/diagnostico', label: 'Diagnóstico', icon: '✓' },
  { to: '/carga', label: 'Carga de Excel', icon: '↑' },
]
</script>

<template>
  <div class="shell">
    <aside class="sidebar" aria-label="Navegación principal">
      <div class="sidebar__brand">
        <img
          class="sidebar__logo"
          :src="logoEnacom"
          alt="ENACOM"
          width="112"
          height="29"
        />
        <p class="sidebar__claim">Base de datos de Radiaciones no Ionizantes</p>
      </div>
      <nav>
        <ul class="sidebar__nav">
          <li v-for="item in nav" :key="item.to">
            <router-link :to="item.to" class="sidebar__link" active-class="sidebar__link--active">
              <span class="sidebar__icon" aria-hidden="true">{{ item.icon }}</span>
              {{ item.label }}
            </router-link>
          </li>
        </ul>
      </nav>

    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar__titulo">
          <h1>{{ route.meta.titulo }}</h1>
        </div>
        <FiltrosBar />
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
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  /* Altura exacta del viewport y sin scroll: la página nunca crece, así que
     el sidebar y la barra superior quedan siempre a la vista. El exceso de
     contenido lo absorbe .content con su propio scroll. Antes valía
     min-height y el contenido se desbordaba POR FUERA del shell: esos px de
     sobra no tenían sidebar detrás, que era exactamente lo que se veía al
     bajar (fondo vacío sin barra). */
  height: 100%;
  overflow: hidden;
}

.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--ink);
  color: var(--on-ink);
  padding: var(--space-8) var(--space-5);

  /* Columna: la marca arriba y la navegación debajo. El pie institucional dejó
     de vivir acá (pasó al final del contenido, ver .pie). */
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.sidebar__brand {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: 0 var(--space-4);
}

/* El PNG es monocromo #0B1742, que es exactamente el fondo del sidebar:
   a pelo quedaba invisible (era el motivo por el que vivía en la barra
   superior sobre fondo claro). `brightness(0)` deja todo lo opaco negro
   y `invert(1)` lo deja blanco; el alfa no se toca, así que el fondo
   sigue transparente y no aparece ningún rectángulo detrás. */
.sidebar__logo {
  width: 112px;
  height: auto;
  display: block;
  filter: brightness(0) invert(1);
}

.sidebar__claim {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  line-height: 1.35;
  color: var(--on-ink-soft);
}

.sidebar__nav {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sidebar__link {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-4);
  color: var(--on-ink-soft);
  text-decoration: none;
  font-size: var(--fs-md);
  border-left: 3px solid transparent;
}

.sidebar__link:hover {
  color: var(--on-ink);
  background: var(--on-ink-wash);
}

.sidebar__link--active {
  color: var(--on-ink);
  border-left-color: var(--signal-on-ink);
  background: var(--on-ink-wash);
}

.sidebar__icon {
  width: 1rem;
  text-align: center;
  color: var(--signal-on-ink);
}

/* El anillo de foco global es --signal, que sobre --ink da 2.52:1 y casi no
   se ve: dentro del sidebar se sustituye por el acento claro (6.15:1). */
.sidebar :focus-visible {
  outline-color: var(--signal-on-ink);
}

.main {
  flex: 1;
  min-width: 0;
  /* Sin esto .main no puede quedarse corto y .content no podría hacer scroll
     por dentro: el hijo flex no podría encoger más allá del contenido. */
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  padding: 1rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.topbar__titulo {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
}

.topbar__titulo h1 {
  margin: 0;
}

.content {
  padding: 1.5rem;
  flex: 1;
  /* El scroll de cada sección vive acá y no en la ventana: el documento
     mide exactamente la pantalla, así que el sidebar nunca se queda sin
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

@media (max-width: 780px) {
  .shell {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    padding: 0.75rem;
  }
  .sidebar__nav {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
