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
book.save(out)
print(out)
