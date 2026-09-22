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
