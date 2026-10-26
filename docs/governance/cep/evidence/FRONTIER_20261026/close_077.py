import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path('.pytest_cache/cep_tools').resolve()))
import yaml

OUT=Path(__file__).parent; BASE=OUT.parent
entry=json.loads((OUT/'ENTRY.json').read_text(encoding='utf8'))
result=json.loads((OUT/'CEP077_RUNTIME_REFRESHED/gate-result.json').read_text())
assert result['status']=='BUILD_CONTROL_PASS' and all(v=='PASS' for v in result['checks'].values())
assert '9 passed' in (OUT/'CEP077_FOCUSED.txt').read_text(encoding='utf8')
for path in ['.github/workflows/supply-chain.yml','.github/workflows/cep013-pure-psycopg-verify.yml']:
    assert result['image_digest'] in Path(path).read_text(encoding='utf8')
manifest=BASE/'CEP-077_EVIDENCE_MANIFEST.csv'
with manifest.open('a',encoding='utf8',newline='') as f:
    w=csv.writer(f)
    for row in [
        ['CEP-077-EV-009','CURRENT ENTRY AND SOURCE IDENTITY','FRONTIER_20261026/ENTRY.json','PASS'],
        ['CEP-077-EV-010','OFFICIAL IMAGE REVIEW AND SEPARATE BOUNDED REMEDIATION','FRONTIER_20261026/IMAGE_REMEDIATION.json','PASS_SAME_APPROVED_TARGET'],
        ['CEP-077-EV-011','ACTUAL REFRESHED END_TO_END GATE','FRONTIER_20261026/CEP077_RUNTIME_REFRESHED/gate-result.json','BUILD_CONTROL_PASS'],
        ['CEP-077-EV-012','FOCUSED FAIL_CLOSED CONTROL TESTS','FRONTIER_20261026/CEP077_FOCUSED.txt','9_PASS'],
    ]:w.writerow(row)
mapping=BASE/'CEP-077_ACCEPTANCE_MAPPING.csv'
with mapping.open(encoding='utf8',newline='') as f: rows=list(csv.DictReader(f)); fields=list(rows[0])
for row in rows:
    row['verdict']='PASS'; row['evidence']+=';CEP-077-EV-009;CEP-077-EV-010;CEP-077-EV-011;CEP-077-EV-012'
    row['reason']='Current20261026 actual fresh gate BUILD_CONTROL_PASS; exact timestamp/source/approved target; all10 checks PASS. Prior failed observations retained in original artifacts/history. Linux installation and signed Production attestation remain UTV outside scoped local verification.'
with mapping.open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
report=Path('docs/governance/cep/reports/CEP-077_COMPLETION_REPORT.md')
with report.open('a',encoding='utf8') as f:f.write('''

## Current completion — 2026-10-26

**EXECUTION COMPLETE — Development supply-chain control verification only.**
Current main/origin `961e3fd942c668337012c22d42f59545c5e9fc0a`; entry tree clean.
Current Human frontier instruction authorizes attributable Development configuration
repair. [Separate bounded image remediation](../evidence/FRONTIER_20261026/IMAGE_REMEDIATION.json)
precedes verification: official registry content addresses verified; same approved
CPython3.11.17/source hash, Debian12/bookworm, linux/amd64, runtime configuration
and Python build instructions. Debian base snapshot was rebuilt upstream.
Only the immutable image index/platform pins and existing two CI references changed;
dependency locks, licenses, scanner/exceptions, gate logic, permissions, attestation
requirements and application behavior are unchanged. No policy waiver or risk acceptance.

[Fresh existing gate](../evidence/FRONTIER_20261026/CEP077_RUNTIME_REFRESHED/gate-result.json)
ran2026-10-26T11:38:14Z..11:39:12Z, exit0 **BUILD_CONTROL_PASS**: all10 checks PASS;
7production and15development wheels acquired and hash/offline-verified; current
OSV returns no blocking findings; exact license review has0unreviewed artifacts;
both CycloneDX SBOMs and artifact inventories retained. [9focused tests](../evidence/FRONTIER_20261026/CEP077_FOCUSED.txt)
PASS. New evidence EV009..012; all6AC PASS and scoped DoD MET. Findings001/002
resolved by actual evidence; historical DNS/image failures remain unchanged,
including the current initial unchanged-gate failure. Production readiness remains
UTV: no Linux application installation, signed attestation, Production action,
Human Sign-off or final certification. GATE08 remains NOT_PASSED because required
other contributors073..076/078 remain incomplete. No schema/data changes or migrations.
All changes uncommitted; Git writes NOT_EXECUTED. Next independent path: CEP078.
''')
p=Path('CEP_EXECUTION_REGISTRY.yaml');text=p.read_text(encoding='utf8');registry=yaml.safe_load(text);r=registry['ceps']['CEP-077']
r['eligibility_status']='COMPLETE_SCOPED_NONPRODUCTION_VERIFICATION'
r['execution'].update(status='COMPLETE',lifecycle='CLOSED_VERIFIED_DEVELOPMENT_SUPPLY_CHAIN')
r['acceptance'].update(passed=6,total=6,status='PASS_ACTUAL_FRESH_GATE')
r['dod']='MET_SCOPED_NONPRODUCTION';r['blockers']=[]
r['remaining_utv']=['Linux application installation, signed Production attestation and Production readiness remain UTV; no production or certification inference']
r['completion_report']['evidence_presence']='CURRENT_FRESH_GATE10_CHECKS_PASS_7PROD15DEV_WHEELS_9FOCUSED_TESTS_PASS'
r['last_execution']={'branch':'main','sha':entry['head']};r['updated_at']='2026-10-26'
r['history'] += [
    {'date':'2026-10-26','status':'RESUMED','reason':'Current Human executable frontier continuation; reviewed official same-target immutable rebuild in separate bounded attributable Development repair before unchanged verification. No dependency/policy/security weakening.','evidence':str(OUT/'IMAGE_REMEDIATION.json').replace('\\','/')},
    {'date':'2026-10-26','status':'BLOCKER_RESOLVED','reason':'Finding002 official image content addresses and same approved target verified; three existing immutable references refreshed. Actual fresh gate image identity PASS; old failures retained.'},
    {'date':'2026-10-26','status':'COMPLETE','reason':'Actual existing end-to-end gate exit0 BUILD_CONTROL_PASS;10checksPASS,7prod/15dev exact wheels; offline hashes/OSV/licenses/SBOM PASS;9focused testsPASS.6of6AC and scopedDoD MET. Linux install/signed Production attestation UTV; Gate08 NOT_PASSED. No migration, Production, Sign-off or Git writes.','evidence':str(OUT/'CEP077_RUNTIME_REFRESHED/gate-result.json').replace('\\','/')},
]
start=text.index('  CEP-077:\n');end=text.index('  CEP-078:\n',start)
block=yaml.safe_dump({'CEP-077':r},sort_keys=False,allow_unicode=True,width=140)
text=text[:start]+''.join('  '+line if line.strip() else line for line in block.splitlines(True))+text[end:]
text=text.replace('execution_state_complete: 69','execution_state_complete: 70',1).replace('partial_current: 6','partial_current: 5',1).replace("last_updated: '2026-10-25'","last_updated: '2026-10-26'",1)
text=text.replace('verified_verification_eligible_unblocked: []','verified_verification_eligible_unblocked:\n  - CEP-078',1)
text=text.replace('next_autonomous_cep: null','next_autonomous_cep: CEP-078',1)
text=text.replace('current_session_continuation: STOP_ALL_INDEPENDENT_PATHS_EXHAUSTED_AT_CURRENT_AUTHORITY_AND_EVIDENCE','current_session_continuation: CONTINUE_CEP078_INDEPENDENT_QUALIFIED_RUNTIME_ONLY',1)
assert yaml.safe_load(text)['ceps']['CEP-077']['execution']['status']=='COMPLETE'
p.write_text(text,encoding='utf8')
close={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':entry['head'],'state':'EXECUTION COMPLETE','ac':6,'total':6,'dod':'MET_SCOPED_NONPRODUCTION','gate08':'NOT_PASSED_OTHER_REQUIRED_CONTRIBUTORS_INCOMPLETE','runtime_checks':result['checks'],'files':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'CEP077_RUNTIME_REFRESHED').rglob('*') if p.is_file()},'production':'UTV_NOT_EXECUTED','git_writes':'NOT_EXECUTED'}
(OUT/'CEP077_CLOSEOUT.json').write_text(json.dumps(close,indent=2)+'\n',encoding='utf8')
print('CEP077 COMPLETE6of6; Gate08 unchanged; next078')
