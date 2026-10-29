import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request,build_opener,HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import permissions
import organization as org
import updates
import audit_log
from backups import create_backup
from inventory import validate
from monitoring import configure
from vault import decrypt

PASSWORD='enterprise-test-password'

class Client:
    def __init__(self,url):self.url=url;self.csrf='';self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
    def request(self,path,data=None,headers=None):
        raw=None if data is None else json.dumps(data).encode()
        request=Request(self.url+'/api/'+path,data=raw,headers={'Content-Type':'application/json','X-CSRF-Token':self.csrf,**(headers or {})})
        try:response=self.opener.open(request,timeout=15)
        except HTTPError as error:response=error
        with response:return response.status,json.load(response)
    def login(self,name,password=PASSWORD):
        status,result=self.request('login',{'username':name,'password':password})
        if status==200:self.csrf=result['csrf']
        return status,result

class EnterpriseApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=(server.DATA,server.KEY_FILE);server.DATA=Path(self.temp.name)/'data';server.KEY_FILE=Path(self.temp.name)/'key';server.init()
        with server.db() as c:
            self.groups=[org.catalog_command(c,{'kind':'groups','name':name})['id'] for name in ['Equipo A','Equipo B','Vacío']]
            self.app=org.catalog_command(c,{'kind':'applications','name':'Aplicación privada B'})['id']
            self.ids=[]
            for i,group_ids in enumerate([[self.groups[0]],[self.groups[1]],self.groups[:2],[]]):
                sid=server.save_server(c,validate({'name':'server-'+str(i),'uuid':'uuid-'+str(i),'ip':'192.0.2.'+str(i+1)}),'manual');self.ids.append(sid);org.assign(c,sid,{'group_ids':group_ids,'application_ids':[self.app] if i==1 else []})
                configure(c,sid,{'username':'ssh-test','password':'never-log-ssh-secret'},server.KEY_FILE)
            self.users={}
            for name,role,groups in [('admin','admin',[]),('operator','operator',[self.groups[0]]),('reader','reader',[self.groups[0]])]:
                self.users[name]=permissions.save_user(c,{'username':name,'role':role,'active':True,'password':PASSWORD,'group_ids':groups},server.password_hash)['user']
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.http.server_port)
        self.admin=self.client('admin');self.operator=self.client('operator');self.reader=self.client('reader')
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();server.DATA,server.KEY_FILE=self.old;self.temp.cleanup()
    def client(self,name):
        client=Client(self.url);self.assertEqual(client.login(name)[0],200);return client
    def test_read_scope_counts_and_admin_only_ungrouped(self):
        for client in [self.operator,self.reader]:
            status,rows=client.request('servers');self.assertEqual(status,200);self.assertEqual({v['id'] for v in rows},{self.ids[0],self.ids[2]})
            status,dashboard=client.request('dashboard');self.assertEqual({v['id'] for v in dashboard['servers']},{self.ids[0],self.ids[2]})
            status,catalogs=client.request('catalogs');self.assertEqual([g['id'] for g in catalogs['groups']],[self.groups[0]]);self.assertEqual(catalogs['groups'][0]['server_count'],2);self.assertEqual(catalogs['applications'],[])
        self.assertNotIn('ssh_username',self.reader.request('servers')[1][0]);self.assertNotIn('ssh_port',self.reader.request('servers')[1][0])
        self.assertEqual(len(self.admin.request('servers')[1]),4)
    def test_reader_cannot_write_even_with_forged_claims(self):
        paths=['servers','users','catalogs','settings','import/preview','import/commit','organization/preview','organization/commit','servers/delete-preview','servers/delete','discover','metrics/refresh','updates/check']
        for path in paths:
            self.assertEqual(self.reader.request(path,{'id':self.ids[0]},headers={'X-Role':'admin'})[0],403,path)
        for path in ['users','audit','audit/1','settings','updates/status']:self.assertEqual(self.reader.request(path)[0],403,path)
        self.assertEqual(len(self.admin.request('servers')[1]),4)
    def test_operator_target_checks_happen_before_secret_read_or_network(self):
        with patch('server.connection') as connection,patch('server.discover') as discover:
            self.assertEqual(self.operator.request('discover',{'server_id':self.ids[1],'ip':'192.0.2.2','password':''})[0],403)
            self.assertEqual(self.operator.request('discover',{'ip':'192.0.2.8','password':'supplied-secret'})[0],403)
            self.assertEqual(self.operator.request('discover',{'server_id':self.ids[0],'ip':'192.0.2.99','password':'supplied-secret'})[0],403)
            connection.assert_not_called();discover.assert_not_called()
        for path in ['servers/delete-preview','servers/delete','users','settings','import/preview','catalogs','updates/check']:
            self.assertEqual(self.operator.request(path,{})[0],403,path)
        self.assertEqual(self.operator.request('metrics/refresh',{'id':self.ids[1]})[0],403)
    def test_operator_creation_classification_and_atomic_scope_failures(self):
        self.assertEqual(self.operator.request('servers',{'name':'no-group'})[0],403)
        self.assertEqual(self.operator.request('servers',{'name':'outside','organization':{'group_ids':[self.groups[1]]}})[0],403)
        status,created=self.operator.request('servers',{'name':'within','organization':{'group_ids':[self.groups[0]]}});self.assertEqual(status,200)
        row=next(v for v in self.operator.request('servers')[1] if v['id']==self.ids[0]);row['name']='Updated by operator'
        self.assertEqual(self.operator.request('servers',row)[0],200)
        row['ip']='192.0.2.100'
        self.assertEqual(self.operator.request('servers',row)[0],403)
        row['ssh']={'username':'ssh-test','port':22,'password':'fresh-destination-password','enabled':True}
        self.assertEqual(self.operator.request('servers',row)[0],200)
        row['organization']['application_ids']=[self.app];self.assertEqual(self.operator.request('servers',row)[0],403)
        row['id']=self.ids[1];self.assertEqual(self.operator.request('servers',row)[0],403)
        shared=next(v for v in self.operator.request('servers')[1] if v['id']==self.ids[2]);shared['organization']['group_ids']=[self.groups[0]]
        self.assertEqual(self.operator.request('servers',shared)[0],403)
        self.assertEqual(len(self.admin.request('servers')[1]),5)
    def test_revocation_closes_sessions_and_rechecks_old_bulk_preview(self):
        status,preview=self.operator.request('organization/preview',{'ids':[self.ids[0]],'changes':{'owner_id':None}});self.assertEqual(status,200)
        user=dict(self.users['operator'],group_ids=[])
        self.assertEqual(self.admin.request('users',user)[0],200)
        self.assertEqual(self.operator.request('servers')[0],401)
        self.assertEqual(self.operator.login('operator')[0],200)
        self.assertEqual(self.operator.request('organization/commit',{'token':preview['token']})[0],403)
        self.assertEqual(self.operator.request('servers')[1],[])
    def test_disable_password_reset_and_last_admin_guard(self):
        self.assertEqual(self.admin.request('users',dict(self.users['admin'],active=False))[0],409)
        self.assertEqual(self.admin.request('users',dict(self.users['admin'],role='reader'))[0],409)
        self.assertEqual(self.admin.request('users',dict(self.users['reader'],active=False))[0],200)
        self.assertEqual(self.reader.request('servers')[0],401);self.assertEqual(self.reader.login('reader')[0],401)
        new_password='different-enterprise-password'
        self.assertEqual(self.admin.request('users',dict(self.users['reader'],active=True,password=new_password))[0],200)
        self.assertEqual(self.reader.login('reader')[0],401);self.assertEqual(self.reader.login('reader',new_password)[0],200)
    def test_concurrent_last_admin_changes_leave_one_active_admin(self):
        status,other=self.admin.request('users',{'username':'second-admin','password':PASSWORD,'role':'admin','active':True,'group_ids':[]});self.assertEqual(status,200)
        second=self.client('second-admin');results=[]
        def change(client,user):results.append(client.request('users',dict(user,role='reader'))[0])
        threads=[threading.Thread(target=change,args=(self.admin,self.users['admin'])),threading.Thread(target=change,args=(second,other['user']))]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sorted(results),[200,409])
        with server.db() as c:self.assertEqual(c.execute("SELECT count(*) FROM users WHERE role='admin' AND active=1").fetchone()[0],1)
    def test_audit_before_after_secret_redaction_and_immutability(self):
        status,result=self.admin.request('servers',{'name':'Audited server','ssh':{'username':'new-user','password':'do-not-log-this-password','port':22,'enabled':True}});self.assertEqual(status,200)
        status,page=self.admin.request('audit');self.assertEqual(status,200)
        event=next(r for r in page['records'] if r['event']=='servers.create');self.assertNotIn('details',event)
        status,detail=self.admin.request('audit/'+str(event['id']));self.assertEqual(status,200);self.assertEqual(detail['actor_username'],'admin');self.assertEqual(detail['details']['after']['name'],'Audited server');self.assertTrue(detail['details']['password_changed'])
        with server.db() as c:
            audit_log.record(c,None,'test.redaction',{'password':'hidden','nested':{'TOKEN':'hidden','safe':1}})
            raw=' '.join(r[0]+r[1] for r in c.execute('SELECT action,details FROM audit'))
            for secret in ['do-not-log-this-password','never-log-ssh-secret','hidden',PASSWORD,self.admin.csrf]:self.assertNotIn(secret,raw)
            with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM audit')
            with self.assertRaises(sqlite3.IntegrityError):c.execute("UPDATE audit SET outcome='success'")
        status,page=self.admin.request('audit?limit=2');self.assertEqual(len(page['records']),2);self.assertIsNotNone(page['next_before']);self.assertLess(self.admin.request('audit?limit=2&before='+str(page['next_before']))[1]['records'][0]['id'],page['records'][-1]['id'])
    def test_large_import_audits_every_affected_server(self):
        records=[{'data':validate({'name':'import-'+str(i),'uuid':'import-uuid-'+str(i)})} for i in range(501)]
        with server.db() as c:
            c.execute('INSERT INTO imports(token,user_id,payload,expires) VALUES(?,?,?,?)',('large-import',self.users['admin']['id'],json.dumps({'records':records,'errors':[]}),time.time()+60))
        status,result=self.admin.request('import/commit',{'token':'large-import'})
        self.assertEqual(status,200);self.assertEqual(result['created'],501)
        with server.db() as c:
            events=[json.loads(row[0]) for row in c.execute("SELECT details FROM audit WHERE event='inventory.import' ORDER BY id")]
        self.assertEqual(len(events),6)
        self.assertEqual(len({sid for event in events for sid in event['ids']}),501)
        self.assertEqual(sum(len(event['records']) for event in events),501)
    def test_catalog_cannot_delete_authorization_group(self):
        self.assertEqual(self.admin.request('users',dict(self.users['reader'],group_ids=[self.groups[2]]))[0],200)
        self.assertEqual(self.admin.request('catalogs',{'kind':'groups','action':'delete','id':self.groups[2]})[0],409)
    def test_update_check_is_admin_only_and_network_error_is_audited(self):
        with patch('updates.check',side_effect=updates.UpdateError('Sin red')) as check:
            self.assertEqual(self.reader.request('updates/check',{})[0],403);check.assert_not_called()
            self.assertEqual(self.admin.request('updates/check',{})[0],503);check.assert_called_once()
        self.assertTrue(any(r['event']=='updates.check' and r['outcome']=='failure' for r in self.admin.request('audit')[1]['records']))
    def test_backup_restores_database_and_credential_key(self):
        backup=create_backup(server.DATA,server.KEY_FILE,Path(self.temp.name)/'backup')
        self.assertEqual((backup/'credentials.key').stat().st_mode&0o777,0o600)
        with sqlite3.connect(backup/'database.sqlite3') as c:
            secret=c.execute('SELECT secret FROM server_credentials LIMIT 1').fetchone()[0]
        self.assertEqual(decrypt(secret,backup/'credentials.key'),'never-log-ssh-secret')
        with self.assertRaises(FileExistsError):create_backup(server.DATA,server.KEY_FILE,backup)

class UpdatesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'VERSION').write_text('v0.5.0\n')
    def tearDown(self):self.temp.cleanup()
    def release(self,tag='v0.6.0'):
        return {'tag_name':tag,'draft':False,'prerelease':False,'assets':[{'name':name} for name in ['q-inv-'+tag+'.tar.gz','SHA256SUMS','install.sh']]}
    def check(self,payload):
        with patch('updates.build_opener') as opener:
            opener.return_value.open.return_value=io.BytesIO(json.dumps(payload).encode())
            result=updates.check(self.root)
            args=opener.return_value.open.call_args;self.assertEqual(args.kwargs['timeout'],8);self.assertEqual(args.args[0].full_url,updates.API)
            return result
    def test_stable_version_and_fixed_update_urls(self):
        result=self.check(self.release());self.assertTrue(result['available']);self.assertIn('/v0.6.0/install.sh',result['update_command']);self.assertIn('q-inv-admin --backup',result['backup_command'])
        self.assertFalse(self.check(self.release('v0.4.9'))['available']);self.assertIsNone(self.check(self.release('v0.4.9'))['update_command'])
        self.assertGreater(updates.version('v0.10.0'),updates.version('v0.9.99'))
    def test_reject_unstable_incomplete_malformed_or_injected_release(self):
        for tag in ['v1.0.0;sh','v1.0.0-beta','v01.2.3','../../evil',None]:
            with self.assertRaises(updates.UpdateError):self.check(self.release(tag) if tag else {'tag_name':None,'draft':False,'prerelease':False})
        for field in ['draft','prerelease']:
            release=self.release();release[field]=True
            with self.assertRaises(updates.UpdateError):self.check(release)
        release=self.release();release['assets']=[]
        with self.assertRaises(updates.UpdateError):self.check(release)
    def test_policy_and_size_limit_no_network_when_disabled(self):
        with patch.dict(os.environ,{'QINV_UPDATE_CHECKS':'0'}),patch('updates.build_opener') as opener:
            with self.assertRaises(updates.UpdateError):updates.check(self.root)
            opener.assert_not_called()
        with patch('updates.build_opener') as opener:
            opener.return_value.open.return_value=io.BytesIO(b'x'*(512*1024+1))
            with self.assertRaises(updates.UpdateError):updates.check(self.root)

class LegacyMigrationTests(unittest.TestCase):
    def test_existing_accounts_become_admin_without_password_change(self):
        with tempfile.TemporaryDirectory() as folder:
            old=(server.DATA,server.KEY_FILE);server.DATA=Path(folder)/'data';server.DATA.mkdir();server.KEY_FILE=Path(folder)/'key'
            try:
                with sqlite3.connect(server.DATA/'inventory.sqlite3') as c:
                    c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,salt TEXT,password TEXT)');c.execute("INSERT INTO users VALUES(1,'legacy','00000000000000000000000000000000','existing-hash')")
                server.init();server.init()
                with server.db() as c:
                    row=c.execute('SELECT * FROM users WHERE id=1').fetchone();self.assertEqual(row['role'],'admin');self.assertEqual(row['active'],1);self.assertEqual(row['password'],'existing-hash')
                    self.assertEqual(c.execute('SELECT count(*) FROM user_group_access').fetchone()[0],0)
            finally:server.DATA,server.KEY_FILE=old

class SshPolicyTests(unittest.TestCase):
    def test_transport_does_not_negotiate_legacy_rsa_or_sha1_kex(self):
        import socket
        import paramiko
        left,right=socket.socketpair()
        transport=paramiko.Transport(left)
        try:
            options=transport.get_security_options()
            self.assertNotIn('ssh-rsa',options.key_types)
            self.assertTrue('rsa-sha2-256' in options.key_types or 'rsa-sha2-512' in options.key_types)
            self.assertFalse(any(method.endswith('-sha1') for method in options.kex))
        finally:transport.close();right.close()
