from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_db
from app.db.repositories import resumen_repo
from app.schemas.filters import FiltrosQuery, filtros_query
from app.services import measurements

router = APIRouter()


class EditarLocalidadRequest(BaseModel):
    ccte: str | None = None
    provincia: str | None = None
    localidad: str | None = None
    expediente: str | None = None


@router.get("/localities")
def get_localities(filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    return resumen_repo.listar_resumen_localidad(conn, ccte=filtros.ccte, provincia=filtros.provincia)


@router.get("/localities/{localidad}")
def get_locality_detail(localidad: str, ccte: str, provincia: str, conn=Depends(get_db)):
    filas = conn.execute(
        "SELECT * FROM resumen_localidad WHERE ccte = ? AND provincia = ? AND localidad = ?",
        (ccte, provincia, localidad),
    ).fetchone()
    if not filas:
        raise HTTPException(status_code=404, detail="Localidad no encontrada")
    return dict(filas)


@router.put("/localities/{localidad}")
def put_locality(localidad: str, ccte: str, provincia: str, body: EditarLocalidadRequest, conn=Depends(get_db)):
    """UPDATE dirigido (no reescribe toda la tabla -- Auditoría Fase 1, hallazgo A8)."""
    nuevos = {k: v for k, v in body.model_dump().items() if v is not None}
    if not nuevos:
        raise HTTPException(status_code=400, detail="No se envió ningún campo para actualizar.")
    filas_afectadas = measurements.editar_metadata_localidad(conn, ccte, provincia, localidad, nuevos)
    if filas_afectadas == 0:
        raise HTTPException(status_code=404, detail="Localidad no encontrada")
    return {"filas_afectadas": filas_afectadas}


@router.delete("/localities/{localidad}")
def delete_locality(localidad: str, ccte: str, provincia: str, conn=Depends(get_db)):
    filas_borradas = measurements.eliminar_localidad(conn, ccte, provincia, localidad)
    if filas_borradas == 0:
        raise HTTPException(status_code=404, detail="Localidad no encontrada")
    return {"filas_borradas": filas_borradas}


@router.get("/top-localities")
def get_top_localities(metric: str = "resultado_max_vm", limit: int = 5, conn=Depends(get_db)):
    columnas_validas = {
        "resultado_max_vm", "resultado_max_pct", "resultado_prom_pct", "mediciones",
    }
    if metric not in columnas_validas:
        raise HTTPException(status_code=400, detail=f"metric debe ser una de {columnas_validas}")

    # `metric` se interpola en el SQL porque SQLite no permite parametrizar
    # nombres de columna con placeholders -- es seguro porque arriba se
    # validó contra una whitelist cerrada, nunca contra input libre.
    cur = conn.execute(
        f"SELECT ccte, provincia, localidad, {metric} AS valor FROM resumen_localidad "
        f"WHERE {metric} IS NOT NULL ORDER BY {metric} DESC LIMIT ?",
        (limit,),
    )
    return [{"metric": metric, **dict(r)} for r in cur.fetchall()]
