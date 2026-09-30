from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.deps import get_db
from app.db.repositories import resumen_repo
from app.schemas.filters import FiltrosQuery, filtros_query
from app.services import reports as reports_service

router = APIRouter()

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF = "application/pdf"


def _descarga(buffer, *, nombre: str, media_type: str) -> StreamingResponse:
    """Un solo lugar que arma la descarga: todos los formatos bajan igual.

    El buffer ya viene con el puntero en cero (los generadores hacen seek(0)),
    asi que StreamingResponse lo lee desde el principio.
    """
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


def _exigir_datos(datos: dict, *, que: str) -> None:
    """Un informe sin mediciones es un error de la consulta, no un archivo vacio.

    Antes de existir esta validacion, pedir una localidad que no existe devolvia
    un Word o un Excel con solo el titulo y "Total de puntos medidos: 0".
    """
    if not datos.get("total_puntos"):
        raise HTTPException(status_code=404, detail=f"No hay mediciones de {que}")


def _texto_filtros(filtros: FiltrosQuery) -> str:
    """Lo que se imprime en el Excel para dejar constancia de que se filtro.

    El anio queda fuera a proposito: `resumen_localidad` es un resumen TOTAL
    por localidad sin columna de anio, igual que en la vista Resumen -- ver el
    comentario de get_top_localities. Listarlo aqui seria decir que filtro algo
    que no filtro.
    """
    partes = []
    if filtros.ccte:
        partes.append("CCTE: " + ", ".join(filtros.ccte))
    if filtros.provincia:
        partes.append("Provincia: " + ", ".join(filtros.provincia))
    if filtros.localidad:
        partes.append("Localidad: " + ", ".join(filtros.localidad))
    return " | ".join(partes) if partes else "Sin filtros"


# --- Word -------------------------------------------------------------------

@router.get("/reports/word")
def get_report_word(ccte: str, provincia: str, localidad: str,
                    ambito: str = "Localidad", conn=Depends(get_db)):
    datos = reports_service.obtener_datos_informe(conn, ccte, provincia, localidad)
    _exigir_datos(datos, que=f"la localidad {localidad}")
    buffer = reports_service.generar_word(datos, ambito=ambito, etiqueta=localidad)
    return _descarga(buffer, nombre=f"Informe_RNI_{localidad}.docx", media_type=DOCX)


@router.get("/reports/word/ccte")
def get_report_word_ccte(ccte: str, conn=Depends(get_db)):
    """Informe de TODO el centro, para las opciones del Centro operativo."""
    datos = reports_service.obtener_datos_informe_ccte(conn, ccte)
    _exigir_datos(datos, que=f"el CCTE {ccte}")
    buffer = reports_service.generar_word(datos, ambito="CCTE", etiqueta=ccte)
    return _descarga(buffer, nombre=f"Informe_RNI_{ccte}.docx", media_type=DOCX)


# --- PDF --------------------------------------------------------------------

@router.get("/reports/pdf")
def get_report_pdf(ccte: str, provincia: str, localidad: str,
                   ambito: str = "Localidad", conn=Depends(get_db)):
    datos = reports_service.obtener_datos_informe(conn, ccte, provincia, localidad)
    _exigir_datos(datos, que=f"la localidad {localidad}")
    buffer = reports_service.generar_pdf(datos, ambito=ambito, etiqueta=localidad)
    return _descarga(buffer, nombre=f"Informe_RNI_{localidad}.pdf", media_type=PDF)


@router.get("/reports/pdf/ccte")
def get_report_pdf_ccte(ccte: str, conn=Depends(get_db)):
    datos = reports_service.obtener_datos_informe_ccte(conn, ccte)
    _exigir_datos(datos, que=f"el CCTE {ccte}")
    buffer = reports_service.generar_pdf(datos, ambito="CCTE", etiqueta=ccte)
    return _descarga(buffer, nombre=f"Informe_RNI_{ccte}.pdf", media_type=PDF)


# --- Excel ------------------------------------------------------------------

@router.get("/reports/excel")
def get_report_excel(filtros: FiltrosQuery = Depends(filtros_query), conn=Depends(get_db)):
    """La tabla de Resumen tal cual se ve en pantalla, con logo y titulos.

    Baja por la MISMA puerta que la vista (`listar_resumen_localidad`), asi que
    el archivo no puede mostrar otra cosa que lo que el usuario esta mirando.
    Las columnas se declaran en el servicio y tienen que coincidir con las de
    frontend/src/views/ResumenView.vue.
    """
    filas = resumen_repo.listar_resumen_localidad(
        conn, ccte=filtros.ccte, provincia=filtros.provincia, localidad=filtros.localidad,
    )
    if not filas:
        raise HTTPException(status_code=404, detail="Ninguna localidad coincide con los filtros")
    buffer = reports_service.generar_excel_resumen(filas, filtros=_texto_filtros(filtros))
    return _descarga(buffer, nombre="Resumen_RNI.xlsx", media_type=XLSX)


@router.get("/reports/excel/localidad")
def get_report_excel_localidad(ccte: str, provincia: str, localidad: str,
                               ambito: str = "Localidad", conn=Depends(get_db)):
    datos = reports_service.obtener_datos_informe(conn, ccte, provincia, localidad)
    _exigir_datos(datos, que=f"la localidad {localidad}")
    buffer = reports_service.generar_excel_informe(datos, ambito=ambito, etiqueta=localidad)
    return _descarga(buffer, nombre=f"Informe_RNI_{localidad}.xlsx", media_type=XLSX)


@router.get("/reports/excel/ccte")
def get_report_excel_ccte(ccte: str, conn=Depends(get_db)):
    datos = reports_service.obtener_datos_informe_ccte(conn, ccte)
    _exigir_datos(datos, que=f"el CCTE {ccte}")
    buffer = reports_service.generar_excel_informe(datos, ambito="CCTE", etiqueta=ccte)
    return _descarga(buffer, nombre=f"Informe_RNI_{ccte}.xlsx", media_type=XLSX)


# --- Mapa -------------------------------------------------------------------

class MapaPdfRequest(BaseModel):
    # data URL ("data:image/png;base64,...") o base64 pelado: las dos formas
    # en que canvas.toDataURL() puede llegar desde el cliente.
    png: str
    titulo: str = "Mapa de mediciones RNI"
    notas: list[str] = Field(default_factory=list)


@router.post("/reports/map-pdf")
def post_report_map_pdf(body: MapaPdfRequest):
    """Pasa la captura del mapa (lo que se ve en pantalla, con los filtros que
    esten marcados en la barra) por reportlab para imprimirla en una hoja A4.
    """
    crudo = body.png.split(",", 1)[-1] if "," in body.png else body.png
    try:
        imagen = base64.b64decode("".join(crudo.split()))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="La imagen no es base64 valido") from exc
    if not imagen.startswith(b"\x89PNG"):
        raise HTTPException(status_code=400, detail="Se esperaba una imagen PNG")
    if len(imagen) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen supera los 20 MB")

    buffer = reports_service.generar_pdf_mapa(
        imagen, titulo=body.titulo[:200], notas=[n[:500] for n in body.notas[:20]],
    )
    return _descarga(buffer, nombre="Mapa_RNI.pdf", media_type=PDF)
