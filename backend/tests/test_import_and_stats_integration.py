import pandas as pd
import pytest

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


def _df_automap_dms() -> pd.DataFrame:
    """Formato del PRIMER generador, tal cual lo escribe AutoMap
    ("SAN MIGUEL DE TUCUMAN 1.xlsx"): resultado como texto con coma decimal y
    coordenadas DMS con letra de hemisferio.

    Lo importante: NO existe columna llamada "Resultado" ni "V/m". Se llama
    "Resultado con incertidumbre", que era exactamente lo que no matcheaba --
    por eso toda carga devolvía `registros_nuevos=0` con el aviso
    "no se encontró columna de Resultado (V/m)".
    """
    return pd.DataFrame({
        "Indice": [1, 2],
        "Fecha": ["30/9/2025", "30/9/2025"],
        "Hora": ["14:02:53", "14:03:38"],
        "Latitud": ['26° 49\' 52,187" S', '26° 49\' 51,222" S'],
        "Longitud": ['65° 11\' 42,766" O', '65° 11\' 42,442" O'],
        "Sonda": ["EF1891", "EF1891"],
        "N° serie de sonda": ["A-0057", "A-0057"],
        "Fecha de calibración": ["01/21/25", "01/21/25"],
        "Incertidumbre de medición": ["3,12", "3,12"],
        "Resultado con incertidumbre": ["0,942", "1,022"],
        "Unidad": ["V/m", "V/m"],
        "Tipo de resultado": ["Max Hold", "Max Hold"],
    })


def _df_automap_decimal() -> pd.DataFrame:
    """Formato del SEGUNDO generador ("AGUAS BLANCAS 2026-09-01
    105334_reporte.xlsx"): mismos encabezados, pero el resultado ya es número
    y las coordenadas vienen en grados decimales con signo explícito."""
    return pd.DataFrame({
        "Indice": [1, 2],
        "Fecha": ["1/9/2026", "1/9/2026"],
        "Hora": ["10:53:33", "10:55:18"],
        "Latitud": ["-22.735365", "-22.735585"],
        "Longitud": ["-64.354018", "-64.354225"],
        "Sonda": ["EF0391", "EF0391"],
        "N° serie de sonda": ["D-1484", "D-1484"],
        "Fecha de calibración": ["03.03.26", "03.03.26"],
        "Incertidumbre de medición": [1.37, 1.37],
        "Resultado con incertidumbre": [0.69, 1.27],
        "Unidad": ["V/m", "V/m"],
        "Tipo de resultado": ["Max Hold", "Max Hold"],
    })


def test_import_acepta_el_formato_automap_dms(conn):
    """Regresión del bug real reportado por el usuario: los dos generadores
    nombran la columna "Resultado con incertidumbre" y ninguna trae "Resultado"."""
    reporte = import_service.importar_lote(
        conn, ccte="Salta", provincia="Tucumán", localidad="San Miguel",
        expediente=None, archivos=[("SAN MIGUEL DE TUCUMAN 1.xlsx", _df_automap_dms())],
    )

    assert reporte["advertencias"] == []
    assert reporte["registros_nuevos"] == 2
    assert reporte["registros_rechazados"] == 0

    filas = conn.execute(
        "SELECT resultado_vm, lat, lon FROM mediciones ORDER BY id"
    ).fetchall()
    assert [f["resultado_vm"] for f in filas] == [0.942, 1.022]
    # DMS con hemisferio: Tucumán está al SUR y al OESTE. Con el regex legacy
    # salían positivos y el punto caía en el hemisferio equivocado.
    assert filas[0]["lat"] == pytest.approx(-26.831163055555557)
    assert filas[0]["lon"] == pytest.approx(-65.19521277777778)
    assert filas[1]["lat"] < 0 and filas[1]["lon"] < 0


def test_import_acepta_el_formato_automap_decimal(conn):
    reporte = import_service.importar_lote(
        conn, ccte="Salta", provincia="Salta", localidad="Aguas Blancas",
        expediente=None,
        archivos=[("AGUAS BLANCAS 2026-09-01 105334_reporte.xlsx", _df_automap_decimal())],
    )

    assert reporte["advertencias"] == []
    assert reporte["registros_nuevos"] == 2
    assert reporte["registros_rechazados"] == 0

    filas = conn.execute(
        "SELECT resultado_vm, lat, lon FROM mediciones ORDER BY id"
    ).fetchall()
    assert [f["resultado_vm"] for f in filas] == [0.69, 1.27]
    # Decimal con signo: no pasa por la lógica de hemisferio, sale tal cual.
    assert filas[0]["lat"] == pytest.approx(-22.735365)
    assert filas[0]["lon"] == pytest.approx(-64.354018)


def test_encabezados_se_comparan_sin_importar_caja_ni_acentos():
    """La capitalización no debería decidir si una columna se encuentra."""
    df = pd.DataFrame({
        "RESULTADO CON INCERTIDUMBRE": ["3,2"],
        "FECHA ": ["1/9/2026"],
        "Hora": ["10:53:33"],
        "LATITUD": ["-22.735365"],
        "LONGITUD": ["-64.354018"],
        "SONDA": ["EF0391"],
    })
    out, advertencias = import_service._leer_y_normalizar(df, "x.xlsx")
    assert advertencias == []
    assert out["resultado_vm"].iloc[0] == pytest.approx(3.2)
    assert out["lat"].iloc[0] == pytest.approx(-22.735365)


def test_resultado_con_nombre_futuro_tambien_se_encuentra():
    """Respaldo por prefijo: si el generador vuelve a renombrar la columna,
    cualquier variante que empiece con "Resultado" sirve sin tocar código."""
    df = pd.DataFrame({
        "Resultado (V/m)": ["2,5"],
        "Fecha": ["1/9/2026"],
        "Hora": ["10:53:33"],
        "Latitud": ["-22.735365"],
        "Longitud": ["-64.354018"],
        "Sonda": ["EF0391"],
    })
    out, advertencias = import_service._leer_y_normalizar(df, "x.xlsx")
    assert advertencias == []
    assert out["resultado_vm"].iloc[0] == pytest.approx(2.5)


def test_no_confunde_tipo_de_resultado_con_el_resultado():
    """"Tipo de resultado" es el tipo ("Max Hold"), no el valor: el respaldo
    por prefijo no puede caer ahí. Y el aviso tiene que decir QUÉ buscaba,
    no solo que algo falló -- con el mensaje genérico no se pudo diagnosticar."""
    df = pd.DataFrame({
        "Tipo de resultado": ["Max Hold"],
        "Fecha": ["1/9/2026"],
        "Hora": ["10:53:33"],
        "Latitud": ["-22.735365"],
        "Longitud": ["-64.354018"],
        "Sonda": ["EF0391"],
    })
    out, advertencias = import_service._leer_y_normalizar(df, "x.xlsx")
    assert len(advertencias) == 1
    assert "no se encontró columna de Resultado (V/m)" in advertencias[0]
    assert "Resultado con incertidumbre" in advertencias[0]  # qué buscaba
    assert "Tipo de resultado" in advertencias[0]           # qué había
    assert pd.isna(out["resultado_vm"]).all()


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


def _df_con_signo_cero_y_excedencia() -> pd.DataFrame:
    """Un caso de cada uno de los tres que el Lote 7 separa:

    -0.001  negativo -> imposible, la sonda reporta eso por debajo de su piso
    0       cero exacto -> error del equipo, se conserva y se cuenta
    30      119,24 % -> excede la MEP, es posible y lo trata el área técnica
    1,5     valor normal
    """
    return pd.DataFrame({
        "Resultado": ["-0.001", "0", "30", "1.5"],
        "Fecha": ["20/03/2026"] * 4,
        "Hora": ["10:00:00", "10:01:00", "10:02:00", "10:03:00"],
        "Lat": [-34.6037, -34.6040, -34.6050, -34.6060],
        "Lon": [-58.3816, -58.3820, -58.3830, -58.3840],
        "Sonda": ["S1"] * 4,
    })


def test_resultado_negativo_pasa_a_absoluto_en_el_import(conn):
    """Un campo eléctrico no puede ser negativo. Esa era exactamente la forma
    de los 17 registros negativos que tenía la base (-0.001, CCTE Comodoro
    Rivadavia)."""
    out, advertencias = import_service._leer_y_normalizar(
        _df_con_signo_cero_y_excedencia(), "x.xlsx"
    )

    assert list(out["resultado_vm"]) == [0.001, 0.0, 30.0, 1.5]
    # El porcentaje no cambia con el signo (la fórmula eleva al cuadrado),
    # pero igual se normaliza ANTES de calcularlo para que quede coherente.
    assert list(out["resultado_pct"])[0] == pytest.approx(
        import_service.resultado_pct(0.001)
    )
    assert any("signo negativo" in a for a in advertencias)


def test_sanear_signo_resultados_corrige_lo_ya_cargado_y_es_idempotente(conn):
    """El arranque sanea las filas que ya estaban en la base. No recalcula
    nada: el cuadrado de la fórmula ya dejó el porcentaje en positivo y
    ninguna tabla derivada guarda MIN(resultado_vm)."""
    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Cosquín",
        expediente=None, archivos=[("a.xlsx", _df_con_signo_cero_y_excedencia())],
    )
    # Vuelve a dejar la base como estaba ANTES de este lote.
    conn.execute("UPDATE mediciones SET resultado_vm = -resultado_vm WHERE resultado_vm != 0")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM mediciones WHERE resultado_vm < 0").fetchone()[0] == 3

    assert measurements.sanear_signo_resultados(conn) == 3

    valores = [f["resultado_vm"] for f in conn.execute(
        "SELECT resultado_vm FROM mediciones ORDER BY id"
    )]
    assert valores == [0.001, 0.0, 30.0, 1.5]

    # Segunda pasada: no encuentra nada y no escribe.
    assert measurements.sanear_signo_resultados(conn) == 0


def test_diagnostico_distingue_ceros_de_excedencias(conn):
    """Los dos contadores nuevos no se mezclan entre sí ni con los
    faltantes: la fila del cero NO está vacía, tiene todo menos la medición."""
    import_service.importar_lote(
        conn, ccte="Córdoba", provincia="Córdoba", localidad="Cosquín",
        expediente=None, archivos=[("a.xlsx", _df_con_signo_cero_y_excedencia())],
    )
    diag = diagnostics_service.obtener_diagnostico(conn)

    assert diag["total_registros"] == 4
    assert diag["resultados_faltantes"] == 0
    assert diag["resultados_en_cero"] == 1
    assert diag["excedencias_mep"] == 1

    # 30 V/m = 119,24 % del límite: por arriba de la MEP.
    assert conn.execute(
        "SELECT resultado_pct FROM mediciones WHERE resultado_vm = 30"
    ).fetchone()["resultado_pct"] == pytest.approx(119.24, rel=1e-3)
