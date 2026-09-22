"""Funciones puras de agregación sobre filas de mediciones (dicts).

Estas funciones no tocan la base de datos -- reciben listas de filas
(sqlite3.Row o dict) y devuelven los agregados. Las usa
app/services/statistics.py para poblar resumen_localidad / resumen_ccte /
resumen_provincia / resumen_anual.
"""
from __future__ import annotations

from app.calculations.dates import calcular_tiempo_trabajado_segundos, format_timedelta_long  # noqa: F401
from app.calculations.rni import promedio_pct_de_valores


def agregar_mediciones(filas: list[dict]) -> dict:
    """Agregados básicos de un conjunto de mediciones: conteo, máximos, promedio,
    fecha inicio/fin, tiempo trabajado.
    """
    import pandas as pd

    if not filas:
        return {
            "mediciones": 0,
            "resultado_max_vm": None,
            "resultado_max_pct": None,
            "resultado_prom_pct": None,
            "fecha_inicio": None,
            "fecha_fin": None,
            "tiempo_trabajado_seg": 0,
            "dias_con_medicion": 0,
        }

    df = pd.DataFrame(filas)
    resultados_vm = df["resultado_vm"].dropna().tolist()

    resultado_max_vm = df["resultado_vm"].max() if "resultado_vm" in df else None
    resultado_max_pct = df["resultado_pct"].max() if "resultado_pct" in df else None
    resultado_prom_pct = promedio_pct_de_valores(resultados_vm)

    fecha_hora_valida = df["fecha_hora"].dropna() if "fecha_hora" in df else None
    fecha_inicio = fecha_hora_valida.min() if fecha_hora_valida is not None and not fecha_hora_valida.empty else None
    fecha_fin = fecha_hora_valida.max() if fecha_hora_valida is not None and not fecha_hora_valida.empty else None

    tiempo_trabajado_seg = calcular_tiempo_trabajado_segundos(df) if "fecha_hora" in df else 0
    dias_con_medicion = (
        df["fecha_hora"].dropna().apply(lambda x: str(x)[:10]).nunique() if "fecha_hora" in df else 0
    )

    return {
        "mediciones": len(df),
        "resultado_max_vm": None if resultado_max_vm is None or pd.isna(resultado_max_vm) else float(resultado_max_vm),
        "resultado_max_pct": None if resultado_max_pct is None or pd.isna(resultado_max_pct) else float(resultado_max_pct),
        "resultado_prom_pct": resultado_prom_pct,
        "fecha_inicio": None if fecha_inicio is None else str(fecha_inicio),
        "fecha_fin": None if fecha_fin is None else str(fecha_fin),
        "tiempo_trabajado_seg": tiempo_trabajado_seg,
        "dias_con_medicion": int(dias_con_medicion),
    }
