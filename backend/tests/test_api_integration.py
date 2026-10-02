"""Tests de integración que levantan la app FastAPI de verdad (TestClient),
a diferencia de los tests de services/ que llaman funciones Python
directamente en un solo hilo. Esto es justamente lo que hizo falta para
detectar el bug de threading de SQLite (Auditoría Fase 4, hallazgo de
integración): TestClient enruta las requests igual que un servidor real.
"""
import io

import pandas as pd


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


# --- caché de /api/diagnostics ----------------------------------------
# Son 11 COUNT sobre toda la tabla: 1.3 s en caliente y 33 s la primera vez
# después de un reinicio. Ver services/diagnostics.py.

def _contar_calculos(monkeypatch, diagnostics_service):
    """Reemplaza `obtener_diagnostico` por una que anota cada vez que se
    calcula de verdad. Lo que no aparezca en la lista salió de la caché."""
    llamadas = []
    original = diagnostics_service.obtener_diagnostico

    def contadora(conn):
        llamadas.append(1)
        return original(conn)

    monkeypatch.setattr(diagnostics_service, "obtener_diagnostico", contadora)
    return llamadas


def test_diagnostics_se_cachea(client, monkeypatch):
    """La segunda llamada al endpoint no vuelve a calcular nada."""
    from app.services import diagnostics as diagnostics_service

    diagnostics_service.invalidar_cache()
    primero = client.get("/api/diagnostics")
    assert primero.status_code == 200
    assert primero.json()["total_registros"] == 0

    llamadas = _contar_calculos(monkeypatch, diagnostics_service)
    segundo = client.get("/api/diagnostics")

    assert segundo.status_code == 200
    assert segundo.json() == primero.json()
    assert llamadas == [], "la caché no hizo falta recalcular"


def test_diagnostics_cachea_por_firma_aunque_nadie_la_invalid(client, monkeypatch):
    """La firma (COUNT + MAX(rowid)) corta la caché sola: sirve para toda
    escritura que no pase por los ganchos explícitos, por ejemplo un script
    que toque la base directo."""
    from app.services import diagnostics as diagnostics_service

    diagnostics_service.invalidar_cache()
    assert client.get("/api/diagnostics").json()["total_registros"] == 0

    monkeypatch.setattr(diagnostics_service, "invalidar_cache", lambda: None)
    resp = client.post(
        "/api/import",
        data={"ccte": "Salta", "provincia": "Salta", "localidad": "Salta Capital"},
        files={"archivos": ("a.xlsx", _excel_bytes_estilo_enacom(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text

    assert client.get("/api/diagnostics").json()["total_registros"] == 3


def test_editar_localidad_tira_el_cache_de_diagnostics(client, monkeypatch):
    """Un rename no cambia la firma, así que sin el `invalidar_cache` de la
    ruta la caché seguiría con los números viejos."""
    from app.services import diagnostics as diagnostics_service

    client.post(
        "/api/import",
        data={"ccte": "Neuquén", "provincia": "Neuquén", "localidad": "Neuquén Capital"},
        files={"archivos": ("a.xlsx", _excel_bytes_estilo_enacom(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert client.get("/api/diagnostics").json()["total_registros"] == 3

    llamadas = _contar_calculos(monkeypatch, diagnostics_service)
    resp = client.put(
        "/api/localities/Neuquén Capital",
        params={"ccte": "Neuquén", "provincia": "Neuquén"},
        json={"localidad": "Neuquén Centro"},
    )
    assert resp.status_code == 200

    assert client.get("/api/diagnostics").status_code == 200
    assert llamadas, "la edición tiene que tirar el diagnóstico cacheado"
