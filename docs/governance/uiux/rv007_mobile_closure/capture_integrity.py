import sys, json, hashlib, subprocess
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / 'docs/governance/uiux/rv007_controlled_time'))
from support import guard, snapshot, REAL_NOW
from django.db import connection, transaction
out = root / 'docs/governance/uiux/rv007_mobile_closure'
prior = root / 'docs/governance/uiux/rv007_controlled_time'
guard()
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
    data = snapshot()
old = json.loads((prior / 'DATA_AFTER.json').read_text())
drift = {}
for label in old:
    if old[label] != data[label]:
        drift[label] = {kind: ids for kind, ids in {
            'added': sorted(set(data[label]) - set(old[label])),
            'deleted': sorted(set(old[label]) - set(data[label])),
            'modified': sorted(k for k in old[label].keys() & data[label].keys() if old[label][k] != data[label][k])
        }.items() if ids}
entry = json.loads((prior / 'ENTRY.json').read_text())
files = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in entry['hashes'] if (root/p).is_file()}
changed = [p for p in entry['hashes'] if files.get(p) != entry['hashes'][p]]
record = {'recorded_at': str(REAL_NOW()), 'head': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), 'branch': subprocess.check_output(['git','branch','--show-current'],text=True).strip(), 'origin_main': subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip(), 'index_sha256': hashlib.sha256((root/'.git/index').read_bytes()).hexdigest(), 'hashes': files, 'prior_entry_changed_files': changed, 'prior_data_drift': drift, 'status': subprocess.check_output(['git','status','--short'],text=True), 'database_guard': 'Development loopback PostgreSQL construction_erp; migrations current; snapshot read-only transaction'}
(out/'ENTRY.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
(out/'DATA_BEFORE.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps({'prior_entry_changed_files': changed, 'prior_data_drift': {k:{t:len(v) for t,v in d.items()} for k,d in drift.items()}, 'head_unchanged': record['head']==entry['head'], 'index_unchanged': record['index_sha256']==entry['index_sha256']}))
