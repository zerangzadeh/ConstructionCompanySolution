"""Bounded CEP078 reconciliation, complete evidence inventory and integrity checks."""
import csv
from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
REG = ROOT / 'CEP_EXECUTION_REGISTRY.yaml'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def write_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def blocks(text):
    return dict(re.findall(r'^  (CEP-\d{3}):\n(.*?)(?=^  CEP-|^authority_scope:)', text, re.M|re.S))

def section(text, name):
    return re.search(r'^'+name+r':\n(.*?)(?=^[A-Za-z_]+:|\Z)', text, re.M|re.S).group(1)

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()

entry = read('ENTRY.json')
assert git('branch', '--show-current') == 'main'
assert git('rev-parse', 'HEAD') == entry['head'] == git('rev-parse', 'origin/main')
assert sha(ROOT / '.git/index') == entry['index_sha256']
assert not git('diff', '--cached', '--name-only')
prior_mismatch = [p for p,v in entry['prior_evidence'].items() if sha(ROOT/p) != v]
assert not prior_mismatch, prior_mismatch
sources = {p:sha(ROOT/p) for p in entry['product_hashes']}
changed = [p for p,v in sources.items() if v != entry['product_hashes'][p]]
expected = {'core/forms.py','core/test_cep003_localization_accessibility.py','apps/daily_reports/forms.py','apps/equipment/forms.py','apps/accounts/static/js/erp_context.js','apps/accounts/static/js/erp_jalali.js','templates/base.html','tests/test_uiux_f111_scope.py'}
assert set(changed) == expected, changed
save('SOURCE_MANIFEST.json', {'at':datetime.now(timezone.utc).isoformat(),'head':entry['head'],'product_hashes':sources,'changed_this_continuation':changed,'dirty_sources_included':True})
matrix = json.loads((OUT.parent/'CEP-078_REENTRY_02/EXT0024_MATRIX.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/p)==v for p,v in matrix['scope_sources'].items())
assert sha(ROOT/'docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md') == entry['prompt_sha256']
accepted = json.loads((OUT.parent/'CEP-078_ENTRY_REVIEW.json').read_text(encoding='utf-8'))
accepted_count=0
for folder, metadata in accepted['accepted_evidence_integrity'].items():
    base=ROOT/'docs/governance/uiux'/folder
    assert sha(base/'MANIFEST.json')==metadata['manifest_sha256']
    for name,value in json.loads((base/'MANIFEST.json').read_text(encoding='utf-8')).items():
        assert sha(base/name)==value, name
        accepted_count+=1
assert accepted_count==340
runtime=read('RUNTIME_RESULTS.json')
final={(r['id'],r['family'],tuple(r['viewport'])):r for r in runtime if not r['id'].endswith('BEFORE') and r['id']!='CASCADE-DAILY-PROJECT'}
assert len(final)==60 and all(r['result']=='PASS' for r in final.values())
assert sum(len(r['checks']) for r in final.values())==408
save('RUNTIME_SUMMARY.json', {'at':datetime.now(timezone.utc).isoformat(),'all_records':len(runtime),'original_results':dict(Counter(r['result'] for r in runtime)),'final_cells':len(final),'final_assertions':408,'final_results':dict(Counter(r['result'] for r in final.values())),'groups':dict(Counter(r['id'] for r in final.values())),'supersession':{'CASCADE-DAILY-PROJECT':'Actual CASCADE-DAILY final cells','JALALI-MONTH-NAVIGATION-BEFORE':'Actual JALALI-KEYBOARD-EMPTY-POPULATED final cells','A11Y-EMPLOYEE Edge1024 transient duplicate':'Later direct same-cell PASS without product edits'},'not_a_full_matrix_or_wcag_pass':True})
plan=json.loads((OUT.parent/'CEP-078_REENTRY_03/EXTENDED_BROWSER_PLAN.json').read_text(encoding='utf-8'))['rows']
old_results=json.loads((OUT.parent/'CEP-078_REENTRY_03/SURFACE_RESULTS.json').read_text(encoding='utf-8'))
old_latest={(r['id'],r['family'],tuple(r['viewport'])):r for r in old_results}
scenario_rows=[]
for sc in matrix['scenario_plan']:
    number=int(sc['cep_scenario_id'][-3:])
    rows=[r for r in plan if number in r['scenarios']]
    observed=[r for r in old_latest.values() if number in r['scenarios']]
    gap='Rendered prepared state only; unexecuted configured states/interaction/accessibility dimensions remain UTV. No business lifecycle outcome inferred.'
    status='EXECUTED_RENDERED_STATE_SCOPE_WITH_EXPLICIT_UTV'
    extra=''
    if number==1:
        extra='REENTRY03 LOGIN_REVALIDATION/LOGIN_FOCUS_CORRECTION/LOGIN_EMPTY_ERRORS; accepted login repair retained'
    if number==6:
        extra='Current CASCADE-DAILY/EQUIPMENT/EXPENSES/ESTIMATES:24 final cells PASS'
        gap='Asynchronous loading/error branches not directly exercised remain UTV; existing server scope tests are supplemental only.'
    if number==14:
        status='PARTIAL_BLOCKER_DATA_FINDING016'
        gap='Populated ProgressClaim requires missing approved effective commercial/regulatory source and review; no invented rates/bases/approvals. Empty/preparation surfaces only.'
    if number==23:
        status='PASS_EXECUTED_SHARED_TABLE_VARIANT'
        extra='Current TABLE-FILTER-SORT-PAGE-CLEAR:6 final cells PASS'
        gap='Only the exact Projects shared-table variant is proved; not all list consumers or business journeys.'
    if number==24:
        extra='Current A11Y-EMPLOYEE/RECONCILIATIONS/CASE:18 final cells PASS; prior Login actual semantics retained'
        gap='Keyboard skip and rendered semantics proved; native screen-reader, reduced-motion and unexecuted error/interaction dimensions remain UTV.'
    if number==32:
        gap='Original row067 stale receipt/404/Edge UTV retained; distinct prepared current positive portal rows068/069 PASS, not relabeled as067.'
    if number==33:
        status='PARTIAL_QUALIFIED_ADMIN_VARIANT_UTV_FINDING022'
        gap='Existing Platform Admin lacks staff access in both browsers; planned admin route precondition fails. Existing member/effective-role proof retained; governed all-persona catalogue not proved.'
    scenario_rows.append({'scenario':sc['cep_scenario_id'],'canonical_source_block_sha256':sc['block_sha256'],'source_journey':sc['canonical_input_block'].splitlines()[0].strip(),'planned_surface_ids':';'.join(r['id'] for r in rows),'retained_observed_cells':len(observed),'retained_pass_cells':sum(r['result']=='PASS' for r in observed),'status':status,'additional_actual_evidence':extra,'remaining_gap_or_limit':gap,'full_source_contract':'../CEP-078_REENTRY_02/EXT0024_MATRIX.json (unchanged full33 source blocks)'})
assert len(scenario_rows)==33
write_csv('SCENARIO_RECONCILIATION.csv',scenario_rows)
mapping=[
('AC1','Approved target runtime outcome','PARTIAL','RUNTIME_SUMMARY.json; SCENARIO_RECONCILIATION.csv','Required source/fixture and unexecuted state gaps remain'),
('AC2','Exact scenario environment and version','PASS','ENTRY.json; SOURCE_MANIFEST.json; RUNTIME_IDENTITIES.json; retained EXT0024_MATRIX.json','Provider PID binding inferred; CSS emulation not physical devices'),
('AC3','Actual complete scenario execution rather than inference','PARTIAL','RUNTIME_RESULTS.json; retained REENTRY03 actual results','Actual cells proved; missing qualified states never inferred'),
('AC4','Measured timestamped artifacts with explicit outcomes','PASS','RUNTIME_RESULTS.json; CEP-078_EVIDENCE_MANIFEST.csv','Original FAIL/UTV and new actual rechecks retained'),
('AC5','Failed required scenarios stay evidence gaps','PASS','FINDINGS.md; CEP-078_COMPLETION_REPORT.md','Actual supersession only; no waiver'),
('AC6','UTV persists until executed','PASS','SCENARIO_RECONCILIATION.csv; VARIANT_PREFLIGHT.json','Full remaining approved dimensions explicit'),
('DoD1','Exact target outcome within approved scope','PARTIAL','CEP-078_COMPLETION_REPORT.md','No complete outcome while required gaps remain'),
('DoD2','Environment and scenario documented','PASS','CEP-078_EXECUTION_MANIFEST.md; SOURCE_MANIFEST.json','Retained approved matrix unchanged'),
('DoD3','Execution procedure prepared','PASS','CEP-078_EXECUTION_MANIFEST.md; retained browser_procedure.mjs','Current actual calls measured in RUNTIME_RESULTS.json'),
('DoD4','Explicit evidence and result format','PASS','RUNTIME_RESULTS.json; CEP-078_EVIDENCE_MANIFEST.csv','Bounded evidence identities and hashes'),
('DoD5','Actual complete scoped execution evidence','PARTIAL','RUNTIME_SUMMARY.json; SCENARIO_RECONCILIATION.csv','Preparation/partial actual evidence does not complete DoD')]
write_csv('CEP-078_ACCEPTANCE_MAPPING.csv',[dict(zip(['criterion','requirement','result','evidence','limitation'],r)) for r in mapping])

before=entry['registry_before'].replace('\r\n','\n')
text=REG.read_text(encoding='utf-8').replace('\r\n','\n')
initial=text
assert text==before, 'Registry changed during continuation; do not overwrite concurrent changes'
old_blocks=blocks(before)
current=old_blocks['CEP-078']
history=current.split('    history:\n',1)[1]
head=current.split('    execution:\n',1)[0]
head=re.sub(r'    eligibility_status: .*', '    eligibility_status: ENTRY_RETAINED_PARTIAL_RUNTIME_REQUIRED_STATE_GAPS',head)
body='''    execution:
      status: PARTIAL
      lifecycle: PARTIAL_RECONCILED_REQUIRED_SOURCE_FIXTURE_AND_COVERAGE_GAPS
      advisor_review: NOT_REQUIRED_CURRENT_GOVERNANCE
    acceptance:
      passed: 4
      total: 6
      status: PARTIAL_AC1_AC3_PARTIAL_AC2_4_5_6_PASS
    dod: NOT_MET_REQUIRED_SOURCE_FIXTURE_AND_UNEXECUTED_STATE_GAPS
    blockers:
    - CEP-078-FINDING-016 / BLOCKER-DATA / Populated Billing claim lacks approved effective mandatory commercial-regulatory source and review; technical UI authority does not supply policy values
    - CEP-078-FINDING-022 / BLOCKER-DATA / Planned SC033 admin variant lacks qualified existing staff actor; Platform Admin authority is distinct; no elevation or catalogue completion inferred
    remaining_utv:
    - Full approved configured journey-state/accessibility dimensions not directly executed remain UTV; rendered-state coverage is not complete runtime acceptance
    - Populated ProgressClaim detail and qualified SC033 admin/catalogue coverage remain UTV; no new source/rate/approval/permission/staff grant invented
    - Historical row067 receipt unavailable; original404 and Edge unexecuted cells retained; separate current positive portal rows068/069 actual PASS not relabeled
    - Native screen-reader/reduced-motion and unexecuted async loading-error branches remain UTV; CSS emulation is not physical-device certification
    - REENTRY03 prior audit-event and document-number-sequence aggregate attribution remains PARTIAL; current518-model integrity PASS is limited to this continuation
    completion_report:
      path: docs/governance/cep/evidence/CEP-078_REENTRY_04/CEP-078_COMPLETION_REPORT.md
      evidence_presence: ACTUAL_RUNTIME_REMEDIATION_AND_REVALIDATION_WITH_EXPLICIT_REQUIRED_GAPS
'''
git_block=current.split('    git:\n',1)[1].split('    entry_review:\n',1)[0]
git_block=git_block.replace('remote_main_evidence: UNCOMMITTED_ENTRY_REVIEW_ONLY','remote_main_evidence: UNCOMMITTED_RUNTIME_REMEDIATION_NO_REMOTE_FRESHNESS_QUERY')
entry_review=current.split('    entry_review:\n',1)[1].split('    verification_review:\n',1)[0]
review='''    verification_review:
      evidence: docs/governance/cep/evidence/CEP-078_REENTRY_04/RUNTIME_RESULTS.json
      acceptance_mapping: docs/governance/cep/evidence/CEP-078_REENTRY_04/CEP-078_ACCEPTANCE_MAPPING.csv
      scenario_reconciliation: docs/governance/cep/evidence/CEP-078_REENTRY_04/SCENARIO_RECONCILIATION.csv
      canonical_verdict: EXECUTION PARTIAL
      entry_result: PASS_RETAINED
      ext0024: APPROVED_CHROME_EDGE_READINESS_PASS_RETAINED
      finding006: RESOLVED_BY_PRIOR_AUTHORIZED_REPAIR_AND_ACTUAL_BOTH_BROWSER_LOGIN_REVALIDATION
      finding018: RESOLVED_TOOLING_SESSION_INTERRUPTION_NO_PRODUCT_FAILURE_INFERRED
      current_final_runtime: 60_OF_60_CELLS_AND_408_ASSERTIONS_PASS_BOUNDED_SCOPE
      retained_observations: ALL_PRIOR_PASS_FAIL_UTV_AND_REMEDIATION_PRESERVED
      current_focused_validation: 53_OF_54_PASS_ONE_KNOWN_NAV019_BASELINE_ASSERTION_DEBT
      current_business_data: 515_OF_518_MODELS_UNCHANGED_ONLY_CANONICAL_SYNTHETIC_ROLE_SCOPE_CLEANUP_AND_THREE_AUDIT_APPENDS
      safari_requirement: EXCLUDED_BY_HUMAN_DECISION
'''
events='''    - date: '2026-10-23'
      status: RESUMED_AFTER_TOOLING_SESSION_INTERRUPTION
      reason: Explicit Human CEP078-only resume. First Browser inventory and fresh Chrome-Edge tabs proved control; old prior-session tab ownership handled with fresh tabs. Same main43ac319, accepted11 remediation deltas,1497 source hashes and retained gate-scope evidence grounded; no unobserved runtime product failure inferred.
    - date: '2026-10-23'
      status: BOUNDED_REMEDIATION_AND_RUNTIME_REVALIDATION
      reason: Actual remaining table-Jalali-cascade-residual-semantic checks executed; parent metadata filters only already authorized choices, month navigation preserves event path-focus, stale login assertion aligned to accepted single-main behavior. Final60 cells408 assertions PASS; original failures preserved. Focused53of54 PASS with known NAV019 baseline assertion debt; lint-format-system-whitespace PASS. No new schema-domain-policy-role-definition or financial behavior.
    - date: '2026-10-23'
      status: PARTIAL_RECONCILED
      reason: Four of six AC PASS; AC1-and-AC3 PARTIAL and DoD NOT_MET while Finding016 approved Billing source, Finding022 qualified admin variant and explicit unexecuted state dimensions remain gaps. Existing synthetic accessibility role-two-scopes revoked with independent audited services; current518-model comparison permits exactly those changes and three audit appends. Earlier data-attribution PARTIAL retained. Prior evidence unchanged, original identities restored, viewports reset, new tabs closed. All86 records/counts reconciled; global gates and079 untouched. STOP at CEP078 boundary; no Git writes-Production-Human Sign-off.
'''
new=head+body+'    git:\n'+git_block+'    entry_review:\n'+entry_review+review+'    history:\n'+history+events
text=text.replace('  CEP-078:\n'+current,'  CEP-078:\n'+new,1)
records=blocks(text)
states=Counter(re.search(r'    execution:\n      status: (\S+)',v).group(1) for k,v in records.items() if int(k[-3:])<=79)
assert states=={'COMPLETE':68,'PARTIAL':4,'NOT_STARTED':7}, states
blocked=sum('    blockers: []' not in v and '    blockers:\n' in v for k,v in records.items() if int(k[-3:])<=79 and '      status: NOT_STARTED\n' in v)
summary=section(text,'summary')
for key,value in {'execution_state_complete':states['COMPLETE'],'in_progress':states['IN_PROGRESS'],'blocked_current':blocked,'partial_current':states['PARTIAL'],'failed_current':states['FAILED'],'not_started_other_current_governed':states['NOT_STARTED']-blocked}.items():
    summary,n=re.subn(r'^  '+key+r': .*$',f'  {key}: {value}',summary,count=1,flags=re.M)
    assert n==1
text=text.replace('summary:\n'+section(text,'summary'),'summary:\n'+summary,1)
frontier=section(text,'execution_frontier')
for key,value in {'current_session_continuation':'STOP_CEP078_PARTIAL_AFTER_FINAL_AC_DOD_RECONCILIATION','next_candidate_full_entry_eligibility':'CEP078_REQUIRES_APPROVED_BILLING_SOURCE_QUALIFIED_VARIANT_AND_REMAINING_ACTUAL_STATE_EVIDENCE','boundary_reason':'Tooling interruption resolved; bounded repairs and60final cells PASS. Required source-fixture and unexecuted coverage gaps retain partial AC-DoD. Explicit Human excludes079-Production-Signoff-Git writes.'}.items():
    frontier,n=re.subn(r'^  '+key+r': .*$',f'  {key}: '+json.dumps(value),frontier,count=1,flags=re.M)
    assert n==1
text=text.replace('execution_frontier:\n'+section(text,'execution_frontier'),'execution_frontier:\n'+frontier,1)
assert len(records)==86
assert all(records[k]==v for k,v in old_blocks.items() if k!='CEP-078')
assert records['CEP-078'].split('    history:\n',1)[1].startswith(history)
for name in ('governance','inventory','gates','authorization_batches','authority_scope','v1_closure_triage','repository_state','human_decisions'):
    assert section(text,name)==section(before,name),name
REG.write_bytes(text.replace('\n','\r\n').encode('utf-8'))
(OUT/'REGISTRY_DELTA.diff').write_text(''.join(difflib.unified_diff(initial.splitlines(True),text.splitlines(True),fromfile='Registry_at_resume',tofile='Registry_after_CEP078_reconciliation')),encoding='utf-8')
assert read('DATA_INTEGRITY.json')['result']=='PASS'
check={'at':datetime.now(timezone.utc).isoformat(),'result':'PASS_BOUNDED_RECONCILIATION_AND_EVIDENCE_INTEGRITY','cep_disposition':'EXECUTION PARTIAL;4of6AC PASS;DoD NOT_MET','final_runtime_cells':60,'final_runtime_assertions':408,'runtime_original_records':64,'prior_reentry_files_preserved':len(entry['prior_evidence']),'accepted_audit_artifacts_preserved':accepted_count,'product_sources_checked':len(sources),'authorized_current_changed_sources':sorted(changed),'other_cep_records_unchanged':85,'all_cep_records':86,'calculated_current_governed_states':dict(states),'calculated_blocked_not_started':blocked,'head_index_and_unrelated_sources_unchanged':True,'canonical_prompt_and_matrix_sources_unchanged':True,'all_gates_and_human_decisions_unchanged':True,'data_integrity':'518models;515unchanged;one synthetic role-two scopes-three audit appends only','prior_data_attribution':'REENTRY03 PARTIAL preserved; not retrospectively resolved','tests':'53of54 distinct PASS;one known NAV019 baseline failure;initial failures retained','git_writes_production_signoff_cep079':'NOT_EXECUTED','yaml_method':'Bounded block edits and86record/scalar verification; no full YAML conformance claim','manifest_self_hashes':'Excluded to avoid circularity','stop':'CEP078_PARTIAL_FINAL_RECONCILIATION_COMPLETE'}
save('CLOSEOUT_CHECK.json',check)
changes=[{'path':p,'kind':'BOUNDED_TECHNICAL_PRODUCT_OR_TEST_REMEDIATION','before_sha256':entry['product_hashes'][p],'after_sha256':sources[p]} for p in sorted(changed)]
changes.append({'path':'CEP_EXECUTION_REGISTRY.yaml','kind':'BOUNDED_CEP078_STATE_HISTORY_SUMMARY_FRONTIER','before_sha256':'NORMALIZED_LF_SHA256:'+hashlib.sha256(before.encode()).hexdigest(),'after_sha256':sha(REG)})
for p in sorted(OUT.rglob('*')):
    if p.is_file() and '__pycache__' not in p.parts and p.name not in {'CEP-078_CHANGE_MANIFEST.csv','CEP-078_EVIDENCE_MANIFEST.csv'}:
        changes.append({'path':p.relative_to(ROOT).as_posix(),'kind':'NEW_CEP078_CONTINUATION_EVIDENCE','before_sha256':'ABSENT','after_sha256':sha(p)})
write_csv('CEP-078_CHANGE_MANIFEST.csv',changes)
files=[p for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='CEP-078_EVIDENCE_MANIFEST.csv']
write_csv('CEP-078_EVIDENCE_MANIFEST.csv',[{'evidence_id':f'CEP-078-EV-{i:03d}','path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'kind':'Actual continuation artifact; see explicit scoped PASS/FAIL/PARTIAL/UTV; no blanket acceptance','result':'RETAINED_ACTUAL_EVIDENCE'} for i,p in enumerate(files,200)])
print(json.dumps({'integrity':check['result'],'final_runtime':'60/60 cells;408/408 assertions PASS','cep':'PARTIAL;4/6 AC PASS;DoD NOT_MET','prior_files_preserved':len(entry['prior_evidence']),'accepted_artifacts_preserved':accepted_count,'other_ceps_preserved':85,'evidence_files':len(files),'states':dict(states)}))
