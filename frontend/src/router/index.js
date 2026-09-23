import { createRouter, createWebHistory } from 'vue-router'

// Vistas con import dinámico: cada una es su propio chunk. Antes los 7
// imports eran eager y todo caía en un solo bundle de 505 kB (Vite venía
// avisando "chunks > 500 kB"). Con esto Leaflet (Mapa) y Chart.js
// (Gráficos/Dashboard) solo se descargan cuando se entra a esas vistas.
const routes = [
  { path: '/', name: 'inicio', component: () => import('../views/DashboardView.vue'), meta: { titulo: 'Inicio' } },
  { path: '/resumen', name: 'resumen', component: () => import('../views/ResumenView.vue'), meta: { titulo: 'Resumen' } },
  { path: '/graficos', name: 'graficos', component: () => import('../views/GraficosView.vue'), meta: { titulo: 'Gráficos' } },
  { path: '/gestion', name: 'gestion', component: () => import('../views/GestionView.vue'), meta: { titulo: 'Gestión' } },
  { path: '/mapa', name: 'mapa', component: () => import('../views/MapaView.vue'), meta: { titulo: 'Mapa' } },
  { path: '/diagnostico', name: 'diagnostico', component: () => import('../views/DiagnosticoView.vue'), meta: { titulo: 'Diagnóstico' } },
  { path: '/carga', name: 'carga', component: () => import('../views/CargaView.vue'), meta: { titulo: 'Carga de Excel' } },
  // Sin catch-all antes: una ruta mal tipeada ("/gestio") quedaba en blanco
  // eterno porque MainLayout seguía montado y route.meta.titulo era undefined.
  {
    path: '/:pathMatch(.*)*',
    name: 'no-encontrada',
    component: () => import('../views/NotFoundView.vue'),
    meta: { titulo: 'Página no encontrada' },
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  // Sin esto, volver atrás después de scrollear dejaba la vista nueva
  // a media pantalla (comportamiento de la app original, no del navegador).
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})
