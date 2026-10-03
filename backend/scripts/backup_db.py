"""Backup consistente de la base rni.db.

    python scripts/backup_db.py                     # respalda y limpia los viejos
    python scripts/backup_db.py --listar            # qué hay respaldado
    python scripts/backup_db.py --destino D:\\respaldos --retener 20
    python scripts/backup_db.py --origen otro/ruta/rni.db --sin-limpiar

Por qué no alcanza con copiar el archivo: SQLite escribe la base en medio de
cada transacción, así que un "copiar y pegar" en caliente puede guardarte un
archivo a medio escribir que no sirve para restaurar nada. `Connection.backup()`
pagina la copia desde la propia base con el mismo mecanismo que usa `.dump`,
de modo que el resultado queda consistente aunque la aplicación esté
escribiendo en ese momento (se puede correr con uvicorn arriba).

El destino queda FUERA del repo a propósito: `data/` está en .gitignore, así
que un respaldo adentro de esa carpeta se caería junto con lo que queremos
resguardar — era exactamente lo que pasaba con `rni_lote6_backup.db`, que
vivía en backend/data/ al lado de la base.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# para que "python scripts/backup_db.py" desde backend/ encuentre el paquete app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import BACKUP_DIR, DB_PATH  # noqa: E402  (una sola fuente de verdad)

# El nombre lo conservan restore_db.py y el CLI: es la misma ruta que
# config.BACKUP_DIR, que es donde también la mira backup_service para subirla.
DESTINO_DEFECTO = BACKUP_DIR
RETENCION_DEFECTO = 10
PREFIJO = "rni_"
LOG = "backup.log"


def _mediciones(conn: sqlite3.Connection) -> int | None:
    """Filas de la tabla principal, para poder comparar origen y copia.
    Best effort: si el esquema cambia, se omite el dato y no se rompe."""
    try:
        return conn.execute("SELECT COUNT(*) FROM mediciones").fetchone()[0]
    except sqlite3.Error:
        return None


def verificar(ruta: Path) -> str:
    """Abre la copia y le pregunta a SQLite si está sana.

    Un backup que no se pudo abrir no es un backup: mejor fallar acá que
    descubrirlo el día que hace falta restaurar.
    """
    try:
        conn = sqlite3.connect(str(ruta))
    except sqlite3.Error as e:
        raise SystemExit("FALLO al abrir la copia %s: %s" % (ruta, e))
    try:
        filas = conn.execute("PRAGMA integrity_check").fetchall()
        if not filas or filas[0][0].lower() != "ok":
            raise SystemExit("FALLO integrity_check en %s: %s"
                             % (ruta, [f[0] for f in filas]))
        return _mediciones(conn)
    finally:
        conn.close()


def respaldar(origen: Path, destino_dir: Path) -> Path:
    if not origen.exists():
        raise SystemExit("No existe la base de origen: %s" % origen)
    destino_dir.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    salida = destino_dir / (PREFIJO + sello + ".db")
    if salida.exists():
        # dos respaldos en el mismo minuto: no pisar el primero
        salida = destino_dir / (PREFIJO + sello + "_%d.db" % os.getpid())

    origen_conn = sqlite3.connect(str(origen))
    destino_conn = sqlite3.connect(str(salida))
    try:
        origen_conn.backup(destino_conn)
        # La base vive en WAL y `backup()` le copia el encabezado entero a la
        # copia, así que el respaldo nacería en WAL: un archivo con su
        # diario en `*-wal` aparte. `restore_db` restaura con un
        # `shutil.copy2` crudo y las copias se arrastran a mano, así que un
        # `-wal` que no viaje con el `.db` daría una base a medias.
        # Volviendo a DELETE cada respaldo queda autocontenido en un archivo.
        destino_conn.commit()
        destino_conn.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.Error:
        if salida.exists():
            salida.unlink()  # no dejar una copia incompleta dando vueltas
        raise
    finally:
        destino_conn.close()
        origen_conn.close()
    return salida


def limpiar(destino_dir: Path, retener: int) -> list[Path]:
    viejos = sorted(destino_dir.glob(PREFIJO + "*.db"),
                    key=lambda p: p.stat().st_mtime)
    sobran = len(viejos) - retener
    borrados = []
    if sobran > 0:
        for ruta in viejos[:sobran]:
            ruta.unlink()
            borrados.append(ruta)
    return borrados


def listar(destino_dir: Path) -> None:
    copias = sorted(destino_dir.glob(PREFIJO + "*.db"),
                    key=lambda p: p.stat().st_mtime)
    if not copias:
        print("Sin respaldos en %s" % destino_dir)
        return
    total = sum(p.stat().st_size for p in copias)
    for p in copias:
        print("  %s  %6.1f MB  %s"
              % (p.name, p.stat().st_size / 1024 / 1024,
                 datetime.fromtimestamp(p.stat().st_mtime)
                 .strftime("%d/%m/%Y %H:%M")))
    print("  %d copias, %.1f MB en total" % (len(copias), total / 1024 / 1024))


def _log(destino_dir: Path, texto: str) -> None:
    linea = "%s  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), texto)
    try:
        with open(destino_dir / LOG, "a", encoding="utf-8") as fh:
            fh.write(linea)
    except OSError:
        pass  # el log es secundario


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Respaldar rni.db con una copia consistente en caliente.")
    p.add_argument("--origen", type=Path, default=DB_PATH,
                   help="base a respaldar (por defecto la de la app)")
    p.add_argument("--destino", type=Path, default=DESTINO_DEFECTO,
                   help="carpeta de destino, fuera del repo")
    p.add_argument("--retener", type=int, default=RETENCION_DEFECTO,
                   help="cuantas copias conservar (por defecto %d)"
                        % RETENCION_DEFECTO)
    p.add_argument("--sin-limpiar", action="store_true",
                   help="no borra las copias viejas")
    p.add_argument("--listar", action="store_true",
                   help="muestra las copias existentes y sale")
    args = p.parse_args(argv)

    if args.listar:
        listar(args.destino)
        return 0

    print("Origen   : %s" % args.origen)
    print("Destino  : %s" % args.destino)

    filas_origen = verificar(args.origen)
    salida = respaldar(args.origen, args.destino)
    filas_copia = verificar(salida)

    tam = salida.stat().st_size / 1024 / 1024
    mensaje = ("%s  %.1f MB" % (salida.name, tam))
    if filas_origen is not None and filas_origen != filas_copia:
        # sólo puede pasar si alguien escribió entre la copia y la verificación;
        # igual se avisa porque es raro
        mensaje += ("  (mediciones origen=%s copia=%s, reintentar)"
                    % (filas_origen, filas_copia))
        print("AVISO: " + mensaje)
        _log(args.destino, "AVISO " + mensaje)
        return 2

    print("OK      : %s  integrity_check=ok  mediciones=%s"
          % (salida.name, filas_copia))
    _log(args.destino, "OK    " + mensaje)

    if not args.sin_limpiar:
        borrados = limpiar(args.destino, args.retener)
        if borrados:
            print("Retención: borradas %d copias viejas (quedan %d)"
                  % (len(borrados), args.retener))
    return 0


if __name__ == "__main__":
    sys.exit(main())
