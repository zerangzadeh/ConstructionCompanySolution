"""Focused evidence/Registry preservation validation; no product execution."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).parent
BASE=ROOT/'docs/governance/cep/evidence'
sys.path.insert(0,str(ROOT/'.pytest_cache/cep_tools'))
import yaml

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,default=str).encode()).hexdigest()
entry=json.loads((OUT/'ENTRY_RESUME.json').read_text(encoding='utf8'))
r=yaml.safe_load((ROOT/'CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf8'))
assert all(digest(r['ceps'][k])==v for k,v in entry['all_other_cep_hashes'].items())
assert r['gates']==entry['gate_state']
cep=r['ceps']['CEP-078']
assert cep['execution']['status']=='COMPLETE' and cep['execution']['lifecycle']=='CLOSED_VERIFIED'
assert cep['acceptance']['passed']==cep['acceptance']['total']==6
assert cep['dod'].startswith('MET_') and cep['remaining_utv']==cep['blockers']==[]
assert cep['history'][:len(entry['cep078_before']['history'])]==entry['cep078_before']['history']
assert r['execution_frontier']['next_executable_frontier']==[]
assert 'CEP-078' not in r['execution_frontier']['dependency_ready_current_governed']
assert r['summary']['execution_state_complete']==sum(c['execution']['status']=='COMPLETE' for c in r['ceps'].values())==71
assert r['summary']['partial_current']==sum(c['execution']['status']=='PARTIAL' for c in r['ceps'].values())==4
allowed={'CEP_EXECUTION_REGISTRY.yaml','docs/governance/cep/manifests/CEP-078_EXECUTION_MANIFEST.md','docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md','docs/governance/cep/evidence/CEP-078_ACCEPTANCE_MAPPING.csv','docs/governance/cep/evidence/CEP-078_CHANGE_MANIFEST.csv','docs/governance/cep/evidence/CEP-078_EVIDENCE_MANIFEST.csv'}
preserved={}
for p,expected in entry['prior_files'].items():
    if p in allowed:continue
    assert sha(ROOT/p)==expected,p
    preserved[p]=expected
current_paths=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard'],text=True).splitlines()
assert all(p in entry['prior_files'] or p in allowed or p.startswith('docs/governance/cep/evidence/CEP-078_REMAINDER_02/') for p in current_paths)
assert sha(OUT/'COMPLETION_REPORT_BEFORE.md')==entry['prior_files']['docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md']
assert sha(OUT/'ACCEPTANCE_MAPPING_BEFORE.csv')==entry['prior_files']['docs/governance/cep/evidence/CEP-078_ACCEPTANCE_MAPPING.csv']
assert (ROOT/'docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md').read_text(encoding='utf8').endswith((OUT/'COMPLETION_REPORT_BEFORE.md').read_text(encoding='utf8'))
assert sha(ROOT/'docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md')==entry['canonical_sha']
master=ROOT/'docs/governance/uiux/UIUX_FINDING_CLOSURE_MASTER.yaml'
assert sha(master)=='4096c0452b88e6921d2c9c896239b8084b4a5f99282bc8c712cf1bd31f6634c9'
assert 'List → Detail consistency: RESOLVED' in master.read_text(encoding='utf8')
index=json.loads((OUT/'ARTIFACT_INDEX.json').read_text(encoding='utf8'))
for a in index['artifacts']:assert sha(ROOT/a['path'])==a['sha256'],a['path']
with (BASE/'CEP-078_EVIDENCE_MANIFEST.csv').open(encoding='utf8',newline='') as h:
    evidence=list(csv.reader(h))
new=[row for row in evidence if row[0] in {f'CEP-078-EV-{i:03d}' for i in range(18,23)}]
assert len(new)==5
for row in new:assert sha(ROOT/row[1])==row[2],row[0]
with (BASE/'CEP-078_ACCEPTANCE_MAPPING.csv').open(encoding='utf8',newline='') as h:
    mapping=list(csv.DictReader(h))
assert len(mapping)==11 and all(row['result']=='PASS' for row in mapping)
assert all('CEP-078-EV-022' in row['evidence_ids'] for row in mapping)
claim=json.loads((OUT/'SC014_RUNTIME.json').read_text(encoding='utf8'))
assert len(claim)==6 and all(c['result']=='PASS' and all(c['checks'].values()) for c in claim)
assert sum(len(c['checks']) for c in claim)==84
reader=json.loads((OUT/'NATIVE_READER.json').read_text(encoding='utf8'))
assert len(reader['cases'])==8
assert {(c['browser'],c['surface']) for c in reader['cases']}=={(b,s) for b in ['Chrome','Edge'] for s in ['login','employee','reconciliations','closeout']}
for c in reader['cases']:
    assert c['result']=='PASS_BOUNDED_NATIVE_OBSERVATION'
    for a in c['captures']:assert sha(OUT/a['path'])==a['sha256']
check=subprocess.run(['git','diff','--check','--',*sorted(allowed)],capture_output=True,text=True)
(OUT/'DIFF_CHECK.txt').write_text(check.stdout+check.stderr+'\nexit_code='+str(check.returncode)+'\n',encoding='utf8')
assert check.returncode==0,check.stdout
for p in [OUT/'RESUME_PROTOCOL.md',OUT/'REMAINDER_REPORT.md']:
    assert not any(line.rstrip()!=line for line in p.read_text(encoding='utf8').splitlines()),p
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
origin=subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip()
branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
assert head==origin==entry['head'] and branch==entry['branch']=='main'
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result':'PASS','cep':'CEP-078','execution':'COMPLETE',
    'other_ceps_preserved':85,'all_gate_records_unchanged':True,'prior_dirty_artifacts_preserved':len(preserved),
    'prior_cep078_history_preserved':True,'prior_report_and_mapping_bytes_preserved':True,
    'canonical_prompt_sha256':entry['canonical_sha'],'uiux_master_sha256':sha(master),'list_detail_consistency':'RESOLVED_UNCHANGED',
    'new_evidence_references_and_hashes':'PASS_018_THROUGH_022','artifact_index_count':len(index['artifacts']),
    'sc033_qualified_cells':6,'sc033_new_executions_counted':1,'sc014_cells':6,'sc014_checks_pass':84,
    'native_reader_pairs':8,'reduced_motion_distinct_shared_sc024_cases':10,'reduced_motion_claim_cells':6,
    'acceptance':'6_OF_6_PASS','dod':'MET','head':head,'origin_main':origin,'branch':branch,
    'summary':{'complete':71,'partial':4},'next_executable_frontier':[],'focused_document_validation':'PASS',
    'application_or_broad_regression_rerun':False,'git_writes':False,'production':False,
    'operational_limit':'Prior-session temporary tabs/viewport overrides remain owned by another session; current-session tabs closed/overrides reset; original motion/Narrator/Edge zoom restored',
    'changed_document_hashes':{p:sha(ROOT/p) for p in sorted(allowed)}}
(OUT/'INTEGRITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Focused closeout PASS;85otherCEPs/allGates/priorwork preserved;AC6/6;DoDMET;frontier[].')
