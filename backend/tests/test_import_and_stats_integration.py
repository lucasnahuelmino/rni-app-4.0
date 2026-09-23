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


def test_import_no_confunde_localidades_homonimas_de_provincias_distintas(conn):
    """Reimportar el MISMO contenido bajo un nombre de localidad repetido
    tiene que insertar, no deduplicar.

    La clave de duplicados es (ccte, provincia, localidad, fecha_hora,
    resultado_vm). Sin `provincia`, las dos "San Pedro" de la base real
    (Catamarca y Santiago del Estero, ambas CCTE Salta) competían entre sí y
    la segunda importación se descartaba entera como duplicada.
    """
    df = _df_excel_sintetico()

    primero = import_service.importar_lote(
        conn, ccte="Salta", provincia="Catamarca", localidad="San Pedro",
        expediente=None, archivos=[("a.xlsx", df)],
    )
    assert primero["registros_nuevos"] == 3

    # Mismo archivo, mismo nombre de localidad, distinta provincia.
    segundo = import_service.importar_lote(
        conn, ccte="Salta", provincia="Santiago del Estero", localidad="San Pedro",
        expediente=None, archivos=[("a.xlsx", df)],
    )
    assert segundo["registros_nuevos"] == 3
    assert segundo["registros_duplicados"] == 0

    filas = conn.execute(
        "SELECT provincia, COUNT(*) AS n FROM mediciones "
        "WHERE localidad = 'San Pedro' GROUP BY provincia ORDER BY provincia"
    ).fetchall()
    assert [(r["provincia"], r["n"]) for r in filas] == [
        ("Catamarca", 3),
        ("Santiago del Estero", 3),
    ]

    # Y la detección de duplicados sigue funcionando DENTRO de una misma
    # provincia: una tercera carga idéntica para Catamarca es duplicado.
    tercero = import_service.importar_lote(
        conn, ccte="Salta", provincia="Catamarca", localidad="San Pedro",
        expediente=None, archivos=[("a.xlsx", df)],
    )
    assert tercero["registros_nuevos"] == 0
    assert tercero["registros_duplicados"] == 3


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
    # Sanity check: el import sí dejó las 4 tablas de agregación pobladas.
    # (Todas las fechas sintéticas caen en 2025-03, así que hay 1 mes y 1 año.)
    assert conn.execute("SELECT COUNT(*) AS n FROM resumen_anual").fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM resumen_mensual").fetchone()["n"] == 1
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM resumen_provincia WHERE provincia='Misiones'"
    ).fetchone()["n"] == 1

    measurements.eliminar_localidad(conn, "Posadas", "Misiones", "Posadas Centro")

    quedan = conn.execute("SELECT COUNT(*) AS n FROM mediciones WHERE localidad='Posadas Centro'").fetchone()["n"]
    resumen = conn.execute(
        "SELECT * FROM resumen_localidad WHERE localidad='Posadas Centro'"
    ).fetchone()
    assert quedan == 0
    assert resumen is None

    # Regresión: al borrar no alcanza con limpiar resumen_localidad -- como ya
    # no quedan filas de la localidad, recalcular() no puede adivinar qué
    # años/meses ocupaba. Sin `periodos_afectados` estas 4 tablas seguían
    # contando las 3 mediciones borradas.
    assert conn.execute("SELECT COUNT(*) AS n FROM resumen_anual").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM resumen_mensual").fetchone()["n"] == 0
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM resumen_provincia WHERE provincia='Misiones'"
    ).fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM resumen_provincia_ccte").fetchone()["n"] == 0


def test_eliminar_una_de_dos_localidades_solo_deja_fuera_sus_periodos(conn):
    """Si quedan otras localidades con mediciones en el mismo período, ese
    período se RECALCULA (no se borra) y queda con lo que sigue vivo.

    Ambas localidades comparten año 2025 y mes 2025-03, así que es el caso
    donde un borrado ingenuo dejaba los conteos viejos en vez de restarlos."""
    import_service.importar_lote(
        conn, ccte="Posadas", provincia="Misiones", localidad="Posadas Centro",
        expediente=None, archivos=[("a.xlsx", _df_excel_sintetico())],
    )
    import_service.importar_lote(
        conn, ccte="Posadas", provincia="Misiones", localidad="Otra Localidad",
        expediente=None, archivos=[("b.xlsx", _df_excel_sintetico())],
    )
    assert conn.execute("SELECT mediciones FROM resumen_anual").fetchone()["mediciones"] == 6

    measurements.eliminar_localidad(conn, "Posadas", "Misiones", "Posadas Centro")

    anual = conn.execute("SELECT * FROM resumen_anual").fetchall()
    assert len(anual) == 1
    assert anual[0]["mediciones"] == 3  # solo lo de "Otra Localidad"

    mensual = conn.execute("SELECT * FROM resumen_mensual").fetchall()
    assert len(mensual) == 1
    assert mensual[0]["mes"] == "2025-03"
    assert mensual[0]["mediciones"] == 3


def test_diagnostico_detecta_rechazados_y_coordenadas(conn):
    import_service.importar_lote(
        conn, ccte="Comodoro Rivadavia", provincia="Chubut", localidad="Comodoro",
        expediente=None, archivos=[("a.xlsx", _df_excel_sintetico())],
    )
    diag = diagnostics_service.obtener_diagnostico(conn)
    assert diag["total_registros"] == 3
    assert diag["resultados_faltantes"] == 0  # los rechazados no se insertan
