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

- **Teselas de OpenStreetMap, en blanco y negro.** Hay `L.tileLayer` apuntando
  a `tile.openstreetmap.org`: es un mapa político, no físico — no trae
  alturas ni sombreado, solo calles, bordes de país y de provincia, ciudades
  y nombres. Sin ninguna capa los puntos flotaban sobre un fondo liso y no
  había forma de saber en qué parte del país se estaba mirando.
- **Todo el mapa en blanco y negro, y lo más blanco posible.** Sobre
  `.leaflet-tile-pane` va `grayscale(1) brightness(1.08)`: el primero hace
  desaparecer el celeste del agua y los colores de las rutas, el segundo
  tira el conjunto hacia el blanco — sin él el mar queda en un gris medio
  (≈ 200/255) y todo se ve apagado, mientras que con el brillo la tierra
  satura a blanco puro y el agua queda en un gris muy claro. El filtro va en
  el pane y **no** en el contenedor: aplicado ahí descolorearía también los
  marcadores, que es justo lo que no se quiere. Si no hay red, no cargan las
  teselas y queda el fondo `--surface` de abajo: el mapa sigue siendo usable
  igual.
- **Sin API key.** Se probó primero CARTO Positron (más limpio: solo bordes
  y etiquetas), pero pasó a exigir una clave y en vez de tirar un HTTP error
  devuelve un placeholder con el texto "API key required" dibujado dentro de
  la tesela, que es indetectable salvo mirando los bytes. El servidor de
  OpenStreetMap no pide clave.
- **Atribución obligatoria.** OpenStreetMap exige declararla, así que
  `attributionControl` está encendido (antes estaba apagado, cuando no
  había capa alguna que atribuir).
- **Borde de los marcadores.** `fillColor` = color del dato, pero el borde
  va a `--ink` al 55% y no al color del tramo: cuatro de los diez rangos
  (`#84C2F5`, `#A9E7A9`, `#89DD89`, `#D9FF00`) miden entre 1.15 y 1.91:1
  sobre blanco y con borde del mismo color casi no se recortan. La leyenda
  usa el mismo borde por la misma razón. El color sigue siendo el del dato.
- **El rango abierto es alerta, no un escalón más.** El último tramo de la
  escala (`≥100 %`, el único con `hasta: null`) lleva una pastilla con el
  texto "excede la MEP" en `--risk-high`, no es simplemente el rojo más
  fuerte: es una excedencia que después trata el área técnica en detalle.
  Se detecta por `r.hasta == null` y no por posición en el array, así que
  si algún día se agrega un tramo por encima no se le cuela la pastilla.
  La regla del semáforo de la UI se respeta: nunca información solo por
  color.
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

## Decimales
**La UI muestra exactamente los decimales que tiene la base, sin redondear.**
Todo pasa por `src/format.js` (`fmtVm` / `fmtPct`); ningún componente llama a
`toFixed()` por su cuenta.

| Campo | Quién lo define | Decimales |
|---|---|---|
| `resultado_vm` | Instrumento, en pasos de 0,001 | **3**, los que hay |
| `resultado_pct` | Calculado: `vm² / 3770 / límite × 100` | **4** de 17 |
| Conteos (`mediciones`, `localidades`) | `COUNT(*)`, enteros | tal cual |

Por qué: el 83,32 % de los V/m (183.160 de 219.818) tiene 3 decimales, así
que con `.toFixed(2)` salía `0.942 → 0.94` y, peor, `0.001 → 0.00` y
`0.005 → 0.01`. Con el % el caso era peor: `.toFixed(1)` cambiaba
215.212 de 219.818 filas y dejaba `0,04022315030756169` como **`0,0 %`**,
que se confunde con el contador de "resultados en cero" del Diagnóstico.

Las dos funciones devuelven **números**, no strings: en el template se
imprimen con la representación más corta que los reproduce exacto, así no
quedan ceros de relleno (`19.260 → 19.26`, `0.000 → 0`).

La contraparte en Python es `app/utils/formato.py`, que usa el mismo
criterio para los informes Word/PDF. Si cambian los decimales, cambien en
los dos lados.

## Catálogos (Provincia y CCTE)
Dos archivos, uno por catálogo, y **todo lo que pida o muestre un valor de
esos campos lee de ahí**:

| Archivo | Qué define | Cuándo se toca |
|---|---|---|
| `src/provincias.js` | `PROVINCIAS`, 23 + CABA | Si entra una provincia nueva al país del sistema |
| `src/ccte.js` | `CCTE_FIJOS`, los 7 | Nunca sin cambiar `app/core/config.py` del backend |

`constants.js` se borró: solo contenía el CCTE. El backend tiene su propia
lista en `config.py` y **manda**; la del frontend tiene que coincidir con ella.

Por qué son catálogo cerrado y no texto libre: un error de tipeo **no falla**.
Entra igual a la base y a partir de ahí hay dos "Córdoba" en Resumen, en el KPI
"Provincias" y en el mapa, y ningún conteo vuelve a dar lo mismo. Hoy la base
está limpia —10 provincias y 5 CCTE, todas bien escritas— y el catálogo es lo
que la mantiene así.

### `Combobox.vue`
Campo con búsqueda (`role="combobox"` + `aria-expanded` + `aria-controls` +
`aria-activedescendant` sobre un `listbox`), reemplaza al `<select>` de CCTE y
a los tres `<input type="text">` que había (Carga, Gestión y el filtro global).

- **La búsqueda ignora mayúsculas y acentos**: `sant` → *Santiago del Estero*,
  `cordoba` → *Córdoba*, `rio` → *Río Negro*. `NFD` + `\p{M}`.
- **Al perder el foco, lo escrito se resuelve solo**: si identifica a una sola
  opción se adopta (escribir el nombre completo a mano tiene que servir, y de
  paso lo normaliza); si no, se revierte al último valor elegido. Así el campo
  nunca muestra algo que no esté elegido y el `required` nativo alcanza.
- **Nada se resalta solo al tipear** (`activo` arranca en -1). Con la primera
  coincidencia marcada, `sant` + Enter habría confirmado *Santa Cruz* sin que
  nadie lo eligiera, que es justo el error que el control existe para evitar.
- El catálogo va **completo** aunque solo 10 provincias tengan datos: la carga
  tiene que poder recibir una que todavía no existe, y filtrar una sin datos
  devuelve vacío, que es un resultado válido y no un error.
- El menú no usa sombra: no hay `--shadow-*` en el sistema a propósito, se
  separa con el mismo borde que un input.

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
