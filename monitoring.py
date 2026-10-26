"""Periodic, bounded SSH collection; immutable samples and configurable retention."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import threading
import time
from discovery import discover
from inventory import ValidationError
from vault import decrypt, encrypt

METRICS_SCRIPT = r'''export LC_ALL=C
printf 'QM_SYSTEM='; uname -s
if test "$(uname -s)" = Linux; then
 printf 'QM_CORES='; getconf _NPROCESSORS_ONLN 2>/dev/null
 printf 'QM_UPTIME='; awk '{print $1}' /proc/uptime
 printf 'QM_LOAD='; awk '{print $1}' /proc/loadavg
 printf 'QM_MEM='; awk '/^MemTotal:/{t=$2}/^MemAvailable:/{a=$2;has=1}/^MemFree:/{f=$2}/^Buffers:/{b=$2}/^Cached:/{c=$2}/^SReclaimable:/{r=$2}/^Shmem:/{s=$2}END{if(!has)a=f+b+c+r-s; print t,a}' /proc/meminfo
 printf 'QM_ROOT='; df -Pk / 2>/dev/null | awk 'NR==2{gsub(/%/,"",$5);print $2,$3,$5}'
 printf 'QM_TEMP='
 for f in /sys/class/thermal/thermal_zone*/temp; do if test -r "$f"; then cat "$f"; break; fi; done
 printf '\n'
 snapshot() {
  printf "QM_TIME$1="; awk '{print $1}' /proc/uptime
  printf "QM_CPU$1="; awk 'NR==1{for(i=2;i<=9;i++)t+=$i;print t,$5+$6}' /proc/stat
  printf "QM_NET$1="; awk -F: '/:/{gsub(/ /,"",$1);if($1!="lo"){sub(/^ +/,"",$2);split($2,a,/ +/);r+=a[1];t+=a[9]}}END{printf "%.0f %.0f\n",r,t}' /proc/net/dev
  printf "QM_IO$1="
  for f in /sys/block/*/stat; do
   case "$f" in /sys/block/loop*|/sys/block/ram*|/sys/block/zram*|/sys/block/dm-*|/sys/block/md*) continue;; esac
   test -r "$f" && awk '{printf "%.0f %.0f\n",$3*512,$7*512}' "$f"
  done | awk '{r+=$1;w+=$2}END{if(NR)printf "%.0f %.0f\n",r,w;else print ""}'
 }
 snapshot 1; sleep 1; snapshot 2
fi
printf '\nQM_END=1\n'
'''


def parse_metrics(output, address):
    values = {}
    for line in output.splitlines():
        if line.startswith('QM_') and '=' in line:
            key, value = line.split('=', 1); values[key[3:]] = value.strip()
    if values.get('END') != '1': raise ValidationError('La consulta de métricas no terminó')
    if values.get('SYSTEM') != 'Linux':
        raise ValidationError('Métricas periódicas disponibles inicialmente para Linux; recolector de esta plataforma pendiente')
    def numbers(key, count=1):
        try:
            result = [float(v) for v in values.get(key, '').split()]
            return result if len(result) == count and all(math.isfinite(v) and v >= 0 for v in result) else None
        except ValueError: return None
    def one(key):
        result = numbers(key); return result[0] if result else None
    result = {'system':'Linux', 'uptime_seconds':one('UPTIME'), 'load_1m':one('LOAD'), 'cpu_cores':one('CORES')}
    start, end = numbers('CPU1', 2), numbers('CPU2', 2)
    if start and end and end[0] > start[0] and 0 <= end[1]-start[1] <= end[0]-start[0]:
        result['cpu_percent'] = round(100 * (1-(end[1]-start[1])/(end[0]-start[0])), 1)
    mem = numbers('MEM', 2)
    if mem and mem[0] > 0 and mem[1] <= mem[0]:
        result.update(ram_total_gb=round(mem[0]/1024**2, 2), memory_percent=round(100*(mem[0]-mem[1])/mem[0], 1))
    disk = numbers('ROOT', 3)
    if disk and disk[0] > 0 and disk[1] <= disk[0] and disk[2] <= 100:
        result.update(disk_total_gb=round(disk[0]/1024**2, 2), disk_percent=disk[2], disk_scope='/')
    temperature = one('TEMP')
    if temperature and 1000 <= temperature <= 150000: result['temperature_c'] = round(temperature/1000, 1)
    t1, t2 = one('TIME1'), one('TIME2')
    for kind, names in [('NET', ('net_rx','net_tx')), ('IO', ('io_read','io_write'))]:
        first, last = numbers(kind+'1', 2), numbers(kind+'2', 2)
        if last:
            for name, total in zip(names, last): result[name+'_bytes'] = total
        if first and last and t1 is not None and t2 is not None and t2 > t1:
            for name, before, after in zip(names, first, last):
                if after >= before: result[name+'_bps'] = round((after-before)/(t2-t1), 1)
    if not any(key in result for key in ('cpu_percent','memory_percent','disk_percent')):
        raise ValidationError('SSH respondió, pero no se pudieron leer CPU, RAM ni disco')
    return {'data': result}


def configure(c, server_id, ssh, key_path):
    old = c.execute('SELECT * FROM server_credentials WHERE server_id=?', (server_id,)).fetchone()
    if ssh is None:
        if old: c.execute('UPDATE server_credentials SET revision=revision+1,next_due=0 WHERE server_id=?', (server_id,))
        return
    if not isinstance(ssh, dict): raise ValidationError('Configuración SSH inválida')
    username, password, port = ssh.get('username',''), ssh.get('password',''), ssh.get('port',22)
    enabled = ssh.get('enabled', True)
    if not isinstance(username,str) or not isinstance(password,str) or type(enabled) is not bool:
        raise ValidationError('Configuración SSH inválida')
    username = username.strip()
    if not old and not username and not password: return
    if not username or len(username)>200 or len(password)>1024 or type(port) is not int or not 1 <= port <= 65535:
        raise ValidationError('Indica usuario SSH y puerto entre 1 y 65535')
    if not password and (not old or old['username'] != username):
        raise ValidationError('Introduce la contraseña al crear o cambiar el usuario SSH')
    secret = encrypt(password, key_path) if password else old['secret']
    c.execute('''INSERT INTO server_credentials(server_id,username,port,secret,enabled,next_due,revision)
        VALUES(?,?,?,?,?,0,1) ON CONFLICT(server_id) DO UPDATE SET username=excluded.username,
        port=excluded.port,secret=excluded.secret,enabled=excluded.enabled,next_due=0,revision=server_credentials.revision+1''',
        (server_id,username,port,secret,int(enabled)))


def connection(c, server_id, key_path):
    row = c.execute('''SELECT s.ip,c.* FROM servers s JOIN server_credentials c ON c.server_id=s.id
        WHERE s.id=?''', (server_id,)).fetchone()
    if not row: raise ValidationError('Este servidor no tiene credenciales SSH guardadas')
    return {'ip':row['ip'], 'port':row['port'], 'username':row['username'], 'password':decrypt(row['secret'],key_path)}


def dashboard(c):
    interval = c.execute('SELECT interval_minutes FROM settings WHERE id=1').fetchone()[0]
    rows = c.execute('''SELECT s.id,s.name,s.ip,s.os,s.cpu,s.ram_gb,s.disk_gb,s.group_name,s.application,
        c.enabled,c.server_id AS configured,m.collected_at,m.status,m.error,m.payload
        FROM servers s LEFT JOIN server_credentials c ON c.server_id=s.id
        LEFT JOIN metrics m ON m.id=(SELECT id FROM metrics WHERE server_id=s.id ORDER BY id DESC LIMIT 1)
        ORDER BY s.name COLLATE NOCASE''').fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        item['metrics']=json.loads(item.pop('payload') or '{}')
        item['state']='unconfigured' if not item['configured'] else 'paused' if not item['enabled'] else 'pending' if not item['collected_at'] else 'stale' if time.time()-item['collected_at'] > max(120,interval*120) else item['status']
        item.pop('configured'); result.append(item)
    return {'servers':result,'interval_minutes':interval,'now':time.time()}


class Monitor:
    def __init__(self, db, data_dir, key_path):
        self.db=db; self.data_dir=data_dir; self.key_path=key_path
        self.wake=threading.Event(); self.stop=threading.Event(); self.inflight=set()
        self.pool=ThreadPoolExecutor(max_workers=6,thread_name_prefix='qinv-ssh')
        self.lock=threading.Lock(); self.last_cleanup=0
    def start(self):
        self.thread=threading.Thread(target=self.run,name='qinv-monitor',daemon=True); self.thread.start()
    def run(self):
        while not self.stop.is_set():
            try: self.tick()
            except Exception:
                import logging
                logging.exception('Error en el programador de métricas')
            self.wake.wait(5); self.wake.clear()
    def tick(self):
        now=time.time()
        with self.lock:
            capacity=6-len(self.inflight)
            with self.db() as c:
                if now-self.last_cleanup>3600:
                    days=c.execute('SELECT retention_days FROM settings WHERE id=1').fetchone()[0]
                    c.execute('DELETE FROM metrics WHERE collected_at<?',(now-days*86400,))
                    self.last_cleanup=now
                rows=c.execute('''SELECT s.id,s.ip,c.revision FROM servers s JOIN server_credentials c ON c.server_id=s.id
                    WHERE c.enabled=1 AND c.next_due<=? ORDER BY c.next_due,s.id LIMIT ?''',(now,max(0,capacity))).fetchall()
                claimed=[]
                for row in rows:
                    if row['id'] in self.inflight: continue
                    c.execute('UPDATE server_credentials SET next_due=? WHERE server_id=?',(now+120,row['id']))
                    self.inflight.add(row['id']); claimed.append(row)
                c.commit()
            for row in claimed: self.pool.submit(self.collect,dict(row))
    def collect(self, row):
        payload={}; error=None; status='error'; credentials=None
        try:
            with self.db() as c: credentials=connection(c,row['id'],self.key_path)
            result=discover(credentials,self.data_dir/'ssh_known_hosts',script=METRICS_SCRIPT,parser=parse_metrics)
            if result.get('host_confirmation'):
                raise ValidationError('Verifica la huella SSH con Conectar y descubrir antes de activar la recolección')
            payload=result['data']; status='online'
        except ValidationError as e: error=str(e)
        except Exception: error='Error interno al consultar métricas; revisa el servicio y la clave de cifrado'
        finally:
            if credentials: credentials['password']=''
            try:
                with self.db() as c:
                    current=c.execute('SELECT c.revision,c.enabled,s.ip FROM server_credentials c JOIN servers s ON s.id=c.server_id WHERE c.server_id=?',(row['id'],)).fetchone()
                    if current and current['enabled'] and current['revision']==row['revision'] and current['ip']==row['ip']:
                        interval=c.execute('SELECT interval_minutes FROM settings WHERE id=1').fetchone()[0]
                        c.execute('INSERT INTO metrics(server_id,collected_at,status,error,payload) VALUES(?,?,?,?,?)',
                            (row['id'],time.time(),status,error,json.dumps(payload)))
                        c.execute('UPDATE server_credentials SET next_due=? WHERE server_id=?',(time.time()+interval*60,row['id']))
            finally:
                with self.lock: self.inflight.discard(row['id'])
                self.wake.set()
    def close(self):
        self.stop.set(); self.wake.set(); self.thread.join(timeout=6); self.pool.shutdown(wait=True)
