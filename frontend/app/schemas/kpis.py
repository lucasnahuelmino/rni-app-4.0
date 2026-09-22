from __future__ import annotations

from pydantic import BaseModel


class PicoMaximo(BaseModel):
    localidad: str | None = None
    provincia: str | None = None
    ccte: str | None = None
    resultado_vm: float | None = None
    resultado_pct: float | None = None
    expediente: str | None = None


class KpisResponse(BaseModel):
    registros_totales: int
    localidades: int
    provincias: int
    cctes: int
    promedio_pct: float | None
    pico_maximo: PicoMaximo | None
