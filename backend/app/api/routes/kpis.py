from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_db
from app.schemas.filters import FiltrosQuery, filtros_query
from app.schemas.kpis import KpisResponse
from app.services import kpis_service

router = APIRouter()


@router.get("/kpis", response_model=KpisResponse)
def get_kpis(filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    return kpis_service.obtener_kpis(conn, filtros)


@router.get("/ccte-summary")
def get_ccte_summary(orden: str = "mediciones", conn=Depends(get_db)):
    return kpis_service.obtener_ccte_summary(conn, orden=orden)
