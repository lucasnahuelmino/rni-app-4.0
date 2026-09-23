from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.calculations.dates import format_timedelta_long
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


def _con_tiempo_formateado(row: dict) -> dict:
    row = dict(row)
    row["tiempo_trabajado_fmt"] = format_timedelta_long(row.get("tiempo_trabajado_seg"))
    # `expedientes`/`sondas` se guardan como string separado por comas
    # (ya deduplicado en services/statistics.py) -- acá se exponen también
    # como lista, para que el frontend no tenga que hacer el split.
    row["expedientes_lista"] = [e for e in (row.get("expedientes") or "").split(",") if e]
    row["sondas_lista"] = [s for s in (row.get("sondas") or "").split(",") if s]
    return row


@router.get("/localities")
def get_localities(filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    filas = resumen_repo.listar_resumen_localidad(
        conn, ccte=filtros.ccte, provincia=filtros.provincia, localidad=filtros.localidad
    )
    return [_con_tiempo_formateado(f) for f in filas]


@router.get("/localities/{localidad}")
def get_locality_detail(localidad: str, ccte: str, provincia: str, conn=Depends(get_db)):
    filas = conn.execute(
        "SELECT * FROM resumen_localidad WHERE ccte = ? AND provincia = ? AND localidad = ?",
        (ccte, provincia, localidad),
    ).fetchone()
    if not filas:
        raise HTTPException(status_code=404, detail="Localidad no encontrada")
    return _con_tiempo_formateado(dict(filas))


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
def get_top_localities(metric: str = "resultado_max_vm",
                        limit: int = Query(5, ge=1, le=500),
                        conn=Depends(get_db)):
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
