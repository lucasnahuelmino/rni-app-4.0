import pandas as pd

from app.schemas.filters import FiltrosQuery
from app.services import import_service, tiempos as tiempos_service


def _df_dos_dias(lat: float = -34.6037, lon: float = -58.3816) -> pd.DataFrame:
    """Dos días de mediciones alrededor de (lat, lon).

    Las coordenadas son parámetro y no un valor fijo: sin esto todas las
    localidades importadas en un mismo test caían exactamente en el mismo
    punto del mapa y ningún filtro por bbox se podía probar (el bbox de CABA
    devolvía también a Salta y a Mendoza, porque estaban "en" CABA).
    """
    return pd.DataFrame({
        "Resultado": ["1,5", "3.2", "10", "2.1"],
        "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025", "21/03/2025"],
        "Hora": ["10:00:00", "10:30:00", "09:00:00 a.m.", "09:20:00 a.m."],
        "Lat": [lat, lat + 0.0003, lat + 0.0013, lat + 0.0023],
        "Lon": [lon, lon - 0.0004, lon - 0.0014, lon - 0.0024],
        "Sonda": ["S1", "S1", "S2", "S2"],
    })


def test_map_modo_max_localidad_trae_un_punto_por_localidad(conn):
    import_service.importar_lote(
        conn, ccte="Buenos Aires", provincia="Buenos Aires", localidad="CABA",
        expediente="EXP-1", archivos=[("a.xlsx", _df_dos_dias())],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias())],
    )

    from app.api.routes.map import get_map
    resultado = get_map(modo="max_localidad", filtros=FiltrosQuery(), conn=conn)
    assert resultado["truncado"] is False
    assert len(resultado["puntos"]) == 2  # una fila por localidad

    caba = next(p for p in resultado["puntos"] if p["localidad"] == "CABA")
    assert caba["resultado_vm"] == 10.0  # el de mayor resultado_pct de esa localidad


def test_map_payload_trae_provincia_para_distinguir_homonimas(conn):
    """El payload del mapa tiene que traer `provincia`.

    En la base real hay DOS "San Pedro": Catamarca y Santiago del Estero,
    ambas bajo el CCTE Salta. Sin provincia, los dos popups del mapa eran
    literalmente indistinguibles (mismo localidad, mismo ccte).
    """
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Catamarca", localidad="San Pedro",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias(-27.9460, -65.0960))],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Santiago del Estero", localidad="San Pedro",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias(-27.7000, -64.8600))],
    )

    from app.api.routes.map import get_map

    # Los dos caminos que pinta el frontend: la vista general (muestreo
    # proporcional) y el modo automático por zoom (una fila por localidad).
    for modo in ("todos", "max_localidad"):
        puntos = get_map(modo=modo, filtros=FiltrosQuery(), conn=conn)["puntos"]
        assert puntos, modo

        # Presente Y no vacío: un `provincia: null` no distingue nada.
        assert all(p.get("provincia") for p in puntos), modo

        # La identidad completa es (ccte, provincia, localidad). Si el
        # backend agrupara solo por localidad+ccte, las dos filas
        # colapsarían en una sola.
        identidades = {(p["ccte"], p["provincia"], p["localidad"]) for p in puntos}
        assert len(identidades) == 2, modo
        assert {p["provincia"] for p in puntos} == {"Catamarca", "Santiago del Estero"}, modo


def test_map_modo_invalido_rechaza(conn):
    from fastapi import HTTPException
    from app.api.routes.map import get_map
    try:
        get_map(modo="no-existe", filtros=FiltrosQuery(), conn=conn)
        assert False, "debería haber lanzado HTTPException"
    except HTTPException as e:
        assert e.status_code == 400


def test_map_filtro_localidad(conn):
    import_service.importar_lote(
        conn, ccte="Buenos Aires", provincia="Buenos Aires", localidad="CABA",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias())],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias())],
    )
    from app.api.routes.map import get_map
    resultado = get_map(modo="todos", filtros=FiltrosQuery(localidad=["CABA"]), conn=conn)
    assert all(p["localidad"] == "CABA" for p in resultado["puntos"])
    assert resultado["total_disponible"] == 4


def _importar_tres_localidades(conn):
    """Tres localidades en tres puntos distintos del país."""
    import_service.importar_lote(
        conn, ccte="Buenos Aires", provincia="Buenos Aires", localidad="CABA",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias(-34.6037, -58.3816))],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias(-24.7859, -65.4116))],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Mendoza", localidad="Godoy Cruz",
        expediente=None, archivos=[("c.xlsx", _df_dos_dias(-32.9314, -68.8728))],
    )


def test_map_todos_sin_tope_devuelve_todo(conn):
    """Cuando entra todo, tiene que devolver TODO y decir que no truncó."""
    _importar_tres_localidades(conn)
    from app.api.routes.map import get_map
    resultado = get_map(modo="todos", filtros=FiltrosQuery(), conn=conn)
    assert resultado["truncado"] is False
    assert resultado["total_disponible"] == 12
    assert len(resultado["puntos"]) == 12
    assert len({p["localidad"] for p in resultado["puntos"]}) == 3


def test_map_todos_truncado_cubre_todas_las_localidades(conn, monkeypatch):
    """Regresión del bug real: el SELECT terminaba en LIMIT sin ORDER BY,
    así que devolvía las primeras filas en orden de inserción y con la base
    de producción 5000 puntos eran exactamente 3 localidades de las 61.

    Con el muestreo proporcional, aunque el tope no alcance para todos los
    puntos, TIENE que haber al menos un punto de cada localidad."""
    _importar_tres_localidades(conn)
    monkeypatch.setattr("app.api.routes.map.MAX_PUNTOS_MAPA", 4)

    from app.api.routes.map import get_map
    resultado = get_map(modo="todos", filtros=FiltrosQuery(), conn=conn)

    assert resultado["truncado"] is True
    assert resultado["total_disponible"] == 12
    assert len(resultado["puntos"]) < 12  # de verdad está muestreando
    # el piso de 1 por localidad: ninguna se queda afuera
    assert {p["localidad"] for p in resultado["puntos"]} == {"CABA", "Salta Capital", "Godoy Cruz"}


def test_map_todos_con_bbox_restringe_al_viewport(conn):
    """El frontend manda el bbox visible en cada moveend: tiene que acotar
    en SQL antes del muestreo, no filtrar la respuesta después."""
    _importar_tres_localidades(conn)
    from app.api.routes.map import get_map

    # CABA está en -34.60 / -58.38; Salta y Godoy Cruz quedan afuera de ese
    # rectángulo, así que el bbox no puede devolverlas.
    dentro = get_map(modo="todos", bbox="-34.7,-34.5,-58.5,-58.3",
                     filtros=FiltrosQuery(), conn=conn)
    assert len(dentro["puntos"]) == 4
    assert {p["localidad"] for p in dentro["puntos"]} == {"CABA"}
    assert dentro["total_disponible"] == 4  # el COUNT también respeta el bbox
    assert dentro["truncado"] is False

    afuera = get_map(modo="todos", bbox="-50,-49,-70,-69",
                     filtros=FiltrosQuery(), conn=conn)
    assert afuera["puntos"] == []
    assert afuera["total_disponible"] == 0
    assert afuera["truncado"] is False


def test_map_bbox_malformado_devuelve_400(conn):
    from fastapi import HTTPException
    from app.api.routes.map import get_map
    for bbox in ("1,2,3", "a,b,c,d", "1,2"):
        try:
            get_map(bbox=bbox, filtros=FiltrosQuery(), conn=conn)
            assert False, f"bbox={bbox} debería haber lanzado HTTPException"
        except HTTPException as e:
            assert e.status_code == 400



def test_tiempo_diario_localidad_dos_jornadas(conn):
    import_service.importar_lote(
        conn, ccte="Neuquén", provincia="Neuquén", localidad="Neuquén Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias())],
    )
    diario = tiempos_service.tiempo_diario_localidad(conn, "Neuquén", "Neuquén", "Neuquén Capital")
    assert len(diario) == 2
    assert diario[0]["fecha"] == "2025-03-20"
    assert diario[0]["duracion_seg"] == 1800  # 10:00 a 10:30
    assert diario[1]["fecha"] == "2025-03-21"
    assert diario[1]["duracion_seg"] == 1200  # 09:00 a 09:20


def test_tiempo_mensual_localidad(conn):
    import_service.importar_lote(
        conn, ccte="Posadas", provincia="Misiones", localidad="Posadas Centro",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias())],
    )
    mensual = tiempos_service.tiempo_mensual_localidad(conn, "Posadas", "Misiones", "Posadas Centro")
    assert len(mensual) == 1  # ambos días caen en marzo 2025
    assert mensual[0]["mes"] == "2025-03"
    assert mensual[0]["dias_con_medicion"] == 2
    assert mensual[0]["tiempo_trabajado_seg"] == 1800 + 1200


def test_tiempo_mensual_global_filtrado_por_ccte(conn):
    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Córdoba Capital",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias())],
    )
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("b.xlsx", _df_dos_dias())],
    )
    mensual_cordoba = tiempos_service.tiempo_mensual(conn, FiltrosQuery(ccte=["Córdoba"]))
    assert mensual_cordoba[0]["tiempo_trabajado_seg"] == 1800 + 1200

    mensual_todo = tiempos_service.tiempo_mensual(conn, FiltrosQuery())
    assert mensual_todo[0]["tiempo_trabajado_seg"] == (1800 + 1200) * 2


def test_ccte_summary_incluye_tiempo_trabajado_formateado(conn):
    import_service.importar_lote(
        conn, ccte="Comodoro Rivadavia", provincia="Chubut", localidad="Comodoro",
        expediente=None, archivos=[("a.xlsx", _df_dos_dias())],
    )
    from app.services import kpis_service
    resumen = kpis_service.obtener_ccte_summary(conn)
    comodoro = next(r for r in resumen if r["ccte"] == "Comodoro Rivadavia")
    assert comodoro["tiempo_trabajado_fmt"] != "0 s"


def test_localities_incluye_expedientes_lista_y_tiempo_formateado(conn):
    import_service.importar_lote(
        conn, ccte="CABA", provincia="Buenos Aires", localidad="Palermo",
        expediente="EXP-A", archivos=[("a.xlsx", _df_dos_dias())],
    )
    from app.db.repositories import resumen_repo
    from app.api.routes.localities import _con_tiempo_formateado
    fila = resumen_repo.listar_resumen_localidad(conn, ccte=["CABA"])[0]
    enriquecida = _con_tiempo_formateado(fila)
    assert enriquecida["expedientes_lista"] == ["EXP-A"]
    assert "tiempo_trabajado_fmt" in enriquecida


def test_color_scale_endpoint_tiene_10_bandas(conn):
    from app.api.routes.colors import get_color_scale
    escala = get_color_scale()
    assert len(escala) == 10
    banda_4_8 = next(b for b in escala if b["desde"] == 4)
    assert banda_4_8["hasta"] == 8
    assert banda_4_8["color"] == "#A9E7A9"


def test_color_por_pct_coincide_con_escala():
    from app.core.config import color_por_pct
    assert color_por_pct(0.5) == "#84C2F5"
    assert color_por_pct(5) == "#A9E7A9"
    assert color_por_pct(150) == "#CC0000"
    assert color_por_pct(None) == "#9aa5ab"
