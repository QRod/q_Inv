"""Read-only, on-demand SSH inventory. Credentials never enter persistent storage."""
import base64
import hashlib
import ipaddress
from pathlib import Path
import socket
import shlex
import threading
import time
import paramiko
from inventory import ValidationError

SLOTS = threading.BoundedSemaphore(8)
SCRIPT = r'''export LC_ALL=C
printf 'QINV_SYSTEM='; uname -s
printf 'QINV_NAME='; uname -n
case "$(uname -s)" in
Linux)
 printf 'QINV_OS='
 if test -r /etc/os-release; then sed -n 's/^PRETTY_NAME=//p' /etc/os-release | tr -d '"'; elif test -r /etc/redhat-release; then cat /etc/redhat-release; else uname -sr; fi
 printf '\nQINV_CPU='; getconf _NPROCESSORS_ONLN 2>/dev/null || awk '/^processor/{n++}END{print n}' /proc/cpuinfo
 printf 'QINV_RAM_KIB='; awk '/^MemTotal:/{print $2}' /proc/meminfo
 printf 'QINV_UUID='; cat /sys/class/dmi/id/product_uuid 2>/dev/null; printf '\n'
 printf 'QINV_KIND='
 if command -v systemd-detect-virt >/dev/null 2>&1; then v=$(systemd-detect-virt --vm 2>/dev/null); test "$v" != none && test -n "$v" && printf virtual; fi
 printf '\nQINV_DISK_BYTES='
 if command -v lsblk >/dev/null 2>&1; then lsblk -bdn -o SIZE,TYPE 2>/dev/null | awk '$2=="disk"{s+=$1}END{if(s>0)printf "%.0f\n",s}'; else printf '\n'; fi
 ;;
AIX)
 printf 'QINV_OS=AIX '; oslevel -s
 printf 'QINV_CPU='; getconf _NPROCESSORS_ONLN
 printf 'QINV_RAM_KIB='; lsattr -El sys0 -a realmem | awk '{print $2}'
 printf 'QINV_DISK_MIB='; lspv | awk '{print $1}' | while read d; do bootinfo -s "$d" 2>/dev/null; done | awk '{s+=$1}END{if(s>0)print s}'
 ;;
SunOS)
 printf 'QINV_OS='; head -n 1 /etc/release
 printf 'QINV_CPU='; psrinfo | wc -l
 printf 'QINV_RAM_MIB='; prtconf 2>/dev/null | awk '/Memory size:/{print $3;exit}'
 ;;
esac
printf '\nQINV_ROOT_KIB='; df -Pk / 2>/dev/null | awk 'NR==2{print $2}'
printf '\nQINV_END=1\n'
'''

def fingerprint(key):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')

class HostConfirmation(Exception):
    def __init__(self, key): self.key = key

class VerifyHost(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected): self.expected = expected; self.accepted = None
    def missing_host_key(self, client, hostname, key):
        if self.expected != fingerprint(key): raise HostConfirmation(key)
        self.accepted = (hostname, key)
        client.get_host_keys().add(hostname, key.get_name(), key)

def parse_output(output, address):
    values = {}
    for line in output.splitlines():
        if line.startswith('QINV_') and '=' in line:
            k,v = line.split('=',1); values[k[5:]] = v.strip()[:500]
    if values.get('END') != '1': raise ValidationError('El descubrimiento no terminó; revisa el shell y los permisos del usuario')
    system = values.get('SYSTEM')
    if system not in ('Linux','AIX','SunOS'):
        raise ValidationError('Descubrimiento SSH disponible para Linux, AIX y SunOS. Windows requiere un recolector específico.')
    data = {'ip':address}
    warnings = []
    for field,key in [('name','NAME'),('os','OS'),('uuid','UUID'),('kind','KIND')]:
        if values.get(key): data[field]=values[key].lower() if field=='uuid' else values[key]
    def numeric(key, divisor=1):
        try:
            value=float(values.get(key,''))/divisor
            return round(value,3) if 0 < value <= 1e9 else None
        except (ValueError,OverflowError): return None
    cpu=numeric('CPU')
    if cpu and cpu.is_integer(): data['cpu']=int(cpu)
    ram=numeric('RAM_KIB',1024**2) or numeric('RAM_MIB',1024)
    if ram: data['ram_gb']=ram
    disk=numeric('DISK_BYTES',1024**3) or numeric('DISK_MIB',1024)
    disk_basis='Suma de discos visibles al sistema operativo; no equivale necesariamente al espacio provisionado por VMware.'
    if not disk:
        disk=numeric('ROOT_KIB',1024**2)
        disk_basis='Solo capacidad del sistema de archivos raíz; no representa el total de discos.'
    if disk: data['disk_gb']=disk; warnings.append(disk_basis)
    for field,label in [('cpu','CPU'),('ram_gb','RAM'),('disk_gb','disco'),('uuid','UUID')]:
        if field not in data: warnings.append(f'No se pudo obtener {label} con los permisos disponibles; complétalo manualmente.')
    if 'kind' not in data: warnings.append('Confirma manualmente si el servidor es físico o virtual.')
    warnings.append('Grupo, aplicación, host VMware y clúster requieren asignación manual o importación RVTools.')
    return {'data':data,'warnings':warnings}

def discover(payload, known_hosts, *, script=SCRIPT, parser=parse_output):
    if not isinstance(payload,dict): raise ValidationError('Solicitud inválida')
    try:
        address=ipaddress.ip_address(str(payload.get('ip','')).strip())
        if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local:
            raise ValueError()
        port=payload.get('port',22)
        if type(port) is not int or not 1 <= port <= 65535: raise ValueError()
    except ValueError: raise ValidationError('Indica una IP válida y un puerto entre 1 y 65535')
    username=payload.get('username',''); password=payload.get('password','')
    if not isinstance(username,str) or not username.strip() or len(username)>200 or not isinstance(password,str) or not password or len(password)>1024:
        raise ValidationError('Usuario y contraseña SSH requeridos')
    if not SLOTS.acquire(blocking=False): raise ValidationError('Hay varias consultas SSH en curso; intenta de nuevo en unos segundos')
    client=paramiko.SSHClient()
    policy=VerifyHost(payload.get('fingerprint'))
    try:
        known_hosts=Path(known_hosts)
        if known_hosts.exists(): client.load_host_keys(str(known_hosts))
        client.set_missing_host_key_policy(policy)
        client.connect(str(address),port=port,username=username.strip(),password=password,look_for_keys=False,allow_agent=False,timeout=8,banner_timeout=8,auth_timeout=8,channel_timeout=8)
        # Host key persistence is serialized to avoid losing keys during simultaneous discoveries.
        if policy.accepted:
            with HOST_LOCK:
                keys=paramiko.HostKeys()
                if known_hosts.exists(): keys.load(str(known_hosts))
                name,key=policy.accepted; keys.add(name,key.get_name(),key); keys.save(str(known_hosts))
        _,stdout,_=client.exec_command("/bin/sh -c " + shlex.quote(script),timeout=8)
        channel=stdout.channel; output=bytearray(); started=time.monotonic()
        while True:
            if time.monotonic()-started>25: raise ValidationError('El descubrimiento excedió 25 segundos')
            if channel.recv_ready(): output.extend(channel.recv(8192))
            if channel.recv_stderr_ready(): channel.recv_stderr(8192)
            if len(output)>65536: raise ValidationError('La respuesta SSH excede el tamaño permitido')
            if channel.exit_status_ready() and not channel.recv_ready(): break
            time.sleep(.02)
        return parser(output.decode('utf-8',errors='replace'),str(address))
    except HostConfirmation as e:
        return {'host_confirmation':True,'fingerprint':fingerprint(e.key),'ip':str(address),'port':port}
    except paramiko.BadHostKeyException:
        raise ValidationError('La clave SSH del servidor cambió. Verifica el equipo antes de actualizar data/ssh_known_hosts.')
    except paramiko.AuthenticationException:
        raise ValidationError('El servidor rechazó el usuario o la contraseña SSH')
    except (paramiko.SSHException, OSError, socket.timeout):
        raise ValidationError('No se pudo establecer SSH. Revisa IP, puerto, conectividad y compatibilidad del servidor.')
    finally:
        client.close(); SLOTS.release()

HOST_LOCK=threading.Lock()
