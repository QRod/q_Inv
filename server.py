import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import re
import sqlite3
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from inventory import FIELDS, ValidationError, validate, parse_rvtools, anonymize
import organization
import deletion
import permissions
import audit_log
import updates
import network_inventory
import history
from discovery import discover
from vault import load_key
from monitoring import Monitor, configure, connection, dashboard

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('QINV_DATA', ROOT / 'data'))
KEY_FILE = Path(os.environ.get('QINV_KEY_FILE', ROOT / 'secrets' / 'credentials.key'))
MONITOR = None

class Database(sqlite3.Connection):
    def __exit__(self, *args):
        try: return super().__exit__(*args)
        finally: self.close()

def db():
    con = sqlite3.connect(DATA / 'inventory.sqlite3', timeout=15, factory=Database)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init():
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, csrf TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS servers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, uuid TEXT, os TEXT, cpu INTEGER, ram_gb REAL, disk_gb REAL, ip TEXT, host TEXT, cluster TEXT, power TEXT, kind TEXT, group_name TEXT, application TEXT, source TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS server_ids(id INTEGER PRIMARY KEY CHECK(id=1),last_id INTEGER NOT NULL);
        INSERT OR IGNORE INTO server_ids SELECT 1,coalesce(max(id),0) FROM servers;
        CREATE TABLE IF NOT EXISTS deletion_previews(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,payload TEXT NOT NULL,signature TEXT NOT NULL,expires REAL NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS server_uuid ON servers(uuid) WHERE uuid != '';
        CREATE TABLE IF NOT EXISTS imports(token TEXT PRIMARY KEY, user_id INTEGER, payload TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), interval_minutes INTEGER, retention_days INTEGER);
        INSERT OR IGNORE INTO settings VALUES(1,5,60);
        CREATE TABLE IF NOT EXISTS server_credentials(server_id INTEGER PRIMARY KEY REFERENCES servers(id) ON DELETE CASCADE, username TEXT NOT NULL, port INTEGER NOT NULL, secret TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, next_due REAL NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY, server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE, collected_at REAL NOT NULL, status TEXT NOT NULL, error TEXT, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS metrics_latest ON metrics(server_id,id DESC);
        CREATE INDEX IF NOT EXISTS metrics_retention ON metrics(collected_at);
        CREATE INDEX IF NOT EXISTS metrics_server_time ON metrics(server_id,collected_at,id);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        organization.migrate(c)
        permissions.migrate(c)
        audit_log.migrate(c)
        network_inventory.migrate(c)
        has_secrets = bool(c.execute('SELECT 1 FROM server_credentials LIMIT 1').fetchone())
    load_key(KEY_FILE, allow_create=not has_secrets)

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def save_server(c, data, source, server_id=None):
    if server_id is None:
        c.execute('UPDATE server_ids SET last_id=max(last_id,coalesce((SELECT max(id) FROM servers),0))+1 WHERE id=1')
        new_id=c.execute('SELECT last_id FROM server_ids WHERE id=1').fetchone()[0]
        c.execute(f"INSERT INTO servers(id,{','.join(FIELDS)},source) VALUES({','.join('?' for _ in range(len(FIELDS)+2))})", [new_id]+[data[k] for k in FIELDS]+[source])
        return new_id
    c.execute(f"UPDATE servers SET {','.join(k+'=?' for k in FIELDS)},source=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", [data[k] for k in FIELDS] + [source, server_id])
    return server_id

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def send(self, status, value, cookie=None):
        raw = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        actor=getattr(self,'request_identity',None)
        self.send_header('X-Qinv-Context',hashlib.sha256(actor['token'].encode()).hexdigest() if actor else '')
        if cookie: self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(raw)
    def session(self, c):
        jar = cookies.SimpleCookie()
        try: jar.load(self.headers.get('Cookie', ''))
        except cookies.CookieError: return None
        token = jar.get('qinv')
        if not token: return None
        row=c.execute('SELECT s.*,u.username,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE token=? AND expires>? AND u.active=1', (token.value,time.time())).fetchone()
        return dict(row) if row else None
    def body(self):
        try: length = int(self.headers.get('Content-Length', '0'))
        except ValueError: raise ValidationError('Tamaño inválido')
        if length < 1 or length > 20*1024*1024: raise ValidationError('Tamaño permitido: 1 byte a 20 MB')
        return self.rfile.read(length)
    def denied(self, actor, method, path):
        routes={'/api/servers','/api/dashboard','/api/catalogs','/api/settings','/api/users','/api/audit','/api/discover','/api/metrics/refresh','/api/import/preview','/api/import/commit','/api/organization/preview','/api/organization/commit','/api/servers/delete-preview','/api/servers/delete','/api/updates/check','/api/updates/status'}
        with db() as c:audit_log.record(c,actor,'access.denied',{'method':method,'route':path if path in routes else 'other'},outcome='denied')

    def failed(self, actor, path):
        events={'/api/servers':'servers.save','/api/users':'users.save','/api/settings':'settings.update','/api/catalogs':'catalogs.save','/api/import/preview':'inventory.import.preview','/api/import/commit':'inventory.import','/api/organization/preview':'organization.preview','/api/organization/commit':'organization.bulk','/api/servers/delete-preview':'servers.delete.preview','/api/servers/delete':'servers.delete','/api/discover':'servers.discover','/api/metrics/refresh':'metrics.refresh'}
        if actor and path in events:
            with db() as log:audit_log.record(log,actor,events[path],outcome='failure')

    def do_GET(self):
        path=urlparse(self.path).path;actor=None;self.request_identity=None
        if not path.startswith('/api/'):
            files={'/':'index.html','/app.js':'app.js','/history.js':'history.js','/style.css':'style.css'}
            if path not in files:return self.send(404,{'error':'No encontrado'})
            raw=(ROOT/'static'/files[path]).read_bytes();self.send_response(200)
            self.send_header('Content-Type',{'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/history.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path])
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(raw);return
        try:
            with db() as c:
                c.execute('BEGIN');actor=self.session(c);self.request_identity=actor
                if path=='/api/session':return self.send(200,permissions.identity(c,actor))
                if not actor:return self.send(401,{'error':'Inicia sesión'})
                if path=='/api/servers':
                    visible=permissions.visible_ids(c,actor)
                    rows=organization.hydrate(c,c.execute('SELECT s.*,c.username AS ssh_username,c.port AS ssh_port,c.enabled AS monitoring_enabled,CASE WHEN c.server_id IS NULL THEN 0 ELSE 1 END AS credentials_configured FROM servers s LEFT JOIN server_credentials c ON c.server_id=s.id ORDER BY s.name COLLATE NOCASE').fetchall())
                    rows=network_inventory.hydrate(c,[row for row in rows if row['id'] in visible])
                    if actor['role']=='reader':
                        for row in rows:row.pop('ssh_username',None);row.pop('ssh_port',None)
                    return self.send(200,rows)
                match=re.fullmatch(r'/api/servers/([1-9][0-9]*)(/history)?',path)
                if match:
                    sid=int(match[1]);permissions.require_server(c,actor,sid)
                    if match[2]:return self.send(200,history.read(c,sid,parse_qs(urlparse(self.path).query,keep_blank_values=True)))
                    row=c.execute('SELECT * FROM servers WHERE id=?',(sid,)).fetchone()
                    detail=network_inventory.hydrate(c,organization.hydrate(c,[row]))[0]
                    return self.send(200,{'server':detail,'current':dashboard(c,sid)['servers'][0]})
                if path=='/api/catalogs':return self.send(200,permissions.catalogs(c,actor))
                if path=='/api/dashboard':
                    result=dashboard(c);visible=permissions.visible_ids(c,actor)
                    result['servers']=network_inventory.hydrate(c,organization.hydrate(c,[row for row in result['servers'] if row['id'] in visible]));return self.send(200,result)
                permissions.require_admin(actor)
                if path=='/api/settings':return self.send(200,dict(c.execute('SELECT * FROM settings WHERE id=1').fetchone()))
                if path=='/api/users':return self.send(200,{'users':[permissions.user_view(c,row) for row in c.execute('SELECT * FROM users ORDER BY username COLLATE NOCASE')]})
                if path=='/api/audit':return self.send(200,audit_log.page(c,parse_qs(urlparse(self.path).query)))
                if path.startswith('/api/audit/'):
                    try:event_id=int(path.rsplit('/',1)[1])
                    except ValueError:raise ValidationError('Registro inválido')
                    result=audit_log.detail(c,event_id)
                    return self.send(200,result) if result else self.send(404,{'error':'Registro no encontrado'})
                if path=='/api/updates/status':return self.send(200,{'installed':updates.installed(ROOT),'checks_enabled':os.environ.get('QINV_UPDATE_CHECKS','1')!='0'})
            return self.send(404,{'error':'No encontrado'})
        except permissions.Forbidden as error:
            self.denied(actor,'GET',path);self.send(403,{'error':str(error)})
        except ValidationError as error:self.send(400,{'error':str(error)})
        except Exception:
            import traceback
            traceback.print_exc();self.send(500,{'error':'Error interno; consulta el registro del servidor'})

    def do_POST(self):
        path=urlparse(self.path).path;actor=None;self.request_identity=None
        try:
            with db() as c:
                # Re-read identity after taking the write lock: revocation cannot
                # race an inventory mutation or confirmation of an old preview.
                c.execute('BEGIN IMMEDIATE');actor=self.session(c);self.request_identity=actor
                if path=='/api/login':
                    if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValidationError('Se requiere JSON')
                    d=json.loads(self.body())
                    if not isinstance(d,dict):raise ValidationError('Solicitud inválida')
                    user=c.execute('SELECT * FROM users WHERE username=?',(str(d.get('username','')),)).fetchone()
                    check=password_hash(str(d.get('password',''))[:1024],user['salt'] if user else '00'*16)
                    if not user or not user['active'] or not hmac.compare_digest(check,user['password']):
                        audit_log.record(c,user['id'] if user else None,'auth.login',outcome='failure');c.commit();time.sleep(.4)
                        return self.send(401,{'error':'Credenciales incorrectas'})
                    token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
                    c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token,user['id'],csrf,time.time()+8*3600))
                    audit_log.record(c,user['id'],'auth.login');c.commit()
                    secure='; Secure' if os.environ.get('QINV_SECURE_COOKIE')=='1' else ''
                    return self.send(200,{'csrf':csrf,'username':user['username']},f'qinv={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}')
                if not actor:return self.send(401,{'error':'Inicia sesión'})
                supplied=self.headers.get('X-CSRF-Token','')
                if not supplied.isascii() or not hmac.compare_digest(supplied,actor['csrf']):raise permissions.Forbidden('Sesión inválida; recarga la página')
                if path=='/api/logout':
                    c.execute('DELETE FROM sessions WHERE token=?',(actor['token'],));audit_log.record(c,actor,'auth.logout');c.commit()
                    return self.send(200,{},'qinv=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                admin_paths={'/api/users','/api/catalogs','/api/settings','/api/import/preview','/api/import/commit','/api/servers/delete-preview','/api/servers/delete','/api/updates/check'}
                if path in admin_paths:permissions.require_admin(actor)
                else:permissions.require_write(actor)
                if path=='/api/import/preview':
                    records,errors=parse_rvtools(self.body())
                    for item in records:
                        old=c.execute('SELECT s.id,s.ip,c.server_id AS configured FROM servers s LEFT JOIN server_credentials c ON c.server_id=s.id WHERE s.uuid=?',(item['data']['uuid'],)).fetchone()
                        item['action']='update' if old else 'create'
                        item['connection_ip']=old['ip'] if old and old['configured'] else item['data']['ip']
                        item['connection_ip_preserved']=bool(old and old['configured'] and old['ip']!=item['data']['ip'])
                    token=secrets.token_urlsafe(32);c.execute('DELETE FROM imports WHERE expires<?',(time.time(),))
                    c.execute('INSERT INTO imports VALUES(?,?,?,?)',(token,actor['user_id'],json.dumps({'records':records,'errors':errors}),time.time()+1800))
                    audit_log.record(c,actor,'inventory.import.preview',{'records':len(records),'errors':len(errors)});c.commit()
                    return self.send(200,{'token':token,'records':records,'errors':errors})
                d=json.loads(self.body())
                if not isinstance(d,dict):raise ValidationError('Solicitud inválida')
                for field in ('id','server_id'):
                    if d.get(field) is not None and (type(d[field]) is not int or d[field]<1):raise ValidationError('Identificador inválido')
                if 'token' in d and (not isinstance(d['token'],str) or len(d['token'])>200):raise ValidationError('Confirmación inválida')
                if path=='/api/users':
                    result=permissions.save_user(c,d,password_hash)
                    audit_log.record(c,actor,'users.update' if result['before'] else 'users.create',{'before':result['before'],'after':result['user'],'password_changed':result['password_changed']},target_type='user',target_id=result['user']['id'])
                    c.commit();return self.send(200,{'user':result['user'],'session_revoked':result['user']['id']==actor['user_id']})
                if path in ('/api/servers/delete-preview','/api/servers/delete'):
                    result=deletion.preview(c,actor['user_id'],d) if path.endswith('delete-preview') else deletion.commit(c,actor['user_id'],d)
                    c.commit();return self.send(200,result)
                if path=='/api/catalogs':
                    old=c.execute('SELECT id,kind,name,description,contact FROM catalog_entries WHERE id=?',(d.get('id'),)).fetchone()
                    if d.get('action')=='delete' and d.get('kind')=='groups' and c.execute('SELECT 1 FROM user_group_access WHERE group_id=?',(d.get('id'),)).fetchone():raise organization.OrganizationError('El grupo autoriza usuarios; retira esas autorizaciones antes de eliminarlo',409)
                    result=organization.catalog_command(c,d);after=c.execute('SELECT id,kind,name,description,contact FROM catalog_entries WHERE id=?',(result['id'],)).fetchone()
                    audit_log.record(c,actor,'catalogs.'+('delete' if d.get('action')=='delete' else 'save'),{'before':dict(old) if old else None,'after':dict(after) if after else None},target_type='catalog',target_id=result['id'])
                    c.commit();return self.send(200,result)
                if path in ('/api/organization/preview','/api/organization/commit'):
                    if path.endswith('preview'):payload=d
                    else:
                        pending=c.execute('SELECT payload FROM bulk_previews WHERE token=? AND user_id=? AND expires>?',(d.get('token'),actor['user_id'],time.time())).fetchone()
                        if not pending:raise organization.OrganizationError('Vista previa expirada o ya utilizada',409)
                        payload=json.loads(pending['payload'])
                    permissions.require_ids(c,actor,payload.get('ids'))
                    changes=organization.validate_changes(c,payload.get('changes'));allowed=permissions.catalogs(c,actor)
                    for row in organization.selected_servers(c,payload['ids']):
                        after=dict(row['organization']);after.update(changes);permissions.check_assignment(c,actor,row['organization'],after,allowed)
                    result=organization.preview_bulk(c,actor['user_id'],d) if path.endswith('preview') else organization.commit_bulk(c,actor['user_id'],d.get('token'))
                    if 'catalogs' in result:result['catalogs']=allowed
                    c.commit();return self.send(200,result)
                if path=='/api/discover':
                    if not permissions.is_admin(actor):
                        permissions.require_server(c,actor,d.get('server_id'))
                        address=c.execute('SELECT ip FROM servers WHERE id=?',(d['server_id'],)).fetchone()['ip']
                        if d.get('ip')!=address:raise permissions.Forbidden('Guarda primero la nueva dirección IP del servidor')
                    if not d.get('password') and d.get('server_id'):
                        permissions.require_server(c,actor,d['server_id']);saved=connection(c,d['server_id'],KEY_FILE)
                        if any(d.get(k)!=saved[k] for k in ('ip','port','username')):raise ValidationError('Introduce la contraseña para consultar una IP, puerto o usuario diferente')
                        d['password']=saved['password']
                    elif d.get('server_id') is not None:permissions.require_server(c,actor,d['server_id'])
                    c.commit()
                    try:
                        result=discover(d,DATA/'ssh_known_hosts')
                        with db() as log:audit_log.record(log,actor,'servers.discover',{'host_confirmation_required':bool(result.get('host_confirmation'))},target_type='server',target_id=d.get('server_id'))
                        return self.send(200,result)
                    finally:d['password']=''
                if path=='/api/metrics/refresh':
                    permissions.require_server(c,actor,d.get('id'))
                    updated=c.execute('UPDATE server_credentials SET next_due=0 WHERE server_id=? AND enabled=1',(d['id'],))
                    if not updated.rowcount:raise ValidationError('Configura las credenciales y activa la recolección de este servidor')
                    audit_log.record(c,actor,'metrics.refresh',target_type='server',target_id=d['id']);c.commit()
                    if MONITOR:MONITOR.wake.set()
                    return self.send(200,{'queued':True})
                if path=='/api/import/commit':
                    pending=c.execute('SELECT * FROM imports WHERE token=? AND user_id=? AND expires>?',(d.get('token'),actor['user_id'],time.time())).fetchone()
                    if not pending:raise ValidationError('Vista previa expirada o ya importada')
                    payload=json.loads(pending['payload'])
                    if payload['errors']:raise ValidationError('Corrige las filas inválidas antes de importar')
                    created=updated=0;changes=[]
                    for item in payload['records']:
                        data=item['data'];reported_primary_ip=data['ip'];old=c.execute('SELECT * FROM servers WHERE uuid=?',(data['uuid'],)).fetchone()
                        before=audit_log.server_state(c,old['id']) if old else None
                        if old:
                            data['group_name'],data['application']=old['group_name'],old['application'];updated+=1
                            if c.execute('SELECT 1 FROM server_credentials WHERE server_id=?',(old['id'],)).fetchone():data['ip']=old['ip']
                        else:created+=1
                        sid=save_server(c,data,'rvtools',old['id'] if old else None);configure(c,sid,None,KEY_FILE)
                        network_inventory.save(c,sid,data.get('network_interfaces'),reported_primary_ip)
                        changes.append({'id':sid,'before':before,'after':audit_log.server_state(c,sid)})
                    c.execute('DELETE FROM imports WHERE token=?',(d['token'],))
                    for offset in range(0,max(1,len(changes)),100):
                        batch=changes[offset:offset+100]
                        audit_log.record(c,actor,'inventory.import',{'created':created,'updated':updated,'batch':offset//100+1,'ids':[v['id'] for v in batch],'records':batch})
                    c.commit()
                    return self.send(200,{'created':created,'updated':updated})
                if path=='/api/servers':
                    data=validate(d);sid=d.get('id');allowed=permissions.catalogs(c,actor)
                    if sid is not None:permissions.require_server(c,actor,sid)
                    before=audit_log.server_state(c,sid) if sid is not None else None
                    old=c.execute('SELECT * FROM servers WHERE id=?',(sid,)).fetchone() if sid is not None else None
                    sid=save_server(c,data,'manual',sid);organization.save_classification(c,sid,d,old)
                    after=audit_log.server_state(c,sid);permissions.check_assignment(c,actor,(before or {}).get('organization'),after['organization'],allowed)
                    credential_before=c.execute('SELECT username,port,enabled,secret FROM server_credentials WHERE server_id=?',(sid,)).fetchone()
                    ssh=d.get('ssh')
                    if not permissions.is_admin(actor) and old and credential_before:
                        proposed_user=ssh.get('username',credential_before['username']) if isinstance(ssh,dict) else credential_before['username']
                        proposed_port=ssh.get('port',credential_before['port']) if isinstance(ssh,dict) else credential_before['port']
                        changed_target=(before['ip'],credential_before['username'],credential_before['port'])!=(after['ip'],proposed_user,proposed_port)
                        if changed_target and (not isinstance(ssh,dict) or not ssh.get('password')):raise permissions.Forbidden('Cambiar IP, puerto o usuario SSH requiere introducir una contraseña para ese destino')
                    configure(c,sid,ssh,KEY_FILE)
                    credential_after=c.execute('SELECT username,port,enabled,secret FROM server_credentials WHERE server_id=?',(sid,)).fetchone()
                    credential_changed=(tuple(credential_before) if credential_before else None)!=(tuple(credential_after) if credential_after else None)
                    audit_log.record(c,actor,'servers.update' if old else 'servers.create',{'before':before,'after':after,'credentials_changed':credential_changed,'password_changed':bool((d.get('ssh') or {}).get('password'))},target_type='server',target_id=sid);c.commit()
                    if MONITOR:MONITOR.wake.set()
                    return self.send(200,{'ok':True,'id':sid})
                if path=='/api/settings':
                    interval,retention=d.get('interval_minutes'),d.get('retention_days')
                    if type(interval) is not int or type(retention) is not int or not 1<=interval<=1440 or not 1<=retention<=3650:raise ValidationError('Intervalo: 1–1440 minutos; retención: 1–3650 días')
                    before=dict(c.execute('SELECT * FROM settings WHERE id=1').fetchone())
                    c.execute('UPDATE settings SET interval_minutes=?,retention_days=? WHERE id=1',(interval,retention));c.execute('UPDATE server_credentials SET next_due=0 WHERE enabled=1')
                    audit_log.record(c,actor,'settings.update',{'before':before,'after':{'interval_minutes':interval,'retention_days':retention}});c.commit()
                    if MONITOR:MONITOR.wake.set()
                    return self.send(200,{'ok':True})
                if path=='/api/updates/check':
                    c.commit()
                    try:result=updates.check(ROOT)
                    except updates.UpdateError:
                        with db() as log:audit_log.record(log,actor,'updates.check',outcome='failure')
                        raise
                    with db() as log:audit_log.record(log,actor,'updates.check',{'installed':result['installed'],'latest':result['latest'],'available':result['available']})
                    return self.send(200,result)
                return self.send(404,{'error':'No encontrado'})
        except permissions.Forbidden as error:
            self.denied(actor,'POST',path);self.send(403,{'error':str(error)})
        except organization.OrganizationError as error:
            self.failed(actor,path);self.send(error.status,{'error':str(error)})
        except updates.UpdateError as error:self.send(503,{'error':str(error)})
        except sqlite3.IntegrityError:
            self.failed(actor,path);self.send(409,{'error':'El identificador ya existe o está en uso'})
        except (ValidationError,json.JSONDecodeError,TypeError,AttributeError) as error:
            self.failed(actor,path);self.send(400,{'error':str(error)})
        except Exception:
            import traceback
            traceback.print_exc();self.send(500,{'error':'Error interno; consulta el registro del servidor'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--create-user')
    parser.add_argument('--role',choices=permissions.ROLES)
    parser.add_argument('--backup',metavar='DIRECTORIO')
    parser.add_argument('--anonymize',nargs=2,metavar=('ORIGINAL','COPIA'))
    args = parser.parse_args()
    if args.anonymize:
        print(f'Muestra creada: {anonymize(*args.anonymize)} servidores sintéticos. Revisa la copia antes de compartirla.')
    else:
        init()
        if args.backup:
            from backups import create_backup
            try:
                target=create_backup(DATA,KEY_FILE,Path(args.backup))
                with db() as c:audit_log.record(c,None,'system.backup',{'directory':target.name})
                print("Respaldo creado: "+str(target))
            except Exception:
                with db() as c:audit_log.record(c,None,'system.backup',outcome='failure')
                raise
        elif args.create_user:
            import getpass
            pwd = getpass.getpass('Contraseña (mínimo 12 caracteres): ')
            if len(pwd) < 12 or len(pwd) > 1024: raise SystemExit('Contraseña: entre 12 y 1024 caracteres')
            if pwd != getpass.getpass('Confirma contraseña: '): raise SystemExit('Las contraseñas no coinciden')
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                role=args.role or ('admin' if c.execute('SELECT count(*) FROM users').fetchone()[0]==0 else 'reader')
                if c.execute('SELECT count(*) FROM users').fetchone()[0]==0 and role!='admin':raise SystemExit('La primera cuenta debe ser administradora')
                result=permissions.save_user(c,{'username':args.create_user,'role':role,'password':pwd,'active':True,'group_ids':[]},password_hash)
                audit_log.record(c,None,'users.create.cli',{'after':result['user']},target_type='user',target_id=result['user']['id'])
            print('Usuario creado')
        else:
            print(f'q_Inv: http://{args.host}:{args.port}', flush=True)
            MONITOR=Monitor(db,DATA,KEY_FILE)
            MONITOR.start()
            try: ThreadingHTTPServer((args.host,args.port), Handler).serve_forever()
            except KeyboardInterrupt: pass
            finally: MONITOR.close()
