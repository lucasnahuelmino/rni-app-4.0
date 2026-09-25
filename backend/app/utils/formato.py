"""Formateo de V/m y % para los informes Word y PDF.

Gemelo de `frontend/src/format.js` (fmtVm / fmtPct): mismo criterio, mismos
decimales, para que lo que dice el informe impreso sea lo mismo que lo que
muestra la pantalla.

La regla es no redondear lo que la base guarda. El instrumento mide en
pasos de 0,001 y el 83,32 % de los valores (183.160 de 219.818) tiene 3
decimales, así que un `:.2f` se comía el tercer decimal ("0.942 -> 0.94")
y en los más chicos dejaba cero ("0.001 -> 0.00", "0.005 -> 0.01"). El %
en cambio es un float calculado con 17 dígitos, y ahí sí se acota -- pero
hasta 4, que es lo que alcanza para no mostrar "0,0 %" para un valor que
no es cero.

Devolven strings listos para imprimir y sin ceros de relleno:
    19.260 -> "19.26"     0.000 -> "0"     0.942 -> "0.942"
"""
from __future__ import annotations

import math

SIN_VALOR = "-"

# Decimales del instrumento. Es el máximo que existe en `mediciones`, así
# que formatear con estos nunca pierde un dígito real: solo limpia ruido de
# punto flotante en el caso de que un V/m salga de un cálculo en vez de
# venir leído del Excel.
DECIMALES_VM = 3

# El % es derivado (vm^2 / 3770 / limite * 100) y la base guarda el float
# completo; 4 decimales son los que usa el frontend.
DECIMALES_PCT = 4


def vm(valor: float | None) -> str:
    """V/m con la precisión exacta de la base, sin ceros de relleno."""
    if _sin_valor(valor):
        return SIN_VALOR
    return _sin_ceros(f"{float(valor):.{DECIMALES_VM}f}")


def pct(valor: float | None) -> str:
    """% del límite con hasta 4 decimales, sin ceros de relleno."""
    if _sin_valor(valor):
        return SIN_VALOR
    return _sin_ceros(f"{float(valor):.{DECIMALES_PCT}f}")


def _sin_valor(valor) -> bool:
    """`None` o `NaN`.

    El NaN hace falta mirarlo aparte porque `f"{nan:.3f}"` no falla: imprime
    "nan", que era exactamente lo que podía llegar a decir un informe si un
    resumen traía el máximo vacío. `numpy.float64` es subclase de `float`,
    así que el isinstance también cubre los NaN que vienen de pandas.
    """
    if valor is None:
        return True
    return isinstance(valor, float) and math.isnan(valor)


def _sin_ceros(texto: str) -> str:
    """`19.260` -> `19.26`, `0.000` -> `0`, `100.000` -> `100`.

    Solo se recortan los ceros DESPUÉS del punto: en `100.000` el cero de
    "100" no es trailing (lo separa el punto), así que `rstrip("0")` solo se
    come los tres del decimal y después se va el punto sobrante.
    """
    if "." not in texto:
        return texto
    return texto.rstrip("0").rstrip(".") or "0"
