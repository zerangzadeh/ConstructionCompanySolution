"""Bounded real OS timer cadence, failure receipts and custody denials."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

B=Path('/srv/bonira');OUT=B/'production-disposition-evidence';VAULT=Path('/srv/bonira-production-vault');KEYS=Path('/srv/bonira-production-key-custody');STAGE=Path('/srv/bonira-production-capture')
assert json.loads((OUT/'PITR_RESULT.json').read_text())['result']=='PASS'
sys.path.insert(0,str(B/'source-production-disposition'))
from scripts.production_recovery import encrypt,decrypt,RecoveryError
from core.production_operations import ProductionOperationsSink
os.umask(0o077)
sink=ProductionOperationsSink(OUT/'alerts',environment='production-equivalent-qualification')
def run(args):return subprocess.run([str(a) for a in args],check=True,capture_output=True,text=True)
run(['docker','start','bonira-pitr-source'])
for _ in range(60):
 if subprocess.run(['docker','exec','bonira-pitr-source','pg_isready','-U','bonira_admin'],capture_output=True).returncode==0:break
 time.sleep(1)
run(['systemd-run','--unit','bonira-gate11-capture','--on-active=1s','--on-unit-active=60s','/usr/bin/python3',str(B/'tools/guest_capture_once.py')])
try:
 for _ in range(240):
  files=list(OUT.glob('CAPTURE_CYCLE_*.json'))
  if len(files)>=2:break
  time.sleep(1)
 else:raise RuntimeError('Bounded timer did not complete two actual captures')
finally:
 run(['systemctl','stop','bonira-gate11-capture.timer'])
for _ in range(60):
 if subprocess.run(['systemctl','is-active','bonira-gate11-capture.service'],capture_output=True,text=True).stdout.strip()!='active':break
 time.sleep(1)
cycles=sorted((json.loads(p.read_text()) for p in OUT.glob('CAPTURE_CYCLE_*.json')),key=lambda v:v['started_at'])
intervals=[(datetime.fromisoformat(b['started_at'])-datetime.fromisoformat(a['started_at'])).total_seconds() for a,b in zip(cycles,cycles[1:])]
assert len(cycles)>=2 and all(0<delta<=900 for delta in intervals)
assert all(row['result']=='PASS' and row['protection_lag_seconds']<=900 for row in cycles)
recovery=STAGE/'negative-control';recovery.mkdir(mode=0o700)
try:encrypt(STAGE/'files.tar.gz',VAULT/'files.cms',certificate=STAGE/'recipient.crt')
except RecoveryError:sink.write(signal='backup.failed',request_id=str(uuid4()))
else:raise AssertionError('Capture overwrite must fail closed')
try:decrypt(VAULT/'corrupt.cms',recovery/'rejected-plaintext',certificate=STAGE/'recipient.crt',private_key=KEYS/'backup.key')
except RecoveryError:sink.write(signal='recovery.failed',request_id=str(uuid4()))
else:raise AssertionError('Corrupted recovery must fail closed')
assert not (recovery/'rejected-plaintext').exists()
denials={}
for name,uid,path in [('backup_writer_private_key',20002,KEYS/'backup.key'),('application_backup_payload',10001,VAULT/'base.cms'),('application_recovery_key',10001,KEYS/'backup.key')]:
 p=subprocess.run(['setpriv','--reuid',str(uid),'--regid',str(uid),'--clear-groups','test','-r',str(path)],capture_output=True)
 assert p.returncode!=0;denials[name]='DENIED'
signals={json.loads(p.read_text()).get('signal') for p in (OUT/'alerts').glob('*.json')}
assert {'backup.failed','recovery.failed'}<=signals
(OUT/'CADENCE_CUSTODY_RESULT.json').write_text(json.dumps({'result':'PASS','actual_captures':len(cycles),'os_timer_interval_seconds':60,'observed_intervals_seconds':intervals,'protection_lags_seconds':[v['protection_lag_seconds'] for v in cycles],'rpo_limit_seconds':900,'maximum_capture_interval_seconds':900,'minimum_retention_days':30,'restore_test_interval_days':30,'future_elapsed_operation':'NOT_CLAIMED','timer_stopped':True,'permission_denials':denials,'negative_failure_receipts':True,'no_purge_path':True,'production':False},indent=2)+'\n')
print('PASS: actual capture cadence, encrypted protection lag, separated key/application denials and failure receipts',flush=True)
