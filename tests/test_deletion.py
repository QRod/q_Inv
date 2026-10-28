import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,build_opener,HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar
import server
import deletion
import organization as org
from inventory import validate
from monitoring import Monitor,configure
import test_organization as fixtures

class DeletionTests(unittest.TestCase):
    setUp=fixtures.OrganizationTests.setUp
    tearDown=fixtures.OrganizationTests.tearDown
    def test_delete_cascades_selected_only_and_keeps_catalogs(self):
        with server.db() as c:
            org.assign(c,self.ids[0],{'group_ids':self.entries['groups']})
            count=c.execute('SELECT count(*) FROM catalog_entries').fetchone()[0]
            preview=deletion.preview(c,1,{'ids':self.ids[:2]})
            self.assertEqual(c.execute('SELECT count(*) FROM servers').fetchone()[0],3)
            self.assertTrue(preview['records'][0]['has_credentials'])
            self.assertEqual(preview['records'][0]['metric_samples'],1)
            self.assertEqual(deletion.commit(c,1,{'token':preview['token'],'confirmed':True})['deleted'],2)
            self.assertEqual([r[0] for r in c.execute('SELECT id FROM servers')],[self.ids[2]])
            for table in ['server_credentials','metrics','server_classification']:
                self.assertEqual(c.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM catalog_entries').fetchone()[0],count)
            action=c.execute('SELECT action FROM audit ORDER BY id DESC LIMIT 1').fetchone()[0]
            self.assertNotIn('secret',action);self.assertIn('servers.delete',action)
    def test_confirmation_expiry_owner_and_reuse(self):
        with server.db() as c:
            preview=deletion.preview(c,1,{'ids':self.ids})
            for payload in [{'ids':self.ids,'confirmed':True},{'token':preview['token']},{'token':preview['token'],'confirmed':'true'}]:
                with self.assertRaises(org.OrganizationError):deletion.commit(c,1,payload)
            with self.assertRaises(org.OrganizationError):deletion.commit(c,2,{'token':preview['token'],'confirmed':True})
            c.execute('UPDATE deletion_previews SET expires=0')
            with self.assertRaises(org.OrganizationError):deletion.commit(c,1,{'token':preview['token'],'confirmed':True})
            self.assertEqual(c.execute('SELECT count(*) FROM servers').fetchone()[0],3)
            preview=deletion.preview(c,1,{'ids':self.ids})
            deletion.commit(c,1,{'token':preview['token'],'confirmed':True})
            with self.assertRaises(org.OrganizationError):deletion.commit(c,1,{'token':preview['token'],'confirmed':True})
        server.init()
        with server.db() as c:
            new_id=server.save_server(c,validate({'name':'new-server'}),'manual')
            self.assertGreater(new_id,max(self.ids))
    def test_concurrent_server_or_credentials_edit_rejects_whole_delete(self):
        with server.db() as c:
            preview=deletion.preview(c,1,{'ids':self.ids})
            c.execute('UPDATE servers SET cpu=32 WHERE id=?',(self.ids[0],))
            with self.assertRaises(org.OrganizationError):deletion.commit(c,1,{'token':preview['token'],'confirmed':True})
            self.assertEqual(c.execute('SELECT count(*) FROM servers').fetchone()[0],3)
            preview=deletion.preview(c,1,{'ids':self.ids})
            configure(c,self.ids[0],{'username':'reader','password':'replacement-qa'},server.KEY_FILE)
            with self.assertRaises(org.OrganizationError):deletion.commit(c,1,{'token':preview['token'],'confirmed':True})
            preview=deletion.preview(c,1,{'ids':self.ids})
            c.execute('DELETE FROM servers WHERE id=?',(self.ids[-1],))
            with self.assertRaises(org.OrganizationError):deletion.commit(c,1,{'token':preview['token'],'confirmed':True})
            self.assertEqual(c.execute('SELECT count(*) FROM servers').fetchone()[0],2)
    def test_inflight_collection_cannot_resurrect_deleted_or_write_to_new_server(self):
        sid=self.ids[-1]
        with server.db() as c:configure(c,sid,{'username':'reader','password':'collection-qa'},server.KEY_FILE)
        monitor=Monitor(server.db,server.DATA,server.KEY_FILE)
        created=[]
        def finish_after_delete(*args,**kwargs):
            with server.db() as c:
                preview=deletion.preview(c,1,{'ids':[sid]});deletion.commit(c,1,{'token':preview['token'],'confirmed':True})
                new_id=server.save_server(c,validate({'name':'srv-app','uuid':'uuid-2','ip':'192.0.2.3'}),'manual')
                configure(c,new_id,{'username':'reader','password':'new-qa'},server.KEY_FILE);created.append(new_id)
            return {'data':{'cpu_percent':99}}
        try:
            with patch('monitoring.discover',side_effect=finish_after_delete):monitor.collect({'id':sid,'ip':'192.0.2.3','revision':1})
            self.assertGreater(created[0],sid)
            with server.db() as c:
                self.assertIsNone(c.execute('SELECT 1 FROM servers WHERE id=?',(sid,)).fetchone())
                self.assertEqual(c.execute('SELECT count(*) FROM metrics WHERE server_id=?',(created[0],)).fetchone()[0],0)
        finally:monitor.pool.shutdown(wait=True)
    def test_api_auth_csrf_and_delete_flow(self):
        salt='00'*16
        with server.db() as c:c.execute('INSERT INTO users(username,salt,password) VALUES(?,?,?)',('qa',salt,server.password_hash('deletion-qa-password',salt)))
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        client=build_opener(HTTPCookieProcessor(CookieJar()));base=f'http://127.0.0.1:{http.server_port}/api/'
        def post(path,data,csrf=''):
            request=Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':csrf})
            with client.open(request) as response:return json.load(response)
        try:
            with self.assertRaises(HTTPError) as err:post('servers/delete-preview',{'ids':self.ids})
            self.assertEqual(err.exception.code,401)
            csrf=post('login',{'username':'qa','password':'deletion-qa-password'})['csrf']
            with self.assertRaises(HTTPError) as err:post('servers/delete-preview',{'ids':self.ids})
            self.assertEqual(err.exception.code,403)
            for ids in [[],[True],[99999],list(range(1,502))]:
                with self.assertRaises(HTTPError):post('servers/delete-preview',{'ids':ids},csrf)
            preview=post('servers/delete-preview',{'ids':self.ids},csrf)
            self.assertNotIn('password',json.dumps(preview));self.assertNotIn('organization-test-secret',json.dumps(preview))
            with self.assertRaises(HTTPError):post('servers/delete',{'token':preview['token'],'confirmed':False},csrf)
            self.assertEqual(post('servers/delete',{'token':preview['token'],'confirmed':True},csrf)['deleted'],3)
        finally:http.shutdown();http.server_close();thread.join()

if __name__=='__main__':unittest.main()
