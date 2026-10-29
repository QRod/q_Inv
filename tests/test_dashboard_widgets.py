import copy,json,time,unittest
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,lifecycle,dashboard_widgets as widgets
import test_enterprise as enterprise

class LifecycleTests(unittest.TestCase):
 def test_legacy_and_current_versions_and_no_contract_assumption(self):
  today=date(2026,10,29)
  for text in ['RHEL 5','Red Hat Enterprise Linux Server release 6.10','RHEL 7.9','Windows Server 2012 R2','AIX 7.1','Solaris 11.3']:
   with self.subTest(text=text):self.assertEqual(lifecycle.assess(text,today=today)['status'],'expired')
  self.assertEqual(lifecycle.assess('Windows Server 2016',today=today)['status'],'ending')
  self.assertEqual(lifecycle.assess('RHEL 8.10',today=today)['status'],'active')
  self.assertEqual(lifecycle.assess('RHEL 8.4',today=today)['status'],'unknown')
  self.assertEqual(lifecycle.assess('RHEL 9.8',today=today)['status'],'unknown')
 def test_ambiguous_and_unidentified_versions_are_never_inferred(self):
  for text in ['Microsoft Windows Server 2016 or later (64-bit)','Linux 5.11','SunOS 5.11','AIX 7','Ubuntu MATE 22.04','Kubuntu 24.04','Zorin OS 18','Rocky Linux 9','']:
   with self.subTest(text=text):self.assertEqual(lifecycle.assess(text,today=date(2026,10,29))['status'],'unknown')
  self.assertEqual(lifecycle.assess('Microsoft Windows Server 2016 or later')['version'],'')
 def test_aix_technology_level_and_month_precision(self):
  today=date(2026,10,29)
  for text in ['AIX 7.3 TL2','IBM AIX 7.3 Technology Level 2','7300-02-05-2633']:
   assessment=lifecycle.assess(text,today=today);self.assertEqual(assessment['status'],'ending');self.assertEqual(assessment['end'],'2026-11-30');self.assertIn('Technology',assessment['basis'])
  self.assertEqual(lifecycle.assess('AIX 7.3',today=today)['status'],'unknown')
  self.assertEqual(lifecycle.assess('AIX 7.2 TL5',today=today)['status'],'unknown')
  result=lifecycle.assess('Ubuntu 24.04.3 LTS',today=today);self.assertEqual(result['date_precision'],'month');self.assertEqual(result['end'],'2029-05');self.assertEqual(result['status'],'active')
  self.assertEqual(lifecycle.assess('Ubuntu 24.04',today=date(2029,5,15))['status'],'unknown')
  self.assertEqual(lifecycle.assess('Oracle Solaris 11.4',today=today)['end'],'2031-11')

class DashboardWidgetApiTests(unittest.TestCase):
 setUp=enterprise.EnterpriseApiTests.setUp
 tearDown=enterprise.EnterpriseApiTests.tearDown
 client=enterprise.EnterpriseApiTests.client
 def config(self,**changes):return dict(copy.deepcopy(widgets.DEFAULT),**changes)
 def save(self,client,config,revision=0):return client.request('dashboard/preferences',{'revision':revision,'config':config})
 def test_counts_and_sources_respect_scope_before_aggregation(self):
  with server.db() as c:
   c.execute('UPDATE servers SET os=? WHERE id=?',('RHEL 5',self.ids[0]));c.execute('UPDATE servers SET os=? WHERE id=?',('SecretOS 99',self.ids[1]))
  status,data=self.reader.request('dashboard/widgets');self.assertEqual(status,200);self.assertEqual(data['scope_count'],2);self.assertEqual(sum(v['count'] for v in data['os_distribution']),2)
  raw=json.dumps(data,ensure_ascii=False);self.assertNotIn('SecretOS',raw);self.assertNotIn('Aplicación privada B',raw);self.assertEqual(data['support_lifecycle']['counts']['expired'],1)
  self.assertTrue(all(s['id'] in {self.ids[0],self.ids[2]} for s in data['support_lifecycle']['rows']))
  self.assertEqual(self.admin.request('dashboard/widgets')[1]['scope_count'],4)
 def test_reader_can_only_save_own_ui_preferences_and_revisions(self):
  config=self.config(widgets=['inventory_quality','os_distribution'],show_servers=False,group_id=self.groups[0],cpu_threshold=90)
  status,saved=self.save(self.reader,config);self.assertEqual(status,200);self.assertEqual(saved['revision'],1)
  self.assertEqual(self.reader.request('dashboard/widgets')[1]['config'],config)
  self.assertEqual(self.admin.request('dashboard/widgets')[1]['revision'],0)
  self.assertEqual(self.save(self.reader,self.config(),0)[0],409)
  self.assertEqual(self.reader.request('servers',{'name':'forbidden'})[0],403)
  self.assertEqual(self.reader.request('dashboard/preferences',{'revision':1,'config':config,'user_id':self.users['admin']['id']})[0],400)
  self.assertEqual(self.save(self.reader,self.config(group_id=self.groups[1]),1)[0],403)
  with server.db() as c:self.assertEqual(c.execute("SELECT count(*) FROM audit WHERE event='dashboard.preferences'").fetchone()[0],1)
 def test_invalid_configuration_has_no_side_effects(self):
  for change in [{'widgets':['anything']},{'widgets':[{}]},{'widgets':['os_distribution']*2},{'cpu_threshold':True},{'memory_threshold':101},{'show_servers':1},{'os_grouping':'sql'},{'environment_id':'1'},{'support_horizon':1}]:
   status,_=self.save(self.admin,self.config(**change));self.assertIn(status,[400,403]);self.assertEqual(self.admin.request('dashboard/widgets')[1]['revision'],0)
 def test_group_revocation_sanitizes_filters_without_leaking_names(self):
  self.assertEqual(self.save(self.reader,self.config(group_id=self.groups[0]))[0],200)
  with server.db() as c:c.execute('DELETE FROM user_group_access WHERE user_id=?',(self.users['reader']['id'],))
  status,data=self.reader.request('dashboard/widgets');self.assertEqual(status,200);self.assertEqual(data['scope_count'],0);self.assertTrue(data['adjusted']);self.assertIsNone(data['config']['group_id']);self.assertEqual(data['os_distribution'],[])
 def test_fresh_metrics_only_and_shared_app_capacity_not_double_counted(self):
  with server.db() as c:
   for sid,when,value in [(self.ids[0],time.time()-5,90),(self.ids[1],time.time()-5000,99),(self.ids[2],time.time()-5,0)]:
    c.execute('INSERT INTO metrics(server_id,collected_at,status,payload) VALUES(?,?,?,?)',(sid,when,'online',json.dumps({'cpu_percent':value,'memory_percent':None,'disk_percent':70})))
   import organization
   app=organization.catalog_command(c,{'kind':'applications','name':'Segunda app'})['id']
   organization.assign(c,self.ids[0],{'group_ids':[self.groups[0]],'application_ids':[self.app,app]})
  data=self.admin.request('dashboard/widgets')[1]
  self.assertEqual(data['resource_pressure']['affected_ids'],[self.ids[0]])
  shared=next(row for row in data['allocated_capacity'] if row['label']=='Compartidos (varias aplicaciones)');self.assertEqual(shared['ids'],[self.ids[0]])
  self.assertEqual(sum(row['count'] for row in data['allocated_capacity']),4)
  self.assertEqual(sum(row['virtual_cpu'] for row in data['allocated_capacity']),sum((s['cpu'] or 0) for s in self.admin.request('servers')[1] if s['kind']=='virtual'))
 def test_configuration_survives_restart_and_scope_filters_apply(self):
  self.assertEqual(self.save(self.admin,self.config(group_id=self.groups[1],server_type='virtual',widgets=[]))[0],200)
  server.init();data=self.admin.request('dashboard/widgets')[1];self.assertEqual(data['scope_count'],2);self.assertEqual(data['config']['widgets'],[])

if __name__=='__main__':unittest.main()
