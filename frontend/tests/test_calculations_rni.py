import math

from app.calculations.rni import (
    pct_del_promedio_legacy,
    promedio_pct_de_valores,
    resultado_pct,
)


def _formula_streamlit_actual(resultado_vm: float) -> float:
    """Reimplementación literal de la fórmula tal como aparece en el
    repositorio Streamlit auditado, para verificar equivalencia exacta."""
    return (resultado_vm ** 2) / 3770 / 0.20021 * 100


def test_resultado_pct_coincide_con_formula_actual():
    for vm in [0.5, 1.0, 3.7, 10.0, 27.35, 0.0]:
        assert math.isclose(resultado_pct(vm), _formula_streamlit_actual(vm), rel_tol=1e-12)


def test_resultado_pct_none_para_none():
    assert resultado_pct(None) is None


def test_resultado_pct_cero_da_cero():
    assert resultado_pct(0.0) == 0.0


def test_promedio_pct_no_es_igual_al_metodo_legacy_con_dispersion():
    """Demuestra la discrepancia matemática documentada en la Auditoría Fase 1, §5.2:
    mean(x^2) != mean(x)^2 para valores con dispersión."""
    valores = [1.0, 5.0, 10.0]
    correcto = promedio_pct_de_valores(valores)
    legacy = pct_del_promedio_legacy(valores)
    assert correcto > legacy  # Jensen: la fórmula legacy subestima


def test_promedio_pct_coincide_con_legacy_si_todos_los_valores_son_iguales():
    valores = [5.0, 5.0, 5.0]
    assert math.isclose(promedio_pct_de_valores(valores), pct_del_promedio_legacy(valores), rel_tol=1e-9)


def test_promedio_pct_vacio_es_none():
    assert promedio_pct_de_valores([]) is None
    assert pct_del_promedio_legacy([]) is None


def test_promedio_pct_ignora_none():
    valores = [1.0, None, 3.0]
    esperado = promedio_pct_de_valores([1.0, 3.0])
    assert math.isclose(promedio_pct_de_valores(valores), esperado, rel_tol=1e-12)
