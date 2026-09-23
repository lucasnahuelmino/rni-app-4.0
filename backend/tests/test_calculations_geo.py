from app.calculations.geo import dentro_de_bbox, parse_dms_to_decimal
from app.core.config import ARGENTINA_BBOX


def test_decimal_directo():
    assert parse_dms_to_decimal(-58.381) == -58.381
    assert parse_dms_to_decimal("-58,381") == -58.381


def test_dms_con_hemisferio_se_detecta_por_default():
    """El formato de origen está confirmado con DOS archivos reales de AutoMap:
    traen la letra de hemisferio, así que detectarla pasó a ser el
    comportamiento por default."""
    resultado = parse_dms_to_decimal('34° 30\' 15" S')
    assert resultado < 0
    assert round(resultado, 5) == -34.50417


def test_dms_con_oeste_tambien_se_detecta():
    """Coordenada real de "SAN MIGUEL DE TUCUMAN 1.xlsx": la O es Oeste, no
    Este. Con el regex legacy esto devolvía +65.19 y el punto caía en Asia."""
    resultado = parse_dms_to_decimal('65° 11\' 42,766" O')
    assert resultado < 0
    assert round(resultado, 5) == -65.19521


def test_dms_con_hemisferio_comportamiento_legacy_sigue_disponible():
    """El bug original sigue reproducible a pedido: sirve para comparar contra
    lo que ya cargó el sistema Streamlit."""
    resultado = parse_dms_to_decimal('34° 30\' 15" S', corregir_deteccion_hemisferio=False)
    assert resultado > 0  # la "S" sigue sin capturarse con el regex viejo


def test_dms_sin_hemisferio_preserva_el_signo_por_default():
    """Fase 1 §5.5: grados negativos sin letra de hemisferio. El signo estaba
    en el texto y se tiraba."""
    resultado = parse_dms_to_decimal('-34° 30\' 15"')
    assert resultado < 0
    assert round(resultado, 5) == -34.50417


def test_dms_sin_hemisferio_comportamiento_legacy_sigue_disponible():
    resultado = parse_dms_to_decimal('-34° 30\' 15"', asumir_signo_de_grados=False)
    assert resultado > 0  # bug legacy reproducido a pedido


def test_formato_decimal_no_pasa_por_la_logica_de_hemisferio():
    """Coordenada real de "AGUAS BLANCAS 2026-09-01 ..._reporte.xlsx". El
    `float()` se resuelve ANTES del regex, así que no hay doble negación
    aunque el flag de hemisferio esté activo."""
    assert parse_dms_to_decimal("-22.735365") == -22.735365
    assert parse_dms_to_decimal("-64.354018") == -64.354018


def test_valor_invalido_devuelve_none():
    assert parse_dms_to_decimal(None) is None
    assert parse_dms_to_decimal("texto sin numeros") is None


def test_dentro_de_bbox_argentina():
    assert dentro_de_bbox(-34.6, -58.4, ARGENTINA_BBOX) is True  # Buenos Aires
    assert dentro_de_bbox(40.7, -74.0, ARGENTINA_BBOX) is False  # Nueva York
    assert dentro_de_bbox(None, -58.4, ARGENTINA_BBOX) is False
