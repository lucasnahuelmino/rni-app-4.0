from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import MAX_PUNTOS_MAPA
from app.core.deps import get_db
from app.db.repositories.mediciones_repo import construir_where
from app.schemas.filters import FiltrosQuery, filtros_query

router = APIRouter()


@router.get("/map")
def get_map(bbox: str | None = None, pct_min: float | None = None, modo: str = "todos",
            filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    """`bbox` = "lat_min,lat_max,lon_min,lon_max".

    `modo`:
    - "todos" (default): todos los puntos que matchean los filtros, truncado
      a MAX_PUNTOS_MAPA con aviso explícito de que es una muestra (Auditoría
      Fase 1: nunca se debe interpretar un LIMIT como "todos los puntos"
      sin decirlo).
    - "max_localidad": un solo punto por localidad -- el de mayor
      resultado_pct -- para poder ver el país completo sin street-level
      density. No trunca (ya es liviano: como mucho, una fila por
      localidad).

    Los filtros (incluido `localidad`, para buscar un punto puntual) se
    aplican en SQL ANTES del límite/muestreo, nunca después.
    """
    if modo not in ("todos", "max_localidad"):
        raise HTTPException(status_code=400, detail="modo debe ser 'todos' o 'max_localidad'")

    where, params = construir_where(filtros.ccte, filtros.provincia, filtros.anio, filtros.localidad)
    extra = ["lat IS NOT NULL", "lon IS NOT NULL"]

    if bbox:
        # Sin esta validación, un bbox malformado ("a,b" o "1,2,3") llegaba
        # como ValueError/unpacking error y salía como 500 en vez de 400.
        partes = [p.strip() for p in bbox.split(",")]
        if len(partes) != 4:
            raise HTTPException(
                status_code=400,
                detail="bbox debe ser 'lat_min,lat_max,lon_min,lon_max' (4 valores)",
            )
        try:
            lat_min, lat_max, lon_min, lon_max = (float(p) for p in partes)
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox debe contener 4 números") from None
        extra.append("lat BETWEEN ? AND ?")
        extra.append("lon BETWEEN ? AND ?")
        params += [lat_min, lat_max, lon_min, lon_max]

    if pct_min is not None:
        extra.append("resultado_pct >= ?")
        params.append(pct_min)

    where_full = (where + " AND " + " AND ".join(extra)) if where else ("WHERE " + " AND ".join(extra))

    if modo == "max_localidad":
        # Un punto por localidad: el de mayor resultado_pct. Se resuelve
        # con una window function en SQL (no en Pandas) para no traer las
        # 219k filas al backend y filtrar ahí -- justamente lo que la
        # Auditoría Fase 1 pidió evitar.
        cur = conn.execute(
            f"""
            SELECT id, lat, lon, resultado_vm, resultado_pct, localidad, ccte
            FROM (
                SELECT id, lat, lon, resultado_vm, resultado_pct, localidad, ccte,
                       ROW_NUMBER() OVER (
                           PARTITION BY ccte, provincia, localidad
                           ORDER BY resultado_pct DESC
                       ) AS rn
                FROM mediciones
                {where_full}
            )
            WHERE rn = 1
            """,
            params,
        )
        puntos = [dict(r) for r in cur.fetchall()]
        return {"puntos": puntos, "total_disponible": len(puntos), "truncado": False, "modo": modo}

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
        "modo": modo,
    }
