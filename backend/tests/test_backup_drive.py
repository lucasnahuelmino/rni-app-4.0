"""Respaldo a Google Drive: el guard de los background tasks de
`POST /api/import`, la búsqueda del binario de rclone y el comando de sync.

Lo que hay que cuidar acá es que nada de esto corra en serio dentro de los
tests (otras pruebas hacen POST /api/import y no pueden subir 102 MB) y,
sobre todo, que el `sync` nunca pueda borrar el `rni.db` que está en la
carpeta compartida de Drive.
"""
from pathlib import Path

from app.services import backup_service, import_service


def _excel_falso() -> tuple:
    """Archivo de importación de mentira: el test reemplaza leer_excel e
    importar_lote, así que el contenido nunca se parsea."""
    return ("muestra.xlsx", b"no-se-lee", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- auto()

def test_auto_esta_encendida_por_defecto(monkeypatch):
    monkeypatch.delenv("RNI_BACKUP_AUTO", raising=False)
    assert backup_service.auto() is True


def test_auto_se_apaga_con_rni_backup_auto_cero(monkeypatch):
    monkeypatch.setenv("RNI_BACKUP_AUTO", "0")
    assert backup_service.auto() is False


def test_ejecutar_backup_no_corr_nada_si_esta_apagado(monkeypatch):
    """Con el guard apagado no se invoca ni rclone ni el script de backup:
    es lo que hace que los tests de POST /api/import no suban nada."""
    monkeypatch.setenv("RNI_BACKUP_AUTO", "0")

    def _no_deberia_correr(*args, **kwargs):
        raise AssertionError("se ejecutó un proceso con el respaldo apagado")

    monkeypatch.setattr(backup_service.subprocess, "run", _no_deberia_correr)
    assert backup_service.ejecutar_backup_y_subir() is None


# ------------------------------------------------------- encontrar rclone

def test_encontrar_rclone_usa_rni_rclone_si_existe(monkeypatch, tmp_path):
    falso = tmp_path / "rclone.exe"
    falso.write_text("", encoding="utf-8")
    monkeypatch.setenv("RNI_RCLONE", str(falso))
    assert backup_service.encontrar_rclone() == falso


def test_encontrar_rclone_devuelve_none_si_no_hay(monkeypatch, tmp_path):
    monkeypatch.setenv("RNI_RCLONE", str(tmp_path / "no-existe.exe"))
    monkeypatch.setenv("PATH", str(tmp_path))          # sin rclone en el PATH
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))  # ni en winget
    monkeypatch.setattr(backup_service.shutil, "which", lambda nombre: None)
    assert backup_service.encontrar_rclone() is None


# ----------------------------------------------------------- el sync

def test_resumen_prefiere_los_bytes_y_no_el_conteo_de_archivos():
    """rclone cierra con dos `Transferred:`: el de bytes y el de archivos
    ("3 / 3"). Para el log sirve el primero."""
    salida = ("Transferred:\t   204.047 MiB / 204.047 MiB, 100%, 3.138 MiB/s, ETA 0s\n"
              "Checks:                 2 / 2, 100%, Listed 7\n"
              "Transferred:            3 / 3, 100%\n")
    assert "MiB" in backup_service._resumen(salida)


def test_resumen_se_lee_del_log_cuando_rclone_no_escribe_en_stdout(monkeypatch, tmp_path):
    """Con --log-file el stdout viene vacío: el detalle del drive.log hay que
    sacarlo del rclone.log (pasó en la primera corrida con el flag nuevo)."""
    (tmp_path / backup_service.LOG_RCLONE).write_text(
        "2026/10/02 13:08:35 INFO  :\n"
        "Transferred:\t   204.047 MiB / 204.047 MiB, 100%, 3.138 MiB/s, ETA 0s\n"
        "Transferred:            3 / 3, 100%\n",
        encoding="utf-8")

    monkeypatch.setattr(backup_service, "encontrar_rclone",
                        lambda: Path("C:/rclone.exe"))

    class _Proc:
        returncode = 0
        stdout = ""     # rclone escribió todo en el log
        stderr = ""

    monkeypatch.setattr(backup_service.subprocess, "run",
                        lambda *a, **k: _Proc())

    resultado = backup_service.subir(tmp_path)

    assert resultado["ok"] is True
    assert "MiB" in resultado["detalle"]


def test_comando_sync_excluye_el_rni_db_de_la_carpeta():
    """La carpeta compartida trae un `rni.db` que no generamos nosotros. El
    exclude es lo único que impide que `sync` lo borre."""
    cmd = backup_service.comando_sync(Path("rclone.exe"), Path("respaldos"),
                                      backup_service.REMOTO_DEFECTO)
    assert cmd[1] == "sync"
    assert cmd[cmd.index("--exclude") + 1] == "rni.db"
    assert "--dry-run" not in cmd


def test_comando_sync_no_sube_su_propio_log():
    """`rclone.log` lo escribe rclone durante la transferencia: si entrara en
    el sync estaría subiendo un archivo que cambia mientras se lee."""
    cmd = backup_service.comando_sync(Path("rclone.exe"), Path("respaldos"),
                                      backup_service.REMOTO_DEFECTO)
    excluidos = [cmd[i + 1] for i, c in enumerate(cmd) if c == "--exclude"]
    assert backup_service.EXCLUIR in excluidos
    assert backup_service.LOG_RCLONE in excluidos
    assert "--log-file" in cmd
    assert "--stats" in cmd   # progreso visible si el sync se corta


def test_comando_sync_dry_run_no_toca_nada():
    cmd = backup_service.comando_sync(Path("rclone.exe"), Path("respaldos"),
                                      backup_service.REMOTO_DEFECTO, dry_run=True)
    assert "--dry-run" in cmd


def test_subir_sin_rclone_no_lanza_nada_y_lo_dice(monkeypatch, tmp_path):
    monkeypatch.setattr(backup_service, "encontrar_rclone", lambda: None)
    monkeypatch.setattr(backup_service.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no correr")))
    (tmp_path / "rni_20261002_1200.db").write_text("x", encoding="utf-8")

    resultado = backup_service.subir(tmp_path)

    assert resultado["ok"] is False
    assert resultado["estado"] == "sin-rclone"


def test_sync_dry_run_no_ejecuta_el_backup_local(monkeypatch, tmp_path):
    """`--dry-run` no debe crear una copia local: simula nada más la subida."""
    comandos = []
    monkeypatch.setattr(backup_service, "encontrar_rclone",
                        lambda: Path("C:/rclone.exe"))

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(backup_service.subprocess, "run",
                        lambda cmd, **kwargs: comandos.append(cmd) or _Proc())

    resultado = backup_service.respaldar_y_subir(tmp_path, dry_run=True)

    assert resultado["ok"] is True
    assert len(comandos) == 1
    assert comandos[0][1] == "sync"          # sólo el sync, nunca backup_db.py
    assert "--dry-run" in comandos[0]


def test_backup_local_fallido_no_se_sube(monkeypatch, tmp_path):
    """Si la copia local salió mal (backup_db devuelve distinto de 0) no se
    sube nada: en Drive tendríamos un respaldo que no sirve para restaurar."""
    (tmp_path / "rni_20261002_1200.db").write_text("x", encoding="utf-8")
    comandos = []

    class _Proc:
        returncode = 1
        stdout = "boom"
        stderr = ""

    monkeypatch.setattr(backup_service.subprocess, "run",
                        lambda cmd, **kwargs: comandos.append(cmd) or _Proc())

    resultado = backup_service.respaldar_y_subir(tmp_path)

    assert resultado["ok"] is False
    assert resultado["estado"] == "fallo-backup"
    assert len(comandos) == 1                 # sólo el backup, ningún sync


def test_copia_inconsistente_no_se_sube(monkeypatch, tmp_path):
    """backup_db sale con 2 cuando la copia tiene otra cantidad de
    mediciones: es la señal de que la copia quedó a medias."""
    (tmp_path / "rni_20261002_1200.db").write_text("x", encoding="utf-8")

    class _Proc:
        returncode = 2
        stdout = "mediciones 100 != 219818"
        stderr = ""

    comandos = []
    monkeypatch.setattr(backup_service.subprocess, "run",
                        lambda cmd, **kwargs: comandos.append(cmd) or _Proc())

    resultado = backup_service.respaldar_y_subir(tmp_path)

    assert resultado["ok"] is False
    assert resultado["estado"] == "copia-inconsistente"
    assert len(comandos) == 1


# ------------------------------------------------------- el hook del POST

def test_import_agenda_el_respaldo(client, monkeypatch):
    """El motivo de todo el lote: después de una carga, el respaldo queda
    agendado para correr cuando se responde (BackgroundTasks)."""
    agendado = []
    monkeypatch.setattr(import_service, "leer_excel", lambda contenido: None)
    monkeypatch.setattr(import_service, "importar_lote",
                        lambda *args, **kwargs: {"registros_nuevos": 3})
    monkeypatch.setattr(backup_service, "ejecutar_backup_y_subir",
                        lambda: agendado.append("corrio"))

    resp = client.post(
        "/api/import",
        data={"ccte": "Salta", "provincia": "Salta", "localidad": "Salta Capital"},
        files={"archivos": _excel_falso()},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"registros_nuevos": 3}
    assert agendado == ["corrio"]
