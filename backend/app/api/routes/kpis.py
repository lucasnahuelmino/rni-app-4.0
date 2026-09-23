from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_db
from app.schemas.filters import FiltrosQuery, filtros_query
from app.schemas.kpis import KpisResponse
from app.services import kpis_service

router = APIRouter()

# Columnas numéricas por las que se puede ordenar el resumen por CCTE. Un
# whitelist cerrado hace falta: `resto.sort(key=...)` mezcla str con 0 si
# llega una columna de texto y revienta con TypeError (500).
COLUMNAS_ORDEN_CCTE = (
    "mediciones", "localidades", "provincias",
    "resultado_max_vm", "resultado_max_pct",
    "tiempo_trabajado_seg", "dias_con_medicion",
)


@router.get("/kpis", response_model=KpisResponse)
def get_kpis(filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    return kpis_service.obtener_kpis(conn, filtros)


@router.get("/ccte-summary")
def get_ccte_summary(orden: str = "mediciones", conn=Depends(get_db)):
    if orden not in COLUMNAS_ORDEN_CCTE:
        raise HTTPException(
            status_code=400,
            detail=f"orden debe ser una de: {', '.join(COLUMNAS_ORDEN_CCTE)}",
        )
    return kpis_service.obtener_ccte_summary(conn, orden=orden)
