"""Confirmed inventory deletion; never connects to or modifies target servers."""
import hashlib
import json
import secrets
import time
import audit_log
from organization import OrganizationError, selected_servers, fingerprint


def signature(c, rows):
    snapshot=[]
    for row in rows:
        server=dict(c.execute('SELECT * FROM servers WHERE id=?',(row['id'],)).fetchone())
        credentials=c.execute('SELECT revision,username,port,enabled FROM server_credentials WHERE server_id=?',(row['id'],)).fetchone()
        snapshot.append({'server':server,'credentials':dict(credentials) if credentials else None})
        network=c.execute('SELECT interfaces,reported_primary_ip FROM server_networks WHERE server_id=?',(row['id'],)).fetchone()
        snapshot.append({'network':dict(network) if network else None})
    snapshot.append({'classification':fingerprint(c,rows,{})})
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()


def preview(c, user_id, payload):
    if not isinstance(payload,dict):raise OrganizationError('Solicitud inválida')
    rows=selected_servers(c,payload.get('ids'))
    records=[]
    for row in rows:
        configured=bool(c.execute('SELECT 1 FROM server_credentials WHERE server_id=?',(row['id'],)).fetchone())
        metrics=c.execute('SELECT count(*) FROM metrics WHERE server_id=?',(row['id'],)).fetchone()[0]
        records.append({'id':row['id'],'name':row['name'],'ip':row['ip'],'has_credentials':configured,'metric_samples':metrics})
    token=secrets.token_urlsafe(32)
    c.execute('DELETE FROM deletion_previews WHERE expires<?',(time.time(),))
    c.execute('INSERT INTO deletion_previews VALUES(?,?,?,?,?)',(token,user_id,json.dumps([row['id'] for row in rows]),signature(c,rows),time.time()+600))
    return {'token':token,'records':records,'selected':len(records),'expires_in':600}


def commit(c, user_id, payload):
    if not isinstance(payload,dict) or payload.get('confirmed') is not True:
        raise OrganizationError('Confirma explícitamente la eliminación')
    token=payload.get('token')
    if not isinstance(token,str):raise OrganizationError('Confirmación inválida')
    pending=c.execute('SELECT * FROM deletion_previews WHERE token=? AND user_id=? AND expires>?',(token,user_id,time.time())).fetchone()
    if not pending:raise OrganizationError('Confirmación expirada o ya utilizada; revisa la selección de nuevo',409)
    ids=json.loads(pending['payload']);rows=selected_servers(c,ids)
    if signature(c,rows)!=pending['signature']:
        raise OrganizationError('Los servidores cambiaron. Revisa la selección de nuevo antes de eliminar.',409)
    before=[{'id':sid,'state':audit_log.server_state(c,sid)} for sid in ids]
    for sid in ids:c.execute('DELETE FROM servers WHERE id=?',(sid,))
    c.execute('DELETE FROM deletion_previews WHERE token=?',(token,))
    audit_log.record(c,user_id,'servers.delete',{'ids':ids,'deleted':len(ids),'before':before})
    return {'deleted':len(ids)}
