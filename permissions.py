"""Local identities and server-group authorization, independent of UI controls."""
import re
import hashlib
import sqlite3
from organization import OrganizationError

ROLES=('admin','operator','reader')

class Forbidden(OrganizationError):
    def __init__(self,message='No tienes permiso para realizar esta operación'):super().__init__(message,403)


def migrate(c):
    columns={r['name'] for r in c.execute('PRAGMA table_info(users)')}
    legacy='role' not in columns
    if legacy:c.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'reader' CHECK(role IN ('admin','operator','reader'))")
    if 'active' not in columns:c.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))')
    if legacy:c.execute("UPDATE users SET role='admin'")
    c.execute('''CREATE TABLE IF NOT EXISTS user_group_access(
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        group_id INTEGER NOT NULL,kind TEXT NOT NULL DEFAULT 'groups' CHECK(kind='groups'),
        PRIMARY KEY(user_id,group_id),FOREIGN KEY(group_id,kind) REFERENCES catalog_entries(id,kind) ON DELETE RESTRICT)''')
    c.execute('CREATE INDEX IF NOT EXISTS user_group_access_group ON user_group_access(group_id,user_id)')


def is_admin(actor):return actor['role']=='admin'

def require_admin(actor):
    if not is_admin(actor):raise Forbidden('Esta operación requiere una cuenta administradora')


def require_write(actor):
    if actor['role'] not in ('admin','operator'):raise Forbidden('La cuenta lectora solo puede consultar información')


def grants(c, actor):
    return {row[0] for row in c.execute('SELECT group_id FROM user_group_access WHERE user_id=?',(actor['user_id'],))}


def visible_ids(c, actor):
    if is_admin(actor):return {row[0] for row in c.execute('SELECT id FROM servers')}
    return {row[0] for row in c.execute('''SELECT DISTINCT sc.server_id FROM server_classification sc
        JOIN user_group_access a ON a.group_id=sc.entry_id AND a.user_id=? WHERE sc.kind='groups' ''',(actor['user_id'],))}


def require_server(c, actor, sid):
    if type(sid) is not int or sid not in visible_ids(c,actor):raise Forbidden('Servidor fuera de tu ámbito de acceso o inexistente')


def require_ids(c, actor, ids):
    if not isinstance(ids,list) or not ids or len(ids)>500 or any(type(sid) is not int for sid in ids):raise OrganizationError('Selección inválida')
    if not set(ids)<=visible_ids(c,actor):raise Forbidden('La selección contiene servidores fuera de tu ámbito')


def catalogs(c,actor):
    import organization
    all_entries=organization.catalogs(c)
    if is_admin(actor):return all_entries
    visible=visible_ids(c,actor);allowed=grants(c,actor)
    counts={}
    for row in c.execute('SELECT server_id,entry_id FROM server_classification'):
        if row['server_id'] in visible:counts[row['entry_id']]=counts.get(row['entry_id'],0)+1
    result={}
    for kind,entries in all_entries.items():
        result[kind]=[dict(entry,server_count=counts.get(entry['id'],0)) for entry in entries
                      if (entry['id'] in allowed if kind=='groups' else entry['id'] in counts)]
    return result


def check_assignment(c,actor,before,after,allowed_catalogs):
    if is_admin(actor):return
    allowed=grants(c,actor)
    old_groups=set((before or {}).get('group_ids',[]));new_groups=set(after['group_ids'])
    if not new_groups&allowed:raise Forbidden('Asigna el servidor al menos a uno de tus grupos autorizados')
    if new_groups-allowed!=old_groups-allowed:raise Forbidden('No puedes añadir ni retirar grupos fuera de tus autorizaciones')
    import organization
    for field,kind in organization.FIELDS.items():
        value=after[field];ids=set(value if isinstance(value,list) else [] if value is None else [value])
        old=(before or {}).get(field);old_ids=set(old if isinstance(old,list) else [] if old is None else [old])
        permitted={entry['id'] for entry in allowed_catalogs[kind]}|old_ids
        if not ids<=permitted:raise Forbidden('La clasificación contiene opciones fuera de tu ámbito')


def user_view(c,row):
    return {'id':row['id'],'username':row['username'],'role':row['role'],'active':bool(row['active']),
            'group_ids':[v[0] for v in c.execute('SELECT group_id FROM user_group_access WHERE user_id=? ORDER BY group_id',(row['id'],))]}


def identity(c,session):
    if not session:return {'authenticated':False,'username':None,'csrf':None}
    admin=is_admin(session);assigned=grants(c,session)
    return {'authenticated':True,'username':session['username'],'csrf':session['csrf'],'user_id':session['user_id'],
            'role':session['role'],'context':hashlib.sha256(session['token'].encode()).hexdigest(),'group_ids':sorted(assigned),
            'capabilities':{'write':admin or (session['role']=='operator' and bool(assigned)),'delete':admin,'admin':admin}}


def save_user(c,payload,password_hash):
    import secrets
    if not isinstance(payload,dict):raise OrganizationError('Usuario inválido')
    uid=payload.get('id');old=None
    if uid is not None:
        if type(uid) is not int:raise OrganizationError('Usuario inválido')
        old=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not old:raise OrganizationError('Usuario inexistente',404)
    username=payload.get('username');role=payload.get('role');active=payload.get('active',True);groups=payload.get('group_ids',[]);password=payload.get('password','')
    if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}',username):raise OrganizationError('Usuario: de 1 a 80 letras, números o . _ @ -')
    if role not in ROLES or type(active) is not bool:raise OrganizationError('Rol o estado inválido')
    if not isinstance(groups,list) or len(groups)>500 or any(type(gid) is not int or gid<1 for gid in groups):raise OrganizationError('Grupos inválidos')
    groups=sorted(set(groups))
    for gid in groups:
        if not c.execute("SELECT 1 FROM catalog_entries WHERE id=? AND kind='groups'",(gid,)).fetchone():raise OrganizationError('Selecciona grupos existentes')
    if not isinstance(password,str) or (password and not 12<=len(password)<=1024) or (not old and not password):raise OrganizationError('Contraseña: entre 12 y 1024 caracteres')
    if old and old['role']=='admin' and old['active'] and (role!='admin' or not active):
        if c.execute("SELECT count(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1:raise OrganizationError('No puedes desactivar ni degradar al último administrador activo',409)
    before=user_view(c,old) if old else None
    salt=secrets.token_hex(16) if password else old['salt'];hashed=password_hash(password,salt) if password else old['password']
    try:
        if old:c.execute('UPDATE users SET username=?,role=?,active=?,salt=?,password=? WHERE id=?',(username,role,int(active),salt,hashed,uid))
        else:uid=c.execute('INSERT INTO users(username,role,active,salt,password) VALUES(?,?,?,?,?)',(username,role,int(active),salt,hashed)).lastrowid
    except sqlite3.IntegrityError as error:raise OrganizationError('El nombre de usuario ya existe',409) from error
    c.execute('DELETE FROM user_group_access WHERE user_id=?',(uid,))
    c.executemany('INSERT INTO user_group_access(user_id,group_id) VALUES(?,?)',[(uid,gid) for gid in groups])
    c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
    after=user_view(c,c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
    return {'user':after,'before':before,'password_changed':bool(password)}
