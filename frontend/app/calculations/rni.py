"""Fórmulas de negocio del dominio RNI.

Punto de cambio único para la fórmula que hoy está copiada en 12 lugares
del sistema Streamlit (ver Auditoría Fase 1, §5.1). El valor de las
constantes NO se modificó respecto del sistema actual -- la migración no
debe alterar resultados históricos sin validación explícita.
"""
from __future__ import annotations

# Impedancia del espacio libre (377 ohm) x10, para convertir V/m -> mW/cm^2.
IMPEDANCIA_ESPACIO_LIBRE_X10 = 3770.0

# Límite normativo de referencia en mW/cm^2 usado para expresar el resultado
# como porcentaje del límite.
#
# PENDIENTE DE CONFIRMACIÓN (Auditoría Fase 1, punto bloqueante #1): no está
# confirmado si este valor debe variar según la frecuencia/servicio medido.
# Hasta tener esa confirmación se mantiene como constante única, igual que
# en el sistema Streamlit actual.
LIMITE_REFERENCIA_MW_CM2 = 0.20021


def resultado_pct(resultado_vm: float | None) -> float | None:
    """% del límite normativo a partir de un resultado individual en V/m.

    Fórmula: (V/m)^2 / 3770 / limite * 100.
    Verificada como matemáticamente equivalente a las 12 implementaciones
    dispersas del sistema actual (Auditoría Fase 1, §5.1).
    """
    if resultado_vm is None:
        return None
    return (resultado_vm ** 2) / IMPEDANCIA_ESPACIO_LIBRE_X10 / LIMITE_REFERENCIA_MW_CM2 * 100


def promedio_pct_de_valores(resultados_vm: list[float]) -> float | None:
    """Promedio de los % individuales de una lista de resultados en V/m.

    Esto es `mean(resultado_pct(r) for r in resultados)`, NO
    `resultado_pct(mean(resultados))`.

    Auditoría Fase 1, punto bloqueante #2: el dashboard Streamlit actual
    calcula el "Promedio %" del segundo modo (aplica la fórmula cuadrática
    al promedio de V/m), lo cual subestima sistemáticamente el promedio real
    de los porcentajes individuales (desigualdad de Jensen, la función es
    convexa). Esta función implementa la versión matemáticamente correcta;
    se usa para poblar `resumen_localidad.resultado_prom_pct` y los KPIs
    nuevos. Es un cambio de comportamiento respecto del sistema actual y
    debe validarse con el equipo antes de reemplazar el KPI visible en
    producción.
    """
    valores = [resultado_pct(r) for r in resultados_vm if r is not None]
    if not valores:
        return None
    return sum(valores) / len(valores)


def pct_del_promedio_legacy(resultados_vm: list[float]) -> float | None:
    """Replica EXACTA del cálculo actual del dashboard Streamlit.

    Se conserva únicamente para tests de regresión / comparación durante la
    migración (Fase 5). No usar en código nuevo.
    """
    valores = [r for r in resultados_vm if r is not None]
    if not valores:
        return None
    promedio_vm = sum(valores) / len(valores)
    return resultado_pct(promedio_vm)
