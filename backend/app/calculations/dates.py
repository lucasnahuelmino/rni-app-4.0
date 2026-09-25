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


def _agrupar_por_archivo_dia(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa por (nombre_archivo, día) -- o solo por día si no hay
    nombre_archivo -- y devuelve inicio/fin de cada grupo. Es el mismo
    agrupamiento que ya usaba `calcular_tiempo_trabajado_segundos`;
    se extrae acá para poder reutilizarlo también en el desglose diario
    y mensual (Fase 6, punto 8: una única lógica de negocio, no una
    fórmula distinta por pantalla)."""
    if df is None or df.empty or "fecha_hora" not in df.columns:
        return pd.DataFrame(columns=["nombre_archivo", "_dia", "min", "max"])

    out = df.dropna(subset=["fecha_hora"]).copy()
    if out.empty:
        return pd.DataFrame(columns=["nombre_archivo", "_dia", "min", "max"])

    out["_dia"] = pd.to_datetime(out["fecha_hora"]).dt.date
    group_cols = ["_dia"]
    if "nombre_archivo" in out.columns:
        group_cols = ["nombre_archivo", "_dia"]

    agg = out.groupby(group_cols)["fecha_hora"].agg(["min", "max"]).reset_index()
    agg["min"] = pd.to_datetime(agg["min"])
    agg["max"] = pd.to_datetime(agg["max"])
    if "nombre_archivo" not in agg.columns:
        agg["nombre_archivo"] = None
    return agg


def calcular_tiempo_trabajado_segundos(df: pd.DataFrame) -> int:
    """Suma (fin - inicio) por archivo+día, usando fecha_hora ya calculada.

    Espera que `df` ya tenga la columna `fecha_hora` (agregada con
    `add_fecha_hora`). Si `nombre_archivo` está presente, agrupa por
    (nombre_archivo, día); si no, agrupa solo por día.
    """
    agg = _agrupar_por_archivo_dia(df)
    if agg.empty:
        return 0
    dur = (agg["max"] - agg["min"]).dropna()
    if dur.empty:
        return 0
    return int(dur.sum().total_seconds())


def desglose_diario(df: pd.DataFrame) -> list[dict]:
    """Detalle día por día: fecha, hora de inicio, hora de fin, duración.

    Si un mismo día tiene más de un archivo, se listan como filas separadas
    (igual que agrupaba la aplicación Streamlit original) -- no se suman
    entre sí para no ocultar que fueron jornadas/archivos distintos.
    """
    return desglose_diario_desde_agrupado(_agrupar_por_archivo_dia(df))


def desglose_diario_desde_agrupado(agg: pd.DataFrame) -> list[dict]:
    """Detalle día por día sobre un `agg` ya agrupado (nombre_archivo, _dia,
    min, max).

    `agg` puede venir de `_agrupar_por_archivo_dia` (pandas) o de
    `mediciones_repo.agrupar_min_max_por_archivo_dia` (SQL): da lo mismo,
    porque `pd.Timestamp()` normaliza por igual el datetime de pandas y el
    texto ISO que devuelve SQLite. Lo único que cambia es quién agrupa, y
    eso es lo que fija `test_agrupado_en_sql_igual_que_en_pandas`.

    Está separado de `desglose_diario` por rendimiento: el camino SQL trae
    241 filas en vez de 219 818, y todo lo de acá abajo (duración, formato,
    orden) es idéntico al de siempre.
    """
    if agg is None or agg.empty:
        return []

    agg = agg.sort_values("_dia")
    resultado = []
    for _, row in agg.iterrows():
        min_dt = pd.Timestamp(row["min"])
        max_dt = pd.Timestamp(row["max"])
        duracion_seg = int((max_dt - min_dt).total_seconds())
        resultado.append({
            "fecha": str(row["_dia"]),
            "nombre_archivo": row["nombre_archivo"],
            "inicio": min_dt.strftime("%H:%M:%S"),
            "fin": max_dt.strftime("%H:%M:%S"),
            "duracion_seg": duracion_seg,
            "duracion_fmt": format_timedelta_long(duracion_seg),
        })
    return resultado


def desglose_mensual(desglose_diario_list: list[dict]) -> list[dict]:
    """Agrupa el desglose diario (`desglose_diario()`) por mes: tiempo
    trabajado total y cantidad de días distintos con medición.

    Se calcula a partir del desglose diario ya sumado por jornada, NO
    tomando min/max directo del mes completo -- eso mezclaría jornadas de
    días distintos en un solo intervalo y sobrestimaría groseramente el
    tiempo trabajado (ver nota en Fase 6)."""
    if not desglose_diario_list:
        return []

    df = pd.DataFrame(desglose_diario_list)
    df["mes"] = df["fecha"].str.slice(0, 7)
    agrupado = df.groupby("mes").agg(
        tiempo_trabajado_seg=("duracion_seg", "sum"),
        dias_con_medicion=("fecha", "nunique"),
    ).reset_index().sort_values("mes")

    return [
        {
            "mes": row["mes"],
            "tiempo_trabajado_seg": int(row["tiempo_trabajado_seg"]),
            "tiempo_trabajado_fmt": format_timedelta_long(int(row["tiempo_trabajado_seg"])),
            "dias_con_medicion": int(row["dias_con_medicion"]),
        }
        for _, row in agrupado.iterrows()
    ]
