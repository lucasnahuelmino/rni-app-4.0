# Sistema de diseño — Frontend RNI

**Sujeto:** herramienta de monitoreo regulatorio de exposición a RNI para
técnicos de ENACOM. No es un producto de consumo: es una herramienta de
trabajo diaria, densa en datos, que tiene que transmitir precisión y
confiabilidad antes que "onda".

**Principio rector:** nada de tarjetas redondeadas con sombra suave
idénticas entre sí. La jerarquía se construye con líneas finas (hairlines)
y una barra de color a la izquierda de cada bloque, no con sombras.

## Color
- `--ink: #10202B` — texto principal, sidebar
- `--paper: #F4F6F5` — fondo general (gris frío pálido, no crema)
- `--surface: #FFFFFF` — superficies de contenido
- `--signal: #0E7C8C` — acento primario (teal-cian, evoca espectro/telecom)
- `--signal-deep: #0B5C68` — hover/activo
- `--risk-ok: #2F8F5B` / `--risk-mid: #C98A1F` / `--risk-high: #B23A3A` — semáforo,
  SIEMPRE acompañado de texto ("Bajo"/"Moderado"/"Alto"), nunca solo color.

## Tipografía
- Titulares y navegación: **Space Grotesk** (geométrica, técnica, no es el
  Inter/Helvetica por default).
- Texto de UI: **IBM Plex Sans**.
- Todo dato numérico (V/m, %, coordenadas, conteos): **IBM Plex Mono** —
  no es decorativo, alinea dígitos y distingue visualmente "dato" de "texto".

## Layout
Sidebar fijo oscuro (`--ink`) a la izquierda con la navegación. Barra
superior con el título de la vista + los filtros globales (CCTE/Provincia/
Año) como chips, siempre visibles. Contenido principal en grilla densa,
alineado a la izquierda. Los bloques de KPI son rectángulos con borde fino
y una barra de color a la izquierda (no shadow, no border-radius grande).
