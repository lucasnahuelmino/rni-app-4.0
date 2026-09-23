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

- `--ink: #10202B` — texto principal, sidebar
- `--ink-soft: #3C4D59` — texto secundario, labels
- `--paper: #F4F6F5` — fondo general (gris frío pálido, no crema)
- `--surface: #FFFFFF` — superficies de contenido
- `--line` — hairline de borde, sobre cualquier superficie
- `--signal: #0E7C8C` — acento primario (teal-cian, evoca espectro/telecom)
- `--signal-deep: #0B5C68` — hover/activo
- `--risk-ok: #2F8F5B` / `--risk-mid: #C98A1F` / `--risk-high: #B23A3A` — semáforo,
  SIEMPRE acompañado de texto ("Bajo"/"Moderado"/"Alto"), nunca solo color.
- `--sin-dato` — neutro para "sin dato" (leyenda del mapa, marcadores, badges).
  Lo consume `colorScaleStore.colorPorPct(null)`, así que leyenda y puntos no
  pueden divergir.
- `--on-ink` / `--on-ink-soft` / `--on-ink-faint` / `--on-ink-wash` — texto y
  decoración **sobre `--ink`**, derivados de `--surface` con `color-mix()`.
  Cambiá `--surface` y todo lo que va encima de `--ink` se mueve con él.

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
superior con el título de la vista + los filtros globales (CCTE/Provincia/
Año) como chips, siempre visibles. Contenido principal en grilla densa,
alineado a la izquierda. Los bloques de KPI son rectángulos con borde fino
y una barra de color a la izquierda (no shadow, no border-radius grande).

## Estados de datos
`EmptyState` (caja gris **punteada**), `LoadingState` y `ErrorState`
(caja **roja con barra roja a la izquierda**). Error y vacío son cosas
distintas y tienen que distinguirse de un vistazo: `ErrorState` usa
`.error-state`, `.empty-state` queda reservado para "no hay datos".
