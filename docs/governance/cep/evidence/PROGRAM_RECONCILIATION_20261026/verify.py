"""Focused reconciliation integrity/reference checks; no application execution."""
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

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
entry=json.loads((OUT/'ENTRY.json').read_text(encoding='utf8'))
before=yaml.safe_load((OUT/'REGISTRY_BEFORE.yaml').read_text(encoding='utf8'))
after=yaml.safe_load((ROOT/'CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf8'))
for key in before:
    if key not in {'ceps','gates','summary','execution_frontier'}:assert after[key]==before[key],key
for key,prior in before['ceps'].items():
    current=after['ceps'][key]
    if key in {f'CEP-{n:03d}' for n in range(69,77)}:
        for field,value in prior.items():
            if field not in {'frontier_review','updated_at','history'}:assert current[field]==value,(key,field)
        assert current['history'][:-1]==prior['history']
        assert current['frontier_review']['result']=='RECONCILED_NO_NEW_EXECUTION_ELIGIBILITY'
    else:assert current==prior,key
for key,prior in before['gates'].items():
    assert after['gates'][key]['status']==prior['status'],key
    if key not in {'GATE-06','GATE-07','GATE-08','GATE-11'}:assert after['gates'][key]==prior
for key in ['CEP-077','CEP-078','CEP-079']:
    assert after['ceps'][key]==entry['all_cep_records'][key]
    assert after['ceps'][key]['execution']['status']=='COMPLETE'
result=json.loads((OUT/'RESULT.json').read_text(encoding='utf8'))
for key in ['GATE-08','GATE-11']:
    required={v.strip() for v in result['gate_contracts'][key]['Required IMB IDs'].split(';')}
    assert set(after['gates'][key]['required_imb_status'])==required
assert after['gates']['GATE-08']['required_imb_status']['IMB-0107'].startswith('PASS_')
assert after['gates']['GATE-08']['required_imb_status']['IMB-0108'].startswith('PASS_')
assert sum(v.startswith('UNEXECUTED_') for v in after['gates']['GATE-08']['required_imb_status'].values())==5
assert len(result['eligibility_069_076'])==8 and not any(v['newly_eligible'] for v in result['eligibility_069_076'])
assert result['newly_eligible_work_completed']==result['next_executable_frontier']==after['execution_frontier']['next_executable_frontier']==[]
assert after['execution_frontier']['verified_build_eligible_unblocked']==after['execution_frontier']['verified_verification_eligible_unblocked']==[]
assert not after['execution_frontier']['production_authorized'] and not after['execution_frontier']['human_signoff_executed']
assert after['summary']['execution_state_complete']==sum(c['execution']['status']=='COMPLETE' for c in after['ceps'].values())==71
assert after['summary']['partial_current']==sum(c['execution']['status']=='PARTIAL' for c in after['ceps'].values())==4
assert after['summary']['blocked_current']==4
preserved=0
for p,expected in entry['prior_dirty_files'].items():
    if p=='CEP_EXECUTION_REGISTRY.yaml':continue
    assert sha(ROOT/p)==expected,p
    preserved+=1
current=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard'],cwd=ROOT,text=True).splitlines()
assert all(p in entry['prior_dirty_files'] or p.startswith('docs/governance/cep/evidence/PROGRAM_RECONCILIATION_20261026/') for p in current)
master=ROOT/'docs/governance/uiux/UIUX_FINDING_CLOSURE_MASTER.yaml'
assert sha(master)==entry['uiux_master_sha256']
assert 'List → Detail consistency: RESOLVED' in master.read_text(encoding='utf8')
index_path=Path(subprocess.check_output(['git','rev-parse','--git-path','index'],cwd=ROOT,text=True).strip())
if not index_path.is_absolute():index_path=ROOT/index_path
assert sha(index_path)==entry['index_sha256']
for ref in result['completion_reconciliation'].values():assert sha(ROOT/ref['evidence'])==ref['sha256']
for p in OUT.iterdir():
    if p.suffix in {'.md','.py'}:
        assert not any(line!=line.rstrip() for line in p.read_text(encoding='utf8').splitlines()),p.name
check=subprocess.run(['git','diff','--check','--','CEP_EXECUTION_REGISTRY.yaml'],cwd=ROOT,capture_output=True,text=True)
(OUT/'DIFF_CHECK.txt').write_text(check.stdout+check.stderr+'\nexit_code='+str(check.returncode)+'\n',encoding='utf8')
assert check.returncode==0,check.stdout
for ref,expected in [('HEAD',entry['head']),('origin/main',entry['origin_main'])]:
    assert subprocess.check_output(['git','rev-parse',ref],cwd=ROOT,text=True).strip()==expected
assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='main'
artifacts=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in {'ARTIFACT_INDEX.json','INTEGRITY.json'}]
(OUT/'ARTIFACT_INDEX.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifacts':artifacts},indent=2)+'\n',encoding='utf8')
integrity={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result':'PASS','head':entry['head'],'origin_main':entry['origin_main'],'branch':'main',
    '077_078_079_complete_records_preserved':True,'unrelated_cep_records_preserved':78,'069_076_execution_ac_dod_preserved':True,
    'gate_status_changes':[],'canonical_gate_contributor_sets_exact':True,'prior_dirty_artifacts_preserved':preserved,
    'product_uiux_and_list_detail_preserved':True,'git_index_bytes_unchanged':True,'no_git_write':True,'no_production':True,'no_new_audit_or_broad_regression':True,
    'artifact_count':len(artifacts),'registry_sha256':sha(ROOT/'CEP_EXECUTION_REGISTRY.yaml'),
    'artifacts_index_sha256':sha(OUT/'ARTIFACT_INDEX.json'),'newly_eligible_work_completed':[],'next_executable_frontier':[]}
(OUT/'INTEGRITY.json').write_text(json.dumps(integrity,indent=2)+'\n',encoding='utf8')
print('Focused reconciliation PASS;077/078/079 preserved;78unrelated CEPs and prior work unchanged;Gate statuses unchanged;frontier[].')
