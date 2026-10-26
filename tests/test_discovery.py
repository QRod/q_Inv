from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import discovery
from inventory import ValidationError

LINUX='''QINV_SYSTEM=Linux
QINV_NAME=app01
QINV_OS=Red Hat Enterprise Linux 8
QINV_CPU=8
QINV_RAM_KIB=16777216
QINV_DISK_BYTES=107374182400
QINV_UUID=ABC-123
QINV_KIND=virtual
QINV_ROOT_KIB=52428800
QINV_END=1
'''

class DiscoveryTests(unittest.TestCase):
    def test_linux_units_and_identity(self):
        result=discovery.parse_output(LINUX,'192.0.2.10');data=result['data']
        self.assertEqual(data['cpu'],8);self.assertEqual(data['ram_gb'],16);self.assertEqual(data['disk_gb'],100)
        self.assertEqual(data['uuid'],'abc-123');self.assertEqual(data['ip'],'192.0.2.10')
        self.assertNotIn('password',data);self.assertNotIn('host',data)
    def test_unix_fallback_and_missing_data(self):
        aix=discovery.parse_output('QINV_SYSTEM=AIX\nQINV_NAME=aix01\nQINV_CPU=4\nQINV_RAM_KIB=8388608\nQINV_DISK_MIB=204800\nQINV_END=1','192.0.2.1')
        self.assertEqual(aix['data']['disk_gb'],200);self.assertEqual(aix['data']['ram_gb'],8)
        sun=discovery.parse_output('QINV_SYSTEM=SunOS\nQINV_NAME=sun01\nQINV_RAM_MIB=4096\nQINV_ROOT_KIB=10485760\nQINV_END=1','192.0.2.2')
        self.assertEqual(sun['data']['ram_gb'],4);self.assertEqual(sun['data']['disk_gb'],10)
        self.assertTrue(any('raíz' in w for w in sun['warnings']))
        self.assertNotIn('uuid',sun['data']);self.assertNotIn('kind',sun['data'])
    def test_incomplete_unsupported_and_invalid_numbers(self):
        with self.assertRaises(ValidationError):discovery.parse_output('QINV_SYSTEM=Linux','192.0.2.1')
        with self.assertRaises(ValidationError):discovery.parse_output('QINV_SYSTEM=Windows\nQINV_END=1','192.0.2.1')
        result=discovery.parse_output('QINV_SYSTEM=Linux\nQINV_CPU=nan\nQINV_RAM_KIB=-1\nQINV_END=1','192.0.2.1')
        self.assertNotIn('cpu',result['data']);self.assertNotIn('ram_gb',result['data'])
    def test_invalid_target_never_connects(self):
        with patch('discovery.paramiko.SSHClient') as client:
            for payload in [dict(ip='127.0.0.1'),dict(ip='1.2.3.4; reboot'),dict(ip='192.0.2.1',port=0),dict(ip='192.0.2.1',username='x')]:
                with self.assertRaises(ValidationError):discovery.discover(payload,Path('/tmp/unused-known-hosts'))
            client.assert_not_called()
    def test_host_fingerprint_confirmation_and_rejection(self):
        key=discovery.paramiko.RSAKey.generate(2048)
        with self.assertRaises(discovery.HostConfirmation):discovery.VerifyHost(None).missing_host_key(None,'host',key)
        class Client:
            def __init__(self):self.keys=discovery.paramiko.HostKeys()
            def get_host_keys(self):return self.keys
        client=Client();policy=discovery.VerifyHost(discovery.fingerprint(key));policy.missing_host_key(client,'host',key)
        self.assertEqual(client.keys['host']['ssh-rsa'],key)
    def test_credentials_are_transient_and_host_key_persists(self):
        key=discovery.paramiko.RSAKey.generate(2048)
        class Channel:
            def __init__(self):self.output=LINUX.encode()
            def recv_ready(self):return bool(self.output)
            def recv(self,size):out=self.output;self.output=b'';return out
            def recv_stderr_ready(self):return False
            def exit_status_ready(self):return True
        class Client:
            def __init__(self):self.keys=discovery.paramiko.HostKeys();self.closed=False
            def set_missing_host_key_policy(self,policy):self.policy=policy
            def get_host_keys(self):return self.keys
            def connect(self,hostname,**kwargs):
                self.connection=kwargs
                self.policy.missing_host_key(self,hostname,key)
            def exec_command(self,command,**kwargs):
                self.command=command
                stdout=type('Output',(),{'channel':Channel()})()
                return None,stdout,None
            def close(self):self.closed=True
        with tempfile.TemporaryDirectory() as folder:
            known=Path(folder)/'known';payload={'ip':'192.0.2.1','username':'reader','password':'transient-secret'}
            client=Client()
            with patch('discovery.paramiko.SSHClient',return_value=client):
                result=discovery.discover(payload,known)
            self.assertTrue(result['host_confirmation']);self.assertFalse(known.exists());self.assertTrue(client.closed)
            payload['fingerprint']=result['fingerprint'];client=Client()
            with patch('discovery.paramiko.SSHClient',return_value=client):result=discovery.discover(payload,known)
            self.assertEqual(result['data']['name'],'app01');self.assertNotIn(payload['password'],known.read_text());self.assertNotIn(payload['password'],str(result));self.assertNotIn(payload['password'],client.command)
            self.assertFalse(client.connection['allow_agent']);self.assertFalse(client.connection['look_for_keys']);self.assertTrue(client.closed)

if __name__=='__main__':unittest.main()
