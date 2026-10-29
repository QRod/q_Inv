import io
import json
from pathlib import Path
import sys
import unittest
from urllib.request import Request
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook
from inventory import parse_rvtools,ValidationError
from network_inventory import addresses,validate_interfaces
import network_inventory
import server
import test_enterprise as enterprise

HEADERS=['VM','VM UUID','NIC label','Adapter','Network','Switch','MAC Address','Connected','Starts Connected','IPv4 Address','IPv6 Address']
ROWS=[['demo','u-1','Network adapter 1','Vmxnet3','Frontend','demo-switch','00:50:56:00:00:01',True,True,'192.0.2.10, 192.0.2.11','2001:db8::10'],['demo','u-1','Network adapter 2','Vmxnet3','Backend','demo-switch','00-50-56-00-00-02',False,False,'198.51.100.10;198.51.100.11','fe80::1']]

def workbook(network=ROWS,network_headers=HEADERS,vms=None,extra_info=None):
    book=Workbook();info=book.active;info.title='vInfo'
    info.append(['VM','VM UUID','Primary IP Address','CPUs','Memory','Provisioned MiB']+list((extra_info or {}).keys()))
    for row in vms or [['demo','u-1','192.0.2.10',4,8192,102400]]:info.append(row+list((extra_info or {}).values()))
    if network is not None:
        sheet=book.create_sheet('vNetwork');sheet.append(network_headers)
        for row in network:sheet.append(row)
    stream=io.BytesIO();book.save(stream);book.close();return stream.getvalue()

class NetworkParserTests(unittest.TestCase):
    def test_all_nics_addresses_states_and_canonical_mac(self):
        rows,errors=parse_rvtools(workbook());self.assertEqual(errors,[])
        nics=rows[0]['data']['network_interfaces'];self.assertEqual(len(nics),2)
        self.assertEqual(nics[0]['ip_addresses'],['192.0.2.10','192.0.2.11','2001:db8::10'])
        self.assertEqual(nics[1]['ip_addresses'],['198.51.100.10','198.51.100.11','fe80::1'])
        self.assertFalse(nics[1]['connected']);self.assertFalse(nics[1]['starts_connected']);self.assertEqual(nics[1]['mac_address'],'00:50:56:00:00:02')
        self.assertEqual(rows[0]['data']['ip'],'192.0.2.10')
    def test_legacy_combined_ip_column_unique_name_fallback_and_missing_ip(self):
        rows,errors=parse_rvtools(workbook(network_headers=['VM','NIC label','MAC Address','IP Address','Connected'],network=[['demo','NIC 1','00:50:56:00:00:01','192.0.2.1; 2001:db8::1; 192.0.2.1','True'],['demo','NIC 2','00:50:56:00:00:02','unknown','False']]))
        self.assertEqual(errors,[]);nics=rows[0]['data']['network_interfaces'];self.assertEqual(nics[0]['ip_addresses'],['192.0.2.1','2001:db8::1']);self.assertEqual(nics[1]['ip_addresses'],[])
    def test_uuid_prevents_same_name_cross_vm_association(self):
        vms=[['same','id-a','192.0.2.1',1,1024,1024],['same','id-b','192.0.2.2',1,1024,1024]]
        rows,errors=parse_rvtools(workbook(vms=vms,network=[['same','id-b','NIC 1','Vmxnet3','Red B','','00:50:56:00:00:02',True,True,'198.51.100.2','']]))
        self.assertEqual(errors,[]);self.assertEqual(rows[0]['data']['network_interfaces'],[]);self.assertEqual(rows[1]['data']['network_interfaces'][0]['network'],'Red B')
        _,errors=parse_rvtools(workbook(vms=vms,network_headers=['VM','NIC label','IP Address'],network=[['same','NIC 1','192.0.2.1']]))
        self.assertEqual(errors[0]['sheet'],'vNetwork');self.assertIn('ambiguo',errors[0]['error'])
    def test_uuid_mismatch_cannot_fall_back_to_name(self):
        _,errors=parse_rvtools(workbook(network=[['demo','wrong-uuid','NIC 1','Vmxnet3','Red','','00:50:56:00:00:01',True,True,'192.0.2.1','']]))
        self.assertIn('no coincide',errors[0]['error'])
    def test_no_network_sheet_preserves_missing_vs_authoritative_empty(self):
        rows,errors=parse_rvtools(workbook(network=None));self.assertEqual(errors,[]);self.assertNotIn('network_interfaces',rows[0]['data'])
        rows,errors=parse_rvtools(workbook(network=[]));self.assertEqual(rows[0]['data']['network_interfaces'],[])
        rows,errors=parse_rvtools(workbook(network=None,extra_info={'NIC #1':'192.0.2.1;2001:db8::1','NIC #2':'198.51.100.1'}));self.assertEqual(errors,[]);self.assertEqual(len(rows[0]['data']['network_interfaces']),2)
    def test_duplicate_rows_merge_ips_without_duplicate_nics(self):
        row=ROWS[0][:];row[-2]='192.0.2.99'
        rows,errors=parse_rvtools(workbook(network=[ROWS[0],row]));self.assertEqual(errors,[]);self.assertEqual(len(rows[0]['data']['network_interfaces']),1);self.assertIn('192.0.2.99',rows[0]['data']['network_interfaces'][0]['ip_addresses'])
        rows,errors=parse_rvtools(workbook(network_headers=['VM','MAC Address','IP Address'],network=[['demo','00:50:56:00:00:01','192.0.2.1'],['demo','00:50:56:00:00:01','192.0.2.2']]))
        self.assertEqual(errors,[]);self.assertEqual(len(rows[0]['data']['network_interfaces']),1)
    def test_invalid_network_blocks_preview_and_bounded_payloads(self):
        for field,value in [(6,'bad-mac'),(9,'192.0.2.999'),(7,'perhaps')]:
            row=ROWS[0][:];row[field]=value;_,errors=parse_rvtools(workbook(network=[row]));self.assertEqual(errors[0]['sheet'],'vNetwork')
        _,errors=parse_rvtools(workbook(network_headers=['unrecognized'],network=[]));self.assertTrue(errors)
        with self.assertRaises(ValidationError):validate_interfaces([{}]*129)
        with self.assertRaises(ValidationError):addresses(';'.join('192.0.2.'+str(i) for i in range(1,130)))
    def test_ip_normalization_and_untrusted_labels_are_text(self):
        self.assertEqual(addresses('2001:0db8:0:0::1;192.0.2.1/24\n2001:db8::1'),['2001:db8::1','192.0.2.1'])
        self.assertEqual(network_inventory.all_addresses('2001:0db8::1','2001:db8::1',[]),['2001:db8::1'])
        row=ROWS[0][:];row[4]='<img src=x onerror=alert(1)>'
        records,errors=parse_rvtools(workbook(network=[row]));self.assertEqual(errors,[]);self.assertEqual(records[0]['data']['network_interfaces'][0]['network'],row[4])

class NetworkApiTests(unittest.TestCase):
    setUp=enterprise.EnterpriseApiTests.setUp
    tearDown=enterprise.EnterpriseApiTests.tearDown
    client=enterprise.EnterpriseApiTests.client
    def preview(self,raw):
        request=Request(self.url+'/api/import/preview',data=raw,headers={'Content-Type':'application/octet-stream','X-CSRF-Token':self.admin.csrf})
        with self.admin.opener.open(request) as response:return json.load(response)
    def test_roundtrip_scope_reimport_manual_edit_and_ssh_target(self):
        vms=[['server-0','uuid-0','192.0.2.77',4,8192,102400]]
        nics=[['server-0','uuid-0',*ROWS[0][2:]],['server-0','uuid-0',*ROWS[1][2:]]]
        preview=self.preview(workbook(vms=vms,network=nics));self.assertTrue(preview['records'][0]['connection_ip_preserved']);self.assertEqual(preview['records'][0]['connection_ip'],'192.0.2.1')
        self.assertEqual(self.admin.request('import/commit',{'token':preview['token']})[0],200)
        row=next(s for s in self.reader.request('servers')[1] if s['id']==self.ids[0]);self.assertEqual(len(row['network_interfaces']),2);self.assertEqual(row['ip'],'192.0.2.1');self.assertEqual(row['reported_primary_ip'],'192.0.2.77');self.assertIn('2001:db8::10',row['ip_addresses']);self.assertIn('192.0.2.77',row['ip_addresses'])
        self.assertEqual({s['id'] for s in self.reader.request('servers')[1]},{self.ids[0],self.ids[2]})
        row['name']='Edited';self.assertEqual(self.operator.request('servers',row)[0],200)
        self.assertEqual(len(self.reader.request('servers')[1][0]['network_interfaces']),2)
        preview=self.preview(workbook(vms=vms,network=nics[:1]));self.assertEqual(self.admin.request('import/commit',{'token':preview['token']})[0],200)
        rows=self.reader.request('servers')[1];row=next(s for s in rows if s['id']==self.ids[0]);self.assertEqual(len(row['network_interfaces']),1);self.assertNotIn('198.51.100.10',row['ip_addresses'])
        preview=self.preview(workbook(vms=vms,network=None));self.assertEqual(self.admin.request('import/commit',{'token':preview['token']})[0],200)
        row=next(s for s in self.reader.request('servers')[1] if s['id']==self.ids[0]);self.assertEqual(len(row['network_interfaces']),1)
        dashboard=next(s for s in self.reader.request('dashboard')[1]['servers'] if s['id']==self.ids[0]);self.assertEqual(dashboard['network_interfaces'],row['network_interfaces'])
        with server.db() as c:
            details=json.loads(c.execute("SELECT details FROM audit WHERE event='inventory.import' ORDER BY id DESC LIMIT 1").fetchone()[0]);self.assertTrue(details['records'][0]['after']['network_interfaces'])
    def test_invalid_network_import_is_atomic_and_delete_cascades(self):
        preview=self.preview(workbook());self.assertEqual(self.admin.request('import/commit',{'token':preview['token']})[0],200)
        row=next(s for s in self.admin.request('servers')[1] if s['uuid']=='u-1');sid=row['id']
        bad=ROWS[0][:];bad[-2]='bad-ip';preview=self.preview(workbook(network=[bad]));self.assertTrue(preview['errors']);self.assertEqual(self.admin.request('import/commit',{'token':preview['token']})[0],400)
        self.assertEqual(next(s for s in self.admin.request('servers')[1] if s['id']==sid)['network_interfaces'],row['network_interfaces'])
        status,preview=self.admin.request('servers/delete-preview',{'ids':[sid]});self.assertEqual(status,200)
        with server.db() as c:network_inventory.save(c,sid,[],row['ip'])
        self.assertEqual(self.admin.request('servers/delete',{'token':preview['token'],'confirmed':True})[0],409)
        status,preview=self.admin.request('servers/delete-preview',{'ids':[sid]});self.assertEqual(status,200)
        self.assertEqual(self.admin.request('servers/delete',{'token':preview['token'],'confirmed':True})[0],200)
        with server.db() as c:self.assertIsNone(c.execute('SELECT * FROM server_networks WHERE server_id=?',(sid,)).fetchone())

if __name__=='__main__':unittest.main()
