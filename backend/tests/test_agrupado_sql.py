# -*- coding: utf-8 -*-
"""El agrupado en SQL tiene que dar EXACTAMENTE lo mismo que en pandas.

Para el tiempo trabajado hay dos caminos hacia el mismo cálculo:
`_agrupar_por_archivo_dia` (pandas, sobre las filas crudas) y
`mediciones_repo.agrupar_min_max_por_archivo_dia` (SQL, sobre la tabla).

El segundo existe por rendimiento: la vista General pedía `fecha_hora` +
`nombre_archivo` de las 219 818 mediciones para quedarse con 241 grupos
(0,78 s de fetch + un DataFrame de 219 818 filas + 219 818 datetime a
parsear + groupby), ~2,8 s solo y 17-21 s cuando la vista dispara sus cinco
pedidos a la vez. En SQL son 0,43 s y 241 filas.

Pero tener dos implementaciones de una regla de negocio es justamente lo que
el docstring de `_agrupar_por_archivo_dia` dice que no hay que hacer. Este
archivo es lo que lo hace aceptable: si alguno de los dos cambia y el otro
no, la tabla "Tiempo trabajado diario" y la "mensual" empiezan a dar números
distintos y el test se entera antes que nadie.
"""
import json

import pandas as pd

from app.calculations.dates import (
    _agrupar_por_archivo_dia,
    desglose_diario,
    desglose_diario_desde_agrupado,
)
from app.db.repositories import mediciones_repo

# (ccte, provincia, localidad, fecha_hora, nombre_archivo)
#
# Los casos que pueden romper la equivalencia:
#   - mismo archivo, dos días  -> dos grupos
#   - DOS archivos el mismo día -> dos grupos, no uno (no se suman)
#   - fecha_hora NULL          -> no cuenta (es el dropna de pandas)
#   - dos CCTE distintos       -> para probar que el filtro separa
FILAS = [
    ("Córdoba", "Córdoba", "Villa Allende", "2025-12-03T09:13:15", "A.xlsx"),
    ("Córdoba", "Córdoba", "Villa Allende", "2025-12-03T10:40:00", "A.xlsx"),
    ("Córdoba", "Córdoba", "Villa Allende", "2025-12-05T08:00:00", "A.xlsx"),
    ("Córdoba", "Córdoba", "Villa Allende", "2025-12-03T14:00:00", "B.xlsx"),
    ("Córdoba", "Córdoba", "Villa Allende", "2025-12-03T15:30:00", "B.xlsx"),
    ("Salta", "Salta", "Salta Capital", "2025-12-03T11:00:00", "C.xlsx"),
    ("Salta", "Salta", "Salta Capital", "2025-12-03T12:15:00", "C.xlsx"),
    ("Salta", "Salta", "Salta Capital", None, "C.xlsx"),
]


def _sembrar(conn) -> None:
    conn.executemany(
        """INSERT INTO mediciones
             (ccte, provincia, localidad, fecha_hora, nombre_archivo, fecha_carga)
           VALUES (?, ?, ?, ?, ?, '2026-01-01')""",
        [tuple(f) for f in FILAS],
    )
    conn.commit()


def _normalizar(agg: pd.DataFrame) -> pd.DataFrame:
    """Mismos tipos y mismo orden en los dos lados para poder compararlos."""
    out = agg.copy()
    out["_dia"] = pd.to_datetime(out["_dia"]).dt.date
    out["min"] = pd.to_datetime(out["min"])
    out["max"] = pd.to_datetime(out["max"])
    cols = ["nombre_archivo", "_dia", "min", "max"]
    return out[cols].sort_values(["nombre_archivo", "_dia"]).reset_index(drop=True)


def _comparar(conn, **filtros):
    filas = mediciones_repo.query_filtrada(
        conn, columnas="fecha_hora, nombre_archivo", **filtros,
    )
    pandas_agg = _agrupar_por_archivo_dia(pd.DataFrame(filas))
    sql_agg = pd.DataFrame(mediciones_repo.agrupar_min_max_por_archivo_dia(conn, **filtros))
    return pandas_agg, sql_agg


def test_agrupado_en_sql_igual_que_en_pandas(conn):
    _sembrar(conn)

    pandas_agg, sql_agg = _comparar(conn)

    # El NULL no tiene que aparecer en ninguno de los dos lados.
    assert len(pandas_agg) == len(sql_agg) == 4
    assert _normalizar(pandas_agg).equals(_normalizar(sql_agg))


def test_agrupado_en_sql_con_filtro_de_ccte(conn):
    _sembrar(conn)

    pandas_agg, sql_agg = _comparar(conn, ccte=["Córdoba"])

    # Los dos archivos de Córdoba, sin mezclar a Salta.
    assert len(pandas_agg) == len(sql_agg) == 3
    assert set(pandas_agg["nombre_archivo"]) == {"A.xlsx", "B.xlsx"}
    assert _normalizar(pandas_agg).equals(_normalizar(sql_agg))


def test_desglose_diario_da_igual_por_los_dos_caminos(conn):
    """El resultado final -- lo que se ve en pantalla -- es idéntico.

    Se compara como multiset porque el orden de dos grupos del MISMO día solo
    lo garantiza el sort por `_dia`, que es el mismo criterio que ya usaba el
    código de siempre: no es parte de la equivalencia.
    """
    _sembrar(conn)

    filas = mediciones_repo.query_filtrada(conn, columnas="fecha_hora, nombre_archivo")
    via_pandas = desglose_diario(pd.DataFrame(filas))
    via_sql = desglose_diario_desde_agrupado(
        pd.DataFrame(mediciones_repo.agrupar_min_max_por_archivo_dia(conn)),
    )

    def ordenado(lista):
        return sorted(json.dumps(f, sort_keys=True, ensure_ascii=False) for f in lista)

    assert len(via_pandas) == 4
    assert ordenado(via_pandas) == ordenado(via_sql)


def test_dos_archivos_en_un_mismo_dia_no_se_suman(conn):
    """Agregado en SQL o en pandas: 2025-12-03 tiene tres jornadas (A por la
    mañana, B por la tarde y C en Salta) y siguen siendo tres filas, con sus
    tres duraciones propias. Es la regla que evita esconder que fueron
    archivos/jornadas distintas."""
    _sembrar(conn)

    diario = desglose_diario_desde_agrupado(
        pd.DataFrame(mediciones_repo.agrupar_min_max_por_archivo_dia(conn)),
    )

    mismo_dia = [d for d in diario if d["fecha"] == "2025-12-03"]
    assert len(mismo_dia) == 3
    # A: 09:13:15 -> 10:40:00 = 1 h 26 min 45 s = 5205 s
    # B: 14:00:00 -> 15:30:00 = 5400 s
    assert sorted(d["duracion_seg"] for d in mismo_dia if d["nombre_archivo"] != "C.xlsx") == [5205, 5400]


def test_localidad_no_usa_fila_por_fila(conn):
    """El desglose por localidad pasa por el mismo agregado SQL: no hay un
    segundo camino que traiga la tabla entera."""
    _sembrar(conn)

    from app.services import tiempos

    diario = tiempos.tiempo_diario_localidad(
        conn, "Córdoba", "Córdoba", "Villa Allende",
    )

    assert [d["fecha"] for d in diario] == ["2025-12-03", "2025-12-03", "2025-12-05"]
    # 2025-12-05 tiene UNA sola medición: min == max y la duración da 0, que
    # es lo correcto -- no se inventa una jornada a partir de una hora suelta.
    assert [d["duracion_seg"] for d in diario if d["fecha"] == "2025-12-05"] == [0]
    assert sum(d["duracion_seg"] for d in diario) == 5205 + 5400
