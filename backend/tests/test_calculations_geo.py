from app.calculations.geo import dentro_de_bbox, parse_dms_to_decimal
from app.core.config import ARGENTINA_BBOX


def test_decimal_directo():
    assert parse_dms_to_decimal(-58.381) == -58.381
    assert parse_dms_to_decimal("-58,381") == -58.381


def test_dms_con_hemisferio_nunca_se_detecta_por_default_reproduce_bug_actual():
    """Bug descubierto en los tests de regresión de Fase 3 (más grave que lo
    reportado en Auditoría Fase 1 §5.5): la letra de hemisferio NUNCA se
    captura con el regex original, ni siquiera estando presente y bien
    formada. Por default se reproduce ese comportamiento (no se corrige
    silenciosamente)."""
    resultado = parse_dms_to_decimal('34° 30\' 15" S')
    assert resultado > 0  # BUG reproducido intencionalmente: "S" se ignora


def test_dms_con_hemisferio_corregido_detecta_la_letra():
    resultado = parse_dms_to_decimal('34° 30\' 15" S', corregir_deteccion_hemisferio=True)
    assert resultado < 0
    assert round(resultado, 5) == -34.50417


def test_dms_sin_hemisferio_con_signo_negativo_reproduce_bug_fase1():
    """Documenta el bug de la Auditoría Fase 1 §5.5: sin hemisferio explícito
    y con `asumir_signo_de_grados=False` (comportamiento por default, igual
    al sistema Streamlit actual), el signo se pierde."""
    resultado = parse_dms_to_decimal('-34° 30\' 15"')
    assert resultado > 0  # BUG reproducido intencionalmente


def test_dms_sin_hemisferio_con_fix_activado_preserva_signo():
    resultado = parse_dms_to_decimal('-34° 30\' 15"', asumir_signo_de_grados=True)
    assert resultado < 0
    assert round(resultado, 5) == -34.50417


def test_valor_invalido_devuelve_none():
    assert parse_dms_to_decimal(None) is None
    assert parse_dms_to_decimal("texto sin numeros") is None


def test_dentro_de_bbox_argentina():
    assert dentro_de_bbox(-34.6, -58.4, ARGENTINA_BBOX) is True  # Buenos Aires
    assert dentro_de_bbox(40.7, -74.0, ARGENTINA_BBOX) is False  # Nueva York
    assert dentro_de_bbox(None, -58.4, ARGENTINA_BBOX) is False
