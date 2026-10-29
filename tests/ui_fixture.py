"""Temporary synthetic instance for browser QA; never uses the live database."""
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import organization as org
from inventory import validate
from monitoring import configure
with tempfile.TemporaryDirectory() as folder:
    server.DATA=Path(folder)/'data'; server.KEY_FILE=Path(folder)/'key';server.init()
    with server.db() as c:
        salt='00'*16
        c.execute("INSERT INTO users(username,salt,password,role) VALUES(?,?,?,'admin')",('qa',salt,server.password_hash('qa-browser-only',salt)))
        catalogs={}
        for kind,names in [('groups',['Infraestructura','Web']),('applications',['Portal']),('owners',['Operaciones']),('tags',['Crítico'])]:
            catalogs[kind]=[org.catalog_command(c,{'kind':kind,'name':name})['id'] for name in names]
        production=next(entry['id'] for entry in org.catalogs(c)['environments'] if entry['name']=='Producción')
        for name,configured,state in [('web-prod-01',True,'online'),('db-prod-01',True,'error'),('app-dev-01',False,None)]:
            sid=server.save_server(c,validate({'name':name,'ip':'192.0.2.'+str(len(name)),'os':'RHEL 8','cpu':4,'ram_gb':8}),'manual')
            if configured:
                org.assign(c,sid,{'group_ids':catalogs['groups'] if state=='online' else catalogs['groups'][:1],'application_ids':catalogs['applications'],'environment_id':production,'owner_id':catalogs['owners'][0],'tag_ids':catalogs['tags']})
                configure(c,sid,{'username':'reader','password':'qa-not-real'},server.KEY_FILE)
                payload={'cpu_percent':0,'memory_percent':40,'disk_percent':12,'cpu_cores':4,'ram_total_gb':8,'disk_total_gb':156.4,'uptime_seconds':1040000,'temperature_c':34.5,'load_1m':.23,'net_rx_bps':2048,'net_tx_bps':0,'net_rx_bytes':1000000,'net_tx_bytes':500000,'io_read_bps':0,'io_write_bps':4096,'io_read_bytes':1048576,'io_write_bytes':2097152} if state=='online' else {}
                c.execute('INSERT INTO metrics(server_id,collected_at,status,error,payload) VALUES(?,?,?,?,?)',(sid,time.time(),state,'El servidor rechazó la autenticación SSH' if state=='error' else None,json.dumps(payload)))
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    print('http://127.0.0.1:'+str(http.server_port),flush=True)
    http.serve_forever()
