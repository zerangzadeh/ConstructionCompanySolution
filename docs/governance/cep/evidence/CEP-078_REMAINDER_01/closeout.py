"""Narrow CEP078 closeout; preserve every other CEP and Gate verbatim in meaning."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / '.pytest_cache/cep_tools'))
import yaml

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
entry = json.loads((OUT/'ENTRY.json').read_text(encoding='utf8'))
registry_path = ROOT/'CEP_EXECUTION_REGISTRY.yaml'
original = registry_path.read_text(encoding='utf8')
registry = yaml.safe_load(original)
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() == entry['head']
for key, expected in entry['all_other_cep_hashes'].items():
    assert digest(registry['ceps'][key]) == expected, key
assert registry['gates'] == entry['gate_state']
runtime = json.loads((OUT/'RUNTIME_FINAL.json').read_text(encoding='utf8'))
assert len(runtime) == 6 and all(c['result']=='PASS' for c in runtime)
assert '7 passed, 8 subtests passed' in (OUT/'FOCUSED_FINAL.txt').read_text(encoding='utf-8-sig')
statutory = json.loads((OUT/'STATUTORY_CURRENT.json').read_text(encoding='utf8'))
assert statutory['qualification']['missing_statutory_input_or_review_for_this_fixture'] == []

cep = registry['ceps']['CEP-078']
cep['eligibility_status'] = 'PARTIAL_REMAINING_EXTERNAL_NATIVE_AND_BROWSER_INPUT_RUNTIME'
cep['authorization']['source'] += '; direct Human SC033 decision approves Development-only read-only all26 definition/readiness discovery for governed Platform Admins; no tenant/object disclosure or authority grant'
cep['execution']['lifecycle'] = 'PARTIAL_SC033_RESOLVED_STATUTORY_SOURCE_QUALIFIED_SC014_BROWSER_AND_ACCESSIBILITY_UTV'
cep['dod'] = 'NOT_MET_REQUIRED_SC014_BROWSER_AND_ACCESSIBILITY_RUNTIME'
cep['blockers'] = [
    'BLOCKER-EXTERNAL / Actual reduced-motion and native screen-reader target runtime UTV: Narrator/Speech Recap available, but Speech Recap higher Windows integrity than helper; Settings recovery and Chrome activation fail. No security boundary bypass or static PASS.',
    'BLOCKER-EXTERNAL / SC014 populated ProgressClaim six supported browser cells UTV: qualified existing claim/source/review and authenticated Django200 render PASS; ordinary browser input/session switching unresponsive. No server-render-to-browser PASS inference.',
]
cep['remaining_utv'] = [
    'Actual reduced-motion and native screen-reader BONIRA target announcements; no WCAG conformance claim',
    'SC014 populated detail Chrome/Edge1440x900,1024x768,390x844; source inputs now qualified, browser input/control must recover',
    'Temporary Narrator/Speech Recap requires desktop cleanup; native Insert+Escape recovery failed activation; Human intervention requested',
    'All older failures/UTV and limits retained within their original evidence scope; completed coverage not rerun',
]
cep['completion_report']['evidence_presence'] = 'SC033_6_FINAL_PASS_CELLS_7_TESTS_8_SUBTESTS_STATUTORY_RESOLVER_AND_CLAIM_SERVER_PASS_EXTERNAL_RUNTIME_GAPS'
cep['verification_review']['current_remainder_evidence'] = 'docs/governance/cep/evidence/CEP-078_REMAINDER_01/REMAINDER_REPORT.md'
cep['verification_review']['finding016'] = 'SOURCE_REVIEW_ABSENCE_RESOLVED_FOR_EXISTING_HUMAN_APPROVED_DEVELOPMENT_UAT_FIXTURE;SC014_BROWSER_UTV'
cep['verification_review']['finding032'] = 'RESOLVED_DIRECT_HUMAN_ALL26_PLATFORM_ADMIN_DISCOVERY_DECISION_IMPLEMENTED_AND_6_BROWSER_CELLS_PASS'
cep['verification_review']['native_accessibility'] = 'AVAILABLE_NARRATOR_AND_SPEECH_RECAP;TARGET_RUNTIME_UTV_HIGHER_INTEGRITY_AND_ACTIVATION_BOUNDARY'
cep['updated_at'] = '2026-10-26'
cep['history'].append({'date':'2026-10-26','status':'CEP078_ONLY_REMAINDER_PARTIAL',
    'reason':'Direct Human SC033 decision implemented bounded Development-only read-only all26 catalogue;6final Chrome/Edge size cells PASS,7focused tests+8subtests PASS. Dated source-backed readiness separated from current mapped-account availability; no tenant detail/authority grant. Current published regulatory v2, real source links and Human-qualified ACCEPTED UAT review plus existing claim supersede old data-absence blocker; read-only native resolver and scoped authenticated Django200 render PASS. SC014 browser cells, reduced-motion and native target screen-reader UTV after higher-integrity Speech Recap/Settings/Chrome activation and ordinary browser input failure. No static/server-render inference; all prior coverage retained, no otherCEP/Gate/Git/Production actions. Evidence CEP-078_REMAINDER_01.'})

frontier = registry['execution_frontier']
frontier['current_session_continuation'] = 'STOP_EXTERNAL_NATIVE_AND_BROWSER_INPUT_BOUNDARY_CEP078_REMAINDER'
frontier['current_session_cep_range'] = 'CEP-078_ONLY'
frontier['boundary_reason'] = frontier['boundary_reason'].replace('078_F016_F032_REDUCED_MOTION_NATIVE_SCREENREADER','078_SC014_BROWSER_INPUT_REDUCED_MOTION_NATIVE_SCREENREADER')
frontier['resume_cep_after_blocker_resolution'] = 'CEP-078'
frontier['unblock_conditions']['CEP-078'] = 'Restore controllable native/browser targets; execute SC014 populated detail6cells plus actual reduced-motion and native screen-reader target runtime. SC033 decision/implementation resolved; statutory source/review qualified for existing approved UAT contract.'
frontier['independent_candidates_entry_status'] = frontier['independent_candidates_entry_status'].replace('07839CURRENT_PASS_CELLS469ASSERTIONS_PARTIAL_REQUIRED_EXTERNAL_GAPS','078_SC033_RESOLVED_STATUTORY_QUALIFIED_PARTIAL_REQUIRED_EXTERNAL_RUNTIME')
assert frontier['next_executable_frontier'] == []

new_cep = '  CEP-078:\n' + '\n'.join('    '+line if line else '' for line in yaml.safe_dump(cep,sort_keys=False,allow_unicode=True,width=140).rstrip().splitlines()) + '\n'
updated, count = re.subn(r'^  CEP-078:\n.*?(?=^  CEP-079:)',lambda m:new_cep,original,flags=re.M|re.S)
assert count == 1
frontier_text = yaml.safe_dump({'execution_frontier':frontier},sort_keys=False,allow_unicode=True,width=140)
updated, count = re.subn(r'^execution_frontier:\n.*\Z',lambda m:frontier_text,updated,flags=re.M|re.S)
assert count == 1
parsed = yaml.safe_load(updated)
assert parsed['gates'] == entry['gate_state']
assert all(digest(parsed['ceps'][key])==expected for key,expected in entry['all_other_cep_hashes'].items())
registry_path.write_text(updated,encoding='utf8')

base = ROOT/'docs/governance/cep/evidence'
mapping = base/'CEP-078_ACCEPTANCE_MAPPING.csv'
with mapping.open(encoding='utf8',newline='') as handle:
    reader=csv.DictReader(handle); rows=list(reader); fields=reader.fieldnames
for row in rows:
    row['reuse_disposition'] += '; CEP078 remainder: SC0336final PASS cells;7tests8subtests PASS;current statutory resolver/claim server PASS;prior coverage retained'
    if row['criterion'] in {'AC-1','AC-3'}:
        row['remaining_gap']='SC014 populated-detail supported browser6cells; actual reduced-motion/native screen-reader target execution; external control boundary only'
    row['evidence_ids'] += ';CEP-078-EV-015;CEP-078-EV-016;CEP-078-EV-017'
with mapping.open('w',encoding='utf8',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)

report = ROOT/'docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md'
with report.open('a',encoding='utf8') as handle:
    handle.write('\n\n## CEP078-only remainder — 2026-10-26\n\nEXECUTION PARTIAL. [Current exact result](../evidence/CEP-078_REMAINDER_01/REMAINDER_REPORT.md) supersedes only the old F016/F032 blocker descriptions. Direct Human SC033 decision implemented: Development-only read-only all26 catalogue, existing active Platform Admin guard, no authority grant/protected tenant details. Six final supported browser size cells PASS;7focused tests+8subtests PASS. Existing effective Human-qualified UAT statutory source/review and populated claim recovered; native resolver and authenticated Django200 render PASS. No missing statutory input/review or persona Product question for this target. Required reduced-motion/native screen-reader target runtime and SC014 six actual browser cells remain UTV due external native/browser input limits. Narrator is available; the earlier browser-only-unavailability statement is historical, not current. AC2/4/5/6 PASS;AC1/3 PARTIAL;DoD NOT_MET;Gates unchanged;next_executable_frontier []. All prior evidence and completed coverage retained. No Git writes, otherCEP execution, Production or Human Sign-off.\n')

change_paths = ['apps/organizations/reference_personas.py','apps/organizations/reference_personas.json','apps/organizations/test_reference_personas.py','apps/organizations/urls.py','apps/organizations/context_processors.py','templates/organizations/reference_personas.html','templates/base.html','config/settings/base.py','config/settings/development.py']
with (base/'CEP-078_CHANGE_MANIFEST.csv').open('a',encoding='utf8',newline='') as handle:
    writer=csv.writer(handle)
    for p in change_paths:writer.writerow([p,'NEW' if p.endswith(('reference_personas.py','reference_personas.json','test_reference_personas.py','reference_personas.html')) else 'MODIFIED','Direct Human approved SC033 bounded Development discovery; no tenant/object detail or authority grant'])

index = {'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'artifacts':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in {'ARTIFACT_INDEX.json','INTEGRITY.json'}],
    'source_hashes':{p:sha(ROOT/p) for p in change_paths},'browser_versions':{'Chrome':'155.0.8059.82','Edge':'156.0.4314.42'},
    'version_binding':'Read-only running process module version aggregation; no per-tab process binding claim',
    'os':'Windows10.0.26200','no_git_write':True,'no_production':True}
(OUT/'ARTIFACT_INDEX.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf8')
with (base/'CEP-078_EVIDENCE_MANIFEST.csv').open('a',encoding='utf8',newline='') as handle:
    writer=csv.writer(handle)
    for number,name,kind in [(15,'ARTIFACT_INDEX.json','Actual bounded artifact/source index'),(16,'STATUTORY_CURRENT.json','Current existing source/review/native resolver qualification'),(17,'RUNTIME_FINAL.json','Six final SC033 supported browser-size discovery results')]:
        p=OUT/name
        writer.writerow([f'CEP-078-EV-{number:03d}',str(p.relative_to(ROOT)).replace('\\','/'),sha(p),kind,'PARTIAL_WITH_EXPLICIT_SCOPED_PASS_AND_UTV'])
print('CEP078 and its frontier reconciled; all85 other CEPs and all Gates unchanged.')
