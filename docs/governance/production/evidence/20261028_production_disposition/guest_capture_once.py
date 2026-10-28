"""One OS-managed protected four-class capture; no purge or business mutation."""
import fcntl
import json
import os
import subprocess
import sys
import tarfile
import time
from datetime import UTC,datetime,timedelta
from pathlib import Path
from uuid import uuid4

B=Path('/srv/bonira');WORK=B/'pitr-production';VAULT=Path('/srv/bonira-production-vault');STAGE=Path('/srv/bonira-production-capture');OUT=B/'production-disposition-evidence'
sys.path.insert(0,str(B/'source-production-disposition'))
from scripts.production_recovery import encrypt
from core.production_operations import ProductionOperationsSink
os.umask(0o077)
sink=ProductionOperationsSink(OUT/'alerts',environment='production-equivalent-qualification')
with (WORK/'capture.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 started=datetime.now(UTC);ident=uuid4().hex
 try:
  def sql(query):
   p=subprocess.run(['docker','exec','-i','bonira-pitr-source','psql','-X','-v','ON_ERROR_STOP=1','-U','bonira_admin','-d','pe_gate11_20261028','-At'],input=query,capture_output=True,text=True)
   if p.returncode:raise RuntimeError('Capture database probe failed')
   return p.stdout.strip()
  # Force a complete WAL segment for a bounded archiver/custody-lag measurement.
  filename=sql('SELECT pg_walfile_name(pg_current_wal_lsn());')
  sql('SELECT pg_switch_wal();')
  for _ in range(90):
   if (WORK/'wal-spool'/filename).exists():break
   time.sleep(1)
  else:raise RuntimeError('WAL archiver did not deliver the complete segment')
  destination=VAULT/('cycle-'+ident);destination.mkdir(mode=0o700)
  captures={}
  for file in sorted((WORK/'wal-spool').iterdir()):
   captures[file.name]=encrypt(file,destination/(file.name+'.cms'),certificate=STAGE/'recipient.crt')
  archive=STAGE/('facts-'+ident+'.tar.gz')
  with tarfile.open(archive,'w:gz') as tar:
   for klass in ['document_media','configuration_metadata','audit_operational']:
    tar.add(WORK/'facts'/klass,arcname=klass)
  captures['files']=encrypt(archive,destination/'files.cms',certificate=STAGE/'recipient.crt')
  finished=datetime.now(UTC)
  record={'result':'PASS','cycle':ident,'started_at':started.isoformat(),'captured_at':finished.isoformat(),'protection_lag_seconds':(finished-started).total_seconds(),'rpo_limit_seconds':900,'required_segment':filename,'captures':captures,'classes':['PostgreSQL WAL plus retained verified base','document_media','configuration_metadata','audit_operational'],'retain_until':(finished+timedelta(days=30)).isoformat(),'restore_acceptance_due':(finished+timedelta(days=30)).isoformat(),'purge_authorized':False,'production':False}
  assert record['protection_lag_seconds']<=900
  (destination/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
  with (destination/'receipt.json').open('rb') as stream:os.fsync(stream.fileno())
  (OUT/('CAPTURE_CYCLE_'+ident+'.json')).write_text(json.dumps(record,indent=2)+'\n')
 except Exception:
  sink.write(signal='backup.failed',request_id=str(uuid4()))
  raise
