# Backend RNI (Fase 3)

## Instalación
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Correr los tests
```
pytest tests/ -v
```
Los tests cubren fórmulas, fechas, coordenadas, importación + recálculo de
resúmenes, KPIs, edición/borrado de localidades, diagnóstico y generación de
informes. La cantidad exacta cambia con el código -- contalos con
`pytest tests/ --co -q | Select-Object -Last 1`.

## Levantar la API
```
uvicorn app.main:app --reload
```
Documentación interactiva en http://localhost:8000/docs

## Migrar desde la base Streamlit actual
```
python -m app.db.migrate --origen /ruta/a/rni.db --destino /ruta/a/rni_v2.db
```
Corre la validación cruzada automáticamente al final (ver Fase 2, §2.1). Si
encuentra diferencias, termina con código de error y NO hay que promover el
destino a producción hasta resolver la causa.

## Puntos pendientes de validación (heredados de la Fase 1 y descubiertos en Fase 3)
Ver comentarios en:
- `app/calculations/rni.py` (significado de la constante 0.20021, fórmula de "Promedio %")
- `app/calculations/geo.py` (DOS bugs de signo en coordenadas DMS, documentados con tests de regresión)
- `app/services/diagnostics.py` (umbral de "valores sospechosos", sin definir)
