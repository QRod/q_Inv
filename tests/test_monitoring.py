from pathlib import Path
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from inventory import validate, ValidationError
from monitoring import configure, connection, dashboard, Monitor, parse_metrics
from vault import load_key, encrypt, decrypt

OUTPUT='''QM_SYSTEM=Linux
QM_CORES=4
QM_UPTIME=86401
QM_LOAD=0.45
QM_MEM=8388608 2097152
QM_ROOT=104857600 52428800 51
QM_CPU1=1000 400
QM_CPU2=1400 700
QM_TIME1=10
QM_TIME2=11
QM_NET1=1000 2000
QM_NET2=2024 4048
QM_IO1=10000 20000
QM_IO2=12048 24096
QM_TEMP=45000
QM_END=1
'''

class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.old_data,self.old_key=server.DATA,server.KEY_FILE
        server.DATA=self.root/'data';server.KEY_FILE=self.root/'separate-secrets'/'key';server.init()
        with server.db() as c:
            self.sid=server.save_server(c,validate({'name':'test','ip':'192.0.2.1'}),'manual')
            configure(c,self.sid,{'username':'reader','password':'secret-not-plaintext','port':22,'enabled':True},server.KEY_FILE)
    def tearDown(self):
        server.DATA,server.KEY_FILE=self.old_data,self.old_key;self.temp.cleanup()
    def test_vault_round_trip_and_missing_key_fail_closed(self):
        token=encrypt('password',server.KEY_FILE)
        self.assertNotIn('password',token);self.assertEqual(decrypt(token,server.KEY_FILE),'password')
        other=self.root/'other-key';load_key(other,allow_create=True)
        with self.assertRaises(ValidationError):decrypt(token,other)
        server.KEY_FILE.unlink()
        with self.assertRaises(RuntimeError):server.init()
        self.assertFalse(server.KEY_FILE.exists())
    def test_key_permissions_and_systemd_credential_directory(self):
        key=self.root/'managed'/'ssh_key';load_key(key,allow_create=True)
        key.chmod(0o644)
        with self.assertRaises(RuntimeError):load_key(key)
        key.chmod(0o440);key.parent.chmod(0o550)
        with self.assertRaises(RuntimeError):load_key(key)
        with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':str(key.parent)}):
            load_key(key)
            key.parent.chmod(0o557)
            with self.assertRaises(RuntimeError):load_key(key)
        key.parent.chmod(0o700)

    def test_preserve_replace_pause_and_no_plaintext(self):
        with server.db() as c:
            before=c.execute('SELECT secret FROM server_credentials').fetchone()[0]
            self.assertNotIn('secret-not-plaintext',before)
            configure(c,self.sid,{'username':'reader','password':'','port':22,'enabled':False},server.KEY_FILE)
            self.assertEqual(c.execute('SELECT secret FROM server_credentials').fetchone()[0],before)
            self.assertEqual(dashboard(c)['servers'][0]['state'],'paused')
            self.assertEqual(connection(c,self.sid,server.KEY_FILE)['password'],'secret-not-plaintext')
            with self.assertRaises(ValidationError):configure(c,self.sid,{'username':'different','password':''},server.KEY_FILE)
            configure(c,self.sid,{'username':'reader','password':'replacement','port':22,'enabled':True},server.KEY_FILE)
            self.assertEqual(connection(c,self.sid,server.KEY_FILE)['password'],'replacement')
            public=json.dumps(dashboard(c));self.assertNotIn('secret',public);self.assertNotIn('reader',public)
    def test_metrics_units_rates_and_missing_values(self):
        data=parse_metrics(OUTPUT,'192.0.2.1')['data']
        self.assertEqual(data['cpu_percent'],25);self.assertEqual(data['memory_percent'],75)
        self.assertEqual(data['ram_total_gb'],8);self.assertEqual(data['disk_total_gb'],100)
        self.assertEqual(data['net_rx_bps'],1024);self.assertEqual(data['io_write_bps'],4096)
        self.assertEqual(data['temperature_c'],45)
        reset=parse_metrics(OUTPUT.replace('QM_NET2=2024 4048','QM_NET2=0 0'),'192.0.2.1')['data']
        self.assertNotIn('net_rx_bps',reset)
        with self.assertRaises(ValidationError):parse_metrics('QM_SYSTEM=AIX\nQM_END=1','192.0.2.1')
        with self.assertRaises(ValidationError):parse_metrics('QM_SYSTEM=Linux\nQM_END=1','192.0.2.1')
    def test_collection_errors_freshness_retention_and_revision(self):
        monitor=Monitor(server.db,server.DATA,server.KEY_FILE)
        try:
            row={'id':self.sid,'ip':'192.0.2.1','revision':1}
            with patch('monitoring.discover',return_value={'data':{'cpu_percent':10}}):monitor.collect(row)
            with server.db() as c:
                self.assertEqual(dashboard(c)['servers'][0]['state'],'online')
                self.assertGreater(c.execute('SELECT next_due FROM server_credentials').fetchone()[0],time.time()+290)
                c.execute('UPDATE metrics SET collected_at=?',(time.time()-700,))
                self.assertEqual(dashboard(c)['servers'][0]['state'],'stale')
                c.execute('UPDATE server_credentials SET revision=2')
            with patch('monitoring.discover',return_value={'data':{'cpu_percent':99}}):monitor.collect(row)
            with server.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM metrics').fetchone()[0],1)
            row['revision']=2
            with patch('monitoring.discover',side_effect=ValidationError('Autenticación rechazada')):monitor.collect(row)
            with server.db() as c:
                state=dashboard(c)['servers'][0];self.assertEqual(state['state'],'error');self.assertEqual(state['metrics'],{})
                c.execute('UPDATE metrics SET collected_at=?',(time.time()-61*86400,))
                c.execute('UPDATE server_credentials SET enabled=0')
            monitor.tick()
            with server.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM metrics').fetchone()[0],0)
        finally:monitor.pool.shutdown(wait=True)
    def test_scheduler_never_submits_same_server_twice(self):
        monitor=Monitor(server.db,server.DATA,server.KEY_FILE)
        try:
            with patch.object(monitor.pool,'submit') as submit:
                monitor.tick();monitor.tick();self.assertEqual(submit.call_count,1)
                with server.db() as c:c.execute('UPDATE server_credentials SET next_due=0')
                monitor.tick();self.assertEqual(submit.call_count,1)
        finally:monitor.pool.shutdown(wait=True)

if __name__=='__main__':unittest.main()
