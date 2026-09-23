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


def _concatenar(where: str, condiciones: list[str]) -> str:
    """Pega condiciones extra al `where` que devuelve construir_where.

    Ese `where` puede venir vacío (sin filtros) o ya con su "WHERE". Unir a
    ciegas con " AND " dejaría "AND lat IS NOT NULL ..." sin WHERE cuando no
    hay filtros, y en cambio sin el " AND " sobraría cuando sí los hay.
    """
    if not condiciones:
        return where
    if not where:
        return "WHERE " + " AND ".join(condiciones)
    return where + " AND " + " AND ".join(condiciones)


# Un único SQL para los DOS caminos de `modo=max_localidad` (la tabla
# precalculada `punto_max` y el respaldo sobre `mediciones`), para que no
# puedan divergir nunca en el criterio con el que se elige el punto.
#
# El desempate `id ASC` no es cosmético: en la base real Las Heras tiene 8
# filas con exactamente el mismo `resultado_pct` (Río Gallegos 4, Río Primero
# y Choele Choel 2). Sin él, decide el orden en que SQLite devuelve las filas
# y el punto del popup podía cambiar entre renders.
#
# El filtro (bbox, pct_min, anio...) va DENTRO del subquery y `rn` afuera:
# el ganador se elige entre los puntos que PASAN el filtro, no al revés.
# Ese es el orden que ya tenía la query original antes de precalcular.
_SQL_MAX_LOCALIDAD = """
    SELECT id, lat, lon, resultado_vm, resultado_pct, provincia, localidad, ccte
    FROM (
        SELECT id, lat, lon, resultado_vm, resultado_pct, provincia, localidad, ccte,
               ROW_NUMBER() OVER (
                   PARTITION BY ccte, provincia, localidad
                   ORDER BY resultado_pct DESC, id ASC
               ) AS rn
        FROM {tabla}
        {where}
    )
    WHERE rn = 1
    -- Orden fijo. Sin él, el orden de salida depende de cómo SQLite
    -- materialice la window function, y los dos caminos podían devolver los
    -- mismos puntos en distinto orden.
    ORDER BY ccte, provincia, localidad
"""


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
    function (`ROW_NUMBER() OVER (...)`) sobre TODA la tabla, porque eso
    obliga a materializar y ordenar las 219.818 filas: medida contra la base
    real, tarda 1.366 ms contra los ~400 ms de esto.

    (El modo `max_localidad` SIEMPRE usó una window function, pero ya no
    sobre `mediciones`: la sirve desde la tabla precalculada `punto_max`,
    de 62 filas. Ver `_SQL_MAX_LOCALIDAD`.)

    Las queries individuales de abajo fuerzan `idx_mediciones_ccte_prov_loc`;
    ver el comentario ahí, es la diferencia entre 0.4 s y 20 s. La
    agrupación de arriba lo fuerza por la misma razón.
    """
    grupos = [
        dict(g)
        for g in conn.execute(
            # `INDEXED BY` también acá, por la misma razón que en las queries
            # por localidad de más abajo: con un bbox en el WHERE, SQLite
            # prefiere idx_mediciones_lat_lon porque el rango de lat parece
            # más selectivo, y entonces el GROUP BY termina recorriendo la
            # tabla entera buscando la localidad. Con el índice de la clave
            # de agrupación las filas salen ya ordenadas y no hace falta
            # un temp store. Medido contra la base real: con bbox la
            # agrupación pasó de 1.066 a 410 ms (2,60x); sin bbox la
            # diferencia es nula (353 -> 347 ms), así que no cuesta nada.
            #
            # OJO: esto NO se puede copiar al COUNT(*) del final: medido,
            # empeora de 116 a 328 ms, porque ahí no hay agrupación que
            # ordenar y el recorrido de índice con lookups solo suma.
            f"SELECT ccte, provincia, localidad, COUNT(*) AS n "
            f"FROM mediciones INDEXED BY idx_mediciones_ccte_prov_loc {where_full} "
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
      density. No trunca (como mucho, una fila por localidad). Se lee de
      la tabla precalculada `punto_max`, de 62 filas: la query equivalente
      sobre `mediciones` tarda 2.756 ms con bbox y era la carga por
      defecto del mapa, esta baja a ~0.7 ms. Si `punto_max` está vacía
      (ver statistics.poblar_tablas_derivadas) cae a la query original,
      más lenta pero idéntica.

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

    # Condiciones que comparten los tres caminos (muestra proporcional,
    # max_localidad precalculado y max_localidad de respaldo). Van aparte de
    # `lat/lon IS NOT NULL` porque `punto_max` solo guarda filas que ya tienen
    # coordenadas: ahí ese predicado es redundante.
    compartidas: list[str] = []

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
        compartidas.append("lat BETWEEN ? AND ?")
        compartidas.append("lon BETWEEN ? AND ?")
        params += [lat_min, lat_max, lon_min, lon_max]

    if pct_min is not None:
        compartidas.append("resultado_pct >= ?")
        params.append(pct_min)

    # El mismo `params` sirve para los dos caminos: `lat/lon IS NOT NULL` no
    # llevan parámetros, así que las listas de valores quedan idénticas.
    where_full = _concatenar(where, ["lat IS NOT NULL", "lon IS NOT NULL"] + compartidas)
    where_pm = _concatenar(where, compartidas)

    if modo == "max_localidad":
        # Un punto por localidad: el de mayor resultado_pct. Se resuelve con
        # una window function en SQL (no en Pandas) para no traer las 219k
        # filas al backend y filtrar ahí -- justamente lo que la Auditoría
        # Fase 1 pidió evitar -- y corriendo sobre `punto_max` en vez de
        # sobre `mediciones`, que es lo que lleva esto de 2.756 ms a ~0.7 ms.
        #
        # `punto_max` vacía no significa "no hay datos": puede ser una base
        # a la que recién se le aplicó el DDL. En ese caso se cae al mismo
        # SQL (un solo template, `_SQL_MAX_LOCALIDAD`) con la otra tabla, así
        # que lo único que cambia es el costo, nunca el resultado.
        if conn.execute("SELECT 1 FROM punto_max LIMIT 1").fetchone():
            tabla, condiciones = "punto_max", where_pm
        else:
            tabla, condiciones = "mediciones", where_full
        cur = conn.execute(_SQL_MAX_LOCALIDAD.format(tabla=tabla, where=condiciones), params)
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
