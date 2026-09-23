from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_db
from app.schemas.filters import FiltrosQuery, filtros_query
from app.services import tiempos as tiempos_service

router = APIRouter()


@router.get("/tiempos/diario")
def get_tiempo_diario(ccte: str, provincia: str, localidad: str, conn=Depends(get_db)):
    """Desglose día por día (fecha, inicio, fin, duración) de UNA localidad
    -- usado en Gestión."""
    return tiempos_service.tiempo_diario_localidad(conn, ccte, provincia, localidad)


@router.get("/tiempos/mensual")
def get_tiempo_mensual(
    ccte: str | None = None, provincia: str | None = None, localidad: str | None = None,
    filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db),
):
    """Desglose mensual (mes, tiempo trabajado, días con medición).

    Si se pasan ccte/provincia/localidad como query params sueltos (para el
    caso de Gestión, una sola localidad puntual), tienen prioridad sobre los
    filtros globales -- si no, se usan los filtros compartidos (para el
    panel de Gráficos > Operativo)."""
    if ccte or provincia or localidad:
        efectivos = FiltrosQuery(
            ccte=[ccte] if ccte else None,
            provincia=[provincia] if provincia else None,
            localidad=[localidad] if localidad else None,
            anio=filtros.anio,
        )
    else:
        efectivos = filtros
    return tiempos_service.tiempo_mensual(conn, efectivos)
