from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from app.core.deps import get_db
from app.db.repositories import import_repo
from app.services import import_service

router = APIRouter()


@router.post("/import")
async def post_import(
    ccte: str = Form(...),
    provincia: str = Form(...),
    localidad: str = Form(...),
    expediente: str | None = Form(None),
    archivos: list[UploadFile] = None,  # type: ignore[assignment]
    conn=Depends(get_db),
):
    if not archivos:
        raise HTTPException(status_code=400, detail="No se recibieron archivos.")

    leidos = []
    for archivo in archivos:
        contenido = await archivo.read()
        try:
            # La detección de la fila de encabezados vive en el service: es
            # la misma lógica que decide qué columnas son, no solo dónde
            # empiezan (ver `import_service.leer_excel`).
            df = import_service.leer_excel(contenido)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"No se pudo leer {archivo.filename}: {exc}") from exc
        leidos.append((archivo.filename, df))

    reporte = import_service.importar_lote(
        conn, ccte=ccte, provincia=provincia, localidad=localidad, expediente=expediente,
        archivos=leidos,
    )
    return reporte


@router.get("/import/{batch_id}")
def get_import_batch(batch_id: int, conn=Depends(get_db)):
    batch = import_repo.obtener_batch(conn, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote de importación no encontrado")
    return batch
