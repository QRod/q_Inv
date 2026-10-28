import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request,build_opener,HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import organization as org
from inventory import validate
from monitoring import configure
from test_inventory import fixture

class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.old_data,self.old_key=server.DATA,server.KEY_FILE
        server.DATA=root/'data';server.KEY_FILE=root/'key';server.init()
        with server.db() as c:
            self.entries={}
            for kind,names in [('groups',['Infraestructura','Web']),('applications',['ERP','Portal']),('owners',['Operaciones','Aplicaciones']),('tags',['Crítico','Compartido'])]:
                self.entries[kind]=[org.catalog_command(c,{'kind':kind,'name':name,'contact':'ops@example.test' if kind=='owners' else ''})['id'] for name in names]
            self.entries['environments']=[row['id'] for row in org.catalogs(c)['environments']]
            self.ids=[server.save_server(c,validate({'name':name,'uuid':'uuid-'+str(i),'ip':'192.0.2.'+str(i+1)}),'manual') for i,name in enumerate(['srv-web','srv-db','srv-app'])]
            configure(c,self.ids[0],{'username':'reader','password':'organization-test-secret','enabled':True},server.KEY_FILE)
            c.execute('INSERT INTO metrics(server_id,collected_at,status,error,payload) VALUES(?,?,?,?,?)',(self.ids[0],time.time(),'online',None,'{"cpu_percent":20}'))
    def tearDown(self):
        server.DATA,server.KEY_FILE=self.old_data,self.old_key;self.temp.cleanup()
    def classification(self,c,sid):return org.hydrate(c,c.execute('SELECT * FROM servers WHERE id=?',(sid,)).fetchall())[0]
    def test_multi_assignment_catalog_counts_and_safe_rename(self):
        with server.db() as c:
            changes={'group_ids':self.entries['groups'],'application_ids':self.entries['applications'],'tag_ids':self.entries['tags'],'environment_id':self.entries['environments'][0],'owner_id':self.entries['owners'][0]}
            org.assign(c,self.ids[0],changes)
            data=self.classification(c,self.ids[0]);self.assertEqual(len(data['groups']),2);self.assertEqual(len(data['applications']),2)
            self.assertEqual(data['owner']['contact'],'ops@example.test')
            eid=self.entries['groups'][0]
            org.catalog_command(c,{'kind':'groups','id':eid,'name':'Infra compartida'})
            data=self.classification(c,self.ids[0]);self.assertIn('Infra compartida',[entry['name'] for entry in data['groups']])
            self.assertEqual(data['group_name'],'Infra compartida')
            with self.assertRaises(org.OrganizationError) as err:org.catalog_command(c,{'kind':'groups','id':eid,'action':'delete'})
            self.assertEqual(err.exception.status,409)
            self.assertEqual(next(e for e in org.catalogs(c)['groups'] if e['id']==eid)['server_count'],1)
            with self.assertRaises(org.OrganizationError):org.catalog_command(c,{'kind':'groups','name':'INFRA COMPARTIDA'})
    def test_cross_kind_validation_and_partial_updates(self):
        with server.db() as c:
            org.assign(c,self.ids[0],{'group_ids':self.entries['groups'],'owner_id':self.entries['owners'][0]})
            with self.assertRaises(org.OrganizationError):org.assign(c,self.ids[0],{'group_ids':[],'environment_id':self.entries['groups'][0]})
            self.assertEqual(len(self.classification(c,self.ids[0])['groups']),2)
            org.assign(c,self.ids[0],{'owner_id':None})
            self.assertIsNone(self.classification(c,self.ids[0])['owner'])
            self.assertEqual(len(self.classification(c,self.ids[0])['groups']),2)
            for changes in [{'group_ids':[True]}, {'tag_ids':'text'}, {'environment_id':-1},{'owner_id':[1]},{'name':'not allowed'}]:
                with self.assertRaises(org.OrganizationError):org.assign(c,self.ids[0],changes)
    def test_bulk_preview_commit_preserves_credentials_metrics_and_source(self):
        with server.db() as c:
            before=tuple(c.execute('SELECT secret,revision,next_due FROM server_credentials').fetchone())
            preview=org.preview_bulk(c,1,{'ids':self.ids[:2],'changes':{'group_ids':self.entries['groups'],'environment_id':self.entries['environments'][0]}})
            self.assertEqual(preview['changed'],2);self.assertEqual(self.classification(c,self.ids[0])['groups'],[])
            self.assertEqual(org.commit_bulk(c,1,preview['token']),{'updated':2,'selected':2})
            self.assertEqual(before,tuple(c.execute('SELECT secret,revision,next_due FROM server_credentials').fetchone()))
            self.assertEqual(c.execute('SELECT count(*) FROM metrics').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT source FROM servers WHERE id=?',(self.ids[0],)).fetchone()[0],'manual')
            with self.assertRaises(org.OrganizationError):org.commit_bulk(c,1,preview['token'])
            noop=org.preview_bulk(c,1,{'ids':self.ids[:2],'changes':{'group_ids':list(reversed(self.entries['groups']))}})
            self.assertEqual(noop['changed'],0)
            self.assertEqual(org.commit_bulk(c,1,noop['token'])['updated'],0)
            clear=org.preview_bulk(c,1,{'ids':self.ids[:2],'changes':{'group_ids':[]}})
            org.commit_bulk(c,1,clear['token'])
            self.assertEqual(self.classification(c,self.ids[0])['groups'],[])
            self.assertIsNotNone(self.classification(c,self.ids[0])['environment'])
    def test_bulk_rejects_stale_membership_and_target_catalog_names(self):
        with server.db() as c:
            changes={'group_ids':[self.entries['groups'][0]]}
            pending=org.preview_bulk(c,1,{'ids':self.ids,'changes':changes})
            org.assign(c,self.ids[1],{'tag_ids':[self.entries['tags'][0]]})
            with self.assertRaises(org.OrganizationError) as err:org.commit_bulk(c,1,pending['token'])
            self.assertEqual(err.exception.status,409)
            self.assertEqual(self.classification(c,self.ids[0])['groups'],[])
            pending=org.preview_bulk(c,1,{'ids':self.ids,'changes':changes})
            org.catalog_command(c,{'kind':'groups','id':self.entries['groups'][0],'name':'Nombre cambiado'})
            with self.assertRaises(org.OrganizationError):org.commit_bulk(c,1,pending['token'])
            self.assertEqual(self.classification(c,self.ids[0])['groups'],[])
    def test_preview_owner_expiry_missing_server_and_input_limits(self):
        with server.db() as c:
            pending=org.preview_bulk(c,1,{'ids':self.ids,'changes':{'owner_id':self.entries['owners'][0]}})
            with self.assertRaises(org.OrganizationError):org.commit_bulk(c,2,pending['token'])
            c.execute('UPDATE bulk_previews SET expires=0')
            with self.assertRaises(org.OrganizationError):org.commit_bulk(c,1,pending['token'])
            for ids in [[],[True],self.ids+[9999],list(range(1,502))]:
                with self.assertRaises(org.OrganizationError):org.preview_bulk(c,1,{'ids':ids,'changes':{'tag_ids':[]}})
    def test_legacy_client_keeps_unmodified_multiple_memberships(self):
        with server.db() as c:
            org.assign(c,self.ids[0],{'group_ids':self.entries['groups']})
            old=c.execute('SELECT * FROM servers WHERE id=?',(self.ids[0],)).fetchone()
            org.save_classification(c,self.ids[0],{'name':'renamed','group_name':old['group_name']},old)
            self.assertEqual(len(self.classification(c,self.ids[0])['groups']),2)
            org.save_classification(c,self.ids[0],{'group_name':'Base de datos'},old)
            self.assertEqual([e['name'] for e in self.classification(c,self.ids[0])['groups']],['Base de datos'])

class LegacyMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_ids_assignments_secrets_and_default_deletions(self):
        old_data,old_key=server.DATA,server.KEY_FILE
        try:
            with tempfile.TemporaryDirectory() as folder:
                server.DATA=Path(folder)/'data';server.KEY_FILE=Path(folder)/'key'
                with patch('server.organization.migrate',return_value=None):server.init()
                with server.db() as c:
                    sid=server.save_server(c,validate({'name':'legacy','uuid':'stable-id','group_name':'Infraestructura','application':'ERP'}),'rvtools')
                    configure(c,sid,{'username':'reader','password':'migration-secret'},server.KEY_FILE)
                    secret=c.execute('SELECT secret FROM server_credentials').fetchone()[0]
                    second=server.save_server(c,validate({'name':'legacy2','group_name':'infraestructura','application':'ERP'}),'manual')
                    third=server.save_server(c,validate({'name':'legacy3','group_name':'Línea 1\nLínea 2'}),'manual')
                server.init()
                with server.db() as c:
                    rows=org.hydrate(c,c.execute('SELECT * FROM servers ORDER BY id').fetchall())
                    self.assertEqual([row['id'] for row in rows],[sid,second,third])
                    self.assertEqual(rows[0]['uuid'],'stable-id');self.assertEqual(rows[0]['groups'][0]['name'],'Infraestructura')
                    self.assertEqual(rows[0]['groups'][0]['id'],rows[1]['groups'][0]['id']);self.assertEqual(rows[0]['applications'][0]['name'],'ERP');self.assertEqual(rows[2]['groups'][0]['name'],'Línea 1\nLínea 2')
                    self.assertIsNone(rows[0]['environment']);self.assertEqual(rows[0]['tags'],[])
                    self.assertEqual(secret,c.execute('SELECT secret FROM server_credentials').fetchone()[0])
                    deleted=org.catalogs(c)['environments'][0]['id'];org.catalog_command(c,{'kind':'environments','id':deleted,'action':'delete'})
                server.init()
                with server.db() as c:self.assertEqual(len(org.catalogs(c)['environments']),2)
        finally:server.DATA,server.KEY_FILE=old_data,old_key

class OrganizationApiTests(unittest.TestCase):
    def test_auth_catalog_bulk_and_reimport_end_to_end(self):
        old_data,old_key=server.DATA,server.KEY_FILE
        try:
            with tempfile.TemporaryDirectory() as folder:
                server.DATA=Path(folder)/'data';server.KEY_FILE=Path(folder)/'key';server.init()
                salt='00'*16
                with server.db() as c:c.execute('INSERT INTO users(username,salt,password) VALUES(?,?,?)',('qa',salt,server.password_hash('organization-qa',salt)))
                http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
                client=build_opener(HTTPCookieProcessor(CookieJar()));base=f'http://127.0.0.1:{http.server_port}/api/'
                def request(path,data=None,csrf='',raw=False):
                    req=Request(base+path,data=data if raw else json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/octet-stream' if raw else 'application/json','X-CSRF-Token':csrf})
                    with client.open(req) as response:return json.load(response)
                try:
                    with self.assertRaises(HTTPError) as err:request('catalogs')
                    self.assertEqual(err.exception.code,401)
                    csrf=request('login',{'username':'qa','password':'organization-qa'})['csrf']
                    with self.assertRaises(HTTPError) as err:request('catalogs',{'kind':'groups','name':'No CSRF'})
                    self.assertEqual(err.exception.code,403)
                    ids={}
                    for kind in org.KINDS:ids[kind]=request('catalogs',{'kind':kind,'name':'API '+kind},csrf)['id']
                    imported=request('import/preview',fixture(),csrf,True);request('import/commit',{'token':imported['token']},csrf)
                    row=request('servers')[0]
                    row['organization']={'group_ids':[ids['groups']],'application_ids':[ids['applications']],'tag_ids':[ids['tags']],'environment_id':ids['environments'],'owner_id':ids['owners']}
                    request('servers',row,csrf)
                    imported=request('import/preview',fixture(),csrf,True);request('import/commit',{'token':imported['token']},csrf)
                    again=request('servers')[0];self.assertEqual(again['organization'],row['organization']);self.assertEqual(again['groups'][0]['name'],'API groups')
                    dash=request('dashboard')['servers'][0];self.assertEqual(dash['organization'],row['organization'])
                    with self.assertRaises(HTTPError) as err:request('catalogs',{'kind':'groups','id':ids['groups'],'action':'delete'},csrf)
                    self.assertEqual(err.exception.code,409)
                    preview=request('organization/preview',{'ids':[row['id']],'changes':{'group_ids':[]}},csrf)
                    request('organization/commit',{'token':preview['token']},csrf)
                    self.assertEqual(request('servers')[0]['groups'],[])
                    request('catalogs',{'kind':'groups','id':ids['groups'],'action':'delete'},csrf)
                    self.assertTrue(all('secret' not in item and 'password' not in item for item in request('servers')))
                finally:http.shutdown();http.server_close();thread.join()
        finally:server.DATA,server.KEY_FILE=old_data,old_key

if __name__=='__main__':unittest.main()
