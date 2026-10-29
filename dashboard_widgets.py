"""Personal dashboard settings and inventory-scoped observations; no free-capacity claims."""
from collections import defaultdict
import copy,json,math
from datetime import datetime,timezone
import permissions,organization,lifecycle
from inventory import ValidationError
from monitoring import dashboard

WIDGETS={'os_distribution':'Sistemas operativos','support_lifecycle':'Ciclo de soporte estándar','monitoring_coverage':'Cobertura de monitoreo','resource_pressure':'Presión de recursos','allocated_capacity':'Capacidad asignada por aplicación','inventory_quality':'Calidad del inventario'}
DEFAULT={'widgets':['os_distribution','support_lifecycle','monitoring_coverage'],'show_servers':True,'group_id':None,'environment_id':None,'server_type':'all','os_grouping':'version','support_horizon':180,'cpu_threshold':85,'memory_threshold':85,'disk_threshold':85}


def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS dashboard_preferences(
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        revision INTEGER NOT NULL,config TEXT NOT NULL)''')


def validate(c,actor,value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULT):raise ValidationError('Configuración del dashboard inválida')
    result=copy.deepcopy(value);widgets=result['widgets']
    if not isinstance(widgets,list) or len(widgets)>len(WIDGETS) or any(not isinstance(item,str) or item not in WIDGETS for item in widgets) or len(set(widgets))!=len(widgets):raise ValidationError('Selecciona widgets válidos, sin duplicados')
    if type(result['show_servers']) is not bool:raise ValidationError('Visibilidad de tarjetas inválida')
    if result['server_type'] not in ('all','physical','virtual') or result['os_grouping'] not in ('family','version'):raise ValidationError('Filtro de inventario inválido')
    if type(result['support_horizon']) is not int or result['support_horizon'] not in (30,90,180,365):raise ValidationError('Horizonte de soporte inválido')
    for field in ('cpu_threshold','memory_threshold','disk_threshold'):
        if type(result[field]) is not int or not 1<=result[field]<=100:raise ValidationError('Umbral: de 1 a 100 por ciento')
    catalogs=permissions.catalogs(c,actor)
    for field,kind in [('group_id','groups'),('environment_id','environments')]:
        item=result[field]
        if item is not None and (type(item) is not int or item not in {entry['id'] for entry in catalogs[kind]}):raise permissions.Forbidden('El filtro no está disponible en tu ámbito de acceso')
    return result


def preferences(c,actor):
    row=c.execute('SELECT * FROM dashboard_preferences WHERE user_id=?',(actor['user_id'],)).fetchone()
    config=json.loads(row['config']) if row else copy.deepcopy(DEFAULT);adjusted=False
    catalogs=permissions.catalogs(c,actor)
    for field,kind in [('group_id','groups'),('environment_id','environments')]:
        if config[field] is not None and config[field] not in {entry['id'] for entry in catalogs[kind]}:config[field]=None;adjusted=True
    return {'revision':row['revision'] if row else 0,'config':config,'adjusted':adjusted}


def save(c,actor,payload):
    if not isinstance(payload,dict) or set(payload)!={'revision','config'} or type(payload['revision']) is not int:raise ValidationError('Preferencias inválidas')
    config=validate(c,actor,payload['config'])
    old=preferences(c,actor)
    if payload['revision']!=old['revision']:raise organization.OrganizationError('El dashboard cambió en otra pestaña. Cierra y vuelve a abrir Personalizar.',409)
    revision=old['revision']+1
    c.execute('INSERT INTO dashboard_preferences VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,config=excluded.config',(actor['user_id'],revision,json.dumps(config)))
    return {'revision':revision,'config':config,'before':old['config']}


def scoped(rows,config):
    return [s for s in rows if (config['server_type']=='all' or s['kind']==config['server_type']) and (config['group_id'] is None or config['group_id'] in s['organization']['group_ids']) and (config['environment_id'] is None or config['environment_id']==s['organization']['environment_id'])]


def bucket(label,ids,**extra):return {'label':label,'ids':ids,'count':len(ids),**extra}


def build(c,actor):
    pref=preferences(c,actor);config=pref['config'];visible=permissions.visible_ids(c,actor)
    rows=organization.hydrate(c,[row for row in c.execute('SELECT * FROM servers ORDER BY name COLLATE NOCASE') if row['id'] in visible]);rows=scoped(rows,config)
    selected={row['id'] for row in rows};states={s['id']:s for s in dashboard(c)['servers'] if s['id'] in selected}
    today=datetime.now(timezone.utc).date();systems=defaultdict(list);lifecycle_ids=defaultdict(list);lifecycle_rows=[]
    quality={label:[] for label in ['Sin sistema operativo','SO o ciclo de soporte por verificar','Sin grupo','Sin aplicación','Sin ambiente','Sin responsable','Capacidad incompleta']}
    coverage=defaultdict(list);pressure={label:[] for label in ['CPU alta','RAM alta','Disco raíz alto','Sin métricas recientes o suficientes']}
    pressure_ids=set();assessed=0;apps=defaultdict(list)
    for s in rows:
        sid=s['id'];support=lifecycle.assess(s['os'],config['support_horizon'],today);family=support['family'];version=support['version']
        label=family if config['os_grouping']=='family' else family+(' '+version if version else ' · sin versión identificada')
        if family=='Sin identificar' and s['os']:label=s['os']
        systems[label].append(sid);lifecycle_ids[support['status']].append(sid);lifecycle_rows.append({'id':sid,'name':s['name'],**support})
        if not s['os']:quality['Sin sistema operativo'].append(sid)
        if support['status']=='unknown':quality['SO o ciclo de soporte por verificar'].append(sid)
        for title,key in [('Sin grupo','groups'),('Sin aplicación','applications'),('Sin ambiente','environment'),('Sin responsable','owner')]:
            if not s[key]:quality[title].append(sid)
        if any(s[field] is None for field in ('cpu','ram_gb','disk_gb')):quality['Capacidad incompleta'].append(sid)
        current=states[sid];coverage[current['state']].append(sid);valid=False
        if current['state']=='online':
            for title,metric,threshold in [('CPU alta','cpu_percent','cpu_threshold'),('RAM alta','memory_percent','memory_threshold'),('Disco raíz alto','disk_percent','disk_threshold')]:
                value=current['metrics'].get(metric)
                if type(value) in (float,int) and math.isfinite(value) and 0<=value<=100:
                    valid=True
                    if value>=config[threshold]:pressure[title].append(sid);pressure_ids.add(sid)
        if valid:assessed+=1
        else:pressure['Sin métricas recientes o suficientes'].append(sid)
        app=s['applications'];key=('app',app[0]['id']) if len(app)==1 else ('shared',0) if len(app)>1 else ('none',0)
        apps[(key,app[0]['name'] if len(app)==1 else 'Compartidos (varias aplicaciones)' if len(app)>1 else 'Sin aplicación')].append(s)
    capacity=[]
    for (_,name),members in apps.items():
        amounts={}
        for kind in ('virtual','physical'):
            for field in ('cpu','ram_gb','disk_gb'):amounts[kind+'_'+field]=round(sum(s[field] for s in members if s['kind']==kind and s[field] is not None),3)
        capacity.append(bucket(name,[s['id'] for s in members],**amounts))
    capacity.sort(key=lambda item:(-item['virtual_ram_gb']-item['physical_ram_gb'],item['label'].casefold()))
    return {**pref,'catalog':WIDGETS,'catalogs':permissions.catalogs(c,actor),'scope_count':len(rows),'as_of':today.isoformat(),'catalog_reviewed_on':lifecycle.CATALOG['reviewed_on'],'catalog_stale':(today-datetime.fromisoformat(lifecycle.CATALOG['reviewed_on']).date()).days>180,
            'os_distribution':sorted([bucket(label,ids) for label,ids in systems.items()],key=lambda item:(-item['count'],item['label'].casefold())),
            'support_lifecycle':{'counts':{key:len(lifecycle_ids[key]) for key in ('expired','ending','active','unknown')},'rows':lifecycle_rows},
            'monitoring_coverage':[bucket(key,ids) for key,ids in coverage.items()],
            'resource_pressure':{'rows':[bucket(key,ids) for key,ids in pressure.items()],'affected_ids':sorted(pressure_ids),'assessed':assessed},
            'allocated_capacity':capacity,'inventory_quality':[bucket(key,ids) for key,ids in quality.items()]}
