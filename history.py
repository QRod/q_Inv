"""Bounded history aggregation. Missing and failed observations never become zero."""
import math
import time
from inventory import ValidationError

METRICS=('cpu_percent','memory_percent','disk_percent','net_rx_bps','net_tx_bps','io_read_bps','io_write_bps')


def window(query,now,retention_days):
    def number(name,default):
        values=query.get(name,[str(default)])
        try:value=float(values[0])
        except (ValueError,TypeError,IndexError):raise ValidationError('Rango histórico inválido')
        if len(values)!=1 or not math.isfinite(value):raise ValidationError('Rango histórico inválido')
        return value
    end=number('to',now);start=number('from',end-number('hours',24)*3600)
    if start<0 or end>now+60 or not 60<=end-start<=3650*86400:raise ValidationError('Selecciona un rango de un minuto a diez años, sin fechas futuras')
    end=min(end,now)
    if start>=end:raise ValidationError('El inicio debe ser anterior al final')
    requested=start;start=max(start,now-retention_days*86400)
    if start>=end:raise ValidationError('El rango está fuera del periodo de retención')
    return start,end,requested


def read(c,sid,query,now=None):
    now=time.time() if now is None else now
    settings=c.execute('SELECT * FROM settings WHERE id=1').fetchone()
    start,end,requested=window(query,now,settings['retention_days'])
    step=max(settings['interval_minutes']*60,math.ceil((end-start)/720))
    count=math.ceil((end-start)/step)
    aggregates=[]
    for metric in METRICS:
        path="'$."+metric+"'";value=f'json_extract(payload,{path})';kind=f'json_type(payload,{path})'
        bounds=f'{value}>=0'+(f' AND {value}<=100' if metric.endswith('_percent') else f' AND {value}<=1e18')
        valid=f"CASE WHEN status='online' AND {kind} IN ('integer','real') AND {bounds} THEN {value} END"
        aggregates.extend([f'avg({valid}) AS {metric}',f'max({valid}) AS {metric}_max'])
    sql='''WITH observations AS (
        SELECT CAST((collected_at-?)/? AS INTEGER) AS bucket,status,
        CASE WHEN json_valid(payload) THEN payload ELSE '{}' END AS payload
        FROM metrics WHERE server_id=? AND collected_at>=? AND collected_at<?)
        SELECT bucket,count(*) AS samples,sum(status='online') AS successful,'''+','.join(aggregates)+' FROM observations GROUP BY bucket ORDER BY bucket'
    rows={row['bucket']:dict(row) for row in c.execute(sql,(start,step,sid,start,end))}
    points=[];total=successful=0
    for i in range(count):
        row=rows.get(i,{});samples=row.get('samples',0);ok=row.get('successful',0)
        point={'at':start+i*step,'until':min(end,start+(i+1)*step),'samples':samples,'successful':ok,'failed':samples-ok}
        point['values']={name:row.get(name) for name in METRICS}
        point['maxima']={name:row.get(name+'_max') for name in METRICS}
        points.append(point);total+=samples;successful+=ok
    return {'from':start,'to':end,'requested_from':requested,'bucket_seconds':step,'interval_minutes':settings['interval_minutes'],'retention_days':settings['retention_days'],
            'samples':total,'successful':successful,'failed':total-successful,'success_percent':round(successful/total*100,2) if total else None,'points':points}
