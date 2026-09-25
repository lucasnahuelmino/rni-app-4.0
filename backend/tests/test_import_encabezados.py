# -*- coding: utf-8 -*-
"""La fila de encabezados del Excel ya no está clavada en la 9.

`POST /api/import` hacía `pd.read_excel(..., header=8)`: la fila 9 era donde
quedaban los encabezados en los archivos del generador original. Cualquier
archivo con los encabezados en otra fila hacía que pandas tomara una fila de
metadata por encabezado, y después el import se quejaba con "no se encontró
columna de Resultado (V/m)": un mensaje que mandaba a buscar un nombre de
columna que sí existía, no decía nada de que el problema era la fila, y no
había manera de saberlo sin mirar el código.

`import_service.leer_excel` lee sin encabezado, puntúa cada una de las
primeras 20 filas contra los campos esperados y se queda con la que más
dé -- con el mismo match normalizado y el respaldo por prefijo que ya usaba
`_encontrar_columna`.
"""
import io

import pandas as pd
import pytest

from app.services import import_service

COLUMNAS = {
    "Resultado": ["1,5", "3.2", "10"],
    "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025"],
    "Hora": ["10:00:00", "10:30:00", "09:00:00"],
    "Lat": [-34.6037, -34.6040, -34.6050],
    "Lon": [-58.3816, -58.3820, -58.3830],
    "Sonda": ["S1", "S1", "S2"],
}


def _excel(fila_header: int, columnas: dict | None = None) -> bytes:
    """Un .xlsx con `fila_header` filas de metadata arriba de los encabezados."""
    df = pd.DataFrame(columnas if columnas is not None else COLUMNAS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if fila_header:
            meta = pd.DataFrame([[f"meta {i}"] for i in range(fila_header)])
            meta.to_excel(writer, index=False, header=False, startrow=0)
        df.to_excel(writer, index=False, startrow=fila_header)
    buf.seek(0)
    return buf.read()


@pytest.mark.parametrize("fila", [0, 1, 3, 8, 14])
def test_encabezados_en_cualquier_fila(fila):
    """Cualquier posición sirve. La 8 era la única que andaba antes."""
    df = import_service.leer_excel(_excel(fila))

    assert list(df.columns) == list(COLUMNAS.keys())
    assert len(df) == 3
    # La primera fila tiene que ser de datos, no de metadata.
    assert df.iloc[0]["Resultado"] == "1,5"


def test_encabezados_en_fila_9_el_caso_viejo():
    """Regresión: el layout original (8 filas de metadata) sigue andando."""
    df = import_service.leer_excel(_excel(8))

    assert list(df.columns) == list(COLUMNAS.keys())
    assert len(df) == 3
    assert df.iloc[2]["Fecha"] == "21/03/2025"


def test_nombre_de_columna_que_no_esta_en_la_lista():
    """"Resultado (V/m)" no figura en COLUMNAS_ESPERADAS, pero el respaldo por
    prefijo -- el mismo que ya usaba `_encontrar_columna` -- lo caza, y el
    puntaje de la fila lo cuenta igual que los demás campos."""
    columnas = {k: v for k, v in COLUMNAS.items() if k != "Resultado"}
    columnas["Resultado (V/m)"] = COLUMNAS["Resultado"]

    df = import_service.leer_excel(_excel(3, columnas))

    assert "Resultado (V/m)" in df.columns
    assert import_service._encontrar_columna(df, "resultado") == "Resultado (V/m)"


def test_encabezados_en_fila_0_sin_metadata_ni_renglon_de_titulo():
    """El archivo que reportó el usuario: encabezados arriba de todo."""
    df = import_service.leer_excel(_excel(0))

    assert list(df.columns) == list(COLUMNAS.keys())
    assert len(df) == 3
    assert df["Resultado"].tolist() == ["1,5", "3.2", "10"]


def test_sin_encabezados_reconocidos_vuelve_a_la_fila_8():
    """Fallo seguro: si NINGUNA fila llega al mínimo de campos esperados, se
    vuelve a la 8 -- el valor del `header=8` viejo -- para que el error que
    sigue sea exactamente el mismo de siempre en vez de inventar una fila al
    azar. (Acá hay 13 filas, así que el mínimo es 8.)"""
    columnas = {
        "Alfa": [f"a{i}" for i in range(12)],
        "Beta": [f"b{i}" for i in range(12)],
        "Gamma": [f"c{i}" for i in range(12)],
    }

    df = import_service.leer_excel(_excel(0, columnas))

    # fila 8 del archivo = "a7", "b7", "c7" (la fila 0 es la que dice
    # Alfa/Beta/Gamma y de ahí siguen los datos)
    assert list(df.columns) == ["a7", "b7", "c7"]


def test_columnas_vacias_y_repetidas_se_renombran():
    """`df[""]` y dos columnas "Fecha" no son nombres con los que se pueda
    trabajar en `_leer_y_normalizar`: sin renombrar, la segunda "Fecha" tapa
    a la primera y la vacía tira KeyError."""
    columnas = {"Fecha": ["20/03/2025"], "": ["10:00:00"], "Fecha ": ["S1"], "Lat": [-34.6037]}

    df = import_service.leer_excel(_excel(0, columnas))

    assert df.columns.tolist() == ["Fecha", "col_1", "Fecha_2", "Lat"]


def test_archivo_vacio_no_explota():
    """Un .xlsx sin filas devuelve un DataFrame vacío; el que se queja después
    es `_leer_y_normalizar`, con su mensaje de columna no encontrada."""
    buf = io.BytesIO()
    pd.DataFrame().to_excel(buf, index=False)
    buf.seek(0)

    df = import_service.leer_excel(buf.read())

    assert df.empty
