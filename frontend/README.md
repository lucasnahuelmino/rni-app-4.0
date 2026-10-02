# Frontend RNI (Fase 4)

## Instalación
```
npm install
```

## Desarrollo (con proxy al backend)
```
npm run dev
```
Levanta en http://localhost:5173, con `/api/*` proxeado al backend FastAPI
(ver Fase 3). El backend tiene que estar en el **8001**.

El target vive en `frontend/.env.local` (`VITE_API_PROXY_TARGET=http://localhost:8001`),
que Vite lee solo; la variable de arriba hace lo mismo pero hay que
escribirla a mano en cada terminal. Ojo con el 8000: lo tiene AeroRF, otro
proyecto de esta máquina, y sin `.env.local` el proxy le pegaría a la app
equivocada sin decirte nada.

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
