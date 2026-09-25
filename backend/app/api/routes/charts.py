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
def get_monthly_trend(filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    """Mediciones por mes.

    Sin filtros lee `resumen_mensual`, que se recalcula en cada import: es la
    misma tabla que usa el resto del sistema y cuesta ~1 ms.

    Con filtros (CCTE / provincia / año) hay que agrupar `mediciones` en el
    momento, porque `resumen_mensual` no guarda ese desglose -- es una tabla
    de una sola dimensión (el mes). El criterio es el mismo que usa
    `recalcular_resumen_mensual` (`substr(fecha_hora, 1, 7) <> ''`), así que
    las dos rutas cuentan igual: sin filtros devuelven exactamente los mismos
    números, que es lo que verifica el test de esta ruta.

    Ojo con el `<> ''`: en SQL `NULL <> ''` es NULL, no TRUE, así que las filas
    con `fecha_hora` nula quedan afuera solas -- igual que en el precalculado,
    donde `substr(NULL) = ?` tampoco se cumple. Sin eso, un mes nulo aparecería
    como un grupo fantasma y la suma con filtro no daría la del resumen.
    """
    if not (filtros.ccte or filtros.provincia or filtros.anio):
        cur = conn.execute("SELECT mes, mediciones FROM resumen_mensual ORDER BY mes")
        return [dict(r) for r in cur.fetchall()]

    where, params = construir_where(filtros.ccte, filtros.provincia, filtros.anio)
    # `where` viene con su "WHERE " adelante (o vacío), por eso el separador
    # cambia: con filtro va "AND", sin filtro hay que poner "WHERE".
    separador = " AND " if where else "WHERE "
    cur = conn.execute(
        f"""SELECT substr(fecha_hora, 1, 7) AS mes, COUNT(*) AS mediciones
            FROM mediciones {where}{separador}substr(fecha_hora, 1, 7) <> ''
            GROUP BY mes ORDER BY mes""",
        params,
    )
    return [dict(r) for r in cur.fetchall()]
