"""Tests de integración que levantan la app FastAPI de verdad (TestClient),
a diferencia de los tests de services/ que llaman funciones Python
directamente en un solo hilo. Esto es justamente lo que hizo falta para
detectar el bug de threading de SQLite (Auditoría Fase 4, hallazgo de
integración): TestClient enruta las requests igual que un servidor real.
"""
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient


def _excel_bytes_estilo_enacom() -> bytes:
    """Arma un .xlsx con 8 filas de metadata antes del header, igual que los
    archivos reales de ENACOM (processing/excel_processor.py usa header=8)."""
    df = pd.DataFrame({
        "Resultado": ["1,5", "3.2", "10"],
        "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025"],
        "Hora": ["10:00:00", "10:30:00", "09:00:00 a.m."],
        "Lat": [-34.6037, -34.6040, -34.6050],
        "Lon": [-58.3816, -58.3820, -58.3830],
        "Sonda": ["S1", "S1", "S2"],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        meta = pd.DataFrame([[f"meta{i}"] for i in range(8)])
        meta.to_excel(writer, index=False, header=False, startrow=0)
        df.to_excel(writer, index=False, startrow=8)
    buf.seek(0)
    return buf.read()


@pytest.fixture()
def client(db_path, monkeypatch):
    """App real con TestClient, apuntando a una DB temporal (via env var,
    ver app/core/config.py) -- nunca toca data/rni.db."""
    monkeypatch.setenv("RNI_DB_PATH", str(db_path))
    # Los módulos ya pueden estar importados de tests anteriores con el
    # DB_PATH viejo "horneado" -- se recargan para que tomen el nuevo path.
    import importlib
    import app.core.config as config_module
    import app.db.database as database_module
    import app.core.deps as deps_module
    import app.main as main_module

    importlib.reload(config_module)
    importlib.reload(database_module)
    importlib.reload(deps_module)
    importlib.reload(main_module)

    with TestClient(main_module.app) as c:
        yield c


def test_health(client):
    """Las dos rutas de estado responden lo mismo: `/api/health` es la de la
    app y `/health` la que golpea el sondeo del entorno, que si no cae en
    404 (ver main.py)."""
    for ruta in ("/api/health", "/health"):
        resp = client.get(ruta)
        assert resp.status_code == 200, ruta
        assert resp.json() == {"status": "ok"}, ruta


def test_import_real_via_http_no_falla_por_threading(client):
    """Este test específicamente reproduce el bug de threading encontrado en
    el smoke test manual: golpear el endpoint real vía HTTP, no llamar al
    service Python directo."""
    resp = client.post(
        "/api/import",
        data={"ccte": "Buenos Aires", "provincia": "Buenos Aires", "localidad": "CABA", "expediente": "EXP-1"},
        files={"archivos": ("muestra.xlsx", _excel_bytes_estilo_enacom(),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["registros_nuevos"] == 3


def test_kpis_y_ccte_summary_reflejan_import_via_http(client):
    client.post(
        "/api/import",
        data={"ccte": "Salta", "provincia": "Salta", "localidad": "Salta Capital"},
        files={"archivos": ("a.xlsx", _excel_bytes_estilo_enacom(),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    kpis = client.get("/api/kpis").json()
    assert kpis["registros_totales"] == 3

    resumen = client.get("/api/ccte-summary").json()
    assert len(resumen) == 7
    salta = next(r for r in resumen if r["ccte"] == "Salta")
    assert salta["mediciones"] == 3


def test_map_endpoint_via_http(client):
    client.post(
        "/api/import",
        data={"ccte": "Córdoba", "provincia": "Córdoba", "localidad": "Córdoba Capital"},
        files={"archivos": ("a.xlsx", _excel_bytes_estilo_enacom(),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    resp = client.get("/api/map")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_disponible"] == 3
    assert len(body["puntos"]) == 3


def test_reports_endpoints_via_http(client):
    client.post(
        "/api/import",
        data={"ccte": "Posadas", "provincia": "Misiones", "localidad": "Posadas Centro"},
        files={"archivos": ("a.xlsx", _excel_bytes_estilo_enacom(),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    # El frontend los baja como <a href>, que siempre manda GET -- si esto
    # fuera POST la descarga devolvería 405.
    resp_word = client.get(
        "/api/reports/word",
        params={"ccte": "Posadas", "provincia": "Misiones", "localidad": "Posadas Centro"},
    )
    assert resp_word.status_code == 200
    assert len(resp_word.content) > 0

    resp_pdf = client.get(
        "/api/reports/pdf",
        params={"ccte": "Posadas", "provincia": "Misiones", "localidad": "Posadas Centro"},
    )
    assert resp_pdf.status_code == 200
    assert len(resp_pdf.content) > 0


def test_editar_y_eliminar_localidad_via_http(client):
    client.post(
        "/api/import",
        data={"ccte": "Neuquén", "provincia": "Neuquén", "localidad": "Neuquén Capital"},
        files={"archivos": ("a.xlsx", _excel_bytes_estilo_enacom(),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    resp_put = client.put(
        "/api/localities/Neuquén Capital",
        params={"ccte": "Neuquén", "provincia": "Neuquén"},
        json={"expediente": "EXP-999"},
    )
    assert resp_put.status_code == 200
    assert resp_put.json()["filas_afectadas"] == 3

    resp_delete = client.delete(
        "/api/localities/Neuquén Capital", params={"ccte": "Neuquén", "provincia": "Neuquén"}
    )
    assert resp_delete.status_code == 200
    assert resp_delete.json()["filas_borradas"] == 3


def _excel_bytes_encabezado_arriba() -> bytes:
    """El mismo archivo de ENACOM pero SIN las 8 filas de metadata: los
    encabezados están en la fila 1."""
    df = pd.DataFrame({
        "Resultado": ["1,5", "3.2", "10"],
        "Fecha": ["20/03/2025", "20/03/2025", "21/03/2025"],
        "Hora": ["10:00:00", "10:30:00", "09:00:00"],
        "Lat": [-34.6037, -34.6040, -34.6050],
        "Lon": [-58.3816, -58.3820, -58.3830],
        "Sonda": ["S1", "S1", "S2"],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, startrow=0)
    buf.seek(0)
    return buf.read()


def test_import_con_encabezados_en_la_primera_fila(client):
    """El caso reportado: "no se encontró columna de Resultado (V/m)".

    La ruta hacía `pd.read_excel(..., header=8)`, así que con los encabezados
    en la fila 1 pandas tomaba una fila de datos por encabezado, no encontraba
    ninguna columna esperada y el import se quejaba de un nombre de columna
    que sí existía. Ahora la fila se detecta por su contenido.
    """
    resp = client.post(
        "/api/import",
        data={"ccte": "Córdoba", "provincia": "Córdoba", "localidad": "Villa Allende",
              "expediente": "EXP-2"},
        files={"archivos": ("nuevo.xlsx", _excel_bytes_encabezado_arriba(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["registros_nuevos"] == 3
    assert body["advertencias"] == [], body["advertencias"]
