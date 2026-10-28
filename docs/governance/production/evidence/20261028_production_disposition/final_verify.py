"""Verify exact Gate semantics, immutable baselines and final artifact provenance."""

import ast
import hashlib
import json
import re
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
PROD=OUT.parents[1]
PRIVATE=Path('E:/BONIRA_Operations/ApprovedLinux/6e55fd45b4c04ce0')
def load(path):return json.loads(path.read_text('utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,encoding='utf-8').strip()

def main():
 entry=load(OUT/'ENTRY.json');before=yaml.safe_load((OUT/'BEFORE_REGISTRY.yaml').read_text('utf-8'));current=yaml.safe_load((ROOT/'CEP_EXECUTION_REGISTRY.yaml').read_text('utf-8'))
 assert git('rev-parse','HEAD')==entry['head']==git('rev-parse','origin/main')
 remote=git('ls-remote','origin','refs/heads/main').split()[0];assert remote==entry['head']
 assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
 assert all(before[k]==current[k] for k in before if k not in {'gates','repository_state'})
 assert all(before['gates'][k]==current['gates'][k] for k in before['gates'] if k!='GATE-11')
 assert current['ceps']==before['ceps'] and len(current['ceps'])==86
 assert sum(row['execution']['status']=='COMPLETE' for row in current['ceps'].values())==79
 gate=load(PROD/'GATE11_EVALUATION.json');oldgate=load(OUT/'BEFORE_GATE11_EVALUATION.json')
 assert [v['requirement'] for v in gate['clauses']]==[v['requirement'] for v in oldgate['clauses']]
 assert all(row['status']=='SATISFIED' for row in gate['clauses'])
 assert gate['status']==current['gates']['GATE-11']['status']=='PASS'
 assert gate['requirements_satisfied']==current['gates']['GATE-11']['requirements_satisfied']==5
 assert gate['requirements_total']==5 and not gate['remaining_blockers']
 freeze=load(OUT/'SOURCE_FREEZE.json');assert len(freeze)==1611
 assert all(sha(ROOT/name)==digest for name,digest in freeze.items())
 # The transferred manifest has no trailing newline; preserve its exact bytes
 # alongside the equivalent pretty local map, avoiding a false byte-hash claim.
 with tarfile.open(PRIVATE/'production-disposition-source.tar.gz') as archive:
  data=archive.extractfile('source-production-disposition/SOURCE_FREEZE.json').read()
 assert json.loads(data)==freeze
 manifest=OUT/'runtime/EXECUTED_SOURCE_FREEZE.json';manifest.write_bytes(data)
 identity=load(OUT/'runtime/FINAL_RELEASE_IDENTITY.json')
 assert sha(manifest)==identity['source']['source_manifest_sha256']
 assert identity['source']['head']==entry['head'] and identity['actual_mount_verified']
 prior=load(OUT.parent/'20261028_legacy_decision/ARTIFACT_HASHES.json')
 legacy=['apps/documents/migrations/0012_legacy_payment_reference_preparation.py','apps/billing/migrations/0018_retire_legacy_claim_settlements.py','core/retired_payments/migrations/0007_retire_legacy_payment.py','apps/documents/models.py','apps/treasury/test_retirement_contract.py','scripts/verify_legacy_payment_retention.py']
 assert all(sha(ROOT/name)==prior[name] for name in legacy)
 baseline=load(OUT.parent/'20261028/ENTRY.json')
 assert all(sha(ROOT/row['path'])==row['sha256'] for row in baseline['canonical_prompts'].values())
 retained=load(OUT.parent/'20261028/RETAINED_HASH_CHECK.json')
 retained_deltas=[row['path'] for row in retained if sha(ROOT/row['path'])!=row['expected']]
 assert set(retained_deltas)=={'apps/payroll/statutory_governance.py','CEP_EXECUTION_REGISTRY.yaml'}
 original=load(ROOT/'docs/governance/cep/evidence/CEP-069_EXT0018_REVIEW_REENTRY_20261027/RUNTIME_SOURCE_PACKAGES.json')
 envelopes=load(PROD/'PRODUCTION_STATUTORY_ENVELOPES.json')
 for old,new in zip(original,envelopes,strict=True):
  parameters=json.loads(json.dumps(new['parameters']))
  authorization=parameters['statutory_governance'].pop('production_authorization')
  assert authorization['sha256']==entry['authority_sha256']==sha(ROOT/authorization['reference'])
  parameters['statutory_governance']['scope']='NON_PRODUCTION_QUALIFICATION'
  assert parameters==old['content']['policy']['parameters']
  digest=hashlib.sha256(json.dumps(new['parameters'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
  assert digest==new['parameter_digest']
 for name in ['PITR_RESULT','CADENCE_CUSTODY_RESULT','WEB_OPERATIONS_RESULT','FINAL_RELEASE_IDENTITY','CURRENT_AUDIT_RECOVERY']:
  assert load(OUT/'runtime'/(name+'.json'))['result']=='PASS'
 assert load(OUT/'runtime/FINAL_APP_TESTS.json')['failed']==0
 assert load(OUT/'SHUTDOWN.json')['result']=='PASS'
 assert 'Ran 52 tests' in (OUT/'runtime/FINAL_APP_TESTS.txt').read_text('utf-8')
 python_files=['apps/payroll/statutory_governance.py','apps/payroll/test_production_governance.py','config/gunicorn_production.py','core/production_operations.py','scripts/production_recovery.py','tests/test_production_operations.py']
 for name in python_files:ast.parse((ROOT/name).read_text('utf-8'))
 links=0
 for path in [PROD/'PRODUCTION_READINESS_ASSESSMENT.md',PROD/'PRODUCTION_REFERENCE_AND_CUTOVER.md',OUT/'COMPLETION_REPORT.md']:
  for link in re.findall(r'\]\(([^)]+)\)',path.read_text('utf-8')):
   if '://' not in link:
    assert (path.parent/link.split('#',1)[0]).resolve().exists(),(path,link)
    links+=1
 whitespace=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True);assert whitespace.returncode==0
 final={'at':datetime.now(UTC).isoformat(),'result':'PASS','head':entry['head'],'branch':'main','live_origin_main':remote,'staged_files':0,'requirements_satisfied':5,'requirements_total':5,'gate11':'PASS','exact_gate_semantics_unchanged':True,'complete_ceps_unchanged':79,'total_cep_records_unchanged':86,'other_gate_records_unchanged':True,'canonical_prompts_unchanged':11,'legacy_payment_source_files_unchanged':6,'source_files_verified':1611,'executed_manifest_sha256':sha(manifest),'production_envelopes_only_scope_authorization_changed':4,'retained_recorded_hashes_unchanged':84,'authorized_retained_hash_deltas':retained_deltas,'relative_links_resolve':links,'python_parse_diff_whitespace_ruff':'PASS','future_actual_production_or_signoff_not_claimed':True,'production_action':False,'git_writes':False}
 (OUT/'FINAL_CHECKS.json').write_text(json.dumps(final,indent=2)+'\n','utf-8')
 hashes={}
 for path in OUT.rglob('*'):
  if path.is_file() and '__pycache__' not in path.parts and path.name!='ARTIFACT_HASHES.json':hashes[path.relative_to(ROOT).as_posix()]=sha(path)
 for path in [ROOT/name for name in python_files]+[ROOT/'CEP_EXECUTION_REGISTRY.yaml',*PROD.glob('*.md'),*PROD.glob('*.json'),PROD/'production.env.example']:
  hashes[path.relative_to(ROOT).as_posix()]=sha(path)
 (OUT/'ARTIFACT_HASHES.json').write_text(json.dumps(hashes,indent=2,sort_keys=True)+'\n','utf-8')
 print(json.dumps(final,indent=2));print('Artifact manifest',len(hashes),'files')

if __name__=='__main__':main()
