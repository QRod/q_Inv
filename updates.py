"""Explicit, administrator-only release checks. Never executes downloaded code."""
import json
import os
from pathlib import Path
import re
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from inventory import ValidationError

API='https://api.github.com/repos/QRod/q_Inv/releases/latest'
VERSION_RE=re.compile(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z')

class UpdateError(ValidationError):pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def version(value):
    match=VERSION_RE.fullmatch(value) if isinstance(value,str) else None
    if not match or len(value)>40:raise UpdateError('La versión publicada no tiene un formato compatible')
    return tuple(int(part) for part in match.groups())


def installed(root):
    try:
        tag=(Path(root)/'VERSION').read_text().strip();version(tag);return tag
    except (OSError,UnicodeError,UpdateError):return None


def check(root):
    if os.environ.get('QINV_UPDATE_CHECKS','1')=='0':raise UpdateError('La consulta de actualizaciones está deshabilitada por la administración')
    request=Request(API,headers={'Accept':'application/vnd.github+json','User-Agent':'q-Inv-release-check','X-GitHub-Api-Version':'2026-03-10'})
    try:
        with build_opener(NoRedirect()).open(request,timeout=8) as response:
            raw=response.read(512*1024+1)
        if len(raw)>512*1024:raise UpdateError('La respuesta de actualizaciones excede el límite permitido')
        release=json.loads(raw)
    except HTTPError as error:
        if error.code in (403,429):raise UpdateError('GitHub limitó las consultas. Espera y vuelve a intentarlo.') from error
        raise UpdateError('No se pudo consultar una publicación estable de GitHub. Inténtalo de nuevo.') from error
    except (URLError,TimeoutError,OSError,UnicodeError,json.JSONDecodeError) as error:raise UpdateError('No se pudo consultar GitHub. Revisa la conexión o el proxy corporativo e inténtalo de nuevo.') from error
    if not isinstance(release,dict) or release.get('draft') is not False or release.get('prerelease') is not False:raise UpdateError('No hay una publicación estable válida disponible')
    latest=release.get('tag_name');new_version=version(latest);latest='v'+'.'.join(map(str,new_version))
    assets=release.get('assets',[])
    names={asset.get('name') for asset in assets if isinstance(asset,dict) and isinstance(asset.get('name'),str)} if isinstance(assets,list) else set()
    if not {'q-inv-'+latest+'.tar.gz','SHA256SUMS','install.sh'}<=names:raise UpdateError('La publicación todavía no contiene todos los archivos de instalación')
    current=installed(root)
    available=new_version>version(current) if current else None
    return {'installed':current,'latest':latest,'available':available,
            'release_url':'https://github.com/QRod/q_Inv/releases/tag/'+latest,
            'backup_command':'sudo q-inv-admin --backup /var/backups/q-inv/manual-$(date +%Y%m%d-%H%M%S)',
            'update_command':f'curl -fsSL https://raw.githubusercontent.com/QRod/q_Inv/{latest}/install.sh -o q-inv-install.sh\nless q-inv-install.sh\nsudo bash q-inv-install.sh --version {latest}' if available else None}
