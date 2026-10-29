import json
from pathlib import Path
import sys,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import history,server
import test_enterprise as enterprise
from inventory import ValidationError

class HistoryTests(unittest.TestCase):
    setUp=enterprise.EnterpriseApiTests.setUp
    tearDown=enterprise.EnterpriseApiTests.tearDown
    client=enterprise.EnterpriseApiTests.client
    def add(self,when,payload,status='online',sid=None):
        with server.db() as c:c.execute('INSERT INTO metrics(server_id,collected_at,status,payload,error) VALUES(?,?,?,?,?)',(self.ids[0] if sid is None else sid,when,status,json.dumps(payload),'SSH no disponible' if status!='online' else None))
    def test_current_detail_and_history_respect_groups_without_credentials(self):
        self.add(time.time()-10,{'cpu_percent':0,'memory_percent':50})
        status,result=self.reader.request('servers/'+str(self.ids[0]));self.assertEqual(status,200);self.assertEqual(result['current']['state'],'online');self.assertEqual(result['current']['metrics']['cpu_percent'],0)
        self.assertEqual(result['server']['organization']['group_ids'],[self.groups[0]])
        for key in ['password','secret','salt','ssh_username','ssh_port']:self.assertNotIn(key,result['server'])
        self.assertEqual(self.reader.request('servers/'+str(self.ids[0])+'/history')[0],200)
        for sid in [self.ids[1],self.ids[3],999999]:
            for suffix in ['', '/history']:self.assertEqual(self.reader.request('servers/'+str(sid)+suffix)[0],403)
        public=enterprise.Client(self.url);self.assertEqual(public.request('servers/'+str(self.ids[0])+'/history')[0],401)
    def test_zero_maximum_gaps_failed_samples_and_partial_buckets(self):
        end=time.time();start=end-3600
        self.add(start+1,{'cpu_percent':0,'net_rx_bps':0});self.add(start+2,{'cpu_percent':100,'net_rx_bps':200})
        self.add(start+3,{'cpu_percent':99},'error');self.add(start+601,{},'error')
        with server.db() as c:result=history.read(c,self.ids[0],{'from':[str(start)],'to':[str(end)]},now=end)
        self.assertEqual(result['samples'],4);self.assertEqual(result['successful'],2);self.assertEqual(result['failed'],2);self.assertEqual(result['success_percent'],50)
        first=result['points'][0];self.assertEqual(first['values']['cpu_percent'],50);self.assertEqual(first['maxima']['cpu_percent'],100);self.assertEqual(first['values']['net_rx_bps'],100);self.assertEqual(first['failed'],1)
        self.assertIsNone(result['points'][1]['values']['cpu_percent']);self.assertEqual(result['points'][1]['samples'],0)
        self.assertEqual(result['points'][2]['failed'],1);self.assertIsNone(result['points'][2]['values']['cpu_percent'])
    def test_bounded_series_keeps_peaks_and_filters_invalid_values(self):
        end=time.time();self.add(end-1,{'cpu_percent':101,'memory_percent':-1,'disk_percent':True,'net_tx_bps':'123','net_rx_bps':1e300})
        with server.db() as c:result=history.read(c,self.ids[0],{'hours':['1440']},now=end)
        self.assertLessEqual(len(result['points']),720);self.assertEqual(result['samples'],1)
        last=next(p for p in result['points'] if p['samples']);self.assertTrue(all(v is None for v in last['values'].values()))
    def test_empty_and_failed_only_are_not_zero_usage_or_uptime(self):
        with server.db() as c:empty=history.read(c,self.ids[0],{})
        self.assertEqual(empty['samples'],0);self.assertIsNone(empty['success_percent']);self.assertTrue(all(p['values']['cpu_percent'] is None for p in empty['points']))
        self.add(time.time()-1,{},'error')
        status,failed=self.reader.request('servers/'+str(self.ids[0])+'/history');self.assertEqual(status,200);self.assertEqual(failed['success_percent'],0);self.assertEqual(failed['failed'],1)
    def test_invalid_custom_ranges_and_retention_are_enforced(self):
        now=time.time()
        for query in [{'hours':['NaN']},{'hours':['0']},{'hours':['24','48']},{'hours':['-1']},{'hours':['999999999']},{'from':[str(now)],'to':[str(now-60)]},{'to':[str(now+1000)]},{'from':['']}]:
            with self.subTest(query=query),server.db() as c:
                with self.assertRaises(ValidationError):history.read(c,self.ids[0],query,now=now)
        with server.db() as c:
            c.execute('UPDATE settings SET retention_days=2');result=history.read(c,self.ids[0],{'hours':['1440']},now=now)
        self.assertEqual(result['from'],now-2*86400);self.assertLess(result['requested_from'],result['from'])
        self.assertEqual(self.reader.request('servers/'+str(self.ids[0])+'/history?hours=NaN')[0],400)
    def test_targeted_snapshot_and_time_index(self):
        self.add(time.time()-1,{'cpu_percent':19});self.add(time.time()-1,{'cpu_percent':88},sid=self.ids[1])
        snapshot=self.admin.request('servers/'+str(self.ids[0]))[1];self.assertEqual(snapshot['current']['metrics']['cpu_percent'],19)
        with server.db() as c:
            indexes={row['name'] for row in c.execute('PRAGMA index_list(metrics)')};self.assertIn('metrics_server_time',indexes)
            server.init()
            self.assertEqual(c.execute('SELECT count(*) FROM metrics').fetchone()[0],2)

if __name__=='__main__':unittest.main()
