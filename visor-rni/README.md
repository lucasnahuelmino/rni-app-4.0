# Visor RNI

Visor de **sólo lectura** para consultar `rni.db` sin levantar el backend y sin
instalar nada: SQLite corre dentro del navegador (WebAssembly) sobre una copia
en memoria del archivo.

- HTML + CSS + JavaScript (módulos ES), **sin build ni Node**.
- Ninguna librería ni fuente sale de internet: todo está en `vendor/` y `fonts/`.
- El visor **no puede escribir**: además de leer el archivo como bytes, la
  conexión se abre con `PRAGMA query_only = ON`.

## Cómo usar

1. Doble clic en **`iniciar.bat`**. Levanta un servidor local y abre el
   navegador en <http://localhost:8090>.
2. Arrastrá `rni.db` sobre la pantalla de carga (o elegilo con el botón).
3. Usá las cinco vistas: **Inicio**, **Localidades**, **Por horarios**,
   **Resúmenes** y **Mapa**.

> **¿Por qué hace falta el `iniciar.bat`?** Los navegadores bloquean los
> módulos ES y la carga del `.wasm` cuando la página viene de `file://`, así
> que doble clic en `index.html` no puede funcionar. Si lo hacés, el visor te
> avisa al pie con la solución.
>
> El `iniciar.bat` levanta `servidor.ps1`, un servidor estático de unas
> pocas líneas escrito en PowerShell, que **ya viene con Windows 10 o
> superior**: no hay que instalar nada (ni Python, ni Node). Si querés,
> cualquier otro servidor estático sirve (`npx serve`, etc.): el contenido de
> la carpeta no cambia, sólo se sirve por `http://`.

Si el puerto 8090 está ocupado, avisame y lo movemos (el backend del proyecto
usa 8001 y AeroRF el 8000/8011). El número vive arriba de `servidor.ps1`.

## Las cinco vistas

| Vista | Fuente | Qué hace |
|---|---|---|
| **Inicio** | `resumen_global` + `resumen_ccte` | Las tarjetas de la app original: registros totales, localidades, provincias, centros (CCTE) y promedio del límite; después el pico máximo registrado con su sello de color; después una tarjeta por cada uno de los **7 CCTE** — los 5 con datos más Buenos Aires y CABA, que la app muestra siempre aunque tengan 0 mediciones, todos en una misma fila — con mediciones, localidades, provincias, pico V/m, pico %, localidad del pico, días y tiempo trabajado. |
| **Localidades** | `resumen_localidad` (si no existe, se recalcula desde `mediciones`) | Resumen por localidad. Buscador en vivo, orden por columna (CCTE, provincia, localidad y máximos) y contador. |
| **Por horarios** | `mediciones` | Medición por medida con fecha y hora. Filtros por localidad, rango de fechas y buscador, con paginación. |
| **Resúmenes** | `resumen_ccte`, `resumen_anual`, `resumen_provincia`, `resumen_provincia_ccte`, `resumen_global` (con respaldo en `mediciones`) | Seis pestañas: **Por centro** (los 7 CCTE, con Buenos Aires y CABA en 0, tiempos trabajados y días de cada uno), **Por mes**, **Por año**, **Por provincia**, **Provincia y CCTE** y **En general** (todos los indicadores de la base en una lista). |
| **Mapa** | `punto_max` (si no existe, el máximo por localidad desde `mediciones`) | Punto máximo de cada localidad coloreado por nivel, con leyenda y tooltip. |

El semáforo de colores y sus etiquetas (`0–1 %` … `≥100 %`) son los mismos que
usa la app principal: están copiados de `backend/app/core/config.py`.

## Exportaciones

- **Excel (.xlsx)** en las cinco vistas: se exporta exactamente lo que se está
  viendo, con los filtros y la búsqueda aplicados. Los números van crudos a la
  celda (se puede seguir ordenando y sumando en Excel) y el nombre del archivo
  incluye la fecha, por ejemplo `localidades_2026-09-30.xlsx`.
- **PNG** en el mapa: descarga la imagen del mapa tal como se ve, con la
  leyenda.

## Qué enviarle a otra persona (por ejemplo, tu jefe)

Son **dos cosas**: la carpeta del visor y la base. Nada más.

1. **La carpeta `visor-rni/`** — comprimida en `.zip` (hay un comando abajo)
   o tal cual. Pesa ~2 MB e incluye todo: librerías, fuentes, el
   `iniciar.bat` y el `servidor.ps1`.
2. **El archivo `rni.db`** (102 MB). Puede ir en cualquier parte de la
   computadora, no hace falta que esté adentro de la carpeta: se arrastra
   sobre la pantalla de carga.

En la computadora de destino hace falta:

- **Windows 10 o superior** (el `iniciar.bat` está escrito para eso, y
  PowerShell —que levanta el servidor— ya viene con el sistema);
- **Chrome, Edge o Firefox** actualizado.

**No hace falta instalar Python ni Node.** Y acá: doble clic en
`iniciar.bat`, arrastrar `rni.db`, listo. Si el puerto 8090 está ocupado, la
consola lo avisa (el número se cambia arriba de `servidor.ps1`).

Para generar el zip desde la consola del proyecto:

```powershell
Compress-Archive -Path visor-rni -DestinationPath visor-rni.zip -Force
```

> El visor no necesita internet ni acceso a la red: las tipografías, las
> librerías y la base son locales. Sólo el mapa pide teselas a OpenStreetMap
> y, si no hay conexión, se dibuja igual sin fondo.

## Cambiar los logos

Van en `assets/`:

- `assets/logoenacom.png` — logo principal (se muestra siempre).
- `assets/logo-secundario.png` — logo opcional: **no hace falta que exista**.
  Si no está (o no carga), la cabecera lo oculta junto a su separador y no se
  rompe nada.

Se pueden usar PNG o JPG; lo único que importa es respetar esos nombres o
ajustar el `src` en `index.html`.

## Actualizar `rni.db`

1. Reemplazá el archivo `rni.db` por la versión nueva (o guardalo donde quieras
   y cargalo desde el disco).
2. Con el visor abierto, botón **Cambiar archivo** en la barra lateral y elegí
   la base nueva. No hace falta recargar la página.

## Carpetas

```
visor-rni/
├── index.html        pantalla única con las cinco vistas
├── iniciar.bat       doble clic: levanta servidor.ps1 y abre el navegador
├── servidor.ps1      servidor estático en PowerShell (puerto 8090)
├── css/              visor.css (estilos) y fuentes.css (@font-face)
├── js/               módulos ES: base, formato, ui, escala, exportar y vistas/
├── fonts/            Space Grotesk, IBM Plex Sans y IBM Plex Mono (woff2)
├── vendor/           sql.js (+ .wasm), SheetJS y Leaflet
├── assets/           logos
└── README.md
```

## Notas

- **Funciona sin internet.** Sólo las teselas del mapa (OpenStreetMap) salen a
  la red: si no hay conexión, el mapa se dibuja igual en un `<canvas>` con
  lat/lon. Las tipografías, las librerías y la base son locales.
- **Sólo lectura:** el visor abre la base en memoria; nunca se escribe en el
  disco, ni siquiera para crear índices.
- Los valores se muestran con el mismo criterio que la app principal: hasta 3
  decimales en V/m y hasta 4 en %, con formato `es-AR`.
