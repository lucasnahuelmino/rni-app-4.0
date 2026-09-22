"""Normalización de fecha/hora.

Port directo de utils/time_utils.py del sistema Streamlit actual -- esa
función ya estaba bien escrita (vectorizada, sin loops fila por fila) y no
tiene inconsistencias detectadas en la Auditoría Fase 1. El comportamiento
NO cambia; solo se centraliza acá para que la importación persista
`fecha_hora` y `anio` en vez de recalcularlos en cada consulta.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd


def _normalize_time_str(s: pd.Series) -> pd.Series:
    out = s.astype("string").fillna("").str.strip().str.lower()
    out = out.str.replace(r"\s+", "", regex=True)
    out = out.str.replace(".", "", regex=False)
    out = out.str.replace("a:m", "am", regex=False)
    out = out.str.replace("p:m", "pm", regex=False)
    return out


def add_fecha_hora(df: pd.DataFrame, fecha_col: str = "fecha_raw", hora_col: str = "hora_raw",
                    out_col: str = "fecha_hora") -> pd.DataFrame:
    """Agrega `out_col` (datetime) combinando fecha y hora de forma robusta."""
    if df is None or df.empty:
        out = df.copy() if df is not None else pd.DataFrame()
        out[out_col] = pd.NaT
        return out

    out = df.copy()
    if fecha_col not in out.columns or hora_col not in out.columns:
        out[out_col] = pd.NaT
        return out

    fecha_dt = pd.to_datetime(out[fecha_col], dayfirst=True, errors="coerce").dt.normalize()

    hora_norm = _normalize_time_str(out[hora_col])
    hora_dt = pd.Series(pd.NaT, index=hora_norm.index, dtype="datetime64[ns]")
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S%p", "%I:%M%p"):
        parsed = pd.to_datetime(hora_norm, format=fmt, errors="coerce")
        hora_dt = hora_dt.fillna(parsed)

    hora_td = (
        pd.to_timedelta(hora_dt.dt.hour.fillna(0).astype("int64"), unit="h")
        + pd.to_timedelta(hora_dt.dt.minute.fillna(0).astype("int64"), unit="m")
        + pd.to_timedelta(hora_dt.dt.second.fillna(0).astype("int64"), unit="s")
    )

    out[out_col] = fecha_dt + hora_td
    invalid = fecha_dt.isna() | hora_dt.isna()
    out.loc[invalid, out_col] = pd.NaT
    return out


def anio_de_fecha_hora(fecha_hora) -> int | None:
    """Extrae el año de un valor de fecha_hora (datetime, Timestamp, ISO string o None)."""
    if fecha_hora is None or (isinstance(fecha_hora, float) and pd.isna(fecha_hora)):
        return None
    ts = pd.Timestamp(fecha_hora)
    if pd.isna(ts):
        return None
    return int(ts.year)


def format_timedelta_long(td) -> str:
    """'2 h 13 min 05 s' / '13 min 05 s' / '0 s'."""
    if td is None:
        return "0 s"
    if not isinstance(td, timedelta):
        try:
            td = timedelta(seconds=float(td))
        except Exception:
            return "0 s"

    total_seconds = max(int(td.total_seconds()), 0)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours} h {minutes:02d} min {seconds:02d} s"
    if minutes > 0:
        return f"{minutes} min {seconds:02d} s"
    return f"{seconds} s"


def calcular_tiempo_trabajado_segundos(df: pd.DataFrame) -> int:
    """Suma (fin - inicio) por archivo+día, usando fecha_hora ya calculada.

    Espera que `df` ya tenga la columna `fecha_hora` (agregada con
    `add_fecha_hora`). Si `nombre_archivo` está presente, agrupa por
    (nombre_archivo, día); si no, agrupa solo por día.
    """
    if df is None or df.empty or "fecha_hora" not in df.columns:
        return 0

    out = df.dropna(subset=["fecha_hora"]).copy()
    if out.empty:
        return 0

    out["_dia"] = pd.to_datetime(out["fecha_hora"]).dt.date
    group_cols = ["_dia"]
    if "nombre_archivo" in out.columns:
        group_cols = ["nombre_archivo", "_dia"]

    agg = out.groupby(group_cols)["fecha_hora"].agg(["min", "max"]).reset_index()
    agg["min"] = pd.to_datetime(agg["min"])
    agg["max"] = pd.to_datetime(agg["max"])
    dur = (agg["max"] - agg["min"]).dropna()
    if dur.empty:
        return 0
    return int(dur.sum().total_seconds())
