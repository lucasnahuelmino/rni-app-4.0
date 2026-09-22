import pandas as pd

from app.services import import_service, reports as reports_service


def _df_excel_sintetico() -> pd.DataFrame:
    return pd.DataFrame({
        "Resultado": ["1,5", "3.2", "10"],
        "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025"],
        "Hora": ["10:00:00", "10:30:00", "09:00:00 a.m."],
        "Lat": [-34.6037, -34.6040, -34.6050],
        "Lon": [-58.3816, -58.3820, -58.3830],
        "Sonda": ["S1", "S1", "S2"],
    })


def test_generar_word_y_pdf_no_escriben_a_disco(conn, tmp_path, monkeypatch):
    import_service.importar_lote(
        conn, ccte="Buenos Aires", provincia="Buenos Aires", localidad="CABA",
        expediente="EXP-1", archivos=[("a.xlsx", _df_excel_sintetico())],
    )

    # Nos paramos en un directorio de trabajo separado del de la DB y nos
    # aseguramos de que generar los informes no deja ningún archivo nuevo ahí
    # (Auditoría Fase 1, hallazgo A9).
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    datos = reports_service.obtener_datos_informe(conn, "Buenos Aires", "Buenos Aires", "CABA")
    assert datos["total_puntos"] == 3

    word_buffer = reports_service.generar_word(datos, localidad="CABA", ambito="Localidad")
    pdf_buffer = reports_service.generar_pdf(datos, localidad="CABA", ambito="Localidad")

    assert word_buffer.getbuffer().nbytes > 0
    assert pdf_buffer.getbuffer().nbytes > 0
    assert list(workdir.iterdir()) == []  # nada se escribió a disco
