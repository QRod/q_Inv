"""Offline vendor lifecycle reference. It does not certify patch or contract coverage."""
import calendar
from datetime import date,datetime,timezone
import json,re
from pathlib import Path

CATALOG=json.loads(Path(__file__).with_name('catalogs').joinpath('os-lifecycle.json').read_text())
ENTRIES={(entry['family'],entry['version']):entry for entry in CATALOG['entries']}


def identify(raw):
    text=str(raw or '').strip();lower=text.casefold()
    family='Sin identificar';version=''
    if re.search(r'\b(red\s*hat|rhel)\b',lower):family='RHEL';pattern=r'(?:linux|release|rhel)\s*(?:server\s*)?(\d+(?:\.\d+)?)'
    elif 'windows' in lower:
        family='Windows Server' if 'server' in lower else 'Windows';pattern=r'\b(2008|2012|2016|2019|2022|2025)\b' if family=='Windows Server' else r'(?!)'
    elif re.search(r'\bubuntu\b',lower):
        if re.search(r'ubuntu\s+(mate|budgie|studio|cinnamon|unity|kylin)',lower):return 'Ubuntu (sabor específico)','',False
        family='Ubuntu';pattern=r'\b(\d{2}\.\d{2})(?:\.\d+)?\b'
    elif re.search(r'\baix\b',lower) or re.match(r'7[123]00-',lower):
        family='AIX';pattern=r'\b(7\.[123])\b'
        oslevel=re.search(r'\b(7)([123])00-(\d{2})-',lower)
        if oslevel:return family,f'7.{oslevel[2]} TL{int(oslevel[3])}',False
    elif 'solaris' in lower or 'sunos' in lower:family='Solaris';pattern=r'(?:solaris|sunos)\s*(\d+(?:\.\d+)?)'
    else:
        for name in ('Rocky','AlmaLinux','CentOS','Debian','SUSE','Zorin','Oracle Linux','Fedora'):
            if name.casefold() in lower:
                release=re.search(r'\b(\d+(?:\.\d+)?)\b',lower);return name,release[1] if release else '',False
        if 'linux' in lower:family='Linux'
        return family,'',False
    match=re.search(pattern,lower);version=match[1] if match else ''
    if family=='Solaris' and ('sunos' in lower or version in ('5.10','5.11')):version='10' if version=='5.10' else ''
    if family=='AIX' and version:
        tl=re.search(r'(?:\btl|technology\s+level)\s*([0-9]+)\b',lower)
        if tl:version+=' TL'+str(int(tl[1]))
    ambiguous=bool(re.search(r'or later|o posterior|or higher|other|unknown|desconocido',lower))
    return family,version,ambiguous


def assess(raw,horizon=180,today=None):
    today=today or datetime.now(timezone.utc).date()
    family,version,ambiguous=identify(raw)
    entry=ENTRIES.get((family,version))
    if family=='RHEL' and version:entry=ENTRIES.get((family,version.split('.')[0]))
    result={'family':family,'version':version,'raw':raw or '', 'status':'unknown','end':None,'date_precision':None,'source':None,'basis':None,'reason':'Versión no identificada o sin referencia validada en el catálogo.','reviewed_on':CATALOG['reviewed_on']}
    if ambiguous:result['version']='';result['reason']='La descripción no identifica una versión exacta (por ejemplo, «o posterior»).';return result
    if not entry:return result
    result.update({key:entry[key] for key in ('end','source','basis')})
    if not entry['end']:result['reason']='El fabricante no publica una fecha final para este nivel; requiere verificación.';return result
    end=entry['end'];precision='day' if len(end)==10 else 'month'
    if precision=='month':year,month=map(int,end.split('-'));boundary=date(year,month,calendar.monthrange(year,month)[1])
    else:boundary=date.fromisoformat(end)
    remaining=(boundary-today).days
    result.update(date_precision=precision,days_remaining=remaining,reason=entry['note'])
    # A future major-version deadline cannot certify a RHEL minor release.
    if family=='RHEL' and remaining>=0 and version!='8.10':
        result['reason']='Ciclo principal vigente; verificar el mantenimiento estándar de la versión menor. No se asume EUS/ELS.';return result
    if precision=='month' and (today.year,today.month)==(boundary.year,boundary.month):
        result['reason']='Mes de finalización publicado, sin día exacto. Verificar la fecha efectiva.';return result
    result['status']='expired' if remaining<0 else 'ending' if remaining<=horizon else 'active'
    return result
