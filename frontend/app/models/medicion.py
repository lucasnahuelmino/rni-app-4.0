"""Modelos de dominio (no son el contrato de la API -- ver app/schemas/ para eso)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Medicion:
    ccte: str
    provincia: str
    localidad: str
    resultado_vm: float | None
    resultado_pct: float | None
    fecha_raw: str | None
    hora_raw: str | None
    fecha_hora: str | None
    anio: int | None
    lat: float | None
    lon: float | None
    lat_raw: str | None
    lon_raw: str | None
    expediente: str | None
    sonda: str | None
    nombre_archivo: str | None
    import_batch_id: int | None
    fecha_carga: str
