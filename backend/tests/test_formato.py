"""Los formateos de V/m y % no redondean lo que la base guarda.

Son la única capa que acota en toda la app (el backend no redondea nada),
y lo hacen sobre los decimales que los datos realmente tienen: 3 para el
V/m, que es la precisión del instrumento, y 4 para el %, que es un float
calculado con 17 dígitos.
"""
import math

import pytest

from app.utils import formato


def test_vm_conserva_los_tres_decimales_del_instrumento():
    """El instrumento mide en pasos de 0,001: 0.942 tiene que salir
    "0.942". Con el `:.2f` anterior salía "0.94", y eso pasaba en el
    83,32 % de la base (183.160 de 219.818 filas)."""
    assert formato.vm(0.942) == "0.942"
    assert formato.vm(1.022) == "1.022"
    assert formato.vm(18.831) == "18.831"


def test_vm_los_valores_chicos_no_se_van_a_cero():
    """Antes 0.001, 0.003 y 0.004 se imprimían "0.00" y 0.005 se iba a
    "0.01" por el redondeo hacia arriba."""
    assert formato.vm(0.001) == "0.001"
    assert formato.vm(0.003) == "0.003"
    assert formato.vm(0.004) == "0.004"
    assert formato.vm(0.005) == "0.005"


def test_vm_no_deja_ceros_de_relleno():
    """19.260 no es "19.260": el cero sobrante no estaba en los datos."""
    assert formato.vm(19.260) == "19.26"
    assert formato.vm(0.0) == "0"
    assert formato.vm(10.0) == "10"
    # El cero de "100" no es trailing: lo separa el punto, así que no se va.
    assert formato.vm(100.0) == "100"
    assert formato.vm(100.000) == "100"


def test_vm_sin_valor():
    assert formato.vm(None) == "-"


def test_pct_acota_a_cuatro_decimales():
    """0,04022315030756169 con un solo decimal salía "0,0 %", que se
    confunde con un resultado en cero. Con `.toFixed(1)` cambiaban
    215.212 de 219.818 filas."""
    assert formato.pct(0.04022315030756169) == "0.0402"
    assert formato.pct(49.14569145368187) == "49.1457"
    assert formato.pct(119.23790247326362) == "119.2379"
    assert formato.pct(0.0) == "0"


def test_pct_sin_valor():
    assert formato.pct(None) == "-"


def test_el_nan_no_se_imprime_como_texto_nan():
    """`f"{nan:.3f}"` no falla: imprime "nan". Un informe no puede decir
    "Resultado máximo registrado: nan V/m"."""
    assert formato.vm(math.nan) == "-"
    assert formato.pct(math.nan) == "-"


def test_numpy_tambien_se_cubre():
    """Los NaN que vienen de pandas llegan como numpy.float64. Es subclase
    de float, así que el isinstance del chequeo los alcanza."""
    np = pytest.importorskip("numpy")
    assert formato.vm(np.float64("nan")) == "-"
    assert formato.vm(np.float64(0.942)) == "0.942"
    assert formato.pct(np.float64("nan")) == "-"
