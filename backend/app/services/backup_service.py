"""Respaldo local de `rni.db` y subida de esa copia a Google Drive.

Dos pasos con dos responsables distintos:

* `scripts/backup_db.py` genera la copia consistente en local, en
  `config.BACKUP_DIR` (fuera del repo, retención 10). Ese script no se
  toca: sigue siendo el que valida con `PRAGMA integrity_check` y con el
  conteo de mediciones antes de dar por buena la copia.
* Este módulo sube esa carpeta con `rclone sync`, espejando lo que hay en
  local. La carpeta compartida ya trae un `rni.db` que no generamos
  nosotros, así que el sync va con `--exclude rni.db`: en rclone lo
  excluido no se copia NI se borra, de modo que un sync no se come lo que
  no es nuestro.

Quién lo llama:

* `POST /api/import` lo agenda como `BackgroundTasks`, después de haber
  respondido: subir 102 MB no tiene que frenar la carga, y si Drive se cae
  la carga igual ya quedó hecha (sólo queda el aviso en el log).
* `scripts/respaldar_y_subir.py`, que es el mismo paso a paso que corre la
  tarea programada de las 20:00.

Con `RNI_BACKUP_AUTO=0` no se hace nada. Los tests de `POST /api/import`
pasan por acá (TestClient corre los background tasks) y ninguno debe subir
102 MB: el conftest los deja apagados.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from app.core.config import BACKUP_DIR

# backend/ — el módulo vive en app/services/
BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPT_BACKUP = BASE_DIR / "scripts" / "backup_db.py"

# Remoto de rclone que apunta a la carpeta compartida (se creó con
# `rclone config create rni-drive drive root_folder_id=...`).
REMOTO_DEFECTO = "rni-drive:"

# El archivo que está en la carpeta de Drive y que no hicimos con este
# proceso. Sin este exclude, `sync` lo consideraría "sobra" y lo borraría.
EXCLUIR = "rni.db"

LOG_DRIVE = "drive.log"

# Lo escribe rclone mientras corre, al lado de los respaldos. Va aparte de
# drive.log porque es el detalle línea por línea (progreso cada 15 s), y por
# eso también entra en el exclude del sync: estaría subiéndose a sí mismo a
# mitad de escritura.
LOG_RCLONE = "rclone.log"

# 102 MB por copia. La primera corrida (02/10/2026) se cortó a los 900 s
# sin terminar ni un .db: matar rclone a mitad deja el archivo a medias y,
# encima, sin ningún registro de a cuánto iba. Una hora de techo alcanza
# sobradamente para cualquier subida razonable, y si se pasa es que algo se
# colgó de verdad.
TIMEOUT_BACKUP = 300
TIMEOUT_SYNC = 3600


def auto() -> bool:
    """¿Está habilitada la subida?

    Se lee en cada llamada y no al importar el módulo: así un
    `monkeypatch.setenv` de los tests alcance, y también si algún día se
    quiere apagar y prender sin reiniciar uvicorn.
    """
    valor = os.environ.get("RNI_BACKUP_AUTO", "1").strip().lower()
    return valor not in {"0", "false", "no", "off"}


def encontrar_rclone() -> Path | None:
    """Dónde está el binario de rclone.

    Orden: `RNI_RCLONE` (ruta exacta, para saltarse el PATH) → PATH →
    instalaciones típicas de Windows. Hacen falta los últimos dos porque el
    PATH del proceso que ya está corriendo (uvicorn levantado antes de
    instalar rclone) no se actualiza solo.
    """
    explicito = os.environ.get("RNI_RCLONE")
    if explicito and Path(explicito).exists():
        return Path(explicito)

    en_path = shutil.which("rclone")
    if en_path:
        return Path(en_path)

    candidatos: list[Path] = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base:
            candidatos.append(Path(base) / "rclone" / "rclone.exe")

    winget = os.environ.get("LOCALAPPDATA")
    if winget:
        paquetes = Path(winget) / "Microsoft" / "WinGet" / "Packages"
        if paquetes.exists():
            # winget lo descomprime en Packages\Rclone.Rclone_*\rclone-*/rclone.exe
            candidatos.extend(sorted(paquetes.glob("Rclone.Rclone_*/*/rclone.exe"),
                                     reverse=True))

    for ruta in candidatos:
        if ruta.exists():
            return ruta
    return None


def comando_sync(rclone: Path, origen: Path, remoto: str,
                 dry_run: bool = False) -> list[str]:
    """El comando exacto del sync, aparte, para poder testearlo sin
    ejecutar rclone (y para que los exclude queden en un solo lugar)."""
    cmd = [str(rclone), "sync", str(origen), remoto,
           "--exclude", EXCLUIR,
           "--exclude", LOG_RCLONE,
           # 8Mi de default son 13 requests para un archivo de 102 MB; con
           # 64M son 2, y cada request sobre un link lento cuesta tiempo.
           "--drive-chunk-size", "64M",
           # Progreso cada 15 s en rclone.log. Sin esto, un sync que se
           # corta no deja ni idea de a cuánto estaba (le pasó al primero).
           "--stats", "15s",
           "--log-file", str(Path(origen) / LOG_RCLONE),
           "-v"]
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def _apendar_log(destino: Path, texto: str) -> None:
    """Una línea por corrida en `drive.log`, al lado de `backup.log`.

    Es secundario: si no se puede escribir no rompe la subida.
    """
    try:
        with open(Path(destino) / LOG_DRIVE, "a", encoding="utf-8") as fh:
            fh.write("%s  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   texto))
    except OSError:
        pass


def _salida(proc: subprocess.CompletedProcess) -> str:
    return "%s%s" % (proc.stdout or "", proc.stderr or "")


def _cola(ruta: Path, bytes_: int = 8192) -> str:
    """Los últimos bytes de un archivo. Para rclone.log no hace falta leerlo
    entero: el resumen final está al final."""
    try:
        with open(ruta, "rb") as fh:
            fh.seek(0, 2)
            tamano = fh.tell()
            fh.seek(max(0, tamano - bytes_))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _resumen(salida: str) -> str:
    """El `Transferred:` que cierra el resumen de rclone.

    Son dos líneas y sirve la de bytes: la otra es el conteo de archivos
    ("3 / 3") y no dice ni cuánto pesó ni a qué velocidad fue.
    """
    en_bytes = ""
    ultima = ""
    for linea in salida.splitlines():
        texto = linea.strip()
        if texto.startswith("Transferred:"):
            ultima = texto
            if any(unidad in texto for unidad in ("MiB", "GiB", "kB", " B")):
                en_bytes = texto
    return en_bytes or ultima


def subir(origen: Path = BACKUP_DIR, remoto: str = REMOTO_DEFECTO,
          dry_run: bool = False) -> dict:
    """`rclone sync` de la carpeta de respaldos hacia Drive.

    Devuelve `{"ok": bool, "estado": str, "detalle": str}` y no lanza por
    problemas de red o de instalación: quien llama sólo tiene que mirar
    `ok`.
    """
    origen = Path(origen)
    rclone = encontrar_rclone()
    if rclone is None:
        _apendar_log(origen, "FALLO  no encontre rclone.exe (probar RNI_RCLONE)")
        return {"ok": False, "estado": "sin-rclone",
                "detalle": "no encontre rclone.exe"}
    if not origen.is_dir():
        return {"ok": False, "estado": "sin-origen",
                "detalle": "no existe la carpeta %s" % origen}

    cmd = comando_sync(rclone, origen, remoto, dry_run)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=TIMEOUT_SYNC, encoding="utf-8",
                              errors="replace")
    except subprocess.TimeoutExpired:
        _apendar_log(origen, "FALLO  sync cortado por timeout (%ss)" % TIMEOUT_SYNC)
        return {"ok": False, "estado": "timeout",
                "detalle": "rclone no terminó en %ss" % TIMEOUT_SYNC}
    except OSError as exc:
        _apendar_log(origen, "FALLO  no pude ejecutar rclone: %s" % exc)
        return {"ok": False, "estado": "error", "detalle": str(exc)}

    salida = _salida(proc)
    if not salida.strip():
        # Con --log-file rclone manda todo al archivo y deja stdout/stderr
        # vacíos. Sin este fallback el drive.log queda con "OK exit=0" sin
        # decir cuánto subió, que es justamente lo que hace falta mirar.
        salida = _cola(Path(origen) / LOG_RCLONE)
    resumen = _resumen(salida)
    ok = proc.returncode == 0
    if dry_run:
        # En dry-run rclone igual imprime "Transferred: N/N", pero es lo que
        # HARÍA, no lo que subió: mezclarlo con una subida real en el log
        # sería engañoso (se verificó justamente eso el 02/10/2026).
        detalle = "dry-run: %s" % (resumen or "sin cambios")
    else:
        detalle = resumen or salida.strip()[-300:]
    _apendar_log(origen, "%s  exit=%d  %s"
                 % ("DRY-RUN" if dry_run else ("OK" if ok else "FALLO"),
                    proc.returncode, detalle))
    if not ok and not resumen:
        # rclone habla por stderr; si no dejó resumen conviene ver qué dijo.
        detalle = salida.strip()[-300:] or ("exit %d" % proc.returncode)
    return {"ok": ok, "estado": "ok" if ok else "fallo-sync",
            "detalle": detalle}


def respaldar_y_subir(origen: Path = BACKUP_DIR, remoto: str = REMOTO_DEFECTO,
                      dry_run: bool = False) -> dict:
    """Copia local con `backup_db.py` y después sube. No lanza.

    Con `dry_run` no se crea copia local: sólo se simula la subida (así
    `--dry-run` no toca nada en ninguna de las dos etapas).
    """
    if dry_run:
        return subir(origen, remoto, dry_run=True)

    try:
        proc = subprocess.run([sys.executable, str(SCRIPT_BACKUP)],
                              cwd=str(BASE_DIR), capture_output=True, text=True,
                              timeout=TIMEOUT_BACKUP, encoding="utf-8",
                              errors="replace")
    except subprocess.TimeoutExpired:
        return {"ok": False, "estado": "timeout-backup",
                "detalle": "backup_db no terminó en %ss" % TIMEOUT_BACKUP}
    except OSError as exc:
        return {"ok": False, "estado": "error-backup", "detalle": str(exc)}

    salida = _salida(proc)
    if proc.returncode == 2:
        # backup_db devuelve 2 cuando la cantidad de mediciones de la copia
        # no coincide con la de origen: sería subir algo a medio escribir.
        _apendar_log(origen, "FALLO  copia inconsistente, no se sube nada")
        return {"ok": False, "estado": "copia-inconsistente",
                "detalle": salida.strip()[-300:]}
    if proc.returncode != 0:
        _apendar_log(origen, "FALLO  backup local exit=%d" % proc.returncode)
        return {"ok": False, "estado": "fallo-backup",
                "detalle": salida.strip()[-300:]}

    return subir(origen, remoto, dry_run=False)


def ejecutar_backup_y_subir() -> None:
    """La tarea de fondo de `POST /api/import`.

    Traga toda excepción: la importación ya se respondió y no tiene que
    enterarse de que Drive está caído o de que falta rclone.
    """
    if not auto():
        return
    try:
        resultado = respaldar_y_subir()
    except Exception as exc:  # noqa: BLE001  (tarea de fondo, nada debe escapar)
        print("[backup] error inesperado: %r" % exc)
        return

    if resultado.get("ok"):
        print("[backup] a Drive: %s" % resultado.get("detalle", "OK"))
    else:
        print("[backup] a Drive NO subio (%s): %s"
              % (resultado.get("estado"), resultado.get("detalle", "")))
