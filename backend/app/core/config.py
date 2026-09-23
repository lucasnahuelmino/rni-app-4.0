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

# Escala de colores del semáforo del mapa, recuperada de la aplicación
# Streamlit original (get_color_por_pct). Única fuente de verdad: tanto el
# color de cada punto del mapa como la leyenda y el badge de la tabla de
# Resumen/Gestión se arman a partir de ESTA lista (vía GET /api/color-scale),
# para que nunca queden desincronizados entre sí (Auditoría Fase 1,
# hallazgo A11: la leyenda no coincidía con los colores reales).
# `hasta=None` en el último tramo significa "sin techo" (100% en adelante).
RANGOS_COLOR = [
    {"desde": 0, "hasta": 1, "color": "#84C2F5", "etiqueta": "0–1 %"},
    {"desde": 1, "hasta": 2, "color": "#489DFF", "etiqueta": "1–2 %"},
    {"desde": 2, "hasta": 4, "color": "#006BD6", "etiqueta": "2–4 %"},
    {"desde": 4, "hasta": 8, "color": "#A9E7A9", "etiqueta": "4–8 %"},
    {"desde": 8, "hasta": 15, "color": "#89DD89", "etiqueta": "8–15 %"},
    {"desde": 15, "hasta": 20, "color": "#4D9623", "etiqueta": "15–20 %"},
    {"desde": 20, "hasta": 35, "color": "#D9FF00", "etiqueta": "20–35 %"},
    {"desde": 35, "hasta": 50, "color": "#F39A6D", "etiqueta": "35–50 %"},
    {"desde": 50, "hasta": 100, "color": "#E68200", "etiqueta": "50–100 %"},
    {"desde": 100, "hasta": None, "color": "#CC0000", "etiqueta": "≥100 %"},
]


def color_por_pct(pct: float | None) -> str:
    """Mismo criterio que RANGOS_COLOR, para usarlo del lado del backend
    (ej. si se necesita en un informe o export) sin duplicar los rangos."""
    if pct is None:
        return "#9aa5ab"
    for rango in RANGOS_COLOR:
        if pct >= rango["desde"] and (rango["hasta"] is None or pct < rango["hasta"]):
            return rango["color"]
    return RANGOS_COLOR[-1]["color"]
