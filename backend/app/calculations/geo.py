r"""Normalización de coordenadas (DMS -> decimal).

Port de utils/geo_utils.py del sistema Streamlit actual. Contenía DOS bugs de
signo que ya están CORREGIDOS por default; el comportamiento legacy sigue
disponible por parámetro para poder reproducir lo que cargó el sistema
anterior:

1. (Fase 1, §5.5) Si el string DMS traía signo negativo en los grados pero NO
   traía letra de hemisferio, el signo se perdía: se aplicaba `abs(d)` siempre
   y solo se reaplicaba el signo si se detectaba una letra de hemisferio.

2. La letra de hemisferio NUNCA se detectaba, en NINGÚN input, incluso
   cuando estaba presente y bien formada (ej. "34° 30' 15\\" S"). La causa es
   que el regex original tiene `\D*\s*` (cualquier cantidad de caracteres
   no-numéricos) inmediatamente antes del grupo opcional de la letra de
   hemisferio -- como una letra también es "no numérica", ese `\D*` se come
   la letra antes de que el grupo de captura tenga oportunidad de matchearla,
   y como el grupo es opcional (`?`), el regex nunca necesita retroceder para
   intentar capturarla.

La corrección estaba pendiente de "confirmar con datos reales qué convención
usan los Excel de origen". Ya se confirmó, contra DOS archivos reales de
AutoMap, uno por generador:

    viejo:  26° 49' 52,187" S   y  65° 11' 42,766" O  -> DMS con letra
    nuevo:  -22.735365          y  -64.354018          -> decimal con signo

Los dos formatos conviven hoy en la base: las 9.828 filas del CCTE Salta ya
venían bien porque eran decimales, y las otras 209.990 traían DMS y guardaron
valores absolutos, que `migrate.py` tuvo que negar a mano. Con las dos
correcciones activadas los dos formatos dan el signo correcto sin
intervención, así que ninguna carga nueva necesita un arreglito posterior.

Para reproducir el comportamiento original (el sistema Streamlit actual):

    parse_dms_to_decimal(x, asumir_signo_de_grados=False,
                             corregir_deteccion_hemisferio=False)

Orden que importa: el caso decimal se resuelve ANTES del regex con un
`float()` directo, así que "-22.735365" nunca llega a la lógica de
hemisferio y no puede haber doble negación.
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
    asumir_signo_de_grados: bool = True,
    corregir_deteccion_hemisferio: bool = True,
) -> float | None:
    """Convierte una coordenada (decimal o DMS en texto) a grados decimales.

    Los dos flags vienen en True (ver el docstring del módulo: los dos bugs
    legacy ya están corregidos y el formato de origen está confirmado).
    Pasalos en False para reproducir el comportamiento del sistema Streamlit.
    """
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
