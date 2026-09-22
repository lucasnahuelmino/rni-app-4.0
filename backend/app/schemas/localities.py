from __future__ import annotations

from pydantic import BaseModel


class CcteSummaryItem(BaseModel):
    ccte: str
    mediciones: int
    resultado_max_vm: float | None = None
    resultado_max_pct: float | None = None
    localidad_max: str | None = None


class LocalidadItem(BaseModel):
    ccte: str
    provincia: str
    localidad: str
    mediciones: int
    resultado_max_vm: float | None = None
    resultado_max_pct: float | None = None
    resultado_prom_pct: float | None = None
    fecha_inicio: str | None = None
    fecha_fin: str | None = None


class TopLocalidadItem(BaseModel):
    localidad: str
    provincia: str
    ccte: str
    valor: float
    metric: str
