"""Generate a fully synthetic RVTools-shaped workbook for a first import."""
from pathlib import Path
from openpyxl import Workbook

out = Path(__file__).resolve().parents[1] / 'examples' / 'RVTools-demo.xlsx'
out.parent.mkdir(exist_ok=True)
book = Workbook()
sheet = book.active
sheet.title = 'vInfo'
sheet.append(['VM', 'VM UUID', 'CPUs', 'Memory', 'Provisioned MiB', 'Primary IP Address', 'Host', 'Cluster', 'OS', 'Powerstate'])
for i, (name, system, cpu, ram) in enumerate([
    ('demo-web-01', 'RHEL 8', 4, 8192),
    ('demo-db-01', 'RHEL 7', 8, 32768),
    ('demo-app-01', 'Windows Server', 4, 16384),
], 1):
    sheet.append([name, f'00000000-0000-4000-8000-{i:012}', cpu, ram, 102400, f'192.0.2.{i}', 'demo-host-01', 'demo-cluster', system, 'poweredOn'])
network=book.create_sheet('vNetwork')
network.append(['VM','VM UUID','NIC label','Adapter','Network','Switch','MAC Address','Connected','Starts Connected','IPv4 Address','IPv6 Address'])
for i,name in enumerate(['demo-web-01','demo-db-01','demo-app-01'],1):
 for nic in range(1,3):
  network.append([name,f'00000000-0000-4000-8000-{i:012}',f'Network adapter {nic}','Vmxnet3',f'demo-network-{nic}','demo-switch',f'00:50:56:00:{i:02x}:{nic:02x}',True,True,f'{"192.0.2" if nic==1 else "198.51.100"}.{i}',f'2001:db8:{i}:{nic}::1'])
book.save(out)
print(out)
