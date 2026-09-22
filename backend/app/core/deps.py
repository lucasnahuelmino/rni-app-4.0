"""Dependencia de FastAPI para obtener una conexión de DB por request."""
from __future__ import annotations

from app.db.database import get_connection


def get_db():
    with get_connection() as conn:
        yield conn
