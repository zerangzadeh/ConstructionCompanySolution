"""Clone the qualified schema, then run only changed-scope tests."""

import json
import subprocess
import time
from pathlib import Path

B=Path('/srv/bonira');OUT=B/'production-disposition-evidence'
OUT.mkdir(exist_ok=True);__import__('os').chown(OUT,10001,10001)

def run(args):
 p=subprocess.run(args,capture_output=True,text=True)
 if p.returncode:
  (B/'private-logs/gate11-test-failure.txt').write_text(p.stdout+p.stderr)
  raise RuntimeError('Owned test command failed; private output retained')
 return p.stdout

run(['docker','start','bonira-db'])
for _ in range(90):
 if subprocess.run(['docker','exec','bonira-db','pg_isready','-U','bonira_admin'],capture_output=True).returncode==0:break
 time.sleep(1)
for database in ['pe_gate11_20261028_tests','test_pe_gate11_20261028_tests']:
 if (OUT/'APP_TESTS.json').exists():
  assert json.loads((OUT/'APP_TESTS.json').read_text())['failed']!=0
  continue
 run(['docker','exec','bonira-db','createdb','-U','bonira_admin','-O','bonira_app','-T','pe_legacy_20261028_empty',database])
env=dict(line.split('=',1) for line in (B/'secrets/legacy-pre.env').read_text().splitlines() if line)
env['DB_NAME']='pe_gate11_20261028_tests'
path=B/'secrets/gate11-tests.env';path.write_text('\n'.join(k+'='+v for k,v in env.items())+'\n');path.chmod(0o600)
if (OUT/'APP_TESTS.json').exists():
 for name in ['APP_TESTS.json','APP_TESTS.txt']:(OUT/name).rename(OUT/('ATTEMPT_01_'+name))
run(['docker','run','--rm','--network','bonira-pe','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,nosuid,noexec,size=67108864','--env-file',str(path),'-v',str(B/'source-production-disposition')+':/app:ro','-v',str(B/'shared')+':/state','-v',str(B/'public')+':/static','-v',str(B/'pki/ca.crt')+':/tls/ca.crt:ro','-v',str(B/'tools')+':/tools:ro','-v',str(OUT)+':/evidence','bonira-pe-np-runtime:20261027','python','/tools/guest_app_probe.py'])
print('PASS: secure Production checks and affected statutory/operations tests',flush=True)
