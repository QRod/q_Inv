import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from inventory import FIELDS, ValidationError, validate, parse_rvtools, anonymize
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
        CREATE UNIQUE INDEX IF NOT EXISTS server_uuid ON servers(uuid) WHERE uuid != '';
        CREATE TABLE IF NOT EXISTS imports(token TEXT PRIMARY KEY, user_id INTEGER, payload TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), interval_minutes INTEGER, retention_days INTEGER);
        INSERT OR IGNORE INTO settings VALUES(1,5,60);
        CREATE TABLE IF NOT EXISTS server_credentials(server_id INTEGER PRIMARY KEY REFERENCES servers(id) ON DELETE CASCADE, username TEXT NOT NULL, port INTEGER NOT NULL, secret TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, next_due REAL NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY, server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE, collected_at REAL NOT NULL, status TEXT NOT NULL, error TEXT, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS metrics_latest ON metrics(server_id,id DESC);
        CREATE INDEX IF NOT EXISTS metrics_retention ON metrics(collected_at);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        has_secrets = bool(c.execute('SELECT 1 FROM server_credentials LIMIT 1').fetchone())
    load_key(KEY_FILE, allow_create=not has_secrets)

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def save_server(c, data, source, server_id=None):
    if server_id is None:
        cur = c.execute(f"INSERT INTO servers({','.join(FIELDS)},source) VALUES({','.join('?' for _ in range(len(FIELDS)+1))})", [data[k] for k in FIELDS] + [source])
        return cur.lastrowid
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
        if cookie: self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(raw)
    def session(self, c):
        jar = cookies.SimpleCookie()
        try: jar.load(self.headers.get('Cookie', ''))
        except cookies.CookieError: return None
        token = jar.get('qinv')
        if not token: return None
        return c.execute('SELECT s.*,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE token=? AND expires>?', (token.value,time.time())).fetchone()
    def body(self):
        try: length = int(self.headers.get('Content-Length', '0'))
        except ValueError: raise ValidationError('Tamaño inválido')
        if length < 1 or length > 20*1024*1024: raise ValidationError('Tamaño permitido: 1 byte a 20 MB')
        return self.rfile.read(length)
    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/api/'):
            with db() as c:
                s = self.session(c)
                if path == '/api/session':
                    return self.send(200, {'authenticated': bool(s), 'username': s['username'] if s else None, 'csrf': s['csrf'] if s else None})
                if not s: return self.send(401, {'error':'Inicia sesión'})
                if path == '/api/servers': return self.send(200, [dict(r) for r in c.execute('SELECT s.*,c.username AS ssh_username,c.port AS ssh_port,c.enabled AS monitoring_enabled,CASE WHEN c.server_id IS NULL THEN 0 ELSE 1 END AS credentials_configured FROM servers s LEFT JOIN server_credentials c ON c.server_id=s.id ORDER BY s.name COLLATE NOCASE')])
                if path == '/api/dashboard': return self.send(200, dashboard(c))
                if path == '/api/settings': return self.send(200, dict(c.execute('SELECT * FROM settings WHERE id=1').fetchone()))
            return self.send(404, {'error':'No encontrado'})
        files = {'/':'index.html', '/app.js':'app.js', '/style.css':'style.css'}
        if path not in files: return self.send(404, {'error':'No encontrado'})
        raw = (ROOT/'static'/files[path]).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path])
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(raw)
    def do_POST(self):
        try:
            path = urlparse(self.path).path
            with db() as c:
                s = self.session(c)
                if path == '/api/login':
                    # Only accept same-origin requests. JSON requests cannot be submitted by cross-origin forms.
                    if self.headers.get('Content-Type','').split(';')[0] != 'application/json': raise ValidationError('Se requiere JSON')
                    d = json.loads(self.body())
                    user = c.execute('SELECT * FROM users WHERE username=?', (str(d.get('username','')),)).fetchone()
                    check = password_hash(str(d.get('password',''))[:1024], user['salt'] if user else '00'*16)
                    if not user or not hmac.compare_digest(check,user['password']):
                        time.sleep(0.4)
                        return self.send(401, {'error':'Credenciales incorrectas'})
                    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                    c.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
                    c.execute('INSERT INTO sessions VALUES(?,?,?,?)', (token,user['id'],csrf,time.time()+8*3600))
                    c.commit()
                    secure = '; Secure' if os.environ.get('QINV_SECURE_COOKIE') == '1' else ''
                    return self.send(200, {'csrf':csrf,'username':user['username']}, f'qinv={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}')
                if not s: return self.send(401, {'error':'Inicia sesión'})
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']): return self.send(403, {'error':'Sesión inválida; recarga la página'})
                if path == '/api/logout':
                    c.execute('DELETE FROM sessions WHERE token=?', (s['token'],))
                    c.commit()
                    return self.send(200, {}, 'qinv=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if path == '/api/import/preview':
                    records, errors = parse_rvtools(self.body())
                    for item in records:
                        found = c.execute('SELECT id FROM servers WHERE uuid=?', (item['data']['uuid'],)).fetchone()
                        item['action'] = 'update' if found else 'create'
                    token = secrets.token_urlsafe(32)
                    c.execute('DELETE FROM imports WHERE expires<?', (time.time(),))
                    c.execute('INSERT INTO imports VALUES(?,?,?,?)',(token,s['user_id'],json.dumps({'records':records,'errors':errors}),time.time()+1800))
                    c.commit()
                    return self.send(200, {'token':token,'records':records,'errors':errors})
                d = json.loads(self.body())
                if path == '/api/discover':
                    if not d.get('password') and d.get('server_id'):
                        saved = connection(c,d['server_id'],KEY_FILE)
                        if any(d.get(k) != saved[k] for k in ('ip','port','username')):
                            raise ValidationError('Introduce la contraseña para consultar una IP, puerto o usuario diferente')
                        d['password'] = saved['password']
                    try: return self.send(200, discover(d, DATA / 'ssh_known_hosts'))
                    finally: d['password'] = ''
                if path == '/api/metrics/refresh':
                    server_id=d.get('id')
                    if type(server_id) is not int: raise ValidationError('Servidor inválido')
                    updated=c.execute('UPDATE server_credentials SET next_due=0 WHERE server_id=? AND enabled=1',(server_id,))
                    if not updated.rowcount: raise ValidationError('Configura las credenciales y activa la recolección de este servidor')
                    c.commit()
                    if MONITOR: MONITOR.wake.set()
                    return self.send(200, {'queued':True})
                if path == '/api/import/commit':
                    # Serialize commit with all inventory mutations; preview never authorizes stale overwrites.
                    c.execute('BEGIN IMMEDIATE')
                    pending = c.execute('SELECT * FROM imports WHERE token=? AND user_id=? AND expires>?',(d.get('token'),s['user_id'],time.time())).fetchone()
                    if not pending: raise ValidationError('Vista previa expirada o ya importada')
                    payload = json.loads(pending['payload'])
                    if payload['errors']: raise ValidationError('Corrige las filas inválidas antes de importar')
                    created = updated = 0
                    for item in payload['records']:
                        data = item['data']
                        old = c.execute('SELECT * FROM servers WHERE uuid=?',(data['uuid'],)).fetchone()
                        if old:
                            data['group_name'], data['application'] = old['group_name'], old['application']
                            updated += 1
                        else: created += 1
                        sid=save_server(c,data,'rvtools',old['id'] if old else None)
                        configure(c,sid,None,KEY_FILE)
                    c.execute('DELETE FROM imports WHERE token=?',(d['token'],))
                    c.execute('INSERT INTO audit(user_id,action) VALUES(?,?)',(s['user_id'],f'import: created={created}, updated={updated}'))
                    c.commit()
                    return self.send(200, {'created':created,'updated':updated})
                if path == '/api/servers':
                    data = validate(d)
                    server_id = d.get('id')
                    if server_id is not None and (not isinstance(server_id,int) or not c.execute('SELECT id FROM servers WHERE id=?',(server_id,)).fetchone()): raise ValidationError('Servidor inexistente')
                    sid=save_server(c,data,'manual',server_id)
                    configure(c,sid,d.get('ssh'),KEY_FILE)
                    c.execute('INSERT INTO audit(user_id,action) VALUES(?,?)',(s['user_id'],'server: update' if server_id else 'server: create'))
                    c.commit()
                    if MONITOR: MONITOR.wake.set()
                    return self.send(200, {'ok':True,'id':sid})
                if path == '/api/settings':
                    interval, retention = d.get('interval_minutes'), d.get('retention_days')
                    if type(interval) is not int or type(retention) is not int or not 1 <= interval <= 1440 or not 1 <= retention <= 3650: raise ValidationError('Intervalo: 1–1440 minutos; retención: 1–3650 días')
                    c.execute('UPDATE settings SET interval_minutes=?,retention_days=? WHERE id=1',(interval,retention))
                    c.execute('UPDATE server_credentials SET next_due=0 WHERE enabled=1')
                    c.commit()
                    if MONITOR: MONITOR.wake.set()
                    return self.send(200, {'ok':True})
                return self.send(404, {'error':'No encontrado'})
        except sqlite3.IntegrityError: self.send(409, {'error':'El UUID ya pertenece a otro servidor'})
        except (ValidationError, json.JSONDecodeError, TypeError, AttributeError) as e: self.send(400, {'error':str(e)})
        except Exception:
            import traceback
            traceback.print_exc()
            self.send(500, {'error':'Error interno; consulta el registro del servidor'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--create-user')
    parser.add_argument('--anonymize',nargs=2,metavar=('ORIGINAL','COPIA'))
    args = parser.parse_args()
    if args.anonymize:
        print(f'Muestra creada: {anonymize(*args.anonymize)} servidores sintéticos. Revisa la copia antes de compartirla.')
    else:
        init()
        if args.create_user:
            import getpass
            pwd = getpass.getpass('Contraseña (mínimo 12 caracteres): ')
            if len(pwd) < 12 or len(pwd) > 1024: raise SystemExit('Contraseña: entre 12 y 1024 caracteres')
            if pwd != getpass.getpass('Confirma contraseña: '): raise SystemExit('Las contraseñas no coinciden')
            salt = secrets.token_hex(16)
            with db() as c: c.execute('INSERT INTO users(username,salt,password) VALUES(?,?,?)',(args.create_user,salt,password_hash(pwd,salt)))
            print('Usuario creado')
        else:
            print(f'q_Inv: http://{args.host}:{args.port}', flush=True)
            MONITOR=Monitor(db,DATA,KEY_FILE)
            MONITOR.start()
            try: ThreadingHTTPServer((args.host,args.port), Handler).serve_forever()
            except KeyboardInterrupt: pass
            finally: MONITOR.close()
