# Sistema de diseño — Frontend RNI

**Sujeto:** herramienta de monitoreo regulatorio de exposición a RNI para
técnicos de ENACOM. No es un producto de consumo: es una herramienta de
trabajo diaria, densa en datos, que tiene que transmitir precisión y
confiabilidad antes que "onda".

**Principio rector:** nada de tarjetas redondeadas con sombra suave
idénticas entre sí. La jerarquía se construye con líneas finas (hairlines)
y una barra de color a la izquierda de cada bloque, no con sombras.

## Color
Definidos en `src/assets/tokens.css` (única fuente de verdad — **no** escribir
hex en los `.vue`; los gráficos y el mapa los leen desde JS con `token()` de
`src/assets/tokens.js`, que cachea por nombre de token).

La paleta es la **institucional ENACOM**: `--ink` es exactamente el azul del
logo oficial (`src/assets/logoenacom.png`, monocromático `#0B1742`) y el resto
son azules derivados de ese. Todos los valores de texto están **medidos**, no
estimados, y pasan WCAG AA.

- `--ink: #0B1742` — texto principal, fondo del sidebar, fondo de `.btn`
  (17.3:1 sobre `--surface`; es el hex del logo)
- `--ink-soft: #3D4670` — texto secundario, labels (9.1:1)
- `--paper: #F4F6FA` — fondo general (frío y levemente azulado, no crema)
- `--surface: #FFFFFF` — superficies de contenido
- `--line` — hairline de borde, sobre cualquier superficie
- `--signal: #1A4FBF` — acento primario (7.2:1): foco, links, bordes activos,
  `.stat-block`, series de Chart.js
- `--signal-deep: #0E2E73` — hover/activo (12.7:1)
- `--signal-on-ink: #6E96FF` — acento que cae **sobre `--ink`** (ícono y
  borde del link activo del sidebar, anillo de foco ahí dentro).
  `--signal` sobre `--ink` da 2.52:1 y no supera el mínimo de 3:1 para
  elementos gráficos; este da 6.15:1. **No usarlo sobre blanco**: allí
  corresponde `--signal`. Regla corta: sobre claro va `--signal`, sobre
  `--ink` va `--signal-on-ink`.
- `--risk-ok: #26794D` / `--risk-mid: #9C6208` / `--risk-high: #B23A3A` —
  semáforo de la UI (estado de riesgo/error), SIEMPRE acompañado de texto
  ("Bajo"/"Moderado"/"Alto"), nunca solo color. Los tres pasan **WCAG AA
  (≥4.5:1)** sobre `--surface` y `--paper`.
  **No confundir con el semáforo del mapa**: esa escala de 10 rangos vive en
  el backend (`RANGOS_COLOR` en `app/core/config.py`, servida por
  `GET /api/color-scale`) y es la que usan leyenda, marcadores y badges.
- `--sin-dato` — neutro para "sin dato" (leyenda del mapa, marcadores, badges).
  Lo consume `colorScaleStore.colorPorPct(null)`, así que leyenda y puntos no
  pueden divergir.
- `--on-ink` / `--on-ink-soft` / `--on-ink-faint` / `--on-ink-wash` — texto y
  decoración **sobre `--ink`**, derivados de `--surface` con `color-mix()`.
  Cambiá `--surface` y todo lo que va encima de `--ink` se mueve con él.

El logo va en la barra superior, junto al título, sobre fondo claro: es la
única forma de que se vea con su azul original (el PNG es monócromo y el
sidebar es del mismo azul, así que ahí sería invisible).

## Tipografía
- Titulares y navegación: **Space Grotesk** (geométrica, técnica, no es el
  Inter/Helvetica por default).
- Texto de UI: **IBM Plex Sans**.
- Todo dato numérico (V/m, %, coordenadas, conteos): **IBM Plex Mono** —
  no es decorativo, alinea dígitos y distingue visualmente "dato" de "texto".

Escala de tamaños (`--fs-*`): `2xs 0.7 · xs 0.75 · sm 0.8 · md 0.85 ·
lg 0.95 · xl 1.125 · 2xl 1.25 · 3xl 1.5rem`, más `--fs-body` (0.875rem).
Todo en `rem`, nunca `px`: respeta el tamaño de fuente que eligió el usuario.
El mínimo del sistema es `--fs-2xs`; por debajo de eso nada es legible.

## Espaciado
Escala `--space-1` (0.15rem) a `--space-10` (2rem). Antes cada vista tenía
sus propios valores casi iguales (1.75, 0.6, 0.55, 0.4, 0.35, 0.3...); si un
número no está en la escala, no se usa.

## Formas y elevación
- `--radius-xs: 2px` — solo controles de formulario. Todo lo demás es cuadrado.
- `--radius-full: 50%` — puntos del semáforo y de la leyenda.
- **No hay `--shadow-*` a propósito.** No es un hueco: ver el principio rector.

## Layout
Sidebar fijo oscuro (`--ink`) a la izquierda con la navegación. Barra
superior con el logo de ENACOM + el título de la vista + los filtros globales
(CCTE/Provincia/Año) como chips, siempre visibles. Contenido principal en
grilla densa, alineado a la izquierda. Los bloques de KPI son rectángulos con
borde fino y una barra de color a la izquierda (no shadow, no border-radius
grande).

### Mapa (vista `/mapa`)
Es la única vista que rompe el padding de `.content`: `MainLayout` le pone
`content--mapa` (padding 0 + flex column) y el mapa ocupa **todo** el alto
que queda. El contenedor `.mapa-escena` es `position: relative` y el canvas
va `position:absolute; inset:0`, de modo que ningún hermano que aparezca o
desaparezca cambia el tamaño que Leaflet ya midió (no hace falta un
`invalidateSize` por cada cambio de estado).

- **Teselas políticas, sin color.** Hay `L.tileLayer` con CARTO Positron
  (`light_all`, datos de OpenStreetMap): es un mapa político, no físico — no
  trae relieve ni usos de suelo, solo bordes de país y de provincia,
  ciudades y nombres. Eso es lo mínimo que hace falta para orientarse; sin
  ninguna capa los puntos flotaban sobre un fondo liso y no había forma de
  saber en qué parte del país se estaba mirando.
- **Todo el mapa en blanco y negro.** Sobre `.leaflet-tile-pane` va
  `grayscale(1)`, así el celeste del agua y cualquier resto de color
  desaparecen y el mapa queda en escala de grises. El filtro va en el pane
  de teselas y **no** en el contenedor: aplicado ahí descolorearía también
  los marcadores, que es justo lo que no se quiere. Si no hay red, no
  cargan las teselas y queda el fondo `--surface` de abajo: el mapa sigue
  siendo usable igual.
- **Atribución obligatoria.** OpenStreetMap y CARTO exigen declararla, así
  que `attributionControl` está encendido (antes estaba apagado, cuando no
  había capa alguna que atribuir).
- **Borde de los marcadores.** `fillColor` = color del dato, pero el borde
  va a `--ink` al 55% y no al color del tramo: cuatro de los diez rangos
  (`#84C2F5`, `#A9E7A9`, `#89DD89`, `#D9FF00`) miden entre 1.15 y 1.91:1
  sobre blanco y con borde del mismo color casi no se recortan. La leyenda
  usa el mismo borde por la misma razón. El color sigue siendo el del dato.
- **Modo automático por zoom** (reemplaza al selector manual). Por debajo de
  `ZOOM_DETALLE = 7`, un punto por localidad (el de mayor `%`); desde ahí en
  adelante, todos los puntos del área visible. Motivo de lectura: a la vista
  nacional los 4.968 puntos se apilan en ~5 zonas y las localidades chicas
  quedan tapadas. Lo que el fieldset explicaba ahora lo dice una sola línea
  en la barra de controles.
- **Todo lo transitorio flota** (leyenda abajo-izquierda, avisos y estados
  arriba-derecha, `z-index: 500`, por debajo del panel de marcadores y de
  las ventanas): así el alto del mapa es constante y Leaflet nunca queda con
  un tamaño viejo.
- **El popup es un componente Vue** (`components/mapa/MapPopup.vue`), montado
  en **una sola app** reutilizada por todos los marcadores. Recibe `punto` y
  `escala` por props en vez de llamar a `useColorScaleStore()` adentro, porque
  esa app no tiene el Pinia raíz. Ventana cuadrada, sin sombra ni punta, con
  la barra de `--signal` a la izquierda como el resto de los bloques.
- **Filtros globales**: por defecto el mapa NO los hereda; hay una casilla
  explícita para activarlos. Es a propósito, no un bug.

## Estados de datos
`EmptyState` (caja gris **punteada**), `LoadingState` y `ErrorState`
(caja **roja con barra roja a la izquierda**). Error y vacío son cosas
distintas y tienen que distinguirse de un vistazo: `ErrorState` usa
`.error-state`, `.empty-state` queda reservado para "no hay datos".

## Accesibilidad
- Los controles interactivos son `<button>`/`<input>` reales, nunca
  `<span @click>`: no hay nada clickeable que no sea alcanzable con Tab.
- Un selector exclusivo de opciones (si vuelve a hacer falta) es un
  `<fieldset>` con `<legend class="sr-only">` y radios nativos, no un
  `div[role=radiogroup]` con botones y `aria-pressed`. Hoy no queda ningún
  en la app: el de modos del mapa se reemplazó por el modo automático por
  zoom, y los tabs de Gestión/Tiempos son `<button>` con roving tabindex.
- `aria-label` sobre un `<div>` sin `role` **no** se expone como nombre
  accesible: los contenedores con label llevan `role="list"`.
- `.sr-only` (en `tokens.css`) oculta visualmente sin sacar el elemento del
  árbol accesible. Cuando el control real queda en `.sr-only` dentro de una
  etiqueta, `.chip:has(.sr-only:focus-visible)` pinta el anillo de foco en la
  etiqueta — requiere `:has()`.
