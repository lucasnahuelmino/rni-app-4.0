from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_db
from app.schemas.map import DiagnosticoResponse
from app.services import diagnostics as diagnostics_service

router = APIRouter()


@router.get("/diagnostics", response_model=DiagnosticoResponse)
def get_diagnostics(conn=Depends(get_db)):
    return diagnostics_service.obtener_diagnostico(conn)
