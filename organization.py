"""Inventory classification with stable catalog IDs and transactional bulk edits."""
import hashlib
import json
import secrets
import time
import unicodedata
import audit_log
from inventory import ValidationError

KINDS = ('groups', 'applications', 'environments', 'owners', 'tags')
FIELDS = {'group_ids':'groups', 'application_ids':'applications', 'environment_id':'environments', 'owner_id':'owners', 'tag_ids':'tags'}
MULTIPLE = {'groups', 'applications', 'tags'}

class OrganizationError(ValidationError):
    def __init__(self, message, status=400):
        super().__init__(message); self.status=status


def label(value, limit=500):
    if not isinstance(value,str): raise OrganizationError('El nombre debe ser texto')
    value=unicodedata.normalize('NFC',value.strip())
    if not value or len(value)>limit or any(ord(ch)<32 for ch in value):
        raise OrganizationError(f'Nombre requerido, sin saltos de línea y de hasta {limit} caracteres')
    return value


def ensure_entry(c, kind, name, legacy=False):
    name=unicodedata.normalize('NFC',name.strip()) if legacy else label(name)
    old=c.execute('SELECT id FROM catalog_entries WHERE kind=? AND name_key=?',(kind,name.casefold())).fetchone()
    if old: return old['id']
    return c.execute('INSERT INTO catalog_entries(kind,name,name_key) VALUES(?,?,?)',(kind,name,name.casefold())).lastrowid


def migrate(c):
    # Schema and legacy data migration share a transaction; no credentials are touched.
    c.execute('BEGIN IMMEDIATE')
    c.execute('''CREATE TABLE IF NOT EXISTS catalog_entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL CHECK(kind IN ('groups','applications','environments','owners','tags')),
        name TEXT NOT NULL,name_key TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',contact TEXT NOT NULL DEFAULT '',
        UNIQUE(kind,name_key),UNIQUE(id,kind))''')
    c.execute('''CREATE TABLE IF NOT EXISTS server_classification(
        server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
        entry_id INTEGER NOT NULL,kind TEXT NOT NULL,
        PRIMARY KEY(server_id,entry_id),FOREIGN KEY(entry_id,kind) REFERENCES catalog_entries(id,kind) ON DELETE RESTRICT)''')
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS classification_single ON server_classification(server_id,kind) WHERE kind IN ('environments','owners')")
    c.execute('CREATE INDEX IF NOT EXISTS classification_entry ON server_classification(entry_id,server_id)')
    c.execute('CREATE TABLE IF NOT EXISTS organization_migrations(name TEXT PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS bulk_previews(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,
        payload TEXT NOT NULL,signature TEXT NOT NULL,expires REAL NOT NULL)''')
    if not c.execute("SELECT 1 FROM organization_migrations WHERE name='organization-v1'").fetchone():
        for name in ('Producción','Pruebas','Desarrollo'): ensure_entry(c,'environments',name)
        rows=c.execute('SELECT id,group_name,application FROM servers ORDER BY id').fetchall()
        for row in rows:
            for field,kind in [('group_name','groups'),('application','applications')]:
                if row[field] and row[field].strip():
                    eid=ensure_entry(c,kind,row[field],legacy=True)
                    c.execute('INSERT OR IGNORE INTO server_classification VALUES(?,?,?)',(row['id'],eid,kind))
        sync_legacy(c,[row['id'] for row in rows])
        c.execute("INSERT INTO organization_migrations VALUES('organization-v1')")


def catalogs(c):
    result={kind:[] for kind in KINDS}
    for row in c.execute('''SELECT e.*,count(s.server_id) AS server_count FROM catalog_entries e
        LEFT JOIN server_classification s ON s.entry_id=e.id GROUP BY e.id ORDER BY e.name_key,e.id'''):
        item=dict(row);item.pop('name_key');result[item['kind']].append(item)
    return result


def hydrate(c, rows):
    result=[dict(row) for row in rows]
    index={row['id']:row for row in result}
    for row in result:
        row['organization']={field:[] if kind in MULTIPLE else None for field,kind in FIELDS.items()}
        row.update(groups=[],applications=[],tags=[],environment=None,owner=None)
    ids=list(index)
    for offset in range(0,len(ids),400):
        chunk=ids[offset:offset+400]
        for link in c.execute(f'''SELECT s.server_id,e.id,e.kind,e.name,e.contact FROM server_classification s
            JOIN catalog_entries e ON e.id=s.entry_id WHERE s.server_id IN ({','.join('?' for _ in chunk)})
            ORDER BY e.name_key,e.id''',chunk):
            row=index[link['server_id']];kind=link['kind'];entry={'id':link['id'],'name':link['name']}
            field=next(field for field,k in FIELDS.items() if k==kind)
            if kind in MULTIPLE:
                row[kind].append(entry);row['organization'][field].append(entry['id'])
            else:
                name='environment' if kind=='environments' else 'owner'
                if kind=='owners':entry['contact']=link['contact']
                row[name]=entry;row['organization'][field]=entry['id']
    return result


def sync_legacy(c, ids):
    for sid in ids:
        c.execute('''UPDATE servers SET
            group_name=coalesce((SELECT e.name FROM server_classification s JOIN catalog_entries e ON e.id=s.entry_id
                WHERE s.server_id=servers.id AND s.kind='groups' ORDER BY e.name_key,e.id LIMIT 1),''),
            application=coalesce((SELECT e.name FROM server_classification s JOIN catalog_entries e ON e.id=s.entry_id
                WHERE s.server_id=servers.id AND s.kind='applications' ORDER BY e.name_key,e.id LIMIT 1),'')
            WHERE id=?''',(sid,))


def validate_changes(c, changes):
    if not isinstance(changes,dict) or not changes or set(changes)-set(FIELDS):
        raise OrganizationError('Selecciona al menos un campo de organización válido')
    normalized={}
    for field,value in changes.items():
        kind=FIELDS[field]
        values=value if kind in MULTIPLE else [] if value is None else [value]
        if not isinstance(values,list) or len(values)>(30 if kind=='tags' else 50):
            raise OrganizationError('Demasiadas asignaciones o formato inválido')
        if any(type(eid) is not int or eid<1 for eid in values):raise OrganizationError('Identificadores de catálogo inválidos')
        values=sorted(set(values))
        if values:
            found=c.execute(f'SELECT count(*) FROM catalog_entries WHERE kind=? AND id IN ({",".join("?" for _ in values)})',[kind]+values).fetchone()[0]
            if found!=len(values):raise OrganizationError('Una opción ya no existe o pertenece a otro catálogo; recarga la vista')
        normalized[field]=values if kind in MULTIPLE else values[0] if values else None
    return normalized


def assign(c, sid, changes):
    changes=validate_changes(c,changes)
    for field,value in changes.items():
        kind=FIELDS[field]
        c.execute('DELETE FROM server_classification WHERE server_id=? AND kind=?',(sid,kind))
        for eid in value if kind in MULTIPLE else [] if value is None else [value]:
            c.execute('INSERT INTO server_classification VALUES(?,?,?)',(sid,eid,kind))
    sync_legacy(c,[sid])


def save_classification(c, sid, payload, old):
    provided=payload.get('organization')
    if 'organization' in payload and not isinstance(provided,dict):raise OrganizationError('Organización inválida')
    changes=dict(provided or {})
    current=hydrate(c,[{'id':sid}])[0]['organization']
    # A GET/edit/POST legacy client can include an unchanged organization object.
    # Honor its explicit scalar edit only when it did not also change that ID list.
    for legacy,field,kind in [('group_name','group_ids','groups'),('application','application_ids','applications')]:
        if legacy in payload:
            value=str(payload.get(legacy) or '').strip()
            unchanged=field not in changes or changes[field]==current[field]
            if unchanged and (old is None or value!=str(old[legacy] or '')):
                changes[field]=[ensure_entry(c,kind,value)] if value else []
    if changes:assign(c,sid,changes)
    sync_legacy(c,[sid])


def catalog_command(c, payload):
    if not isinstance(payload,dict) or payload.get('kind') not in KINDS:raise OrganizationError('Catálogo inválido')
    kind=payload['kind'];eid=payload.get('id');action=payload.get('action','save')
    old=None
    if eid is not None:
        if type(eid) is not int:raise OrganizationError('Identificador inválido')
        old=c.execute('SELECT * FROM catalog_entries WHERE id=? AND kind=?',(eid,kind)).fetchone()
        if not old:raise OrganizationError('La entrada ya no existe',404)
    if action=='delete':
        if not old:raise OrganizationError('Selecciona una entrada')
        count=c.execute('SELECT count(*) FROM server_classification WHERE entry_id=?',(eid,)).fetchone()[0]
        if count:raise OrganizationError(f'No se puede eliminar: está asignada a {count} servidor(es). Reasígnalos primero.',409)
        c.execute('DELETE FROM catalog_entries WHERE id=?',(eid,));return {'id':eid,'deleted':True}
    if action!='save':raise OrganizationError('Acción inválida')
    name=label(payload.get('name'),64 if kind=='tags' else 500)
    description=payload.get('description','');contact=payload.get('contact','')
    if not isinstance(description,str) or len(description)>500 or not isinstance(contact,str) or len(contact)>320:
        raise OrganizationError('Descripción: máximo 500 caracteres; contacto: máximo 320')
    if kind!='owners':contact=''
    duplicate=c.execute('SELECT id FROM catalog_entries WHERE kind=? AND name_key=?',(kind,name.casefold())).fetchone()
    if duplicate and duplicate['id']!=eid:raise OrganizationError('Ya existe una entrada con ese nombre en el catálogo',409)
    if old:
        c.execute('UPDATE catalog_entries SET name=?,name_key=?,description=?,contact=? WHERE id=?',(name,name.casefold(),description.strip(),contact.strip(),eid))
        affected=[row[0] for row in c.execute('SELECT server_id FROM server_classification WHERE entry_id=?',(eid,))]
        sync_legacy(c,affected)
        for sid in affected:c.execute('UPDATE servers SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(sid,))
    else:
        eid=c.execute('INSERT INTO catalog_entries(kind,name,name_key,description,contact) VALUES(?,?,?,?,?)',(kind,name,name.casefold(),description.strip(),contact.strip())).lastrowid
    return {'id':eid}


def selected_servers(c, ids):
    if not isinstance(ids,list) or not ids or len(ids)>500 or any(type(sid) is not int or sid<1 for sid in ids):
        raise OrganizationError('Selecciona entre 1 y 500 servidores')
    ids=sorted(set(ids));rows=[]
    for offset in range(0,len(ids),400):
        chunk=ids[offset:offset+400]
        rows.extend(c.execute(f'SELECT id,name,ip FROM servers WHERE id IN ({",".join("?" for _ in chunk)}) ORDER BY id',chunk).fetchall())
    if len(rows)!=len(ids):raise OrganizationError('Uno de los servidores ya no existe; recarga la vista',409)
    return hydrate(c,rows)


def fingerprint(c, rows, changes):
    relevant=[]
    for field,values in changes.items():
        ids=values if FIELDS[field] in MULTIPLE else [] if values is None else [values]
        for eid in ids:
            entry=c.execute('SELECT id,kind,name FROM catalog_entries WHERE id=?',(eid,)).fetchone()
            if not entry:raise OrganizationError('El catálogo cambió; vuelve a previsualizar',409)
            relevant.append(dict(entry))
    snapshot={'rows':[{key:row[key] for key in ('id','name','ip','organization','groups','applications','tags','environment','owner')} for row in rows],'targets':relevant}
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def preview_bulk(c, user_id, payload):
    if not isinstance(payload,dict):raise OrganizationError('Solicitud inválida')
    changes=validate_changes(c,payload.get('changes'))
    rows=selected_servers(c,payload.get('ids'));records=[]
    for row in rows:
        before=row['organization'];after=dict(before);after.update(changes)
        differs=any(sorted(before[field])!=sorted(value) if isinstance(value,list) else before[field]!=value for field,value in changes.items())
        records.append({'id':row['id'],'name':row['name'],'ip':row['ip'],'before':before,'after':after,'changed':differs})
    token=secrets.token_urlsafe(32)
    c.execute('DELETE FROM bulk_previews WHERE expires<?',(time.time(),))
    c.execute('INSERT INTO bulk_previews VALUES(?,?,?,?,?)',(token,user_id,json.dumps({'ids':[row['id'] for row in rows],'changes':changes}),fingerprint(c,rows,changes),time.time()+900))
    return {'token':token,'records':records,'selected':len(rows),'changed':sum(row['changed'] for row in records),'expires_in':900,'fields':list(changes),'catalogs':catalogs(c)}


def commit_bulk(c, user_id, token):
    if not isinstance(token,str):raise OrganizationError('Vista previa inválida')
    pending=c.execute('SELECT * FROM bulk_previews WHERE token=? AND user_id=? AND expires>?',(token,user_id,time.time())).fetchone()
    if not pending:raise OrganizationError('Vista previa expirada o ya utilizada; vuelve a previsualizar',409)
    payload=json.loads(pending['payload']);rows=selected_servers(c,payload['ids'])
    if fingerprint(c,rows,payload['changes'])!=pending['signature']:
        raise OrganizationError('El inventario o los catálogos cambiaron. Vuelve a previsualizar antes de confirmar.',409)
    changes=validate_changes(c,payload['changes']);updated=0
    for row in rows:
        before=row['organization']
        differs=any(sorted(before[field])!=sorted(value) if isinstance(value,list) else before[field]!=value for field,value in changes.items())
        if differs:
            assign(c,row['id'],changes);c.execute('UPDATE servers SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(row['id'],));updated+=1
    c.execute('DELETE FROM bulk_previews WHERE token=?',(token,))
    audit_log.record(c,user_id,'organization.bulk',{'ids':payload['ids'],'changes':changes,'before':[{'id':row['id'],'organization':row['organization']} for row in rows],'updated':updated})
    return {'updated':updated,'selected':len(rows)}
