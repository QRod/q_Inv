"""Authenticated encryption for SSH secrets. The master key lives outside SQLite."""
import os
from pathlib import Path
import stat
from cryptography.fernet import Fernet, InvalidToken
from inventory import ValidationError


def load_key(path, *, allow_create=False):
    path = Path(path)
    if not path.exists():
        if not allow_create:
            raise RuntimeError('Falta la clave maestra SSH; restaura su respaldo antes de iniciar')
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream: stream.write(Fernet.generate_key())
        except FileExistsError: pass
    mode = stat.S_IMODE(path.stat().st_mode)
    credential_dir = os.environ.get('CREDENTIALS_DIRECTORY')
    managed = (credential_dir and path.resolve().parent == Path(credential_dir).resolve()
               and mode == 0o440 and not stat.S_IMODE(path.parent.stat().st_mode) & 0o027)
    if mode not in (0o600, 0o400) and not managed:
        raise RuntimeError('La clave SSH requiere permisos 600/400 o una credencial protegida de systemd')
    return Fernet(path.read_bytes().strip())


def encrypt(password, key_path):
    return load_key(key_path).encrypt(password.encode()).decode()


def decrypt(token, key_path):
    try: return load_key(key_path).decrypt(token.encode()).decode()
    except InvalidToken: raise ValidationError('No se pudo descifrar la credencial; revisa la clave maestra SSH')
