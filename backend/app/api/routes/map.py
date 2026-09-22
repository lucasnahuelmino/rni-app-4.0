from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import MAX_PUNTOS_MAPA
from app.core.deps import get_db
from app.db.repositories.mediciones_repo import construir_where
from app.schemas.filters import FiltrosQuery, filtros_query

router = APIRouter()


@router.get("/map")
def get_map(bbox: str | None = None, pct_min: float | None = None,
            filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    """`bbox` = "lat_min,lat_max,lon_min,lon_max". Siempre se agrega o se
    trunca en backend (Auditoría Fase 1, hallazgo de performance del mapa)."""
    where, params = construir_where(filtros.ccte, filtros.provincia, filtros.anio)
    extra = ["lat IS NOT NULL", "lon IS NOT NULL"]

    if bbox:
        lat_min, lat_max, lon_min, lon_max = map(float, bbox.split(","))
        extra.append("lat BETWEEN ? AND ?")
        extra.append("lon BETWEEN ? AND ?")
        params += [lat_min, lat_max, lon_min, lon_max]

    if pct_min is not None:
        extra.append("resultado_pct >= ?")
        params.append(pct_min)

    where_full = (where + " AND " + " AND ".join(extra)) if where else ("WHERE " + " AND ".join(extra))

    total_disponible = conn.execute(f"SELECT COUNT(*) AS n FROM mediciones {where_full}", params).fetchone()["n"]

    cur = conn.execute(
        f"""SELECT id, lat, lon, resultado_vm, resultado_pct, localidad, ccte
            FROM mediciones {where_full} LIMIT ?""",
        params + [MAX_PUNTOS_MAPA],
    )
    puntos = [dict(r) for r in cur.fetchall()]

    return {
        "puntos": puntos,
        "total_disponible": total_disponible,
        "truncado": total_disponible > len(puntos),
    }
