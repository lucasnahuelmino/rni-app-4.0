import pandas as pd

from app.schemas.filters import FiltrosQuery
from app.services import import_service, tiempos as tiempos_service


def _df_dos_dias() -> pd.DataFrame:
    return pd.DataFrame({
        "Resultado": ["1,5", "3.2", "10", "2.1"],
        "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025", "21/03/2025"],
        "Hora": ["10:00:00", "10:30:00", "09:00:00 a.m.", "09:20:00 a.m."],
        "Lat": [-34.6037, -34.6040, -34.6050, -34.6060],
        "Lon": [-58.3816, -58.3820, -58.3830, -58.3840],
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
