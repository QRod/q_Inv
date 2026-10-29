"""Local CLI backup. Never callable through the web application."""
from pathlib import Path
import shutil
import sqlite3


def create_backup(data, key, target):
    target=Path(target)
    if not target.is_absolute():raise ValueError('El respaldo requiere una ruta absoluta nueva')
    target.mkdir(mode=0o700,parents=False,exist_ok=False)
    target.chmod(0o700)
    try:
        with sqlite3.connect((Path(data)/'inventory.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as source:
            with sqlite3.connect(target/'database.sqlite3') as destination:source.backup(destination)
        shutil.copyfile(key,target/'credentials.key')
        for name in ['database.sqlite3','credentials.key']:(target/name).chmod(0o600)
        config=Path('/etc/q-inv')
        for name in ['install.env','runtime.env']:
            if (config/name).is_file():shutil.copyfile(config/name,target/name);(target/name).chmod(0o600)
        version=Path(__file__).with_name('VERSION')
        if version.is_file():shutil.copyfile(version,target/'VERSION');(target/'VERSION').chmod(0o600)
        (target/'README.txt').write_text('Respaldo privado de q_Inv. Incluye base y clave para descifrar credenciales. Conservar juntos y con acceso restringido.\nRestaurar con el servicio detenido y permisos de propietario de la instalación.\n')
    except Exception:
        # An incomplete directory is retained for diagnosis, never reused as a backup.
        (target/'INCOMPLETE').write_text('El respaldo no terminó; no usar para restaurar.\n')
        raise
    return target
