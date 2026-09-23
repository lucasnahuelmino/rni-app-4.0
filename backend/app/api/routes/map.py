from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import MAX_PUNTOS_MAPA
from app.core.deps import get_db
from app.db.repositories.mediciones_repo import construir_where
from app.schemas.filters import FiltrosQuery, filtros_query

router = APIRouter()

# `provincia` va en el payload porque el nombre de localidad no alcanza para
# identificar un punto: hay DOS "San Pedro" (Catamarca y Santiago del Estero).
# Sin provincia, los dos popups del mapa eran literalmente indistinguibles.
_CASILLEROS = "id, lat, lon, resultado_vm, resultado_pct, provincia, localidad, ccte"


def _muestra_proporcional(conn, where_full: str, params: list, tope: int) -> list[dict]:
    """Trae hasta `tope` puntos repartidos entre TODAS las localidades.

    Un `SELECT ... LIMIT 5000` sin ORDER BY no garantiza nada: SQLite
    devuelve las filas en el orden en que las encuentra, que en la práctica
    es el orden de insercion, asi que las primeras 5000 salian todas del
    mismo lote de importacion. Con la base actual eso eran exactamente 3
    localidades (Puerto Deseado 2712, Comandante Luis Piedrabuena 1733,
    Puerto San Julian 555) de las 61 que existen: el mapa mostraba un
    puñado de puntos en Santa Cruz y el resto del país en blanco.

    Cada localidad recibe una cuota proporcional a su tamaño con piso 1.
    El piso es lo que garantiza que ninguna quede afuera, y como
    `tope * n // total >= n` siempre que `total <= tope`, cuando todo entra
    cada cuota supera al grupo y la query devuelve la localidad COMPLETA:
    o sea que no muestrea cuando no hace falta, solo recorta cuando pasa.

    Se resuelve con una query por localidad en vez de con una window
    function (`ROW_NUMBER() OVER (...)`) porque esa opcion obliga a
    materializar y ordenar las 219.818 filas: medida contra la base real,
    tarda 1.366 ms contra los ~400 ms de esto, y el modo
    `max_localidad` -- que si usa la window function-- tarda 1.862 ms.

    Las queries individuales fuerzan `idx_mediciones_ccte_prov_loc`;
    ver el comentario ahí abajo, es la diferencia entre 0.4 s y 20 s.
    """
    grupos = [
        dict(g)
        for g in conn.execute(
            f"SELECT ccte, provincia, localidad, COUNT(*) AS n "
            f"FROM mediciones {where_full} "
            f"GROUP BY ccte, provincia, localidad",
            params,
        ).fetchall()
    ]
    if not grupos:
        return []

    total = sum(g["n"] for g in grupos)

    if len(grupos) > tope:
        # Mas localidades que puntos permitidos: no alcanza ni un punto por
        # localidad, asi que el reparto proporcional ya no puede cumplir su
        # promesa y hacer una query por localidad seria un desastre.
        cur = conn.execute(
            f"SELECT {_CASILLEROS} FROM mediciones {where_full} LIMIT ?",
            params + [tope],
        )
        return [dict(r) for r in cur.fetchall()]

    puntos: list[dict] = []
    for g in grupos:
        cuota = max(1, tope * g["n"] // total)
        # `INDEXED BY` no es cosmético. Con un bbox en el WHERE, SQLite elige
        # idx_mediciones_lat_lon porque el rango de lat parece más selectivo,
        # y entonces cada una de estas queries recorre casi la tabla entera
        # buscando la localidad: contra la base real, con el bbox de país
        # completo las 61 queries pasaron de 63 ms a 18.648 ms (el endpoint
        # entero se iba a 20 s). Forzado el índice, el bbox queda como filtro
        # residual sobre las filas de ESA localidad, que es justo lo que se
        # quiere. Sin bbox la diferencia es nula, y con bbox chico también.
        #
        # El índice existe en schema.sql y init_schema() corre en el startup,
        # así que no se puede encontrar con que falte.
        cur = conn.execute(
            f"SELECT {_CASILLEROS} FROM mediciones "
            f"INDEXED BY idx_mediciones_ccte_prov_loc "
            f"{where_full} "
            f"AND ccte = ? AND provincia = ? AND localidad = ? "
            f"LIMIT ?",
            params + [g["ccte"], g["provincia"], g["localidad"], cuota],
        )
        puntos.extend(dict(r) for r in cur.fetchall())

    return puntos[:tope]


@router.get("/map")
def get_map(bbox: str | None = None, pct_min: float | None = None, modo: str = "todos",
            filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    """`bbox` = "lat_min,lat_max,lon_min,lon_max".

    `modo`:
    - "todos" (default): hasta MAX_PUNTOS_MAPA puntos, repartidos entre
      TODAS las localidades que matchean los filtros (muestreo
      proporcional con piso 1 por localidad, ver `_muestra_proporcional`),
      con aviso explícito de que es una muestra cuando no entra todo
      (Auditoría Fase 1: nunca se debe interpretar un LIMIT como "todos
      los puntos" sin decirlo).
    - "max_localidad": un solo punto por localidad -- el de mayor
      resultado_pct -- para poder ver el país completo sin street-level
      density. No trunca (ya es liviano: como mucho, una fila por
      localidad).

    Los filtros (incluido `localidad`, para buscar un punto puntual) se
    aplican en SQL ANTES del límite/muestreo, nunca después.

    El frontend manda `bbox` con el viewport visible en cada `moveend`,
    asi que al hacer zoom la respuesta son los puntos de la zona que se
    esta mirando y no hace falta muestrear: cuando entran todos, cada
    cuota supera al grupo y se devuelve completo.
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
            SELECT id, lat, lon, resultado_vm, resultado_pct, provincia, localidad, ccte
            FROM (
                SELECT id, lat, lon, resultado_vm, resultado_pct, provincia, localidad, ccte,
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

    puntos = _muestra_proporcional(conn, where_full, params, MAX_PUNTOS_MAPA)

    return {
        "puntos": puntos,
        "total_disponible": total_disponible,
        "truncado": total_disponible > len(puntos),
        "modo": modo,
    }
