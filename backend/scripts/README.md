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
intérprete del `.venv` del proyecto y conserva las últimas 10 copias. Ahora
ejecuta `scripts/respaldar_y_subir.py`, así que **además de respaldar sube a
Drive** (ver el apartado siguiente).

```powershell
Get-ScheduledTaskInfo -TaskName "RNI - backup diario de rni.db"   # ultimo resultado (0 = OK)
Start-ScheduledTask      -TaskName "RNI - backup diario de rni.db" # correrla ahora
Unregister-ScheduledTask -TaskName "RNI - backup diario de rni.db" # eliminarla
```

Tiene `StartWhenAvailable = True`: si a las 20:00 la PC estaba apagada,
corre apenas se encienda. Ojo con `DisallowStartIfOnBatteries = True`, que
hoy está prendido: con la notebook sin enchufar, no arranca.

## Subir a Google Drive

La carpeta de respaldos se espeja contra la carpeta compartida de Drive con
**rclone** (v1.75.1, instalado con `winget install Rclone.Rclone`). El remoto
se creó una sola vez:

```bash
rclone config create rni-drive drive root_folder_id=<id de la carpeta>
rclone lsf rni-drive:   # tiene que listar el contenido
```

Hay dos momentos en que sube, y los dos hacen exactamente el mismo paso a
paso (`app/services/backup_service.py`):

| cuándo | quién lo dispara |
|---|---|
| **después de cada carga de expediente** | `POST /api/import` lo agenda como `BackgroundTasks`: responde la carga primero, y si Drive se cae la carga igual quedó hecha |
| **todos los días a las 20:00** | la tarea programada, con `scripts/respaldar_y_subir.py` |

```bash
cd backend
.venv\Scripts\python.exe scripts\respaldar_y_subir.py                # copia + sube
.venv\Scripts\python.exe scripts\respaldar_y_subir.py --dry-run       # qué subiría, sin tocar nada
.venv\Scripts\python.exe scripts\respaldar_y_subir.py --listar        # qué hay local y qué hay en Drive
.venv\Scripts\python.exe scripts\respaldar_y_subir.py --solo-subir    # sube sin crear copia nueva
```

**El sync va con `--exclude rni.db`.** La carpeta compartida trae un
`rni.db` que no generamos nosotros, y en rclone lo excluido no se copia ni
se borra: sin ese flag, un `sync` lo borraría porque en local no existe.
Un dry-run antes de la primera subida confirmó 0 DELETE.

Cada corrida deja dos registros:

- `drive.log` — una línea por intento: fecha, `OK`/`FALLO`/`DRY-RUN` y lo
  que transfirió rclone.
- `rclone.log` — el detalle de rclone con progreso cada 15 s. Es el que
  sirve para mirar si un sync se está quedando quieto, y por eso mismo va
  excluido del sync (lo escribe él mientras corre).

El techo del sync es de **1 hora** por corrida: la primera vez (02/10/2026)
con 900 s no alcanzaba para los 204 MB de arranque y rclone se mató a
mitad de subida.

Si la copia local sale mal, **no se sube nada**: `backup_db.py` devuelve
código `2` cuando la cantidad de mediciones de la copia no coincide con la
de origen, y el script corta antes de mandar algo que no sirve para
restaurar.

### Variables

| variable | efecto |
|---|---|
| `RNI_BACKUP_AUTO=0` | no respalda ni sube tras una carga (así están los tests: `tests/conftest.py`) |
| `RNI_RCLONE=RUTA\rclone.exe` | ruta exacta al binario si no está en el PATH |

Sin esas variables, se busca rclone en el PATH y en las rutas típicas de
winget — hace falta porque el PATH del proceso que ya está corriendo (uvicorn
levantado antes de instalar) no se actualiza solo. Si no aparece, el backup
local igual se hace y la subida queda registrada como
`FALLO  no encontre rclone.exe` en `drive.log`.

### Restaurar desde Drive

```bash
rclone copy rni-drive: C:\Users\lucas\Backups\rni\ --exclude rni.db   # bajar las copias
cd backend
.venv\Scripts\python.exe scripts\restore_db.py --listar
.venv\Scripts\python.exe scripts\restore_db.py --ultimo
```

## Dónde viven

`C:\Users\lucas\Backups\rni\`

- `rni_AAAAmmdd_HHMM.db` — una copia por corrida
- `backup.log` — historial de respaldos locales
- `drive.log` — historial de subidas a Drive (fecha, OK/FALLO y lo que
  transfirió rclone)
- con retención de 10 y 102 MB por copia, ocupa ~1 GB como máximo; en Drive
  queda el mismo espejo, más el `rni.db` de la carpeta compartida
