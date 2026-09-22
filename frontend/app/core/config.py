"""Configuración central de la aplicación.

Cualquier constante que hoy vive duplicada en el sistema Streamlit
(ver Auditoría Fase 1, hallazgo A6) se define UNA sola vez acá.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.environ.get("RNI_DB_PATH", BASE_DIR / "data" / "rni.db"))
SCHEMA_PATH = BASE_DIR / "app" / "db" / "schema.sql"

# Los 7 Centros de Comprobación Técnica de Emisiones. Buenos Aires y CABA
# deben aparecer siempre en /api/ccte-summary aunque tengan 0 mediciones
# (Auditoría Fase 1, requisito de negocio confirmado).
CCTE_FIJOS = [
    "Córdoba",
    "Comodoro Rivadavia",
    "Neuquén",
    "Posadas",
    "Salta",
    "Buenos Aires",
    "CABA",
]

# CCTE que deben mostrarse siempre, incluso con 0 mediciones.
CCTE_SIEMPRE_VISIBLES = {"Buenos Aires", "CABA"}

# Límite de puntos que se envían al frontend para el mapa en una sola
# respuesta antes de exigir un bbox/zoom más acotado (evita repetir el
# problema de performance de la Auditoría Fase 1, punto 5 de "Performance").
MAX_PUNTOS_MAPA = 5000

# Bounding box aproximado de Argentina, usado por calculations/geo.py y por
# el diagnóstico de coordenadas fuera de rango.
ARGENTINA_BBOX = {"lat_min": -55.1, "lat_max": -21.7, "lon_min": -73.6, "lon_max": -53.6}
