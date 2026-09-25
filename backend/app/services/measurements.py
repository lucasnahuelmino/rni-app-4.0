"""CRUD de mediciones. Toda escritura pasa por acá y dispara el recálculo
acotado correspondiente (ver services/statistics.py).

Acá también vive la sanitización de arranque (`sanear_signo_resultados`),
que es una escritura sobre `mediciones` y por lo tanto pertenece al mismo
lugar único por el que pasa todo lo que toca esa tabla."""
from __future__ import annotations

import sqlite3

from app.db.repositories import mediciones_repo
from app.services import statistics as statistics_service


def sanear_signo_resultados(conn: sqlite3.Connection) -> int:
    """Pasa a positivo los `resultado_vm` negativos que haya en la base.

    Un campo eléctrico no puede ser negativo. La sonda reporta `-0.001`
    cuando el valor queda por debajo de su piso de medición, y esa es
    exactamente la forma que traían los 17 registros negativos cargados
    (todos del CCTE Comodoro Rivadavia, sondas EF0391 y EF1891).

    NO hace falta recalcular nada más, y esa es la razón por la que es una
    línea y no un proceso:

      * `resultado_pct` NO cambia, porque es `vm^2 / 3770 / limite * 100` y
        el signo se pierde en el cuadrado: -0.001 y 0.001 dan el mismo
        porcentaje, así que ningún KPI ni ningún color del semáforo se
        mueve.
      * Ninguna tabla derivada guarda `MIN(resultado_vm)`. Los agregados
        usan `MAX(resultado_vm)`, `AVG` de porcentajes y `COUNT`, y los tres
        quedan intactos.
      * Lo único que cambia es el valor que se MUESTRA (el popup del mapa)
        y el `MIN(resultado_vm)` en vivo que usa `routes/charts.py` para
        poner el piso del eje -- que antes arrancaba en -0.001.

    Idempotente: sobre una base saneada el WHERE no matchea nada y no se
    escribe. Corre en el arranque (`main.on_startup`); el import ya no
    puede reintroducir el problema porque `_leer_y_normalizar` también
    fuerza el absoluto.

    Devuelve cuántas filas tocó.
    """
    filas = conn.execute(
        "UPDATE mediciones SET resultado_vm = -resultado_vm WHERE resultado_vm < 0"
    ).rowcount
    if filas:
        conn.commit()
    return filas


def eliminar_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str) -> int:
    # Hay que leer los períodos ANTES del DELETE: una vez que las filas
    # desaparecen ya no queda rastro de qué años/meses ocupaban, y sin eso
    # `recalcular` no puede refrescar resumen_anual / resumen_mensual
    # (quedarían contando mediciones que ya no existen).
    periodos = mediciones_repo.periodos_por_localidad(conn, ccte, provincia, localidad)

    filas_borradas = mediciones_repo.eliminar_por_localidad(conn, ccte, provincia, localidad)
    statistics_service.recalcular(conn, {(ccte, provincia, localidad)}, periodos_afectados=periodos)
    return filas_borradas


def editar_metadata_localidad(conn: sqlite3.Connection, ccte: str, provincia: str, localidad: str,
                               nuevos: dict) -> int:
    """UPDATE dirigido -- reemplaza el patrón 'reescribir toda la tabla' del
    sistema actual (Auditoría Fase 1, hallazgo A8)."""
    filas_afectadas = mediciones_repo.actualizar_metadata_localidad(conn, ccte, provincia, localidad, nuevos)

    claves = {(ccte, provincia, localidad)}
    nueva_ccte = nuevos.get("ccte", ccte)
    nueva_provincia = nuevos.get("provincia", provincia)
    nueva_localidad = nuevos.get("localidad", localidad)
    claves.add((nueva_ccte, nueva_provincia, nueva_localidad))

    statistics_service.recalcular(conn, claves)
    return filas_afectadas
