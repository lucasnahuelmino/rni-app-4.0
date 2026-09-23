from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.deps import get_db
from app.services import reports as reports_service

router = APIRouter()


@router.get("/reports/word")
def get_report_word(ccte: str, provincia: str, localidad: str, ambito: str = "Localidad", conn=Depends(get_db)):
    datos = reports_service.obtener_datos_informe(conn, ccte, provincia, localidad)
    buffer = reports_service.generar_word(datos, localidad=localidad, ambito=ambito)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="Informe_RNI_{localidad}.docx"'},
    )


@router.get("/reports/pdf")
def get_report_pdf(ccte: str, provincia: str, localidad: str, ambito: str = "Localidad", conn=Depends(get_db)):
    datos = reports_service.obtener_datos_informe(conn, ccte, provincia, localidad)
    buffer = reports_service.generar_pdf(datos, localidad=localidad, ambito=ambito)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Informe_RNI_{localidad}.pdf"'},
    )
