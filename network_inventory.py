"""Network inventory is independent of the single SSH connection destination."""
import ipaddress
import json
import re
from inventory import ValidationError

MAX_INTERFACES=128
MAX_ADDRESSES=128
EMPTY={'','unknown','n/a','none','not available','-'}
TEXT_FIELDS=('label','adapter_type','network','switch','mac_address')


def addresses(value):
    text=str(value or '').strip()
    if text.casefold() in EMPTY:return []
    if len(text)>16384:raise ValidationError('Lista de direcciones IP demasiado larga')
    result=[]
    for token in re.split(r'[,;\s]+',text):
        token=token.strip('[]')
        if not token or token.casefold() in EMPTY:continue
        try:
            address=ipaddress.ip_interface(token).ip if '/' in token else ipaddress.ip_address(token)
            # Bound and validate optional IPv6 scope names too.
            if '%' in str(address) and not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',str(address).split('%',1)[1]):raise ValueError()
        except ValueError:raise ValidationError('Dirección IP inválida en los datos de red')
        normalized=str(address)
        if normalized not in result:result.append(normalized)
    if len(result)>MAX_ADDRESSES:raise ValidationError('Máximo 128 direcciones IP por tarjeta')
    return result


def validate_interfaces(items):
    if not isinstance(items,list) or len(items)>MAX_INTERFACES:raise ValidationError('Máximo 128 tarjetas de red por servidor')
    result=[]
    for item in items:
        if not isinstance(item,dict):raise ValidationError('Tarjeta de red inválida')
        clean={}
        for field in TEXT_FIELDS:
            value=item.get(field,'')
            if not isinstance(value,str) or len(value)>500 or any(ord(c)<32 for c in value):raise ValidationError('Dato de tarjeta de red inválido')
            clean[field]=value.strip()
        mac=clean['mac_address']
        if mac.casefold() in EMPTY:mac=clean['mac_address']=''
        if mac:
            compact=re.sub('[:-]','',mac)
            if not re.fullmatch(r'[0-9a-fA-F]{12}',compact):raise ValidationError('Dirección MAC inválida')
            clean['mac_address']=':'.join(compact[i:i+2] for i in range(0,12,2)).lower()
        for field in ('connected','starts_connected'):
            value=item.get(field)
            if value is not None and type(value) is not bool:raise ValidationError('Estado de tarjeta inválido')
            clean[field]=value
        ips=item.get('ip_addresses',[])
        if not isinstance(ips,list) or len(ips)>MAX_ADDRESSES or any(not isinstance(ip,str) for ip in ips):raise ValidationError('Direcciones de tarjeta inválidas')
        clean['ip_addresses']=addresses(';'.join(ips))
        clean['source']=item.get('source','vNetwork')
        if clean['source'] not in ('vInfo','vNetwork'):raise ValidationError('Origen de red inválido')
        result.append(clean)
    if sum(len(item['ip_addresses']) for item in result)>1024:raise ValidationError('Máximo 1024 direcciones IP por servidor')
    return result


def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS server_networks(
        server_id INTEGER PRIMARY KEY REFERENCES servers(id) ON DELETE CASCADE,
        interfaces TEXT NOT NULL,reported_primary_ip TEXT NOT NULL DEFAULT '')''')


def save(c,sid,interfaces,reported_primary_ip=''):
    if interfaces is None:
        old=c.execute('SELECT interfaces FROM server_networks WHERE server_id=?',(sid,)).fetchone()
        interfaces=json.loads(old['interfaces']) if old else []
    payload=json.dumps(validate_interfaces(interfaces),ensure_ascii=False,sort_keys=True)
    c.execute('INSERT INTO server_networks VALUES(?,?,?) ON CONFLICT(server_id) DO UPDATE SET interfaces=excluded.interfaces,reported_primary_ip=excluded.reported_primary_ip',(sid,payload,reported_primary_ip))


def all_addresses(primary,reported_primary,interfaces):
    values=[]
    for raw in (primary,reported_primary):
        try:values.extend(addresses(raw))
        except ValidationError:
            # Keep legacy manual connection names without changing the ip contract.
            if raw:values.append(raw)
    values.extend(ip for nic in interfaces for ip in nic['ip_addresses'])
    return list(dict.fromkeys(values))


def hydrate(c,rows):
    result=[dict(row) for row in rows];index={row['id']:row for row in result}
    for row in result:row.update(network_interfaces=[],reported_primary_ip='')
    ids=list(index)
    for offset in range(0,len(ids),400):
        chunk=ids[offset:offset+400]
        for stored in c.execute('SELECT * FROM server_networks WHERE server_id IN ('+','.join('?' for _ in chunk)+')',chunk):
            index[stored['server_id']]['network_interfaces']=json.loads(stored['interfaces'])
            index[stored['server_id']]['reported_primary_ip']=stored['reported_primary_ip']
    for row in result:
        row['ip_addresses']=all_addresses(row.get('ip'),row['reported_primary_ip'],row['network_interfaces'])
    return result
