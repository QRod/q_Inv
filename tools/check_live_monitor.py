"""Verify real periodic SSH collection in a temporary, isolated database."""
import argparse
import getpass
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from inventory import validate
from monitoring import configure, Monitor

parser=argparse.ArgumentParser()
parser.add_argument('--ip',required=True)
parser.add_argument('--username',required=True)
parser.add_argument('--known-hosts',required=True)
args=parser.parse_args()
password=getpass.getpass('SSH password (temporary isolated verification): ')
with tempfile.TemporaryDirectory(prefix='qinv-monitor-') as folder:
    server.DATA=Path(folder)/'data';server.KEY_FILE=Path(folder)/'key';server.init()
    shutil.copyfile(args.known_hosts,server.DATA/'ssh_known_hosts')
    with server.db() as c:
        sid=server.save_server(c,validate({'name':'isolated-verification','ip':args.ip}),'manual')
        configure(c,sid,{'username':args.username,'password':password,'port':22,'enabled':True},server.KEY_FILE)
        assert password not in c.execute('SELECT secret FROM server_credentials').fetchone()[0]
    password=''
    monitor=Monitor(server.db,server.DATA,server.KEY_FILE);monitor.start()
    try:
        def wait_for(count):
            end=time.monotonic()+70
            while time.monotonic()<end:
                with server.db() as c:
                    rows=c.execute('SELECT status,error,payload FROM metrics ORDER BY id').fetchall()
                if len(rows)>=count:
                    row=rows[-1];assert row['status']=='online',row['error']
                    data=json.loads(row['payload']);assert 'cpu_percent' in data and 'memory_percent' in data and 'disk_percent' in data,data
                    return data
                time.sleep(.5)
            raise RuntimeError('Timed out waiting for the periodic collector')
        first=wait_for(1)
        with server.db() as c:c.execute('UPDATE server_credentials SET next_due=0')
        monitor.wake.set();second=wait_for(2)
        print('LIVE_MONITOR_OK: two background samples; encrypted credentials; CPU, RAM, root disk, network and I/O parsed.')
        print(json.dumps(second,ensure_ascii=False))
    finally:monitor.close()
