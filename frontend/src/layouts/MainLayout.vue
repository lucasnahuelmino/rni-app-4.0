<script setup>
import { useRoute } from 'vue-router'
import FiltrosBar from '../components/FiltrosBar.vue'
// Logo institucional tal cual está en assets: Vite lo copia al build y
// devuelve la URL resuelta. El PNG es monocromático azul marino (#0B1742,
// el mismo valor que --ink), por lo que en el sidebar se lo pasa a blanco
// con un filtro (ver .sidebar__logo) en vez de traer otro archivo.
import logoEnacom from '../assets/logoenacom.png'

const route = useRoute()

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

      <p class="sidebar__pie">Dirección Nacional de Control y Fiscalización</p>
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
      <main class="content" :class="{ 'content--mapa': route.name === 'mapa' }">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  min-height: 100%;
}

.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--ink);
  color: var(--on-ink);
  padding: var(--space-8) var(--space-5);

  /* Columna con el pie anclado abajo: `.shell` estira el aside al alto
     completo, así que el `margin-top: auto` del pie lo mantiene pegado al
     fondo aunque la navegación no llene la altura. */
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

/* Pie del sidebar: el organismo responsable, anclado al fondo del todo.
   `--on-ink-faint` es blanco al 55% sobre --ink (5.76:1), pasa AA. */
.sidebar__pie {
  margin: auto 0 0;
  padding: var(--space-6) var(--space-4) 0;
  border-top: 1px solid var(--on-ink-wash);
  font-size: var(--fs-2xs);
  line-height: 1.4;
  color: var(--on-ink-faint);
}

/* El anillo de foco global es --signal, que sobre --ink da 2.52:1 y casi no
   se ve: dentro del sidebar se sustituye por el acento claro (6.15:1). */
.sidebar :focus-visible {
  outline-color: var(--signal-on-ink);
}

.main {
  flex: 1;
  min-width: 0;
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
}

.content--mapa {
  /* Sin padding ni margen: el mapa llega a los bordes y aprovecha todo el
     alto que deja la barra superior. */
  padding: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
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
