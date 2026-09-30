# Respaldo de la base `rni.db`

La base (`backend/data/rni.db`, ~102 MB, 219 818 mediciones) **no está en
git**: `.gitignore` excluye `*.db` y `data/`. Todo lo que se respalda sale de
ese directorio a propósito — un respaldo adentro de `data/` se cae junto con
lo que queremos resguardar (era lo que pasaba con `rni_lote6_backup.db`, que
vivía al lado de la base).

## Respaldar

```bash
cd backend
.venv\Scripts\python.exe scripts\backup_db.py
```

Se puede correr con la aplicación arriba: `Connection.backup()` pagina la copia
desde la propia base, igual que `.dump`, así que el resultado es consistente
aunque alguien esté escribiendo. Un simple "copiar y pegar" del archivo **no**
te garantiza eso.

Salida esperada:

```
Origen   : ...\backend\data\rni.db
Destino  : C:\Users\lucas\Backups\rni
OK      : rni_20260930_1400.db  integrity_check=ok  mediciones=219818
```

El código de salida es `0` si todo salió bien, `2` si la cantidad de
mediciones de la copia no coincide con la de origen (se reintentaría), y `1`
si falla. Cada corrida deja una línea en `backup.log` dentro del destino.

| opción | para qué |
|---|---|
| `--listar` | qué copias hay, con fecha y tamaño |
| `--destino RUTA` | cambiar la carpeta destino |
| `--retener N` | cuántas copias conservar (por defecto 10) |
| `--sin-limpiar` | no borra las viejas |
| `--origen RUTA` | respaldar otra base (para migraciones) |

## Restaurar

```bash
cd backend
.venv\Scripts\python.exe scripts\restore_db.py --listar     # qué hay
.venv\Scripts\python.exe scripts\restore_db.py --ultimo     # la más reciente
.venv\Scripts\python.exe scripts\restore_db.py --desde RUTA/a/la/copia.db
```

Pide confirmación (o pasá `--si` para un script). Antes de tocar nada abre la
copia y corre `PRAGMA integrity_check`: **no se reemplaza una base sana por
una rota**. La base actual no se borra, pasa a `rni_rota_<fecha>.db` al lado
por si hay que mirarla, y si la copia no se puede escribir se devuelve la
original.

Cerrá uvicorn antes de restaurar: si alguien tiene el archivo abierto,
Windows no deja reemplazarlo (el script te lo avisa en vez de romper nada).

Verificado el 30/09/2026: copia → restauración → 12 tablas, 219 818
mediciones, 61 localidades, 5 CCTE, `health` en 200.

## Tarea programada

`RNI - backup diario de rni.db` — corre todos los días a las **20:00** con el
intérprete del `.venv` del proyecto y conserva las últimas 10 copias.

```powershell
Get-ScheduledTaskInfo -TaskName "RNI - backup diario de rni.db"   # ultimo resultado (0 = OK)
Start-ScheduledTask      -TaskName "RNI - backup diario de rni.db" # correrla ahora
Unregister-ScheduledTask -TaskName "RNI - backup diario de rni.db" # eliminarla
```

## Dónde viven

`C:\Users\lucas\Backups\rni\`

- `rni_AAAAmmdd_HHMM.db` — una copia por corrida
- `backup.log` — historial de corridas
- con retención de 10 y 102 MB por copia, ocupa ~1 GB como máximo

Si querés que además lleguen a la nube, esa carpeta se puede poner dentro de
OneDrive y habilitar su sincronización (hoy el proceso de OneDrive no está
corriendo, así que ni siquiera el repo se está subiendo).
