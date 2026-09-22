"""Query params compartidos por todos los endpoints filtrables."""
from __future__ import annotations

from fastapi import Query
from pydantic import BaseModel


class FiltrosQuery(BaseModel):
    ccte: list[str] | None = None
    provincia: list[str] | None = None
    anio: list[int] | None = None


def filtros_query(
    ccte: list[str] | None = Query(default=None),
    provincia: list[str] | None = Query(default=None),
    anio: list[int] | None = Query(default=None),
) -> FiltrosQuery:
    return FiltrosQuery(ccte=ccte, provincia=provincia, anio=anio)
