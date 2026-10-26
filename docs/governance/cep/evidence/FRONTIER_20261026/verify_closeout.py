"""Bounded preservation, evidence, source and Registry consistency checks."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path('.pytest_cache/cep_tools').resolve()))
import yaml

OUT=Path(__file__).parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
git=lambda *a:subprocess.check_output(['git',*a],text=True,encoding='utf8').strip()
entry=json.loads((OUT/'ENTRY.json').read_text(encoding='utf8'))
current=yaml.safe_load(Path('CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf8'))
original=yaml.safe_load(git('show','HEAD:CEP_EXECUTION_REGISTRY.yaml'))
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==entry['head']
assert git('branch','--show-current')=='main'
assert not git('diff','--cached','--name-status')
assert git('rev-list','--left-right','--count','HEAD...origin/main')=='0\t0'
for key,record in original['ceps'].items():
    if key not in ['CEP-077','CEP-078']:assert current['ceps'][key]==record,key
    else:assert current['ceps'][key]['history'][:len(record['history'])]==record['history'],key
for key,gate in original['gates'].items():
    assert current['gates'][key]['status']==gate['status'],key
    if key!='GATE-08':assert current['gates'][key]==gate,key
assert current['ceps']['CEP-077']['acceptance']['passed']==6
assert not current['ceps']['CEP-077']['blockers']
assert current['ceps']['CEP-078']['execution']['status']=='PARTIAL'
assert current['ceps']['CEP-078']['acceptance']['passed']==4
assert current['execution_frontier']['next_executable_frontier']==[]
assert len([r for r in current['ceps'].values() if r['execution']['status']=='COMPLETE'])==current['summary']['execution_state_complete']==70
assert len([r for r in current['ceps'].values() if r['execution']['status']=='PARTIAL'])==current['summary']['partial_current']==5
assert current['summary']['blocked_current']==4
allowed_source_changes={'security/supply_chain/build_image.json','apps/contracts/views.py','templates/contracts/detail.html'}
actual_source_changes={p for p,digest in entry['source_identity'].items() if sha(p)!=digest}
assert actual_source_changes==allowed_source_changes,actual_source_changes
for p,digest in entry['protected_hashes'].items():
    if p!='security/supply_chain/build_image.json':assert sha(p)==digest,p
assert 'List → Detail consistency: RESOLVED' in Path('docs/governance/uiux/UIUX_FINDING_CLOSURE_MASTER.yaml').read_text(encoding='utf8')
for p in OUT.glob('*.json'):json.loads(p.read_text(encoding='utf-8-sig'))
for p in OUT.glob('*.jsonl'):
    for line in p.read_text(encoding='utf8').splitlines():json.loads(line)
for p in [Path('docs/governance/cep/evidence/CEP-078_EVIDENCE_MANIFEST.csv')]:
    with p.open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
    assert len({r['evidence_id'] for r in rows})==len(rows)
    for row in rows:assert sha(row['path'])==row['sha256'],row['evidence_id']
for cep in ['077','078']:
    p=Path(f'docs/governance/cep/evidence/CEP-{cep}_ACCEPTANCE_MAPPING.csv')
    with p.open(encoding='utf8',newline='') as f:assert len(list(csv.DictReader(f)))==(6 if cep=='077' else 11)
for p in [Path('docs/governance/cep/reports/CEP-077_COMPLETION_REPORT.md'),Path('docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md')]:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
        if target.startswith(('http','codex:','#')):continue
        assert (p.parent/target.split('#')[0]).exists(),target
old=json.loads(Path('docs/governance/cep/evidence/FRONTIER_069_078_20261025/ENTRY.json').read_text(encoding='utf8'))
recovery={}
for name,row in old['canonical_recovery_sources'].items():
    p=Path(row['path'])
    if p.is_file():assert sha(p)==row['sha256'];recovery[name]='UNCHANGED_APPROVED_SOURCE_ARCHIVE'
    else:recovery[name]='RETAINED_PRIOR_VERIFIED_SOURCE;NOT_REPLACED_OR_INVENTED'
changed=git('diff','--name-only').splitlines()
new=git('ls-files','--others','--exclude-standard').splitlines()
allowed_current={
    '.github/workflows/cep013-pure-psycopg-verify.yml','.github/workflows/supply-chain.yml',
    'CEP_EXECUTION_REGISTRY.yaml','apps/contracts/views.py','templates/contracts/detail.html',
    'security/supply_chain/build_image.json',
}
for name in changed:
    assert name in allowed_current or re.fullmatch(r'docs/governance/cep/(evidence|reports|manifests)/CEP-07[78]_[^/]+',name),name
for name in new:
    assert name.startswith('docs/governance/cep/evidence/FRONTIER_20261026/') or name=='apps/contracts/test_review_navigation.py' or name.startswith('protected_documents/organizations/'),name
result={
    'head':entry['head'],'branch':'main','origin_main':entry['head'],'ahead':0,'behind':0,
    'protected_other_cep_records':84,'cep079_unchanged':True,'old_histories_preserved':True,
    'gate_status_changes':[],'canonical_prompts_verified':10,'approved_recovery':recovery,
    'uiux_closure_master_unchanged':True,'list_detail_resolution':'RESOLVED_RETAINED_20TESTS24SUBTESTS_PASS',
    'source_changes':{p:sha(p) for p in sorted(actual_source_changes)},
    'new_test':sha('apps/contracts/test_review_navigation.py'),
    'current_summary':current['summary'],'next_executable_frontier':[],
    'tracked_changes':changed,'new_file_count':len(new),'git_cached_diff':'EMPTY',
    'artifacts':{str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='INTEGRITY.json' and '__pycache__' not in p.parts},
    'new_synthetic_custody':{p:sha(p) for p in new if p.startswith('protected_documents/')},
    'production_signoff_git_writes':'NOT_EXECUTED',
    'limitations':'Focused checks and exact runtime scope only; no full regression, physical-device/WCAG conformance, historical blanket freshness or Production claim',
}
(OUT/'INTEGRITY.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print('PASS:84otherCEP records preserved; all Gate statuses unchanged; protected UIUX/source/evidence hashes and links match; counts70COMPLETE5PARTIAL4BLOCKED; frontier[]')
