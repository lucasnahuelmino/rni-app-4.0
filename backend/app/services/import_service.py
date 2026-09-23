"""Orquesta el pipeline de importación:

Excel -> lectura -> validación -> normalización -> detección de duplicados
-> cálculos derivados -> inserción -> actualización de resúmenes -> reporte.

Port funcional de processing/excel_processor.py + sections/carga_excel.py del
sistema Streamlit, sin UI y con persistencia real del reporte de importación
(Auditoría Fase 1: hoy ese reporte solo vive en memoria de la sesión).
"""
from __future__ import annotations

import json
import sqlite3
import unicodedata
from datetime import datetime, timezone

import pandas as pd

from app.calculations.dates import add_fecha_hora, anio_de_fecha_hora
from app.calculations.geo import parse_dms_to_decimal
from app.calculations.rni import resultado_pct
from app.db.repositories import import_repo, mediciones_repo
from app.services import statistics as statistics_service
from app.utils.excel_utils import extract_numeric_from_text

# Nombres de encabezado aceptados por campo, en orden de prioridad.
#
# NINGÚN generador real trae una columna llamada literalmente "Resultado":
# hay DOS formatos en uso y los dos lo nombran distinto -- el legacy/Streamlit
# traía "Resultado" y los Excel de AutoMap traen "Resultado con incertidumbre".
# Están los tres encabezados verificados contra archivos reales de origen
# (uno por generador) más las variantes cortas que ya estaban contempladas.
#
# Las mayúsculas, los acentos y los espacios sobrantes NO deberían decidir si
# una columna se encuentra o no: la comparación se hace sobre
# `_normalizar_encabezado`, así que "RESULTADO" y "Resultado" matchean igual.
COLUMNAS_ESPERADAS = {
    "resultado": ["Resultado", "Resultado con incertidumbre", "V/m", "Vm"],
    "fecha": ["Fecha"],
    "hora": ["Hora"],
    "lat": ["Lat", "Latitud"],
    "lon": ["Lon", "Longitud"],
    "sonda": ["Sonda"],
}


def _normalizar_encabezado(nombre) -> str:
    """Versión comparable de un encabezado: sin acentos, en minúsculas y con
    los espacios colapsados. `None` y no-str devuelven ""."""
    if nombre is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.casefold().split())


def _encontrar_columna(df: pd.DataFrame, campo: str) -> str | None:
    """Devuelve el nombre ORIGINAL de la columna para `campo`.

    Primero intenta match exacto (normalizado) contra COLUMNAS_ESPERADAS[campo]
    y recién después, solo para `resultado`, un respaldo por prefijo: así
    cualquier variante futura del generador que empiece con "Resultado"
    ("Resultado con incertidumbre", "Resultado (V/m)", "Resultado V/m") entra
    sin tocar código. El respaldo no puede caer en "Tipo de resultado" -- que
    es el tipo ("Max Hold"), no el valor -- porque esa columna empieza con
    "tipo", y en los archivos reales además va DESPUÉS de la de valores.
    """
    indice: dict[str, object] = {}
    for col in df.columns:
        indice.setdefault(_normalizar_encabezado(col), col)

    for candidata in COLUMNAS_ESPERADAS[campo]:
        hit = indice.get(_normalizar_encabezado(candidata))
        if hit is not None:
            return hit  # type: ignore[return-value]

    if campo == "resultado":
        for col in df.columns:
            if _normalizar_encabezado(col).startswith("resultado"):
                return col  # type: ignore[return-value]
    return None


def _leer_y_normalizar(df_excel: pd.DataFrame, nombre_archivo: str) -> tuple[pd.DataFrame, list[str]]:
    """Devuelve (DataFrame normalizado, lista de advertencias)."""
    advertencias: list[str] = []
    out = pd.DataFrame()

    col_resultado = _encontrar_columna(df_excel, "resultado")
    col_fecha = _encontrar_columna(df_excel, "fecha")
    col_hora = _encontrar_columna(df_excel, "hora")
    col_lat = _encontrar_columna(df_excel, "lat")
    col_lon = _encontrar_columna(df_excel, "lon")
    col_sonda = _encontrar_columna(df_excel, "sonda")

    if col_resultado is None:
        # El listado completo es a propósito: el usuario necesita saber QUÉ
        # buscaba, no solo que algo falló.
        esperadas = ", ".join(COLUMNAS_ESPERADAS["resultado"])
        encontradas = ", ".join(str(c) for c in df_excel.columns)
        advertencias.append(
            f"{nombre_archivo}: no se encontró columna de Resultado (V/m). "
            f"Se buscaba entre: {esperadas}. Columnas disponibles: {encontradas}."
        )
        out["resultado_vm"] = pd.NA
    else:
        out["resultado_vm"] = extract_numeric_from_text(df_excel[col_resultado])

    out["fecha_raw"] = df_excel[col_fecha].astype(str) if col_fecha else None
    out["hora_raw"] = df_excel[col_hora].astype(str) if col_hora else None
    out["lat_raw"] = df_excel[col_lat].astype(str) if col_lat else None
    out["lon_raw"] = df_excel[col_lon].astype(str) if col_lon else None
    out["sonda"] = df_excel[col_sonda].astype(str) if col_sonda else None
    out["nombre_archivo"] = nombre_archivo

    out["lat"] = out["lat_raw"].apply(parse_dms_to_decimal) if col_lat else None
    out["lon"] = out["lon_raw"].apply(parse_dms_to_decimal) if col_lon else None

    out = add_fecha_hora(out, fecha_col="fecha_raw", hora_col="hora_raw", out_col="fecha_hora")
    out["anio"] = out["fecha_hora"].apply(anio_de_fecha_hora)
    out["resultado_pct"] = out["resultado_vm"].apply(
        lambda v: resultado_pct(float(v)) if pd.notna(v) else None
    )

    return out, advertencias


def importar_lote(conn: sqlite3.Connection, *, ccte: str, provincia: str, localidad: str,
                   expediente: str | None, archivos: list[tuple[str, pd.DataFrame]]) -> dict:
    """`archivos` es una lista de (nombre_archivo, DataFrame ya leído desde Excel).

    Devuelve el reporte de importación (mismo dict que se persiste en
    import_batches).
    """
    ahora = datetime.now(timezone.utc).isoformat()
    batch_id = import_repo.crear_batch(conn, ccte, provincia, localidad, expediente, ahora)

    registros_nuevos = 0
    registros_duplicados = 0
    registros_rechazados = 0
    errores: list[dict] = []
    advertencias: list[dict] = []
    claves_tocadas: set[tuple[str, str, str]] = set()

    for nombre_archivo, df_excel in archivos:
        try:
            normalizado, warns = _leer_y_normalizar(df_excel, nombre_archivo)
            for w in warns:
                advertencias.append({"archivo": nombre_archivo, "advertencia": w})
        except Exception as exc:  # noqa: BLE001
            errores.append({"archivo": nombre_archivo, "error": str(exc)})
            continue

        filas_a_insertar = []
        for _, fila in normalizado.iterrows():
            resultado_vm = None if pd.isna(fila.get("resultado_vm")) else float(fila["resultado_vm"])
            fecha_hora_val = fila.get("fecha_hora")
            fecha_hora_iso = None if pd.isna(fecha_hora_val) else pd.Timestamp(fecha_hora_val).isoformat()

            if resultado_vm is None:
                registros_rechazados += 1
                continue

            if mediciones_repo.existe_medicion(
                conn, ccte, provincia, localidad, fecha_hora_iso, resultado_vm
            ):
                registros_duplicados += 1
                continue

            filas_a_insertar.append({
                "ccte": ccte, "provincia": provincia, "localidad": localidad,
                "resultado_vm": resultado_vm,
                "resultado_pct": None if pd.isna(fila.get("resultado_pct")) else float(fila["resultado_pct"]),
                "fecha_raw": fila.get("fecha_raw"),
                "hora_raw": fila.get("hora_raw"),
                "fecha_hora": fecha_hora_iso,
                "anio": None if pd.isna(fila.get("anio")) else int(fila["anio"]),
                "lat": None if pd.isna(fila.get("lat")) else float(fila["lat"]),
                "lon": None if pd.isna(fila.get("lon")) else float(fila["lon"]),
                "lat_raw": fila.get("lat_raw"),
                "lon_raw": fila.get("lon_raw"),
                "expediente": expediente,
                "sonda": fila.get("sonda"),
                "nombre_archivo": nombre_archivo,
                "import_batch_id": batch_id,
                "fecha_carga": ahora,
            })

        mediciones_repo.insertar_mediciones(conn, filas_a_insertar)
        registros_nuevos += len(filas_a_insertar)
        claves_tocadas.add((ccte, provincia, localidad))

    import_repo.cerrar_batch(
        conn, batch_id,
        archivos_procesados=len(archivos),
        registros_nuevos=registros_nuevos,
        registros_duplicados=registros_duplicados,
        registros_rechazados=registros_rechazados,
        errores_json=json.dumps(errores, ensure_ascii=False) if errores else None,
        advertencias_json=json.dumps(advertencias, ensure_ascii=False) if advertencias else None,
    )

    if claves_tocadas:
        statistics_service.recalcular(conn, claves_tocadas)

    return {
        "id": batch_id,
        "fecha_carga": ahora,
        "ccte": ccte, "provincia": provincia, "localidad": localidad, "expediente": expediente,
        "archivos_procesados": len(archivos),
        "registros_nuevos": registros_nuevos,
        "registros_duplicados": registros_duplicados,
        "registros_rechazados": registros_rechazados,
        "errores": errores,
        "advertencias": advertencias,
    }
