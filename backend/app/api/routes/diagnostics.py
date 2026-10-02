from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_db
from app.schemas.map import DiagnosticoResponse
from app.services import diagnostics as diagnostics_service

router = APIRouter()


@router.get("/diagnostics", response_model=DiagnosticoResponse)
def get_diagnostics(conn=Depends(get_db)):
    """Lo cacheado.

    `obtener_diagnostico` son 11 COUNT sobre los 219.818 registros: 1.3 s
    con las páginas en memoria y 33 s la primera vez después de reiniciar.
    La vista de Carga lo pide seguido y los números sólo cambian si cambian
    los datos, así que va por el wrapper con caché (ver el service).
    """
    return diagnostics_service.obtener_diagnostico_cacheado(conn)
