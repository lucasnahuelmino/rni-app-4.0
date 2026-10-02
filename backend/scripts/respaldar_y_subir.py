r"""Respalda `rni.db` en local y sube la carpeta de respaldos a Drive.

    .venv\Scripts\python.exe scripts\respaldar_y_subir.py                # copia y sube
    .venv\Scripts\python.exe scripts\respaldar_y_subir.py --solo-subir   # sin copia nueva
    .venv\Scripts\python.exe scripts\respaldar_y_subir.py --dry-run      # no toca nada: qué subiría
    .venv\Scripts\python.exe scripts\respaldar_y_subir.py --listar       # qué hay local y qué hay en Drive

Es el que corre la tarea programada `RNI - backup diario de rni.db`. El
paso a paso es el mismo que usa la app cuando termina una carga
(`app/services/backup_service.py`), así que no hay dos maneras de hacerlo.

La subida es un `rclone sync` de `BACKUP_DIR` contra el remoto `rni-drive:`
(creado con `rclone config create rni-drive drive root_folder_id=...`) con
`--exclude rni.db`: la carpeta compartida trae un `rni.db` que no generamos
nosotros y lo excluido no se copia ni se borra.

Códigos de salida: `0` todo OK, `1` algo falló, `2` la copia local salió
inconsistente (y por lo tanto no se subió nada).
"""
import argparse
import subprocess
import sys
from pathlib import Path

_aqui = Path(__file__).resolve().parent
sys.path.insert(0, str(_aqui))         # scripts/: backup_db
sys.path.insert(0, str(_aqui.parent))  # backend/: el paquete app

import backup_db  # noqa: E402
from app.services import backup_service  # noqa: E402


def _listar_drive(remoto: str) -> int:
    """Qué hay en la carpeta de Drive, para poder verificar una subida sin
    abrir el navegador."""
    rclone = backup_service.encontrar_rclone()
    if rclone is None:
        print("No encontre rclone.exe.")
        return 1
    print("--- Drive (%s) ---" % remoto)
    try:
        proc = subprocess.run([str(rclone), "lsf", remoto], capture_output=True,
                              text=True, timeout=120, encoding="utf-8",
                              errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        print("No pude listar el Drive: %s" % exc)
        return 1
    print((proc.stdout or "").rstrip())
    if proc.returncode:
        print((proc.stderr or "").strip()[-300:])
    return proc.returncode


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Respalda rni.db y sube la carpeta de respaldos a Google Drive.")
    p.add_argument("--solo-subir", action="store_true",
                   help="no crea una copia local nueva, sólo sube lo que hay")
    p.add_argument("--dry-run", action="store_true",
                   help="no hace nada en ninguna de las dos etapas: muestra qué subiría")
    p.add_argument("--listar", action="store_true",
                   help="qué hay local y qué hay en Drive, y sale")
    p.add_argument("--remoto", default=backup_service.REMOTO_DEFECTO,
                   help="destino de rclone (por defecto %s)"
                        % backup_service.REMOTO_DEFECTO)
    args = p.parse_args(argv)

    origen = backup_db.DESTINO_DEFECTO

    if args.listar:
        print("--- local (%s) ---" % origen)
        backup_db.listar(origen)
        return _listar_drive(args.remoto)

    if not args.solo_subir and not args.dry_run:
        codigo = backup_db.main([])
        if codigo != 0:
            # Una copia mala no se sube: en Drive tendríamos un respaldo que
            # no sirve para restaurar, peor que no tener nada.
            print("Backup local fallo (codigo %d): no se sube nada." % codigo)
            return codigo

    if args.dry_run:
        print("--- dry-run: no se creo copia ni se subio nada ---")

    resultado = backup_service.subir(origen, args.remoto, dry_run=args.dry_run)
    print("%s: %s" % ("Subida" if not args.dry_run else "Dry-run",
                      resultado.get("detalle") or resultado.get("estado")))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
