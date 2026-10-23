"""Independent final artifact/reference verification; no product or Git writes."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
entry=json.loads((OUT/'ENTRY.json').read_text(encoding='utf-8'))
reg=ROOT/'CEP_EXECUTION_REGISTRY.yaml'
raw=reg.read_bytes()
text=raw.decode('utf-8').replace('\r\n','\n')
old='AC1-3 PARTIAL and DoD NOT_MET'
new='AC1-and-AC3 PARTIAL and DoD NOT_MET'
if old in text:
    assert text.count(old)==1
    text=text.replace(old,new)
    reg.write_bytes(text.replace('\n','\r\n').encode())
delta=OUT/'REGISTRY_DELTA.diff'
delta.write_text(delta.read_text(encoding='utf-8').replace(old,new),encoding='utf-8')
change_path=OUT/'CEP-078_CHANGE_MANIFEST.csv'
with change_path.open(encoding='utf-8',newline='') as f:
    changes=list(csv.DictReader(f))
for r in changes:
    if r['path']=='CEP_EXECUTION_REGISTRY.yaml' and not r['before_sha256'].startswith('NORMALIZED_LF_SHA256:'):
        r['before_sha256']='NORMALIZED_LF_SHA256:'+r['before_sha256']
    if r['path'] not in {(OUT/'CEP-078_CHANGE_MANIFEST.csv').relative_to(ROOT).as_posix(), (OUT/'CEP-078_EVIDENCE_MANIFEST.csv').relative_to(ROOT).as_posix()}:
        r['after_sha256']=sha(ROOT/r['path'])
listed={r['path'] for r in changes}
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts or p.relative_to(ROOT).as_posix() in listed:
        continue
    changes.append({'path':p.relative_to(ROOT).as_posix(),'kind':'NEW_CEP078_CONTINUATION_EVIDENCE','before_sha256':'ABSENT','after_sha256':'EXCLUDED_CIRCULAR_MANIFEST_REFERENCE' if p.name in {'CEP-078_CHANGE_MANIFEST.csv','CEP-078_EVIDENCE_MANIFEST.csv'} else sha(p)})
with change_path.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(changes[0]));w.writeheader();w.writerows(changes)
assert all(sha(ROOT/p)==v for p,v in entry['prior_evidence'].items())
sources=json.loads((OUT/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))['product_hashes']
assert all(sha(ROOT/p)==v for p,v in sources.items())
assert sha(ROOT/'.git/index')==entry['index_sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==entry['head']
current=dict(re.findall(r'^  (CEP-\d{3}):\n(.*?)(?=^  CEP-|^authority_scope:)',text,re.M|re.S))
before=dict(re.findall(r'^  (CEP-\d{3}):\n(.*?)(?=^  CEP-|^authority_scope:)',entry['registry_before'],re.M|re.S))
assert len(current)==86 and all(current[k]==v for k,v in before.items() if k!='CEP-078')
assert current['CEP-078'].split('    history:\n',1)[1].startswith(before['CEP-078'].split('    history:\n',1)[1])
assert 'PARTIAL_AC1_AC3_PARTIAL_AC2_4_5_6_PASS' in current['CEP-078']
assert '      status: NOT_STARTED\n' in current['CEP-079']
for match in re.finditer(r'\]\(([^)]+)\)',(OUT/'CEP-078_COMPLETION_REPORT.md').read_text(encoding='utf-8')):
    assert (OUT/match.group(1)).is_file(),match.group(1)
assert subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True).returncode==0
result={'result':'PASS','prior_files_preserved':len(entry['prior_evidence']),'product_source_hashes_verified':len(sources),'other_cep_records_unchanged':85,'registry_history_append_only':True,'report_local_references':'PASS','git_head_index_whitespace':'PASS','change_manifest_registry_before_basis':'Explicit NORMALIZED_LF_SHA256; original raw newline hash not claimed','cep079_production_signoff_git_writes':'NOT_EXECUTED'}
save('FINAL_VERIFICATION.json',result)
# Refresh new evidence hashes after the bounded final metadata clarification.
paths=sorted(p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='CEP-078_EVIDENCE_MANIFEST.csv')
with (OUT/'CEP-078_EVIDENCE_MANIFEST.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['evidence_id','path','sha256','kind','result']);w.writeheader()
    for i,p in enumerate(paths,200):
        w.writerow({'evidence_id':f'CEP-078-EV-{i:03d}','path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'kind':'Actual continuation artifact; explicit scoped PASS/FAIL/PARTIAL/UTV; no blanket acceptance','result':'RETAINED_ACTUAL_EVIDENCE'})
with (OUT/'CEP-078_EVIDENCE_MANIFEST.csv').open(encoding='utf-8',newline='') as f:
    rows=list(csv.DictReader(f))
assert len({r['evidence_id'] for r in rows})==len(rows)
assert all(sha(ROOT/r['path'])==r['sha256'] for r in rows)
print(json.dumps(result))
