from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import charts, colors, diagnostics, imports, kpis, localities, map as map_routes, reports, tiempos
from app.db.database import get_connection, init_schema
from app.services import measurements, statistics

app = FastAPI(title="RNI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajustar a los orígenes reales del frontend Vue en producción
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_schema()
    # Crea las tablas (si hacía falta) y las llena si nacieron vacías: a una
    # base existente solo se le aplica el DDL nuevo, que usa IF NOT EXISTS y
    # por eso no escribe datos. Ver services/statistics.poblar_tablas_derivadas.
    with get_connection() as conn:
        # Primero la sanitización: pone en positivo los resultado_vm
        # negativos que traía la carga legacy (la sonda reporta -0.001 por
        # debajo de su piso). Idempotente y no recalcula nada -- ver el
        # docstring. Imprime solo si encontró algo, para que un arranque
        # normal quede en silencio.
        corregidas = measurements.sanear_signo_resultados(conn)
        if corregidas:
            print(f"[startup] resultado_vm negativos pasados a positivo: {corregidas}")
        statistics.poblar_tablas_derivadas(conn)


app.include_router(kpis.router, prefix="/api", tags=["kpis"])
app.include_router(localities.router, prefix="/api", tags=["localities"])
app.include_router(charts.router, prefix="/api", tags=["charts"])
app.include_router(map_routes.router, prefix="/api", tags=["map"])
app.include_router(diagnostics.router, prefix="/api", tags=["diagnostics"])
app.include_router(imports.router, prefix="/api", tags=["imports"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(tiempos.router, prefix="/api", tags=["tiempos"])
app.include_router(colors.router, prefix="/api", tags=["colors"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
