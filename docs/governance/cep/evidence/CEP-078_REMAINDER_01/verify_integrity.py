"""Focused preservation and truthful closeout checks; no product execution."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'.pytest_cache/cep_tools'))
import yaml

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,default=str).encode()).hexdigest()
entry=json.loads((OUT/'ENTRY.json').read_text(encoding='utf8'))
r=yaml.safe_load((ROOT/'CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf8'))
assert all(digest(r['ceps'][k])==v for k,v in entry['all_other_cep_hashes'].items())
assert r['gates']==entry['gate_state']
assert r['execution_frontier']['next_executable_frontier']==[]
assert r['ceps']['CEP-078']['acceptance']['passed']==4
assert r['ceps']['CEP-078']['history'][:len(entry['cep078_before']['history'])]==entry['cep078_before']['history']
allowed={'CEP_EXECUTION_REGISTRY.yaml','docs/governance/cep/manifests/CEP-078_EXECUTION_MANIFEST.md','docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md','docs/governance/cep/evidence/CEP-078_ACCEPTANCE_MAPPING.csv','docs/governance/cep/evidence/CEP-078_CHANGE_MANIFEST.csv','docs/governance/cep/evidence/CEP-078_EVIDENCE_MANIFEST.csv'}
preserved={}
for p,expected in entry['protected_dirty_and_untracked_files'].items():
    if p.replace('\\','/') in allowed:continue
    assert sha(ROOT/p)==expected,p
    preserved[p]=expected
prompt=ROOT/'docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md'
assert sha(prompt)==entry['prompt_sha']
master=ROOT/'docs/governance/uiux/UIUX_FINDING_CLOSURE_MASTER.yaml'
assert subprocess.check_output(['git','diff','--name-only','--',str(master)],text=True).strip()==''
assert 'List → Detail consistency: RESOLVED' in master.read_text(encoding='utf8')
qualified=json.loads((OUT/'RUNTIME_QUALIFIED.json').read_text(encoding='utf8'))
assert len(qualified['canonicalPass'])==5
assert all(c['result']=='PASS' and c['observedViewport']['width']==c['viewport']['width'] and c['observedViewport']['height']==c['viewport']['height'] for c in qualified['canonicalPass'])
assert qualified['unverified'][0]['result'].startswith('UTV')
projection=json.loads((ROOT/'apps/organizations/reference_personas.json').read_text(encoding='utf8'))
sources={s['path']:yaml.safe_load((ROOT/s['path']).read_text(encoding='utf8')) for s in projection['sources']}
assert all(sha(ROOT/s['path'])==s['sha256'] for s in projection['sources'])
catalogue=list(sources.values())[0];matrix=list(sources.values())[1]
for row,p,shape in zip(projection['personas'],catalogue['personas'],matrix['personas'],strict=True):
    assert row['persona_id']==p['persona_id']==shape['persona_id']
    assert row['documented_readiness']==p['provisioning_status']
    assert row['documented_identity']==p['reconciled_identity']
    assert row['authority_shape']==shape['required_authority_shape']
    assert row['context_requirements']==shape['required_data']
assert len(projection['personas'])==26
assert '7 passed, 8 subtests passed' in (OUT/'FOCUSED_FINAL.txt').read_text(encoding='utf-8-sig')
assert 'All checks passed!' in (OUT/'LINT.txt').read_text(encoding='utf-8-sig')
check=subprocess.run(['git','diff','--check'],capture_output=True,text=True)
assert check.returncode==0,check.stdout
index=json.loads((OUT/'ARTIFACT_INDEX.json').read_text(encoding='utf8'))
index['artifacts']=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in {'ARTIFACT_INDEX.json','INTEGRITY.json'}]
index['current_authoritative_runtime']='RUNTIME_QUALIFIED.json; initial Edge requested-size observations not canonical dimension PASS'
index['canonical_css_pass_cells']=5
index['required_edge390']='UTV; nearest391 not promoted'
(OUT/'ARTIFACT_INDEX.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf8')
manifest=ROOT/'docs/governance/cep/evidence/CEP-078_EVIDENCE_MANIFEST.csv'
with manifest.open(encoding='utf8',newline='') as f:
    reader=csv.DictReader(f);rows=list(reader);fields=reader.fieldnames
for row in rows:
    if row['evidence_id']=='CEP-078-EV-015':row['sha256']=sha(OUT/'ARTIFACT_INDEX.json')
with manifest.open('w',encoding='utf8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
for row in rows:
    if row['evidence_id'] in {'CEP-078-EV-015','CEP-078-EV-016','CEP-078-EV-017'}:assert sha(ROOT/row['path'])==row['sha256']
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result':'PASS','other_ceps_preserved':len(entry['all_other_cep_hashes']),'gates_unchanged':True,'prior_dirty_artifacts_preserved':len(preserved),'prior_cep078_history_preserved':True,'canonical_prompt_sha256':sha(prompt),'uiux_master_sha256':sha(master),'list_detail_consistency':'RESOLVED_UNCHANGED','all26_projection_matches_approved_sources':True,'qualified_css_cells':5,'exact_edge390':'UTV','focused_tests':'7 PASS +8 subtests PASS','lint':'PASS','diff_check':'PASS','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'origin_main':subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),'next_executable_frontier':[]}
(OUT/'INTEGRITY.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps(result))
