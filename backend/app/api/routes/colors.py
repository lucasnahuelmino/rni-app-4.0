from __future__ import annotations

from fastapi import APIRouter

from app.core.config import RANGOS_COLOR

router = APIRouter()


@router.get("/color-scale")
def get_color_scale():
    """Única fuente de verdad de la escala de colores del semáforo (10
    bandas, recuperada de la app Streamlit original). El frontend consulta
    esto en vez de hardcodear los rangos en más de un componente."""
    return RANGOS_COLOR
