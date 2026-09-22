from __future__ import annotations

from pydantic import BaseModel


class PuntoMapa(BaseModel):
    id: int
    lat: float
    lon: float
    resultado_vm: float | None
    resultado_pct: float | None
    localidad: str
    ccte: str


class MapaResponse(BaseModel):
    puntos: list[PuntoMapa]
    total_disponible: int
    truncado: bool


class DiagnosticoResponse(BaseModel):
    total_registros: int
    fechas_vacias: int
    fechas_no_parseables: int
    horas_vacias: int
    coordenadas_faltantes: int
    coordenadas_fuera_de_rango: int
    resultados_faltantes: int
    duplicados_probables: int
