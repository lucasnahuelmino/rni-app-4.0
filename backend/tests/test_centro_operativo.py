"""Endpoints nuevos/amendiados del Centro operativo.

Son los que sostienen la fusión de Gestión y Gráficos en una sola sección:
`/tiempos/diario-ccte` (nuevo), `/top-localities` (ahora filtrable por CCTE)
y `/monthly-trend` (que no aceptaba ningún filtro). Los de tiempos por
localidad y el mensual global siguen cubiertos en
test_mapa_tiempos_colores.py.
"""
import pandas as pd

from app.schemas.filters import FiltrosQuery
from app.services import import_service, tiempos as tiempos_service


def _df_dos_dias(lat: float = -34.6037, lon: float = -58.3816) -> pd.DataFrame:
    """Dos días de mediciones: 20/03 10:00-10:30 (1800 s) y
    21/03 09:00-09:20 (1200 s). Es el mismo fixture que usa
    test_mapa_tiempos_colores.py, copiado para que este archivo se pueda
    leer sin tener que importar otro módulo de tests."""
    return pd.DataFrame({
        "Resultado": ["1,5", "3.2", "10", "2.1"],
        "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025", "21/03/2025"],
        "Hora": ["10:00:00", "10:30:00", "09:00:00 a.m.", "09:20:00 a.m."],
        "Lat": [lat, lat + 0.0003, lat + 0.0013, lat + 0.0023],
        "Lon": [lon, lon - 0.0004, lon - 0.0014, lon - 0.0024],
        "Sonda": ["S1", "S1", "S2", "S2"],
    })


def test_tiempo_diario_ccte_agrupa_por_ccte_y_coincide_con_el_mensual(conn):
    """El desglose diario de un centro agrupa por archivo+día sobre TODAS
    las filas del CCTE: el mismo criterio que `tiempo_mensual`, a otro
    nivel. Por eso la suma de uno da exactamente lo que da el otro -- una
    sola fórmula vista desde dos alturas.

    NO se compara contra `resumen_ccte.tiempo_trabajado_seg`: ese agrupa
    por localidad antes de sumar y en general no coincide (medido en
    `tiempo_diario_ccte`). Acá además coincidiría, porque cada localidad
    usa un archivo distinto, así que probarlo probaría nada.
    """
    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Córdoba Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias(lat=-31.42, lon=-64.19))],
    )
    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Villa Allende",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias(lat=-31.29, lon=-64.29))],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("c.xlsx", _df_dos_dias(lat=-24.78, lon=-65.41))],
    )

    diario = tiempos_service.tiempo_diario_ccte(conn, "Córdoba")

    # Dos archivos con dos días cada uno y nombres distintos -> 4 grupos.
    # Los de Salta no se cuelan: el filtro es por ccte.
    assert len(diario) == 4
    assert sum(f["duracion_seg"] for f in diario) == (1800 + 1200) * 2
    assert {f["fecha"] for f in diario} == {"2025-03-20", "2025-03-21"}
    assert all(f["duracion_fmt"] for f in diario)

    # El invariante: diario y mensual suman lo mismo.
    mensual = tiempos_service.tiempo_mensual(conn, FiltrosQuery(ccte=["Córdoba"]))
    assert sum(f["tiempo_trabajado_seg"] for f in mensual) == sum(
        f["duracion_seg"] for f in diario
    )


def test_tiempo_diario_ccte_sin_datos_devuelve_vacio(conn):
    """Un CCTE que no existe no es un error: es una lista vacía. Lo mismo
    que Buenos Aires/CABA, que están en el catálogo con 0 mediciones."""
    assert tiempos_service.tiempo_diario_ccte(conn, "No Existe") == []
    assert tiempos_service.tiempo_diario_ccte(conn, "Buenos Aires") == []


def test_top_localities_acepta_filtro_ccte(conn):
    """Antes `/top-localities` no filtraba nada: siempre el top de todo el
    país, sin importar qué CCTE se estaba mirando."""
    from app.api.routes.localities import get_top_localities

    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Córdoba Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias())],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias())],
    )

    todo = get_top_localities(metric="mediciones", limit=10,
                              filtros=FiltrosQuery(), conn=conn)
    assert len(todo) == 2

    solo = get_top_localities(metric="mediciones", limit=10,
                              filtros=FiltrosQuery(ccte=["Salta"]), conn=conn)
    assert len(solo) == 1
    assert solo[0]["ccte"] == "Salta"
    # Misma forma de respuesta que antes: el frontend no se entera.
    assert set(solo[0]) == {"metric", "ccte", "provincia", "localidad", "valor"}

    # El orden por la columna elegida se mantiene con el filtro puesto.
    acotado = get_top_localities(metric="mediciones", limit=1,
                                 filtros=FiltrosQuery(), conn=conn)
    assert len(acotado) == 1
    assert acotado[0]["valor"] == max(f["valor"] for f in todo)


def test_top_localities_valida_la_metrica(conn):
    import pytest
    from fastapi import HTTPException

    from app.api.routes.localities import get_top_localities

    with pytest.raises(HTTPException) as exc:
        get_top_localities(metric="no_existe", limit=10,
                           filtros=FiltrosQuery(), conn=conn)
    assert exc.value.status_code == 400


def test_top_localities_sin_filas_devuelve_lista_vacia(conn):
    from app.api.routes.localities import get_top_localities

    assert get_top_localities(metric="resultado_max_vm", limit=5,
                              filtros=FiltrosQuery(), conn=conn) == []


def test_monthly_trend_filtra_por_ccte_sin_poder_perder_filas(conn):
    """`/monthly-trend` no tenía NINGÚN parámetro de filtro: leía
    `resumen_mensual` tal cual. En el Centro operativo la tendencia se
    refresca con el CCTE elegido en los botones, así que con el centro puesto
    seguía mostrando el total del país -- la gráfica mentía en silencio.

    `resumen_mensual` es de una sola dimensión (el mes), así que con filtro
    hay que agrupar `mediciones` en el momento. Lo que hay que garantizar es
    que las dos rutas cuenten lo mismo: si una contara de más, los botones
    mostrarían un pico que no existe.
    """
    from app.api.routes.charts import get_monthly_trend

    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Córdoba Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias(lat=-31.42, lon=-64.19))],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias(lat=-24.78, lon=-65.41))],
    )

    total = get_monthly_trend(filtros=FiltrosQuery(), conn=conn)
    assert {f["mes"] for f in total} == {"2025-03"}
    assert total[0]["mediciones"] == 8  # 4 de cada archivo

    por_ccte = {}
    for ccte in ("Córdoba", "Salta"):
        filas = get_monthly_trend(filtros=FiltrosQuery(ccte=[ccte]), conn=conn)
        # Misma forma de respuesta en los dos caminos: el frontend no se
        # entera de cuál de los dos corrió.
        assert set(filas[0]) == {"mes", "mediciones"}
        por_ccte[ccte] = sum(f["mediciones"] for f in filas)

    # Filtra de verdad: cada centro ve solo lo suyo...
    assert por_ccte["Córdoba"] == 4
    assert por_ccte["Salta"] == 4
    # ...y entre los dos reproducen el total: nada duplicado, nada perdido.
    assert sum(por_ccte.values()) == total[0]["mediciones"]


def test_monthly_trend_no_cuenta_fechas_vacias(conn):
    """El precalculado hace `substr(fecha_hora, 1, 7) = ?`, que nunca matchea
    NULL ni cadena vacía. El camino filtrado hace `<> ''`, que tampoco -- en
    SQL `NULL <> ''` es NULL, no TRUE. Si se hubiera usado `IS NOT NULL`
    solo, la fila sin fecha formaría un grupo con `mes = None` y la suma con
    filtro daría más que el total.
    """
    from app.api.routes.charts import get_monthly_trend

    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias(lat=-24.78, lon=-65.41))],
    )
    conn.execute(
        """INSERT INTO mediciones
             (ccte, provincia, localidad, resultado_vm, resultado_pct,
              fecha_hora, anio, fecha_carga)
           VALUES ('Salta', 'Salta', 'Sin Fecha', 1.0, 1.0, NULL, NULL,
                   '2025-03-21 00:00:00')"""
    )

    con_filtro = get_monthly_trend(filtros=FiltrosQuery(ccte=["Salta"]), conn=conn)
    sin_filtro = get_monthly_trend(filtros=FiltrosQuery(), conn=conn)

    # Ningún mes nulo ni vacío en la respuesta.
    assert all(f["mes"] for f in con_filtro)
    assert {f["mes"] for f in con_filtro} == {"2025-03"}
    # Los dos caminos suman lo mismo a pesar de la fila sin fecha.
    assert sum(f["mediciones"] for f in con_filtro) == sum(
        f["mediciones"] for f in sin_filtro
    ) == 4


def test_monthly_trend_con_filtro_que_no_matchea_devuelve_vacio(conn):
    from app.api.routes.charts import get_monthly_trend

    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias(lat=-24.78, lon=-65.41))],
    )
    # Buenos Aires existe en el catálogo pero no tiene mediciones.
    assert get_monthly_trend(filtros=FiltrosQuery(ccte=["Buenos Aires"]),
                             conn=conn) == []


def test_construir_where_no_explota_el_string_en_caracteres(conn):
    """`construir_where` hacía `list(ccte)` sin mirar el tipo. Con una lista
    (que es lo que manda `FiltrosQuery`) va bien, pero con un string suelto
    `list("Córdoba")` da `['C', 'ó', 'r', 'd', 'o', 'b', 'a']` y la query
    queda `ccte IN ('C','ó',...)`: 0 filas, sin error.

    Eso dejó este mismo archivo en rojo: `tiempo_diario_ccte(conn, "Córdoba")`
    devolvía `[]` y el test lo leía como "no hay datos". Un bug que se
    confunde con un caso vacío es el que más cuesta de encontrar, así que
    queda cubierto con el string y con el número sueltos.
    """
    from app.db.repositories.mediciones_repo import construir_where

    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Córdoba Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias(lat=-31.42, lon=-64.19))],
    )

    where, params = construir_where("Córdoba", None, None)
    assert params == ["Córdoba"], f"se comió el string: {params}"
    assert where.count("?") == 1

    # Un año suelto entraba con TypeError; ahora es un IN de un elemento.
    _, anio_params = construir_where(None, None, 2025)
    assert anio_params == [2025]

    # Lo que trae el filtro de verdad (una lista) sigue igual que antes.
    _, lista_params = construir_where(["Córdoba", "Salta"], None, None)
    assert lista_params == ["Córdoba", "Salta"]

    # Y con el string el desglose por fin encuentra sus filas.
    diario = tiempos_service.tiempo_diario_ccte(conn, "Córdoba")
    assert len(diario) == 2
