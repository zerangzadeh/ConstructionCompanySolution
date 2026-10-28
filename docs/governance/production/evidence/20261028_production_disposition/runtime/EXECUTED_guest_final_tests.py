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

env=dict(line.split('=',1) for line in (B/'secrets/legacy-pre.env').read_text().splitlines() if line)
env['DB_NAME']='pe_gate11_20261028_tests'
path=B/'secrets/gate11-tests.env';path.write_text('\n'.join(k+'='+v for k,v in env.items())+'\n');path.chmod(0o600)
run(['docker','run','--rm','--network','bonira-pe','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,nosuid,noexec,size=67108864','--env-file',str(path),'-v',str(B/'source-production-disposition')+':/app:ro','-v',str(B/'shared')+':/state','-v',str(B/'public')+':/static','-v',str(B/'pki/ca.crt')+':/tls/ca.crt:ro','-v',str(B/'tools')+':/tools:ro','-v',str(OUT)+':/evidence','bonira-pe-np-runtime:20261027','python','/tools/guest_app_probe.py'])
print('PASS: secure Production checks and affected statutory/operations tests',flush=True)
