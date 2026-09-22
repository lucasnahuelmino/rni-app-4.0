import pandas as pd

from app.schemas.filters import FiltrosQuery
from app.services import import_service, kpis_service, measurements
from app.services import diagnostics as diagnostics_service


def _df_excel_sintetico() -> pd.DataFrame:
    return pd.DataFrame({
        "Resultado": ["1,5", "3.2", "10", "abc"],  # "abc" -> se rechaza (sin resultado numérico)
        "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025", "21/03/2025"],
        "Hora": ["10:00:00", "10:30:00", "09:00:00 a.m.", "09:15:00 a.m."],
        "Lat": [-34.6037, -34.6040, -34.6050, -34.6060],
        "Lon": [-58.3816, -58.3820, -58.3830, -58.3840],
        "Sonda": ["S1", "S1", "S2", "S2"],
    })


def test_import_inserta_y_calcula_resumenes(conn):
    reporte = import_service.importar_lote(
        conn, ccte="Buenos Aires", provincia="Buenos Aires", localidad="CABA",
        expediente="EXP-1", archivos=[("archivo1.xlsx", _df_excel_sintetico())],
    )

    assert reporte["registros_nuevos"] == 3
    assert reporte["registros_rechazados"] == 1
    assert reporte["registros_duplicados"] == 0

    resumen = conn.execute(
        "SELECT * FROM resumen_localidad WHERE ccte='Buenos Aires' AND localidad='CABA'"
    ).fetchone()
    assert resumen["mediciones"] == 3
    assert resumen["resultado_max_vm"] == 10.0

    resumen_ccte = conn.execute("SELECT * FROM resumen_ccte WHERE ccte='Buenos Aires'").fetchone()
    assert resumen_ccte["mediciones"] == 3


def test_import_detecta_duplicados_si_se_reimporta_mismo_archivo(conn):
    df = _df_excel_sintetico()
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("a.xlsx", df)],
    )
    reporte2 = import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("a.xlsx", df)],
    )
    assert reporte2["registros_nuevos"] == 0
    assert reporte2["registros_duplicados"] == 3


def test_kpis_reflejan_los_datos_importados(conn):
    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Córdoba Capital",
        expediente=None, archivos=[("a.xlsx", _df_excel_sintetico())],
    )
    kpis = kpis_service.obtener_kpis(conn, FiltrosQuery())
    assert kpis["registros_totales"] == 3
    assert kpis["localidades"] == 1
    assert kpis["pico_maximo"]["resultado_vm"] == 10.0


def test_ccte_summary_incluye_buenos_aires_y_caba_con_cero(conn):
    import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Salta Capital",
        expediente=None, archivos=[("a.xlsx", _df_excel_sintetico())],
    )
    resumen = kpis_service.obtener_ccte_summary(conn)
    nombres = {r["ccte"] for r in resumen}
    assert {"Buenos Aires", "CABA", "Salta"}.issubset(nombres)

    bsas = next(r for r in resumen if r["ccte"] == "Buenos Aires")
    caba = next(r for r in resumen if r["ccte"] == "CABA")
    assert bsas["mediciones"] == 0
    assert caba["mediciones"] == 0
    assert len(resumen) == 7  # siempre los 7 CCTE fijos


def test_editar_metadata_localidad_no_reescribe_toda_la_tabla(conn):
    import_service.importar_lote(
        conn, ccte="Neuquén", provincia="Neuquén", localidad="Neuquén Capital",
        expediente=None, archivos=[("a.xlsx", _df_excel_sintetico())],
    )
    filas_afectadas = measurements.editar_metadata_localidad(
        conn, "Neuquén", "Neuquén", "Neuquén Capital", {"expediente": "EXP-999"}
    )
    assert filas_afectadas == 3

    resumen = conn.execute(
        "SELECT * FROM resumen_localidad WHERE ccte='Neuquén' AND localidad='Neuquén Capital'"
    ).fetchone()
    assert resumen["expedientes"] == "EXP-999"


def test_eliminar_localidad_limpia_resumenes(conn):
    import_service.importar_lote(
        conn, ccte="Posadas", provincia="Misiones", localidad="Posadas Centro",
        expediente=None, archivos=[("a.xlsx", _df_excel_sintetico())],
    )
    measurements.eliminar_localidad(conn, "Posadas", "Misiones", "Posadas Centro")

    quedan = conn.execute("SELECT COUNT(*) AS n FROM mediciones WHERE localidad='Posadas Centro'").fetchone()["n"]
    resumen = conn.execute(
        "SELECT * FROM resumen_localidad WHERE localidad='Posadas Centro'"
    ).fetchone()
    assert quedan == 0
    assert resumen is None


def test_diagnostico_detecta_rechazados_y_coordenadas(conn):
    import_service.importar_lote(
        conn, ccte="Comodoro Rivadavia", provincia="Chubut", localidad="Comodoro",
        expediente=None, archivos=[("a.xlsx", _df_excel_sintetico())],
    )
    diag = diagnostics_service.obtener_diagnostico(conn)
    assert diag["total_registros"] == 3
    assert diag["resultados_faltantes"] == 0  # los rechazados no se insertan
