from __future__ import annotations

from pydantic import BaseModel


class ImportBatchResponse(BaseModel):
    id: int
    fecha_carga: str
    ccte: str
    provincia: str
    localidad: str
    expediente: str | None
    archivos_procesados: int
    registros_nuevos: int
    registros_duplicados: int
    registros_rechazados: int
    errores: list[dict] = []
    advertencias: list[dict] = []
