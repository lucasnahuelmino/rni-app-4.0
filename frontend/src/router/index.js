import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import ResumenView from '../views/ResumenView.vue'
import GraficosView from '../views/GraficosView.vue'
import GestionView from '../views/GestionView.vue'
import MapaView from '../views/MapaView.vue'
import DiagnosticoView from '../views/DiagnosticoView.vue'
import CargaView from '../views/CargaView.vue'

const routes = [
  { path: '/', name: 'inicio', component: DashboardView, meta: { titulo: 'Inicio' } },
  { path: '/resumen', name: 'resumen', component: ResumenView, meta: { titulo: 'Resumen' } },
  { path: '/graficos', name: 'graficos', component: GraficosView, meta: { titulo: 'Gráficos' } },
  { path: '/gestion', name: 'gestion', component: GestionView, meta: { titulo: 'Gestión' } },
  { path: '/mapa', name: 'mapa', component: MapaView, meta: { titulo: 'Mapa' } },
  { path: '/diagnostico', name: 'diagnostico', component: DiagnosticoView, meta: { titulo: 'Diagnóstico' } },
  { path: '/carga', name: 'carga', component: CargaView, meta: { titulo: 'Carga de Excel' } },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
