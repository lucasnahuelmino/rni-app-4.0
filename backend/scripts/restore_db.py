"""Restaura la base rni.db desde un respaldo.

    python scripts/restore_db.py --listar            # qué copias hay
    python scripts/restore_db.py --ultimo            # usa la más reciente
    python scripts/restore_db.py --desde C:\\Users\\...\\Backups\\rni\\rni_20260930_2000.db
    python scripts/restore_db.py --ultimo --si       # sin preguntar (para scripts)

Antes de tocar nada verifica la copia con PRAGMA integrity_check: no tiene
ningún sentido reemplazar una base sana por una rota. La base actual NO se
borra, se la mueve a `rni_rota_<fecha>.db` al lado por si querés mirarla
después, y si la copia no se puede escribir se devuelve la original.

Hay que cerrar la aplicación antes: SQLite no deja reemplazar el archivo
mientras alguien lo tenga abierto.
"""
import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

_aqui = Path(__file__).resolve().parent
sys.path.insert(0, str(_aqui))       # carpeta del script (backup_db)
sys.path.insert(0, str(_aqui.parent))  # backend/: el paquete app

from backup_db import DESTINO_DEFECTO, PREFIJO, verificar  # noqa: E402
from app.core.config import DB_PATH                        # noqa: E402


def _copias(destino: Path) -> list[Path]:
    return sorted(destino.glob(PREFIJO + "*.db"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Restaura rni.db desde un respaldo generado por backup_db.")
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--desde", type=Path, help="ruta exacta de la copia")
    grupo.add_argument("--ultimo", action="store_true",
                       help="usa la copia más reciente del destino")
    grupo.add_argument("--listar", action="store_true",
                       help="muestra las copias disponibles y sale")
    p.add_argument("--destino", type=Path, default=DESTINO_DEFECTO,
                   help="carpeta donde viven los respaldos")
    p.add_argument("--si", action="store_true",
                   help="no pregunta confirmación")
    args = p.parse_args(argv)

    if args.listar:
        copias = _copias(args.destino)
        if not copias:
            print("Sin respaldos en %s" % args.destino)
            return 1
        for c in copias:
            print("  %s  %6.1f MB  %s"
                  % (c.name, c.stat().st_size / 1024 / 1024,
                     datetime.fromtimestamp(c.stat().st_mtime)
                     .strftime("%d/%m/%Y %H:%M")))
        return 0

    origen = args.desde
    if args.ultimo:
        copias = _copias(args.destino)
        if not copias:
            print("No hay copias en %s" % args.destino)
            return 1
        origen = copias[0]

    if not origen.exists():
        print("No existe la copia: %s" % origen)
        return 1

    print("Copia    : %s (%.1f MB)"
          % (origen, origen.stat().st_size / 1024 / 1024))
    print("Base     : %s" % DB_PATH)

    # 1) la copia tiene que estar sana antes de tirar lo que hay
    filas = verificar(origen)
    print("Verificada: integrity_check=ok  mediciones=%s" % filas)

    if not args.si:
        respuesta = input("Reemplaza la base actual? [s/N] ").strip().lower()
        if respuesta not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado: no se tocó nada.")
            return 0

    if not DB_PATH.exists():
        print("La base actual no existe; se crea desde la copia.")
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    sello = datetime.now().strftime("%Y%m%d_%H%M")
    reserva = DB_PATH.with_name(
        DB_PATH.stem + "_rota_" + sello + DB_PATH.suffix)

    # 2) la base actual a un lado, sin borrarla
    try:
        os.replace(DB_PATH, reserva)
    except OSError as e:
        print("No pude mover la base actual: %s" % e)
        print("Cerrá la aplicación (uvicorn) y volvé a intentar.")
        return 1

    # 3) copia al lugar de la base, y si falla se devuelve la original
    try:
        shutil.copy2(origen, DB_PATH)
    except OSError as e:
        os.replace(reserva, DB_PATH)
        print("No pude escribir la copia (%s); quedó la base original." % e)
        return 1

    # 4) comprobación final sobre la base ya instalada
    try:
        verificar(DB_PATH)
    except SystemExit:
        os.replace(DB_PATH, DB_PATH.with_name(DB_PATH.name + ".falla"))
        os.replace(reserva, DB_PATH)
        print("La copia no pasó la verificación instalada: devuelvo la original.")
        return 1

    print("RESTAURADO. La base que estaba pasó a: %s" % reserva.name)
    print("Arrancá la aplicación de nuevo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
