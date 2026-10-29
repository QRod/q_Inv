"""Structured, append-only application audit; secrets never enter event payloads."""
import json
from inventory import FIELDS

BLOCKED = {'password','secret','salt','csrf','token','private_key','encrypted_password'}


def migrate(c):
    columns={r['name'] for r in c.execute('PRAGMA table_info(audit)')}
    new_actor='actor_username' not in columns
    for name,definition in [('actor_username',"TEXT NOT NULL DEFAULT ''"),('event',"TEXT NOT NULL DEFAULT 'legacy'"),('outcome',"TEXT NOT NULL DEFAULT 'success'"),('target_type',"TEXT NOT NULL DEFAULT ''"),('target_id','INTEGER'),('details',"TEXT NOT NULL DEFAULT '{}'" )]:
        if name not in columns:c.execute(f'ALTER TABLE audit ADD COLUMN {name} {definition}')
    if new_actor:c.execute("UPDATE audit SET actor_username=coalesce((SELECT username FROM users WHERE users.id=audit.user_id),'')")
    c.execute('CREATE INDEX IF NOT EXISTS audit_event_id ON audit(event,id DESC)')
    c.execute("CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'El registro de auditoría es de solo anexado'); END")
    c.execute("CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'El registro de auditoría es de solo anexado'); END")


def clean(value, depth=0):
    if depth>8:return '[profundidad limitada]'
    if isinstance(value,dict):return {str(k):clean(v,depth+1) for k,v in value.items() if str(k).casefold() not in BLOCKED}
    if isinstance(value,(list,tuple)):return [clean(v,depth+1) for v in value[:500]]
    if isinstance(value,str):return value[:1000]
    if value is None or type(value) in (bool,int,float):return value
    return str(value)[:200]


def record(c, actor, event, details=None, outcome='success', target_type='', target_id=None):
    if isinstance(actor,int):
        row=c.execute('SELECT username FROM users WHERE id=?',(actor,)).fetchone()
        user_id,username=actor,row['username'] if row else ''
    elif actor:
        user_id=actor.get('user_id',actor.get('id'));username=actor.get('username','')
    else:user_id,username=None,''
    payload=clean(details or {});raw=json.dumps(payload,ensure_ascii=False,sort_keys=True)
    if len(raw.encode())>512*1024:
        payload={'truncated':True,'ids':payload.get('ids',[])[:500],'fields':list(payload.get('changes',{}))}
        raw=json.dumps(payload,ensure_ascii=False)
    # Keep action compatible with older audit consumers; only sanitized data is used.
    c.execute('''INSERT INTO audit(user_id,action,actor_username,event,outcome,target_type,target_id,details)
                 VALUES(?,?,?,?,?,?,?,?)''',(user_id,event+' '+raw,username,event,outcome,target_type,target_id,raw))


def server_state(c, sid):
    row=c.execute('SELECT * FROM servers WHERE id=?',(sid,)).fetchone()
    if not row:return None
    import organization
    state={field:row[field] for field in FIELDS}
    state['organization']=organization.hydrate(c,[{'id':sid}])[0]['organization']
    return state


def page(c, query):
    from inventory import ValidationError
    try:
        before=int(query.get('before',['0'])[0]);limit=int(query.get('limit',['50'])[0])
    except (ValueError,TypeError):raise ValidationError('Paginación inválida')
    if before<0 or not 1<=limit<=100:raise ValidationError('Paginación inválida')
    conditions=[];params=[]
    if before:conditions.append('id<?');params.append(before)
    for key in ['event','outcome']:
        value=query.get(key,[''])[0]
        if value:
            if not isinstance(value,str) or len(value)>100:raise ValidationError('Filtro inválido')
            conditions.append(key+'=?');params.append(value)
    sql='SELECT id,user_id,actor_username,event,outcome,target_type,target_id,created_at,substr(action,1,240) AS summary FROM audit'
    if conditions:sql+=' WHERE '+' AND '.join(conditions)
    rows=c.execute(sql+' ORDER BY id DESC LIMIT ?',params+[limit+1]).fetchall()
    more=len(rows)>limit;items=[dict(row) for row in rows[:limit]]
    return {'records':items,'next_before':items[-1]['id'] if more else None}


def detail(c, event_id):
    row=c.execute('SELECT * FROM audit WHERE id=?',(event_id,)).fetchone()
    if not row:return None
    result=dict(row);result['details']=json.loads(result['details']);return result
