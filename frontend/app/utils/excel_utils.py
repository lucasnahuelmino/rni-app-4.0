"""Port directo de utils/excel_utils.py del sistema Streamlit actual."""
from __future__ import annotations

import pandas as pd


def extract_numeric_from_text(series: pd.Series) -> pd.Series:
    """Extrae valores numéricos (float) desde texto."""
    s = series.astype(str).str.replace(",", ".", regex=False)
    num = s.str.extract(r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', expand=False)
    return pd.to_numeric(num, errors="coerce")
