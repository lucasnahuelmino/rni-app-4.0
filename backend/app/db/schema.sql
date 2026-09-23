-- Esquema RNI v2 -- ver Fase 2 del diseño para el detalle de cada decisión.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_batches (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_carga           TEXT NOT NULL,
    ccte                  TEXT NOT NULL,
    provincia             TEXT NOT NULL,
    localidad             TEXT NOT NULL,
    expediente            TEXT,
    archivos_procesados   INTEGER NOT NULL DEFAULT 0,
    registros_nuevos      INTEGER NOT NULL DEFAULT 0,
    registros_duplicados  INTEGER NOT NULL DEFAULT 0,
    registros_rechazados  INTEGER NOT NULL DEFAULT 0,
    errores_json          TEXT,
    advertencias_json     TEXT
);

CREATE TABLE IF NOT EXISTS mediciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    ccte                TEXT NOT NULL,
    provincia           TEXT NOT NULL,
    localidad           TEXT NOT NULL,

    resultado_vm        REAL,
    resultado_pct       REAL,

    fecha_raw           TEXT,
    hora_raw            TEXT,
    fecha_hora          TEXT,
    anio                INTEGER,

    lat                 REAL,
    lon                 REAL,
    lat_raw             TEXT,
    lon_raw             TEXT,

    expediente          TEXT,
    sonda               TEXT,
    nombre_archivo      TEXT,

    import_batch_id     INTEGER REFERENCES import_batches(id),
    fecha_carga         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mediciones_ccte         ON mediciones(ccte);
CREATE INDEX IF NOT EXISTS idx_mediciones_provincia    ON mediciones(provincia);
CREATE INDEX IF NOT EXISTS idx_mediciones_localidad    ON mediciones(localidad);
CREATE INDEX IF NOT EXISTS idx_mediciones_anio         ON mediciones(anio);
CREATE INDEX IF NOT EXISTS idx_mediciones_fecha_hora   ON mediciones(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_mediciones_ccte_prov_loc ON mediciones(ccte, provincia, localidad);
CREATE INDEX IF NOT EXISTS idx_mediciones_lat_lon      ON mediciones(lat, lon);
CREATE INDEX IF NOT EXISTS idx_mediciones_batch        ON mediciones(import_batch_id);

CREATE TABLE IF NOT EXISTS resumen_localidad (
    ccte                TEXT NOT NULL,
    provincia           TEXT NOT NULL,
    localidad           TEXT NOT NULL,
    mediciones          INTEGER NOT NULL,
    resultado_max_vm    REAL,
    resultado_max_pct   REAL,
    resultado_prom_pct  REAL,
    fecha_inicio        TEXT,
    fecha_fin           TEXT,
    expedientes         TEXT,
    sondas              TEXT,
    tiempo_trabajado_seg INTEGER NOT NULL DEFAULT 0,
    dias_con_medicion   INTEGER NOT NULL DEFAULT 0,
    actualizado_en      TEXT NOT NULL,
    PRIMARY KEY (ccte, provincia, localidad)
);

CREATE TABLE IF NOT EXISTS resumen_ccte (
    ccte                TEXT PRIMARY KEY,
    mediciones          INTEGER NOT NULL,
    localidades         INTEGER NOT NULL,
    provincias          INTEGER NOT NULL,
    resultado_max_vm    REAL,
    resultado_max_pct   REAL,
    localidad_max       TEXT,
    tiempo_trabajado_seg INTEGER NOT NULL DEFAULT 0,
    dias_con_medicion   INTEGER NOT NULL DEFAULT 0,
    actualizado_en      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resumen_provincia (
    provincia           TEXT PRIMARY KEY,
    mediciones          INTEGER NOT NULL,
    localidades         INTEGER NOT NULL,
    cctes               INTEGER NOT NULL,
    resultado_max_vm    REAL,
    resultado_max_pct   REAL,
    localidad_max       TEXT,
    actualizado_en      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resumen_anual (
    anio                INTEGER PRIMARY KEY,
    mediciones          INTEGER NOT NULL,
    localidades         INTEGER NOT NULL,
    provincias          INTEGER NOT NULL,
    cctes               INTEGER NOT NULL,
    resultado_max_vm    REAL,
    resultado_max_pct   REAL,
    actualizado_en      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resumen_provincia_ccte (
    provincia           TEXT NOT NULL,
    ccte                TEXT NOT NULL,
    localidades         INTEGER NOT NULL,
    mediciones          INTEGER NOT NULL,
    actualizado_en      TEXT NOT NULL,
    PRIMARY KEY (provincia, ccte)
);

CREATE TABLE IF NOT EXISTS resumen_mensual (
    mes                 TEXT PRIMARY KEY,
    mediciones          INTEGER NOT NULL,
    actualizado_en      TEXT NOT NULL
);

-- Punto "máximo" por localidad y año, precalculado.
--
-- /api/map?modo=max_localidad tiene que devolver, para cada localidad, el de
-- mayor resultado_pct. En vivo sobre las 219.818 filas de `mediciones` eso es
-- una window function que tarda 2.756 ms (medido contra la base real) y es
-- justamente la carga por defecto del mapa. Con esta tabla la lectura baja a
-- ~0.7 ms; el costo de construirla queda del lado del escritor (2,8 s una vez
-- por arranque/recalculo total, 0,8-384 ms por localidad tocada en un import).
--
-- La clave es (anio, ccte, provincia, localidad) y NO solo la localidad,
-- porque el endpoint acepta filtro `anio`: sin el año en la clave no habría
-- forma de servirlo sin releer `mediciones`. Hoy son 62 filas.
--
-- `id` es el `mediciones.id` del punto elegido. Además de desempatar (en la
-- base real Las Heras tiene 8 filas con exactamente el mismo resultado_pct,
-- así que sin `id` el punto del mapa podía cambiar entre renders) permite
-- comparar la tabla contra la query original en los tests.
CREATE TABLE IF NOT EXISTS punto_max (
    anio                INTEGER NOT NULL,
    ccte                TEXT NOT NULL,
    provincia           TEXT NOT NULL,
    localidad           TEXT NOT NULL,
    id                  INTEGER NOT NULL,
    lat                 REAL,
    lon                 REAL,
    resultado_vm        REAL,
    resultado_pct       REAL,
    PRIMARY KEY (anio, ccte, provincia, localidad)
);

-- KPIs nacionales SIN filtros, precalculados: una sola fila (por eso el
-- CHECK, no hay forma de que queden dos).
--
-- El agregado en vivo sobre `mediciones` tarda 590 ms y es la carga del
-- dashboard (GET /api/kpis sin parámetros = 532 ms medidos). Con filtros no
-- existe equivalente precalculado exacto -- haría falta una tabla por
-- combinación ccte x provincia x anio -- así que kpis_service solo usa esta
-- fila cuando no vino ningún filtro.
--
-- `pico_id` guarda el `mediciones.id` del pico (no solo el valor) para poder
-- traer el detalle en una búsqueda por clave primaria y para que el pico sea
-- determinista entre el atajo y el agregado en vivo.
CREATE TABLE IF NOT EXISTS resumen_global (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    registros_totales   INTEGER NOT NULL,
    localidades         INTEGER NOT NULL,
    provincias          INTEGER NOT NULL,
    cctes               INTEGER NOT NULL,
    promedio_pct        REAL,
    pico_vm             REAL,
    pico_id             INTEGER,
    actualizado_en      TEXT NOT NULL
);
