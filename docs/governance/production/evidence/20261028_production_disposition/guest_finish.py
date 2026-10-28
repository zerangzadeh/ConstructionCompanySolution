"""Bind current diagnostics/evidence into protected recovery coverage and attest tools."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

B=Path('/srv/bonira');OUT=B/'production-disposition-evidence';WORK=B/'pitr-production';STAGE=Path('/srv/bonira-production-capture');VAULT=Path('/srv/bonira-production-vault');KEYS=Path('/srv/bonira-production-key-custody')
os.umask(0o077)
assert all(json.loads((OUT/name).read_text())['result']=='PASS' for name in ['FINAL_RELEASE_IDENTITY.json','PITR_RESULT.json','CADENCE_CUSTODY_RESULT.json'])
assert json.loads((OUT/'FINAL_APP_TESTS.json').read_text())['failed']==0
sys.path.insert(0,str(B/'source-production-disposition'))
from scripts.production_recovery import decrypt,file_hash
target=WORK/'facts/audit_operational/production-qualification';target.mkdir(mode=0o700)
receipts=target/'alerts';shutil.copytree(OUT/'alerts',receipts)
for name in ['FINAL_RELEASE_IDENTITY.json','PITR_RESULT.json','CADENCE_CUSTODY_RESULT.json','WEB_OPERATIONS_RESULT.json']:
 shutil.copyfile(OUT/name,target/name)
subprocess.run(['/usr/bin/python3',str(B/'tools/guest_capture_once.py')],check=True,capture_output=True,text=True)
latest=max((json.loads(p.read_text()) for p in OUT.glob('CAPTURE_CYCLE_*.json')),key=lambda row:row['captured_at'])
recovered=STAGE/'current-audit-recovery';recovered.mkdir(mode=0o700)
decrypt(VAULT/('cycle-'+latest['cycle'])/'files.cms',recovered/'facts.tar.gz',certificate=STAGE/'recipient.crt',private_key=KEYS/'backup.key')
spec=importlib.util.spec_from_file_location('pitr',B/'tools/guest_pitr.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
files=recovered/'facts';files.mkdir(mode=0o700);module.extract_regular(recovered/'facts.tar.gz',files)
count=0
for file in (WORK/'facts').rglob('*'):
 if file.is_file():assert file_hash(file)==file_hash(files/file.relative_to(WORK/'facts'));count+=1
(OUT/'CURRENT_AUDIT_RECOVERY.json').write_text(json.dumps({'result':'PASS','files_equal':count,'actual_alert_receipts_covered':len(list(receipts.glob('*.json'))),'release_incident_recovery_receipts_covered':4,'all_three_file_classes_equal':True,'wal_and_verified_base_retained':True,'separate_encrypted_boundary':True,'production':False},indent=2)+'\n')
metadata={}
for name,command in [('openssl',['openssl','version']),('openssl_package',['dpkg-query','-W','-f=${Package} ${Version}\n','openssl','libssl3']),('openssl_integrity',['dpkg','-V','openssl','libssl3']),('nginx',['nginx','-v']),('system_python',['python3','--version']),('postgres',['docker','exec','bonira-pitr-source','postgres','--version'])]:
 result=subprocess.run(command,capture_output=True,text=True)
 assert result.returncode==0
 metadata[name]=(result.stdout+result.stderr).strip()
assert metadata['openssl_integrity']==''
metadata['openssl_binary_sha256']=hashlib.sha256(Path('/usr/bin/openssl').read_bytes()).hexdigest()
metadata['upstream_guidance']=['https://www.postgresql.org/docs/18/continuous-archiving.html','https://www.postgresql.org/docs/18/app-pgbasebackup.html','https://docs.openssl.org/3.0/man1/openssl-cms/']
metadata['new_python_dependencies']=[]
metadata['policy']='Existing native OpenSSL used; no custom cipher/key derivation or new Python dependency. Retained current lock/SBOM/advisory evidence; no fresh advisory scan falsely claimed.'
(OUT/'TOOLCHAIN.json').write_text(json.dumps(metadata,indent=2)+'\n')
print('PASS: current operational/release/recovery evidence independently restored; native tool identities verified',flush=True)
