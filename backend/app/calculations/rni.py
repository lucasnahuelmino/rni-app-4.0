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
# CONSTANTE ÚNICA POR DECISIÓN, no por omisión (Auditoría Fase 1, punto
# bloqueante #1, CERRADO con el equipo): normativamente el límite sí varía
# con la frecuencia, pero los Excel de origen no traen banda, frecuencia ni
# servicio. Las únicas columnas que reconoce el import son resultado, fecha,
# hora, lat, lon, sonda, expediente, ccte, provincia y localidad, y el
# esquema tampoco las tiene -- así que un límite por frecuencia es hoy
# inimplementable por falta del dato, no por falta de código.
#
# Si algún día llega ese dato: mapear frecuencia -> limite y reemplazar esta
# constante por esa tabla. NO cambiar el valor actual sin reimportar todo,
# porque recalcularía los `resultado_pct` históricos de una.
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

    Auditoría Fase 1, punto bloqueante #2 (CERRADO con el equipo): el
    dashboard Streamlit actual calcula el "Promedio %" del segundo modo
    (aplica la fórmula cuadrática al promedio de V/m), lo cual subestima
    sistemáticamente el promedio real de los porcentajes individuales
    (desigualdad de Jensen, la función es convexa). Esta es la versión
    matemáticamente correcta y es la que está en producción: puebla
    `resumen_localidad.resultado_prom_pct`, los KPIs y el ranking de
    Gráficos.

    El impacto se midió sobre los datos reales (61 localidades, 219 818
    mediciones) contra `pct_del_promedio_legacy`: diferencia máxima 0,233 pp
    en Cosquín, mediana 0,043 pp, y NINGUNA localidad cruza un umbral del
    semáforo. O sea que la corrección no mueve ningún color ni ningún punto
    del mapa -- solo aclara el número.
    """
    valores = [resultado_pct(r) for r in resultados_vm if r is not None]
    if not valores:
        return None
    return sum(valores) / len(valores)


def pct_del_promedio_legacy(resultados_vm: list[float]) -> float | None:
    """Replica EXACTA del cálculo actual del dashboard Streamlit.

    Se conserva únicamente para tests de regresión / comparación (Fase 5) y
    para poder rehacer la medición de impacto de `promedio_pct_de_valores`
    cuando haga falta. No usar en código nuevo: es la que subestima el
    promedio (ver el docstring de la función de al lado).
    """
    valores = [r for r in resultados_vm if r is not None]
    if not valores:
        return None
    promedio_vm = sum(valores) / len(valores)
    return resultado_pct(promedio_vm)
