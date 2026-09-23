from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_db
from app.schemas.filters import FiltrosQuery, filtros_query
from app.db.repositories.mediciones_repo import construir_where

router = APIRouter()


@router.get("/histogram")
def get_histogram(campo: str = "resultado_pct", bins: int = Query(20, ge=1, le=500),
                   filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    campo = "resultado_pct" if campo not in ("resultado_pct", "resultado_vm") else campo
    where, params = construir_where(filtros.ccte, filtros.provincia, filtros.anio)
    limites = conn.execute(f"SELECT MIN({campo}) AS lo, MAX({campo}) AS hi FROM mediciones {where}", params).fetchone()
    if limites["lo"] is None:
        return {"campo": campo, "bins": []}

    lo, hi = limites["lo"], limites["hi"]
    ancho = (hi - lo) / bins if hi > lo else 1
    condicion_extra = f"{campo} IS NOT NULL"
    where_full = f"{where} AND {condicion_extra}" if where else f"WHERE {condicion_extra}"

    cur = conn.execute(
        f"""SELECT CAST(({campo} - ?) / ? AS INTEGER) AS bin_idx, COUNT(*) AS n
            FROM mediciones {where_full}
            GROUP BY bin_idx ORDER BY bin_idx""",
        [lo, ancho] + params,
    )
    bins_resultado = [{"desde": lo + r["bin_idx"] * ancho, "hasta": lo + (r["bin_idx"] + 1) * ancho, "n": r["n"]}
                       for r in cur.fetchall()]
    return {"campo": campo, "bins": bins_resultado}


@router.get("/monthly-trend")
def get_monthly_trend(conn=Depends(get_db)):
    cur = conn.execute("SELECT mes, mediciones FROM resumen_mensual ORDER BY mes")
    return [dict(r) for r in cur.fetchall()]
