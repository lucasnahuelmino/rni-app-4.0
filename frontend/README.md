# Frontend RNI (Fase 4)

## Instalación
```
npm install
```

## Desarrollo (con proxy al backend)
```
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```
Levanta en http://localhost:5173, con `/api/*` proxeado al backend FastAPI
(ver Fase 3). Asumir que el backend ya está corriendo en el puerto 8000.

## Build de producción
```
npm run build
```
Genera `dist/`. En producción, `VITE_API_BASE_URL` puede apuntar directo a
la URL pública de la API (por default usa `/api`, pensado para servirse
detrás del mismo dominio/proxy que el backend).

## Estructura
- `src/stores/filtros.js` — filtros globales (CCTE/Provincia/Año), Pinia.
- `src/composables/useFetchOnFiltros.js` — fetch reactivo a los filtros.
- `src/services/domains.js` — llamadas a cada endpoint del backend.
- `src/views/` — las 7 vistas (Dashboard, Resumen, Gráficos, Gestión, Mapa,
  Diagnóstico, Carga).
- `src/components/` — KpiCard, CcteCard, SemaforoBadge, gráficos (Chart.js).
- `DESIGN.md` — sistema de diseño (tokens de color/tipografía) usado en toda la app.

## Pendiente de confirmar con el equipo
`SemaforoBadge.vue` y `MapaView.vue` usan una escala simplificada de 3
niveles (Bajo/Moderado/Alto con cortes en 25% y 80%) en vez de la escala de
10 bandas de color del sistema Streamlit original -- los umbrales exactos
quedaron pendientes de confirmación (ver comentario en el propio componente).
