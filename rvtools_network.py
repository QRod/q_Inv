"""Recognize RVTools network header variants without guessing VM identity."""
import re
from inventory import ValidationError
from network_inventory import addresses,validate_interfaces

ALIASES={
 'uuid':('VM UUID','UUID','Instance UUID'), 'name':('VM','Name','VM name'),
 'label':('NIC label','NIC','Network adapter','Adapter name'),
 'adapter_type':('Adapter','Adapter type'), 'network':('Network','Network name','Portgroup','Port group'),
 'switch':('Switch','Switch name'), 'mac_address':('MAC Address','MAC'),
 'connected':('Connected',), 'starts_connected':('Starts Connected','Start Connected'),
}
IP_HEADERS=('IP Address','IP Addresses','IPv4 Address','IPv4 Addresses','IPv6 Address','IPv6 Addresses')


def key(value):return re.sub(r'[^a-z0-9]','',str(value or '').casefold())


def boolean(value):
    if value is None or str(value).strip().casefold() in ('','unknown','n/a','-'):return None
    value=str(value).strip().casefold()
    if value in ('true','yes','1'):return True
    if value in ('false','no','0'):return False
    raise ValidationError('Estado de conexión no reconocido en vNetwork')


def vinfo_interfaces(headers,row):
    indices=[(i,header) for i,header in enumerate(headers) if re.fullmatch(r'nic\s*#?\s*\d+',header,re.I)]
    if not indices:return None
    items=[{'label':label.upper(),'ip_addresses':addresses(row[i] if i<len(row) else None),'source':'vInfo'} for i,label in indices if i<len(row) and row[i] not in (None,'')]
    return validate_interfaces(items)


def enrich(book,records,errors):
    sheet=next((sheet for sheet in book if sheet.title.strip().casefold()=='vnetwork'),None)
    if sheet is None:return
    rows=sheet.iter_rows(values_only=True);headers=[key(v) for v in next(rows,())]
    mapping={field:next((headers.index(key(alias)) for alias in aliases if key(alias) in headers),None) for field,aliases in ALIASES.items()}
    ip_columns=[i for i,header in enumerate(headers) if header in {key(name) for name in IP_HEADERS}]
    if (mapping['uuid'] is None and mapping['name'] is None) or not (ip_columns or any(mapping[f] is not None for f in ('label','mac_address','network'))):
        errors.append({'sheet':'vNetwork','line':1,'error':'vNetwork requiere VM o VM UUID y columnas de tarjetas de red reconocidas'});return
    by_uuid={item['data']['uuid']:item for item in records};by_name={}
    for item in records:
        by_name.setdefault(item['data']['name'].casefold(),[]).append(item)
        item['data']['network_interfaces']=[]
    for line,row in enumerate(rows,2):
        if line>100001:raise ValidationError('Máximo 100 000 filas en vNetwork')
        if not any(v is not None for v in row):continue
        def value(field):
            i=mapping[field];return row[i] if i is not None and i<len(row) else None
        try:
            uid=str(value('uuid') or '').strip().lower();name=str(value('name') or '').strip().casefold()
            if uid:
                target=by_uuid.get(uid)
                if target is None:
                    if name in by_name:raise ValidationError('VM UUID de vNetwork no coincide con vInfo')
                    continue
            else:
                matches=by_name.get(name,[])
                if len(matches)>1:raise ValidationError('Nombre de VM ambiguo; se requiere VM UUID en vNetwork')
                if not matches:
                    if not name:raise ValidationError('Falta VM UUID o nombre de VM en vNetwork')
                    continue
                target=matches[0]
            item={field:str(value(field) or '').strip() for field in ('label','adapter_type','network','switch','mac_address')}
            item.update(connected=boolean(value('connected')),starts_connected=boolean(value('starts_connected')),ip_addresses=[],source='vNetwork')
            for i in ip_columns:
                for ip in addresses(row[i] if i<len(row) else None):
                    if ip not in item['ip_addresses']:item['ip_addresses'].append(ip)
            item=validate_interfaces([item])[0]
            interfaces=target['data']['network_interfaces']
            identity=item['label'] or item['mac_address']
            prior=next((nic for nic in interfaces if identity and (nic['label']==item['label'] if item['label'] else nic['mac_address']==item['mac_address'])),None)
            if prior:
                if not item['label']:item['label']=prior['label']
                if any(prior[field]!=item[field] for field in item if field!='ip_addresses'):raise ValidationError('Datos contradictorios para la misma tarjeta de red')
                prior['ip_addresses']=list(dict.fromkeys(prior['ip_addresses']+item['ip_addresses']))
            else:
                if not item['label']:item['label']='Interfaz '+str(len(interfaces)+1)
                interfaces.append(item)
            validate_interfaces(interfaces)
        except ValidationError as error:errors.append({'sheet':'vNetwork','line':line,'error':str(error)})
