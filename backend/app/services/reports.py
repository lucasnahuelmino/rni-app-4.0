"""Generación de informes Word/PDF de una localidad.

Port funcional de sections/export_informes.py del sistema Streamlit actual,
con una corrección de la Auditoría Fase 1 (hallazgo A9): el informe Word
original se escribía a un archivo físico en el directorio de trabajo del
proceso antes de leerlo de vuelta para la descarga -- acá todo se arma en
memoria (BytesIO), nunca se toca el disco, así que no hay riesgo de
colisión entre usuarios concurrentes ni archivos huérfanos en el servidor.

El gráfico usa matplotlib en vez de Plotly+Kaleido (el sistema actual
depende de Kaleido solo para poder exportar el PNG del informe) -- reduce
una dependencia pesada para un gráfico simple de barras. Si el equipo
prefiere mantener el estilo visual exacto de Plotly, se puede reemplazar
sin tocar el resto del pipeline.
"""
from __future__ import annotations

import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PILImage
import pandas as pd
from docx import Document
from docx.shared import Inches
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.calculations.dates import calcular_tiempo_trabajado_segundos, format_timedelta_long
from app.utils import formato

# Mismo PNG que encabeza la barra lateral en el frontend. El backend lleva
# su propia copia porque los informes se arman acá: ningún Word, PDF o
# Excel puede depender de un archivo del lado del cliente.
LOGO = Path(__file__).resolve().parent.parent / "assets" / "logoenacom.png"


def _armar_grafico_localidades_por_provincia_ccte(filas: list[dict]) -> io.BytesIO | None:
    df = pd.DataFrame(filas)
    if df.empty or not {"provincia", "ccte", "localidad"}.issubset(df.columns):
        return None

    resumen = df.groupby(["provincia", "ccte"])["localidad"].nunique().reset_index(name="cantidad")
    if resumen.empty:
        return None

    fig, ax = plt.subplots(figsize=(6, 3.5))
    for ccte_val, grupo in resumen.groupby("ccte"):
        ax.bar(grupo["provincia"], grupo["cantidad"], label=ccte_val)
    ax.set_ylabel("Localidades")
    ax.legend(fontsize=7)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def obtener_datos_informe(conn: sqlite3.Connection, ccte: str, provincia: str,
                           localidad: str) -> dict:
    """Informes de UNA localidad."""
    filas = [dict(r) for r in conn.execute(
        "SELECT * FROM mediciones WHERE ccte = ? AND provincia = ? AND localidad = ?",
        (ccte, provincia, localidad),
    ).fetchall()]
    return _construir_datos(filas)


def obtener_datos_informe_ccte(conn: sqlite3.Connection, ccte: str) -> dict:
    """Informes de TODO un centro (CCTE), con la misma salida de arriba."""
    filas = [dict(r) for r in conn.execute(
        "SELECT * FROM mediciones WHERE ccte = ?", (ccte,),
    ).fetchall()]
    return _construir_datos(filas)


def _construir_datos(filas: list) -> dict:
    """Arma el payload del informe a partir de las filas ya leídas.

    Separado de la consulta a proposito: localidad y CCTE pasan por los
    mismos calculos, asi que si cambia un agregado cambia para los dos
    informes y no pueden divergir. `filas` viene de cualquier alcance."""

    df = pd.DataFrame(filas)
    if df.empty:
        return {"filas": [], "df": df}

    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors="coerce")

    idx_max = df["resultado_vm"].idxmax() if df["resultado_vm"].notna().any() else None
    fila_max = df.loc[idx_max] if idx_max is not None else None

    fecha_min = df["fecha_hora"].min() if df["fecha_hora"].notna().any() else None
    fecha_max = df["fecha_hora"].max() if df["fecha_hora"].notna().any() else None

    tiempo_trabajado_seg = calcular_tiempo_trabajado_segundos(df)

    sondas = sorted(df["sonda"].dropna().astype(str).unique().tolist()) if "sonda" in df else []

    resumen_mensual = pd.DataFrame()
    if df["fecha_hora"].notna().any():
        df_mes = df.dropna(subset=["fecha_hora"]).copy()
        df_mes["mes"] = df_mes["fecha_hora"].dt.to_period("M").astype(str)
        resumen_mensual = df_mes.groupby("mes").agg(
            puntos=("resultado_vm", "count"),
            fecha_inicio=("fecha_hora", "min"),
            fecha_fin=("fecha_hora", "max"),
        ).reset_index()
        horas_por_mes = []
        for mes, grupo in df_mes.groupby("mes"):
            horas_por_mes.append({"mes": mes, "horas": format_timedelta_long(calcular_tiempo_trabajado_segundos(grupo))})
        resumen_mensual = resumen_mensual.merge(pd.DataFrame(horas_por_mes), on="mes")

    expedientes_df = pd.DataFrame()
    if "expediente" in df.columns and df["expediente"].notna().any():
        expedientes_df = df.groupby("expediente").agg(
            puntos=("resultado_vm", "count"),
            max_vm=("resultado_vm", "max"),
            ccte=("ccte", lambda x: ", ".join(sorted(x.dropna().unique()))),
            provincias=("provincia", lambda x: ", ".join(sorted(x.dropna().unique()))),
            localidades=("localidad", lambda x: ", ".join(sorted(x.dropna().unique()))),
        ).reset_index().sort_values("max_vm", ascending=False)

    grafico = _armar_grafico_localidades_por_provincia_ccte(filas)

    return {
        "filas": filas,
        "total_puntos": len(df),
        "resultado_max_vm": None if fila_max is None else float(fila_max["resultado_vm"]),
        "resultado_max_pct": None if fila_max is None else fila_max.get("resultado_pct"),
        "localidad_max": None if fila_max is None else fila_max.get("localidad"),
        "provincia_max": None if fila_max is None else fila_max.get("provincia"),
        "ccte_max": None if fila_max is None else fila_max.get("ccte"),
        "fecha_hora_max": None if fila_max is None else fila_max.get("fecha_hora"),
        "fecha_min": fecha_min, "fecha_max": fecha_max,
        "tiempo_trabajado_seg": tiempo_trabajado_seg,
        "sondas": sondas,
        "resumen_mensual": resumen_mensual,
        "expedientes_df": expedientes_df,
        "grafico": grafico,
    }


def generar_word(datos: dict, *, ambito: str, etiqueta: str) -> io.BytesIO:
    doc = Document()
    # El mismo logo que encabeza el sidebar: el informe se lee con la
    # identidad del sistema, no como un archivo suelto.
    if LOGO.exists():
        doc.add_picture(str(LOGO), width=Inches(2.1))
    doc.add_heading("Informe de Mediciones RNI", level=1)
    doc.add_paragraph(f"Ámbito del informe: {ambito}")
    doc.add_paragraph(f"{ambito}: {etiqueta}")
    doc.add_paragraph(f"Fecha de generación: "
                      f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')} UTC")
    doc.add_paragraph(f"Total de puntos medidos: {datos.get('total_puntos', 0)}")

    if datos.get("resultado_max_vm") is not None:
        pct = datos.get("resultado_max_pct")
        texto = f"Resultado máximo registrado: {formato.vm(datos['resultado_max_vm'])} V/m"
        if pct is not None:
            texto += f" ({formato.pct(pct)} % del límite)"
        doc.add_paragraph(texto)
        doc.add_paragraph(
            f"Ubicación del máximo: {datos.get('localidad_max')}, {datos.get('provincia_max')} "
            f"(CCTE {datos.get('ccte_max')})"
        )

    if datos.get("tiempo_trabajado_seg"):
        doc.add_paragraph(f"Tiempo total estimado de medición: {format_timedelta_long(datos['tiempo_trabajado_seg'])}")

    if datos.get("sondas"):
        doc.add_paragraph(f"Sondas utilizadas: {', '.join(datos['sondas'])}")

    if datos.get("grafico") is not None:
        doc.add_heading("Localidades por provincia y CCTE", level=2)
        doc.add_picture(datos["grafico"], width=None)

    resumen_mensual = datos.get("resumen_mensual")
    if resumen_mensual is not None and not resumen_mensual.empty:
        doc.add_heading("Desglose mensual", level=2)
        table = doc.add_table(rows=1, cols=5)
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text, hdr[4].text = (
            "Mes", "Puntos", "Horas trabajadas", "Fecha inicio", "Fecha fin",
        )
        for _, row in resumen_mensual.iterrows():
            cells = table.add_row().cells
            cells[0].text = str(row["mes"])
            cells[1].text = str(row["puntos"])
            cells[2].text = row["horas"]
            cells[3].text = row["fecha_inicio"].strftime("%d/%m/%Y %H:%M") if pd.notna(row["fecha_inicio"]) else "-"
            cells[4].text = row["fecha_fin"].strftime("%d/%m/%Y %H:%M") if pd.notna(row["fecha_fin"]) else "-"

    expedientes_df = datos.get("expedientes_df")
    if expedientes_df is not None and not expedientes_df.empty:
        doc.add_heading("Resumen por expediente", level=2)
        table = doc.add_table(rows=1, cols=6)
        hdr = table.rows[0].cells
        for i, titulo in enumerate(["Expediente", "Puntos", "Max (V/m)", "CCTE", "Provincias", "Localidades"]):
            hdr[i].text = titulo
        for _, row in expedientes_df.iterrows():
            cells = table.add_row().cells
            cells[0].text = str(row["expediente"])
            cells[1].text = str(row["puntos"])
            cells[2].text = formato.vm(row["max_vm"]) if pd.notna(row["max_vm"]) else "-"
            cells[3].text = str(row["ccte"])
            cells[4].text = str(row["provincias"])
            cells[5].text = str(row["localidades"])

    buffer = io.BytesIO()
    doc.save(buffer)  # se guarda directo en memoria, nunca en disco
    buffer.seek(0)
    return buffer


def generar_pdf(datos: dict, *, ambito: str, etiqueta: str) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    if LOGO.exists():
        story.append(RLImage(str(LOGO), width=200, height=51))
        story.append(Spacer(1, 10))
    story += [
        Paragraph("Informe de Mediciones RNI", styles["Title"]),
        Spacer(1, 6),
        Paragraph(f"Ámbito del informe: {ambito}", styles["Heading2"]),
        Spacer(1, 12),
        Paragraph(f"<b>{ambito}:</b> {etiqueta}", styles["Normal"]),
        Paragraph(f"<b>Fecha de generación:</b> "
                  f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')} UTC",
                  styles["Normal"]),
        Paragraph(f"<b>Total de puntos medidos:</b> {datos.get('total_puntos', 0)}",
                  styles["Normal"]),
    ]

    if datos.get("resultado_max_vm") is not None:
        pct = datos.get("resultado_max_pct")
        texto = f"<b>Resultado máximo registrado:</b> {formato.vm(datos['resultado_max_vm'])} V/m"
        if pct is not None:
            texto += f" ({formato.pct(pct)} % del límite)"
        story.append(Paragraph(texto, styles["Normal"]))
        story.append(Paragraph(
            f"<b>Ubicación del máximo:</b> {datos.get('localidad_max')}, {datos.get('provincia_max')} "
            f"(CCTE {datos.get('ccte_max')})", styles["Normal"],
        ))

    if datos.get("tiempo_trabajado_seg"):
        story.append(Paragraph(
            f"<b>Tiempo total estimado de medición:</b> "
            f"{format_timedelta_long(datos['tiempo_trabajado_seg'])}",
            styles["Normal"],
        ))

    if datos.get("sondas"):
        story.append(Paragraph(
            f"<b>Sondas utilizadas:</b> {', '.join(datos['sondas'])}",
            styles["Normal"],
        ))

    story.append(Spacer(1, 16))

    if datos.get("grafico") is not None:
        story.append(RLImage(datos["grafico"], width=400, height=250))
        story.append(Spacer(1, 16))

    resumen_mensual = datos.get("resumen_mensual")
    if resumen_mensual is not None and not resumen_mensual.empty:
        story.append(Paragraph("<b>Desglose por mes</b>", styles["Heading2"]))
        for _, row in resumen_mensual.iterrows():
            story.append(Paragraph(
                f"Mes {row['mes']}: {row['puntos']} puntos, horas trabajadas: {row['horas']}.", styles["Normal"],
            ))
        story.append(Spacer(1, 12))

    expedientes_df = datos.get("expedientes_df")
    if expedientes_df is not None and not expedientes_df.empty:
        story.append(Paragraph("<b>Resumen por expediente</b>", styles["Heading2"]))
        for _, row in expedientes_df.iterrows():
            story.append(Paragraph(
                f"Expediente {row['expediente']}: {row['puntos']} puntos, "
                f"máx {formato.vm(row['max_vm'])} V/m, CCTE: {row['ccte']}.", styles["Normal"],
            ))

    pdf.build(story)
    buffer.seek(0)
    return buffer


# --- Excel ---------------------------------------------------------------
#
# Mismas columnas que la vista Resumen (frontend/src/views/ResumenView.vue,
# su array COLUMNAS). Se declaran aca porque el archivo se arma en el
# servidor, pero es la misma lista de la misma vista: si se agrega una, va
# en los dos lados.
#
# La única que se fue de un lado solo es `fecha_fin`: la vista la sacó para
# que el registro entrara en UN renglón (con 9 columnas la fila no entraba
# en 1366 px) y el Excel la conserva, porque ahí el ancho no es problema.
# Ver el docstring de get_report_excel.
#
# Los tipos deciden el formato de la celda. "vm" y "pct" usan el mismo tope
# de decimales que el frontend (3 y 4, ver frontend/src/format.js): esos son
# los decimales que la base realmente tiene, asi que el formato muestra todo
# lo que hay. El valor se guarda CRUDO en la celda y el formato solo decide
# cuanto se ve -- no se redondea nada, que es la regla de decimales del
# proyecto, y ademas quien copie la celda se lleva el numero exacto.
COLUMNAS_RESUMEN = (
    ("ccte", "CCTE", "texto"),
    ("provincia", "Provincia", "texto"),
    ("localidad", "Localidad", "texto"),
    ("expedientes", "Expediente(s)", "texto"),
    ("mediciones", "Mediciones", "entero"),
    ("resultado_max_vm", "Máx. V/m", "vm"),
    ("resultado_max_pct", "Nivel", "pct"),
    ("fecha_inicio", "Inicio", "fecha"),
    ("fecha_fin", "Fin", "fecha"),
)

# Formato de celda por tipo. '#' no rellena con ceros: 2.5 en '0.###'
# se ve '2.5', igual que lo imprime la vista (parseFloat(toFixed(n))).
FORMATOS_NUM = {
    "entero": "#,##0",
    "vm": "0.###",
    "pct": "0.####",
}

# Azul del sidebar y del logo: el documento se lee como la app.
AZUL = "FF0B1742"


def _borde_tabla():
    fino = Side(style="thin", color="FFB7BFD1")
    return Border(left=fino, right=fino, top=fino, bottom=fino)


def _encabezado_excel(ws, *, titulo, ambito=None, etiqueta=None,
                      total_puntos=None, filtros=None):
    """Logo y títulos del documento, iguales a los del Word y del PDF.

    Devuelve la fila donde arranca la tabla.
    """
    fila = 1
    if LOGO.exists():
        ws.add_image(XLImage(str(LOGO)), "A1")
        ws.row_dimensions[1].height = 46  # el logo mide 267x68 px
        fila = 4  # deja las tres primeras filas libres bajo la imagen

    def linea(texto, *, tam=11, negrita=True, color=AZUL):
        nonlocal fila
        c = ws.cell(row=fila, column=1, value=texto)
        c.font = Font(bold=negrita, size=tam, color=color)
        c.alignment = Alignment(horizontal="left", vertical="center")
        fila += 1

    linea(titulo, tam=16)
    if ambito:
        linea("Ámbito del informe: %s" % ambito, negrita=False)
    if etiqueta:
        linea("%s: %s" % (ambito, etiqueta), negrita=False)
    if total_puntos is not None:
        linea("Total de puntos medidos: %d" % total_puntos, negrita=False)
    if filtros:
        linea("Filtros aplicados: %s" % filtros, negrita=False)
    linea("Fecha de generación: %s UTC" %
          datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S"), negrita=False)
    return fila + 1


def _pie_excel(ws, fila):
    """El mismo pie que tiene el sidebar, para cerrar el documento."""
    c = ws.cell(row=fila + 1, column=1,
                value="Dirección Nacional de Control y Fiscalización")
    c.font = Font(italic=True, size=9, color="FF5A6478")


def _tabla_excel(ws, fila, cabeceras, filas, formatos=None):
    """Escribe una tabla con el mismo estilo del resto de la app: banda de
    encabezado en el azul del sidebar y contenido centrado, igual que la
    regla de centrado de tokens.css. Devuelve la fila siguiente."""
    borde = _borde_tabla()
    for i, texto in enumerate(cabeceras, start=1):
        c = ws.cell(row=fila, column=i, value=texto)
        c.font = Font(bold=True, color="FFFFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = borde
    ws.row_dimensions[fila].height = 26
    fila += 1

    for datos_fila in filas:
        for i, valor in enumerate(datos_fila, start=1):
            if type(valor).__module__.startswith("numpy"):
                valor = valor.item()  # openpyxl no sabe guardar numpy.*
            c = ws.cell(row=fila, column=i, value=valor)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = borde
            if formatos and i in formatos and isinstance(valor, (int, float)):
                c.number_format = formatos[i]
        fila += 1
    return fila


def _ajustar_anchos(ws, tope=46):
    """Ancho por columna según lo mas ancho que haya en ella, sin pasarse.
   
    Se lee toda la hoja y no solo la tabla: la columna A arrastra los
    títulos, que son lo mas largo."""
    for columna in ws.iter_cols():
        ancho = 0
        for c in columna:
            if c.value is not None:
                ancho = max(ancho, len(str(c.value)))
        if ancho:
            ws.column_dimensions[get_column_letter(columna[0].column)].width = \
                min(ancho + 3, tope)


def generar_excel_resumen(filas, *, filtros=None):
    """Excel de la tabla de Resumen: una fila por localidad, con las
    mismas columnas que muestra la vista (incluida Expediente(s)), el logo
    y los títulos de siempre."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"

    fila = _encabezado_excel(ws, titulo="Resumen de mediciones RNI",
                              ambito="Resumen por localidad", filtros=filtros)

    cabeceras = [etiqueta for _, etiqueta, _ in COLUMNAS_RESUMEN]
    filas_excel = []
    for d in filas:
        valores = []
        for campo, _, tipo in COLUMNAS_RESUMEN:
            valor = d.get(campo)
            if tipo == "fecha" and isinstance(valor, str):
                valor = valor[:10]  # lo mismo que muestra la vista
            valores.append(valor)
        filas_excel.append(valores)

    formatos = {i + 1: FORMATOS_NUM[tipo]
                for i, (_, _, tipo) in enumerate(COLUMNAS_RESUMEN)
                if tipo in FORMATOS_NUM}
    fila = _tabla_excel(ws, fila, cabeceras, filas_excel, formatos)

    _ajustar_anchos(ws)
    _pie_excel(ws, fila)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generar_excel_informe(datos, *, ambito, etiqueta):
    """Excel del informe de una localidad o de un CCTE: los mismos bloques
    del Word y del PDF (KPIs, grafico, desglose mensual, resumen por
    expediente), para poder editarlos en planilla."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Informe"

    fila = _encabezado_excel(ws, titulo="Informe de Mediciones RNI",
                              ambito=ambito, etiqueta=etiqueta,
                              total_puntos=datos.get("total_puntos"))

    kpis = []
    if datos.get("resultado_max_vm") is not None:
        kpis.append(("Resultado máximo registrado",
                     "%s V/m" % formato.vm(datos["resultado_max_vm"])))
        if datos.get("resultado_max_pct") is not None:
            kpis.append(("Nivel",
                         "%s %% del límite" % formato.pct(datos["resultado_max_pct"])))
        kpis.append(("Ubicación del máximo",
                     "%s, %s (CCTE %s)" % (datos.get("localidad_max"),
                                             datos.get("provincia_max"),
                                             datos.get("ccte_max"))))
    if datos.get("tiempo_trabajado_seg"):
        kpis.append(("Tiempo total de medición",
                     format_timedelta_long(datos["tiempo_trabajado_seg"])))
    if datos.get("sondas"):
        kpis.append(("Sondas utilizadas", ", ".join(datos["sondas"])))
    if kpis:
        fila = _tabla_excel(ws, fila, ["Dato", "Valor"], kpis)
        fila += 1

    grafico = datos.get("grafico")
    if grafico is not None:
        try:
            img = XLImage(grafico)
            img.width, img.height = 720, 420  # el original es 6x3.5 in
            ws.add_image(img, "A%d" % fila)
            ws.row_dimensions[fila].height = 315
            fila += 22  # 420 px a ~20 px por fila
            fila += 1
        except Exception:  # noqa: BLE001
            # Un grafico que no se puede insertar no tiene por que tumbar
            # la descarga del resto del informe.
            pass

    resumen_mensual = datos.get("resumen_mensual")
    if resumen_mensual is not None and not resumen_mensual.empty:
        c = ws.cell(row=fila, column=1, value="Desglose mensual")
        c.font = Font(bold=True, size=12, color=AZUL)
        fila += 1
        filas_mes = [[r["mes"], int(r["puntos"]), r["horas"],
                      str(r["fecha_inicio"])[:19], str(r["fecha_fin"])[:19]]
                     for _, r in resumen_mensual.iterrows()]
        fila = _tabla_excel(
            ws, fila,
            ["Mes", "Puntos", "Horas trabajadas", "Fecha inicio", "Fecha fin"],
            filas_mes, {2: FORMATOS_NUM["entero"]},
        )
        fila += 1

    expedientes_df = datos.get("expedientes_df")
    if expedientes_df is not None and not expedientes_df.empty:
        c = ws.cell(row=fila, column=1, value="Resumen por expediente")
        c.font = Font(bold=True, size=12, color=AZUL)
        fila += 1
        filas_exp = [[r["expediente"], int(r["puntos"]), float(r["max_vm"]),
                      r["ccte"], r["provincias"], r["localidades"]]
                     for _, r in expedientes_df.iterrows()]
        fila = _tabla_excel(
            ws, fila,
            ["Expediente", "Puntos", "Máx. V/m", "CCTE", "Provincias", "Localidades"],
            filas_exp,
            {2: FORMATOS_NUM["entero"], 3: FORMATOS_NUM["vm"]},
        )

    _ajustar_anchos(ws)
    _pie_excel(ws, fila)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generar_pdf_mapa(imagen_png, *, titulo, notas):
    """PDF de una captura del mapa: lo que se ve en pantalla, que ya
    incluye o no los filtros globales segun lo que este marcado en la barra
    de controles.

    El encabezado (logo, titulo y notas) se DIBUJA en el callback y no va como
    flowable: asi el espacio que ocupa es exactamente el margen superior
    reservado y la imagen, unica del story, mide lo mismo que el frame. Eso
    era lo que tiraba LayoutError cuando la captura quedaba apenas mas alta
    que la caja y reportlab intentaba pasarla a la pagina siguiente.
    """
    buffer = io.BytesIO()
    # El mapa es apaisado: en A4 vertical quedaba media pagina en blanco.
    pagina = landscape(A4)
    margen = 18
    alto_encabezado = 110
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=pagina,
        leftMargin=margen,
        rightMargin=margen,
        topMargin=alto_encabezado,
        bottomMargin=margen,
    )

    with PILImage.open(io.BytesIO(imagen_png)) as img_abierta:
        ancho, alto = img_abierta.size

    # pdf.width y pdf.height ya descuentan los margenes, asi que la imagen
    # entra siempre: primero por ancho, despues por alto si la captura es
    # alta (una captura vertical tampoco puede salirse de la pagina).
    # El frame util deja 6pt de padding por lado que pdf.width/pdf.height no
    # descuentan: sin restarlos la captura quedaba un pelito mas alta que la
    # caja y reportlab seguia tirando LayoutError.
    util_w = pdf.width - 12
    util_h = pdf.height - 12
    escala = min(util_w / ancho, util_h / alto)
    story = [RLImage(io.BytesIO(imagen_png),
                     width=ancho * escala, height=alto * escala,
                     hAlign="CENTER")]

    def encabezado(canvas, doc):
        canvas.saveState()
        x = margen
        y_logo = pagina[1] - margen - 33
        if LOGO.exists():
            canvas.drawImage(str(LOGO), x, y_logo, 130, 33,
                             mask="auto", anchor="nw")
            x_titulo = margen + 130 + 14
        else:
            x_titulo = margen

        canvas.setFillColor("#0B1742")
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(x_titulo, y_logo + 10, titulo)

        # Las notas se acomodan en el aire que deja el margen superior; si
        # no entran, se cortan (nunca pisan el mapa).
        canvas.setFillColor("#5A6478")
        canvas.setFont("Helvetica-Oblique", 8)
        ancho_notas = pagina[0] - 2 * margen
        y = y_logo - 15
        y_min = pagina[1] - alto_encabezado + 12
        pendientes = list(notas)
        dibujadas = 0
        cortadas = 0
        while pendientes and y > y_min:
            linea_actual = pendientes[0]
            linea = ""
            for palabra in linea_actual.split():
                prueba = (linea + " " + palabra).strip()
                if canvas.stringWidth(prueba, "Helvetica-Oblique", 8) <= ancho_notas:
                    linea = prueba
                else:
                    if linea:
                        break
                    linea = palabra
            resto = linea_actual[len(linea):].strip()
            if resto:
                pendientes[0] = resto
            else:
                pendientes.pop(0)
            canvas.drawString(x, y, linea)
            y -= 11
            dibujadas += 1
        if pendientes:
            cortadas = len(pendientes)
        if cortadas:
            canvas.drawString(x, y, f"(y {cortadas} nota(s) mas, sin espacio)")

        # Pie: va por debajo del frame, en el margen inferior.
        canvas.setFillColor("#8A93A5")
        canvas.setFont("Helvetica", 7)
        canvas.drawString(margen, 7,
                          "Dirección Nacional de Control y Fiscalización")
        canvas.drawRightString(pagina[0] - margen, 7,
                               datetime.now(timezone.utc)
                               .strftime("%d/%m/%Y %H:%M:%S UTC"))
        canvas.restoreState()

    # onLaterPages por las dudas: si la captura no entrase en la primera
    # hoja, la segunda tambien tendria que salir con su encabezado.
    pdf.build(story, onFirstPage=encabezado, onLaterPages=encabezado)
    buffer.seek(0)
    return buffer
