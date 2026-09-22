import pandas as pd

from app.calculations.dates import (
    add_fecha_hora,
    anio_de_fecha_hora,
    calcular_tiempo_trabajado_segundos,
    format_timedelta_long,
)


def test_add_fecha_hora_formato_consistente_en_la_columna():
    """Dentro de una misma columna con un único formato de fecha, el parseo
    funciona correctamente para todas las filas."""
    df = pd.DataFrame({
        "fecha_raw": ["20/03/2025", "21/03/2025"],
        "hora_raw": ["10:08:09 a.m.", "22:10:00"],
    })
    out = add_fecha_hora(df)
    assert out["fecha_hora"].notna().sum() == 2
    assert out.loc[0, "fecha_hora"] == pd.Timestamp("2025-03-20 10:08:09")
    assert out.loc[1, "fecha_hora"] == pd.Timestamp("2025-03-21 22:10:00")


def test_add_fecha_hora_formatos_mixtos_en_la_misma_columna_es_una_limitacion_heredada():
    """HALLAZGO (heredado del sistema Streamlit actual, mismo `pd.to_datetime`):
    si una columna mezcla formatos de fecha (ej. DD/MM/YYYY en una fila e
    YYYY-MM-DD en otra), pandas infiere el formato de la PRIMERA fila no nula
    y lo aplica a toda la columna -- las filas que no calzan con ese formato
    quedan como NaT, aunque sean fechas válidas en otro formato. No es un bug
    introducido por esta migración: se reproduce igual con
    utils/time_utils.py del sistema actual. Vale la pena confirmar con el
    equipo si los Excel de origen mezclan formatos de fecha en una misma
    columna -- si es así, esto ya afecta al sistema actual y no solo al
    nuevo backend."""
    df = pd.DataFrame({
        "fecha_raw": ["20/03/2025", "2025-03-21", "invalido"],
        "hora_raw": ["10:08:09 a.m.", "22:10:00", "10:00"],
    })
    out = add_fecha_hora(df)
    assert out["fecha_hora"].notna().sum() == 1
    assert out.loc[0, "fecha_hora"] == pd.Timestamp("2025-03-20 10:08:09")
    assert pd.isna(out.loc[1, "fecha_hora"])
    assert pd.isna(out.loc[2, "fecha_hora"])


def test_add_fecha_hora_dataframe_vacio():
    out = add_fecha_hora(pd.DataFrame())
    assert "fecha_hora" in out.columns


def test_anio_de_fecha_hora():
    assert anio_de_fecha_hora(pd.Timestamp("2025-03-20 10:00:00")) == 2025
    assert anio_de_fecha_hora(None) is None
    assert anio_de_fecha_hora(pd.NaT) is None


def test_format_timedelta_long():
    assert format_timedelta_long(None) == "0 s"
    assert format_timedelta_long(65) == "1 min 05 s"
    assert format_timedelta_long(3725) == "1 h 02 min 05 s"
    assert format_timedelta_long(5) == "5 s"


def test_calcular_tiempo_trabajado_segundos():
    df = pd.DataFrame({
        "fecha_hora": pd.to_datetime([
            "2025-03-20 10:00:00", "2025-03-20 10:30:00", "2025-03-20 11:00:00",
        ]),
        "nombre_archivo": ["a.xlsx", "a.xlsx", "a.xlsx"],
    })
    segundos = calcular_tiempo_trabajado_segundos(df)
    assert segundos == 3600  # de 10:00 a 11:00


def test_calcular_tiempo_trabajado_vacio():
    assert calcular_tiempo_trabajado_segundos(pd.DataFrame()) == 0
