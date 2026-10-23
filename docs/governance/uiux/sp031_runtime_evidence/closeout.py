"""Append SP031 governance only; verify byte preservation and evidence completeness."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
import yaml

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
REGISTER=OUT.parent/'UIUX_FINDINGS_REGISTER.yaml'
def read(name): return json.loads((OUT/name).read_text(encoding='utf-8'))
def save(name,value): (OUT/name).write_text(json.dumps(value,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

before_bytes=REGISTER.read_bytes()
if b'\nsp031_runtime_confirmation:' in before_bytes:
    before_bytes=before_bytes.split(b'\nsp031_runtime_confirmation:',1)[0]
    before_bytes=re.sub(rb'- finding_id: UIUX-F-128\n.*?(?=runtime_wave_a:)',b'',before_bytes,flags=re.S)
    before_bytes=before_bytes.replace(b'  finding_count: 128',b'  finding_count: 127',1).replace(b'    MEDIUM: 46',b'    MEDIUM: 45',1)
    baseline=read('FILES_BEFORE.json')
    assert hashlib.sha256(before_bytes).hexdigest()==next(h for p,h in baseline.items() if p.replace('\\','/')=='docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml')
before=yaml.safe_load(before_bytes)
assert len(before['findings'])==127
assert not any(f['finding_id']=='UIUX-F-128' for f in before['findings'])
assert 'sp031_runtime_confirmation' not in before
save('REGISTER_FINDINGS_BEFORE.json',before['findings'])
http=read('HTTP.json'); direct=read('DIRECT_SERVICE.json'); browser=read('BROWSER.json'); integrity=read('INTEGRITY.json')
assert len(http)==22 and len(direct)==18 and len(browser)==5
assert all(o['cross_tenant_absent'] and o['business_and_success_audit_unchanged'] for o in http)
assert integrity['unauthorized_training_records']==integrity['runtime_success_audit_delta']==0
assert integrity['authority_before']==integrity['authority_after']
assert all(not o.get('success',False) for o in browser)

entry='''- finding_id: UIUX-F-128
  surface_id: SP-031
  module: Workforce
  route: /workforce/foundation/training-records/create/
  page_title: Employee Training Record TrainingRequirement selector
  category: SECURITY_SCOPE
  severity: MEDIUM
  finding_status: OPEN
  status: RUNTIME_CONFIRMED
  runtime_status: RUNTIME_CONFIRMED
  runtime_classification: FAIL_SECURITY_SCOPE
  sweep_classification: AFFECTED_CONFIRMED
  roles:
  - Existing project_manager with A/B Project scope
  - Existing operations_manager with SITE-only scope
  problem: Same-tenant unauthorized project-bound TrainingRequirement UUIDs appear in initial choices and invalid/denied redisplay.
  technical_root_cause: EmployeeTrainingRecordForm filters requirement choices by tenant and lifecycle only; workforce_training_record_create supplies no membership. The outer capability gate accepts limited scope while the write service retains a stricter organization permission gate.
  evidence:
    report: UIUX_SP031_RUNTIME_CONFIRMATION_REPORT.md
    runtime_http: sp031_runtime_evidence/HTTP.json
    runtime_browser: sp031_runtime_evidence/BROWSER.json
    runtime_integrity: sp031_runtime_evidence/INTEGRITY.json
    source_paths:
    - apps/workforce/forms.py
    - apps/workforce/views.py
    - apps/workforce/services.py
  user_impact: Unauthorized identifiers and generic model labels disclosed; requirement names/codes, contents, cross-tenant disclosure and successful unauthorized writes were not observed.
  recommendation: Separately authorize bounded remediation of this selector and redisplay; preserve canonical catalogue semantics and current write authority.
  business_logic_impact: NO_CHANGE_AUTHORIZED
  needs_domain_review: false
  root_pattern_candidate: []
  root_pattern_review: Independent SP031 runtime finding; no F111-family finding or family closure is changed.
  related_cep: []
  related_standard: []
  remediation_status: NOT_STARTED
  confirmed_on: '2026-10-22'

'''
current='''
sp031_runtime_confirmation:
  surface_id: SP-031
  status: AFFECTED_CONFIRMED
  runtime_status: EXECUTED
  confirmed_on: '2026-10-22'
  report: UIUX_SP031_RUNTIME_CONFIRMATION_REPORT.md
  evidence: sp031_runtime_evidence/
  new_independent_finding: UIUX-F-128
  historical_status: NEEDS_RUNTIME_CONFIRMATION
  historical_evidence: UIUX_F111_SAME_PATTERN_SECURITY_SWEEP.md and UIUX_F111_PATTERN_FAMILY_CLOSURE_REPORT.md remain unchanged dated evidence.
  selector_scope: FAIL_SAME_TENANT_PROJECT_AND_SITE_ONLY
  invalid_redisplay: FAIL_PROTECTED_UUIDS_RETAINED
  cross_tenant: PASS_ABSENT
  manipulated_post: PASS_REJECTED
  unauthorized_training_record_or_success_audit: NONE
  remediation: NOT_STARTED
  f111_pattern_family: F111_PATTERN_FAMILY_CLOSED_UNCHANGED
  wave_c: NOT_STARTED
  cep_078_079: NOT_EXECUTED
  production: NO_ACTION
  git_add_commit_push: NOT_EXECUTED
'''
# Byte-preserve the existing findings and all historical reports.
text=before_bytes.decode('utf-8')
assert text.count('  finding_count: 127')==1 and text.count('    MEDIUM: 45')==1
text=text.replace('  finding_count: 127','  finding_count: 128',1).replace('    MEDIUM: 45','    MEDIUM: 46',1)
assert text.count('\nruntime_wave_a:')==1
text=text.replace('\nruntime_wave_a:','\n'+entry+'runtime_wave_a:',1)+current
REGISTER.write_bytes(text.encode('utf-8'))
after=yaml.safe_load(REGISTER.read_bytes())
assert after['findings'][:-1]==before['findings']
assert after['findings'][-1]['finding_id']=='UIUX-F-128'
assert after['runtime_wave_a']==before['runtime_wave_a']
assert after['register_status']['finding_count']==len(after['findings'])==128
assert sum(f['severity']=='MEDIUM' for f in after['findings'])==46

# Remove unrelated workforce labels from HTTP captures; original responses remain hash identified.
for p in OUT.glob('http_*.html'):
    body=p.read_text(encoding='utf-8')
    body=re.sub(r'(<select\b[^>]*name="employee"[^>]*>).*?(</select>)',r'\1<!-- Unrelated Employee choices omitted -->\2',body,flags=re.S)
    p.write_text(body,encoding='utf-8')

files=read('FILES_BEFORE.json')
changed=[p.replace('\\','/') for p,h in files.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert changed==['docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml'],changed
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==read('GROUNDING.json')['head']
save('CLOSEOUT_VERIFICATION.json',dict(status='PASS',historical_findings_preserved=127,independent_new_finding='UIUX-F-128',
    changed_preexisting_files=changed,product_files_byte_unchanged=True,f111_family_and_historical_evidence_byte_unchanged=True,
    canonical_registry_and_roadmap_byte_unchanged=True,http_observations=22,direct_outcomes=18,browser_observations=5,browser_posts=3,
    integrity_tables=integrity['tables'],sp031_status='AFFECTED_CONFIRMED',wave_c='NOT_STARTED',remediation='NOT_STARTED',git_writes='NONE'))
print('Closeout PASS: 127 historical findings preserved; independent F-128; SP031 AFFECTED_CONFIRMED; product and historical evidence byte-unchanged')
