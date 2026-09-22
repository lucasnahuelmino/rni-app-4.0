r"""Normalización de coordenadas (DMS -> decimal).

Port de utils/geo_utils.py del sistema Streamlit actual, con DOS bugs de
signo documentados explícitamente (el segundo se descubrió recién al escribir
los tests de regresión de esta migración, es más grave que lo reportado en
la Auditoría Fase 1 y hay que sumarlo a los puntos a validar):

1. (Fase 1, §5.5) Si el string DMS trae signo negativo en los grados pero NO
   trae letra de hemisferio, el signo se pierde: se aplica `abs(d)` siempre y
   solo se reaplica el signo si se detectó una letra de hemisferio.

2. (NUEVO, encontrado en tests de regresión de Fase 3) La letra de hemisferio
   NUNCA se detecta, en NINGÚN input, incluso cuando está presente y bien
   formada (ej. "34° 30' 15\" S"). La causa es que el regex original tiene
   `\D*\s*` (cualquier cantidad de caracteres no-numéricos) inmediatamente
   antes del grupo opcional de la letra de hemisferio -- como una letra
   también es "no numérica", ese `\D*` se come la letra antes de que el grupo
   de captura tenga oportunidad de matchearla, y como el grupo es opcional
   (`?`), el regex nunca necesita retroceder para intentar capturarla.
   Consecuencia práctica: en el sistema Streamlit actual, TODA coordenada en
   formato DMS con letra de hemisferio devuelve un valor sin corregir el
   signo por hemisferio -- el signo depende únicamente de si el número de
   grados venía con signo negativo en el texto original.

Se preserva el comportamiento original (los dos bugs) por default, para no
alterar coordenadas de datos ya cargados sin validación. Los parámetros
`asumir_signo_de_grados` y `corregir_deteccion_hemisferio` permiten activar
cada corrección por separado una vez que el equipo confirme (con datos
reales) qué convención usan los Excel de origen.
"""
from __future__ import annotations

import math
import re

# Regex original -- preserva el bug #2 (la letra de hemisferio nunca se captura).
_DMS_RE_LEGACY = re.compile(
    r'([+-]?\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)\D*\s*([NnSsEeWwOo])?'
)
# Regex corregida: el separador antes de la letra de hemisferio excluye
# explícitamente las propias letras de hemisferio, para que si están
# presentes, el grupo de captura sí las levante.
_DMS_RE_CORREGIDA = re.compile(
    r'([+-]?\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)[^\dNnSsEeWwOo]*\s*([NnSsEeWwOo])?'
)
_NUM_RE = re.compile(r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)')


def parse_dms_to_decimal(
    val,
    asumir_signo_de_grados: bool = False,
    corregir_deteccion_hemisferio: bool = False,
) -> float | None:
    """Convierte una coordenada (decimal o DMS en texto) a grados decimales."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None

    try:
        return float(val)
    except (TypeError, ValueError):
        pass

    s = str(val).strip().replace(",", ".")

    patron = _DMS_RE_CORREGIDA if corregir_deteccion_hemisferio else _DMS_RE_LEGACY
    m = patron.search(s)
    if m:
        d = float(m.group(1))
        mnt = float(m.group(2))
        sec = float(m.group(3))
        hemi = (m.group(4) or "").upper()

        signo_grados = -1.0 if d < 0 else 1.0
        dec = abs(d) + mnt / 60.0 + sec / 3600.0

        if hemi in ("S", "W", "O"):
            dec = -dec
        elif not hemi and asumir_signo_de_grados:
            dec = dec * signo_grados
        return dec

    m2 = _NUM_RE.search(s)
    if m2:
        try:
            return float(m2.group(1))
        except ValueError:
            return None
    return None


def dentro_de_bbox(lat: float | None, lon: float | None, bbox: dict) -> bool:
    if lat is None or lon is None:
        return False
    return bbox["lat_min"] <= lat <= bbox["lat_max"] and bbox["lon_min"] <= lon <= bbox["lon_max"]
