"""Migración: rni.db (esquema Streamlit actual, tabla `mediciones_rni`) ->
rni_v2.db (esquema nuevo, ver Fase 2).

Además de traducir el esquema, corrige el signo de las coordenadas que el
pipeline legacy guardó como valores absolutos (lat > 0 y lon > 0) -- ver la
nota "Corrección de signo de coordenadas" más abajo.

Uso:
    python -m app.db.migrate --origen /ruta/a/rni.db --destino /ruta/a/rni_v2.db

No modifica el archivo de origen. El destino se crea desde cero (falla si
ya existe, para no pisar una migración anterior por accidente).

Al final corre la validación cruzada del diseño de Fase 2 (§2.1) y
IMPRIME un reporte; si alguna verificación no coincide, termina con
código de salida distinto de 0 y no se debe promover `destino` a
producción hasta resolver la discrepancia.
"""
from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.calculations.dates import add_fecha_hora, anio_de_fecha_hora
from app.calculations.rni import resultado_pct
from app.core.config import ARGENTINA_BBOX, SCHEMA_PATH
from app.services import statistics as statistics_service


def migrar(origen: Path, destino: Path) -> None:
    if destino.exists():
        raise SystemExit(f"El destino ya existe, no se sobreescribe: {destino}")

    origen_conn = sqlite3.connect(str(origen))
    origen_conn.row_factory = sqlite3.Row

    destino_conn = sqlite3.connect(str(destino))
    destino_conn.row_factory = sqlite3.Row
    destino_conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    ahora = datetime.now(timezone.utc).isoformat()

    filas_origen = [dict(r) for r in origen_conn.execute("SELECT * FROM mediciones_rni").fetchall()]
    print(f"Leídas {len(filas_origen)} filas de mediciones_rni en el origen.")

    import pandas as pd
    df = pd.DataFrame(filas_origen)
    if not df.empty:
        df = df.rename(columns={"Nombre Archivo": "nombre_archivo"})
        df = add_fecha_hora(df, fecha_col="Fecha", hora_col="Hora", out_col="fecha_hora")
        df["anio"] = df["fecha_hora"].apply(anio_de_fecha_hora)

    # Corrección de signo de coordenadas ---------------------------------
    # Los lotes legacy guardaron lat/lon como valores absolutos. En
    # `mediciones_rni` eso afecta 209.990 de 219.818 filas (95.5%), todas con
    # FechaCarga 2026-06/07 y parte de 08/09; las 9.828 restantes (CCTE Salta,
    # 2026-08 y 09) ya venían bien.
    #
    # Se corrige SOLO cuando ambos signos están mal a la vez (lat>0 y lon>0):
    # Argentina está entera en el hemisferio sur y oeste, así que esa
    # combinación no puede ser un punto válido, y las filas que ya estaban
    # bien quedan intactas. Verificado antes de aplicar: al negar ambos,
    # las 209.990 filas caen dentro de ARGENTINA_BBOX -- ninguna queda fuera.
    # NaN queda afuera de la comparación, así que las filas sin coordenada
    # no se tocan.
    n_signo_malo = 0
    if not df.empty and {"Lat", "Lon"} <= set(df.columns):
        malas = (df["Lat"] > 0) & (df["Lon"] > 0)
        n_signo_malo = int(malas.sum())
        if n_signo_malo:
            df.loc[malas, "Lat"] = -df.loc[malas, "Lat"]
            df.loc[malas, "Lon"] = -df.loc[malas, "Lon"]
    print(f"Coordenadas con ambos signos corregidas: {n_signo_malo}.")

    filas_nuevas = []
    for _, fila in df.iterrows():
        resultado_vm = fila.get("Resultado")
        resultado_vm = None if pd.isna(resultado_vm) else float(resultado_vm)

        # Se recalcula con la fórmula centralizada para verificar
        # equivalencia (ver validación cruzada más abajo) en vez de copiar
        # directo el valor de origen -- si difieren, la migración avisa.
        pct_recalculado = resultado_pct(resultado_vm) if resultado_vm is not None else None

        fecha_hora_val = fila.get("fecha_hora")
        fecha_hora_iso = None if pd.isna(fecha_hora_val) else pd.Timestamp(fecha_hora_val).isoformat()

        filas_nuevas.append({
            "ccte": fila.get("CCTE"), "provincia": fila.get("Provincia"), "localidad": fila.get("Localidad"),
            "resultado_vm": resultado_vm,
            "resultado_pct": pct_recalculado,
            "fecha_raw": fila.get("Fecha"), "hora_raw": fila.get("Hora"),
            "fecha_hora": fecha_hora_iso,
            "anio": None if pd.isna(fila.get("anio")) else int(fila["anio"]),
            "lat": fila.get("Lat"), "lon": fila.get("Lon"),
            "lat_raw": None, "lon_raw": None,  # el esquema viejo no guardaba el crudo
            "expediente": fila.get("Expediente"), "sonda": fila.get("Sonda"),
            "nombre_archivo": fila.get("nombre_archivo"),
            "import_batch_id": None,
            "fecha_carga": fila.get("FechaCarga") or ahora,
        })

    columnas = list(filas_nuevas[0].keys()) if filas_nuevas else []
    if columnas:
        placeholders = ",".join("?" for _ in columnas)
        destino_conn.executemany(
            f"INSERT INTO mediciones ({','.join(columnas)}) VALUES ({placeholders})",
            [[f[c] for c in columnas] for f in filas_nuevas],
        )
    destino_conn.commit()
    print(f"Insertadas {len(filas_nuevas)} filas en el destino.")

    claves = {(f["ccte"], f["provincia"], f["localidad"]) for f in filas_nuevas}
    statistics_service.recalcular(destino_conn, claves)
    destino_conn.commit()
    print(f"Resúmenes recalculados para {len(claves)} localidades.")

    ok = _validar(origen_conn, destino_conn)
    origen_conn.close()
    destino_conn.close()

    if not ok:
        print("\n❌ La validación cruzada encontró diferencias. NO promover a producción.")
        sys.exit(1)
    print("\n✅ Validación cruzada OK.")


def _validar(origen_conn: sqlite3.Connection, destino_conn: sqlite3.Connection) -> bool:
    ok = True

    total_origen = origen_conn.execute("SELECT COUNT(*) AS n FROM mediciones_rni").fetchone()["n"]
    total_destino = destino_conn.execute("SELECT COUNT(*) AS n FROM mediciones").fetchone()["n"]
    print(f"Total registros -- origen: {total_origen}, destino: {total_destino}")
    ok &= total_origen == total_destino

    for campo_origen, campo_destino in [("CCTE", "ccte"), ("Provincia", "provincia"), ("Localidad", "localidad")]:
        n_origen = origen_conn.execute(f"SELECT COUNT(DISTINCT {campo_origen}) AS n FROM mediciones_rni").fetchone()["n"]
        n_destino = destino_conn.execute(f"SELECT COUNT(DISTINCT {campo_destino}) AS n FROM mediciones").fetchone()["n"]
        print(f"{campo_origen} únicos -- origen: {n_origen}, destino: {n_destino}")
        ok &= n_origen == n_destino

    max_origen = origen_conn.execute("SELECT MAX(Resultado) AS m FROM mediciones_rni").fetchone()["m"]
    max_destino = destino_conn.execute("SELECT MAX(resultado_vm) AS m FROM mediciones").fetchone()["m"]
    print(f"Máximo V/m -- origen: {max_origen}, destino: {max_destino}")
    if max_origen is not None and max_destino is not None:
        ok &= math.isclose(max_origen, max_destino, rel_tol=1e-9)
    else:
        ok &= max_origen == max_destino

    # resultado_pct: comparar fila por fila (join por rowid es lo más simple
    # ya que se insertó en el mismo orden que se leyó).
    origen_pct = [r["Resultado_Pct"] for r in origen_conn.execute(
        "SELECT Resultado_Pct FROM mediciones_rni ORDER BY rowid"
    ).fetchall()]
    destino_pct = [r["resultado_pct"] for r in destino_conn.execute(
        "SELECT resultado_pct FROM mediciones ORDER BY id"
    ).fetchall()]
    diffs = 0
    for a, b in zip(origen_pct, destino_pct):
        if a is None or b is None:
            if a != b:
                diffs += 1
            continue
        if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
            diffs += 1
    print(f"Filas con resultado_pct distinto entre origen y destino (fuera de tolerancia): {diffs}")
    ok &= diffs == 0

    # Argentina está entera en el hemisferio sur (lat < 0) y oeste (lon < 0).
    # Si en el destino queda algún lat > 0 o lon > 0, la corrección de signo
    # no se aplicó -- esos puntos caerían fuera del país en el mapa. Es la
    # condición dura; el bbox se imprime solo como señal, porque un punto
    # puede quedar legítimamente en el borde.
    signo_malo = destino_conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones WHERE lat > 0 OR lon > 0"
    ).fetchone()["n"]
    print(f"Coordenadas con signo imposible para Argentina -- destino: {signo_malo}")
    ok &= signo_malo == 0

    fuera_bbox = destino_conn.execute(
        "SELECT COUNT(*) AS n FROM mediciones"
        " WHERE lat IS NOT NULL AND lon IS NOT NULL"
        " AND NOT (lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?)",
        (
            ARGENTINA_BBOX["lat_min"], ARGENTINA_BBOX["lat_max"],
            ARGENTINA_BBOX["lon_min"], ARGENTINA_BBOX["lon_max"],
        ),
    ).fetchone()["n"]
    print(f"Coordenadas fuera de ARGENTINA_BBOX (informativo, no falla): {fuera_bbox}")

    return ok


if __name__ == "__main__":
    # Sin esto la stdout de Windows queda en cp1252 y el print final de
    # éxito ("✅") revienta con UnicodeEncodeError DESPUÉS de validar bien:
    # el script salía con código 1 sobre una migración exitosa, que es
    # exactamente la señal que el README le dice al operador que interprete
    # como "no promover a producción".
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--origen", required=True, type=Path)
    parser.add_argument("--destino", required=True, type=Path)
    args = parser.parse_args()
    migrar(args.origen, args.destino)
