"""Evidence-supported closeout; preserves unrelated CEPs, gates and prior results."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path('.pytest_cache/cep_tools').resolve()))
import yaml

OUT=Path(__file__).parent;BASE=OUT.parent
load=lambda name:json.loads((OUT/name).read_text(encoding='utf8'))
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
entry=load('ENTRY.json');raw=load('CEP078_RUNTIME.json')
passed=[r for r in raw if r['result']=='PASS'];failed=[r for r in raw if r['result']=='FAIL']
assert len(passed)==39 and len(failed)==14
assert sum(len(r['checks']) for r in passed)==469
assert load('FIXTURE_CLEANUP.json')['total_order_count_unchanged']
assert load('DOCUMENT_ERROR_INTEGRITY.json')['all_document_version_link_rows_unchanged']
current_claims={
    'CEP-078-SC-003-C04':('HOME-FINAL-403','Actual Home403 source branch in isolated loopback fixture; no natural membership revocation claimed'),
    'CEP-078-SC-003-C05':('HOME-FINAL-503','Actual Home503 source branch in isolated loopback fixture; no real outage claimed'),
    'CEP-078-SC-003-C06':('HOME-FINAL','Actual keyboard recovery from both bounded source-fault states'),
    'CEP-078-SC-008-C03':('PO-MISMATCH','Actual canonical POST rejection from labelled invalid-request driver; unchanged validators/CSRF/auth/tenant controls; zero orders created'),
    'CEP-078-SC-028-C06':('DOCUMENT-LINK-ERROR','Actual native document400 error and keyboard; prior20261025 denial cells retained separately; Chrome upload3extra cells'),
    'CEP-078-SC-030-C06':('COMMERCIAL-FIXED','Actual detail-to-review keyboard navigation using compatible existing scoped read authority; no role assignment'),
    'CEP-078-SC-032-C06':('PORTAL','Actual context/receipt keyboard and native required-file error; new labelled native fixture; zero browser quote submissions; grant revoked after verification'),
}
with (OUT/'CEP078_CLAUSE_DELTA.csv').open('w',encoding='utf8',newline='') as f:
    w=csv.writer(f);w.writerow(['canonical_clause','current_result','actual_records','scope_and_limit'])
    for key,(token,limit) in current_claims.items():
        rows=[r['id'] for r in passed if token in r['id']]
        w.writerow([key,'PASS_BOUNDED_RUNTIME',';'.join(rows),limit])
remaining=[
    'CEP-078-FINDING-016 / BLOCKER-DATA / Populated ProgressClaim requires accepted effective statutory values/bases, external provenance and professional review; no approved package available in qualified sources',
    'CEP-078-FINDING-032 / BLOCKER-PD / Defined-unprovisioned-global-nonmember persona discovery/readiness representation requires governed Product/UI authority decision',
    'BLOCKER-EXTERNAL / Required reduced-motion and native screen-reader execution unavailable through enabled browser-only control; documented capabilities expose viewport only for this purpose, native apps disabled; no WCAG conformance or unexecuted PASS',
]
close={
    'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':entry['head'],
    'state':'EXECUTION PARTIAL','pass_cells':39,'pass_assertions':469,'retained_failed_attempts':14,
    'failure_attribution':{'commercial_missing_scoped_link':6,'stylesheet_probe_false_assumption':6,'mobile_portal_fixed_index_assumption':2},
    'attributable_product_defects_fixed':['CEP-078-FINDING-033 scoped contract-review navigation'],
    'unresolved_new_attributable_product_defects':0,
    'ac':{'passed':4,'total':6,'partial':[1,3],'pass':[2,4,5,6]},'dod':'NOT_MET_REQUIRED_DATA_PRODUCT_AND_ACCESSIBILITY_EVIDENCE',
    'current_clause_delta':'CEP078_CLAUSE_DELTA.csv','remaining_blockers':remaining,
    'prior_evidence':'Original observations/failures/UTV retained; no blanket freshness claim for older144cells or accepted UIUX',
    'validation':['9supply-chain testsPASS','3contract navigation tests+2subtestsPASS','20ListDetail tests+24subtestsPASS','Django0issues','RuffPASS'],
    'fixture_limits':'Home/PO use real current DjangoWSGI+static source in disposable8002; labelled fault/request generators only; no normal8000 configuration changes; native portal fixture retained and newgrant revoked',
    'additional_nonblocking_observation':'Optional document category selector displays existing model-object label with UUID; outside the remaining error-state assertion; no claim of complete document semantic conformance',
    'production_signoff_git':'NOT_EXECUTED',
}
save('CEP078_CLOSEOUT.json',close)

# Current residual eligibility is derived from unchanged canonical contracts and
# retained approved-source evidence, not a new audit or production assertion.
registry_path=Path('CEP_EXECUTION_REGISTRY.yaml');text=registry_path.read_text(encoding='utf8');before=yaml.safe_load(text)
recheck={'at':close['at'],'head':entry['head'],'canonical_prompts':'10of10 verified; no scope/AC/DoD/dependency edits','records':{}}
for n in range(69,77):
    key=f'CEP-{n:03d}';r=before['ceps'][key]
    recheck['records'][key]={'execution':r['execution']['status'],'blockers':r['blockers'],'newly_eligible':False}
recheck['gate06']='NOT_PASSED; canonical migration/history/reconciliation/rollback proof for012 remains unverified in retained approved recovery. Historical COMPLETE preserved; no universal nonexistence claim. Exact-build EXT0023 readiness not proved.'
recheck['nonproduction_foundations']='069..072 already prepared; current070recovery objectives,071topology,072named operational ownership/runbooks and069accepted statutory evidence remain authoritative-input gaps, not ordinary local configuration failures'
recheck['new_image_outcome']='077 has no dependency edge unlocking069..076; GATE08 still requires all073..078 contributions'
save('FRONTIER_RECHECK.json',recheck)

start=re.search(r'^  CEP-078:\n',text,re.M).start()
end=re.search(r'^  CEP-079:\n',text,re.M).start()
block=text[start:end]
block=block.replace('eligibility_status: PARTIAL_REQUIRED_SOURCE_PRODUCT_AND_QUALIFIED_RUNTIME_GAPS','eligibility_status: PARTIAL_REMAINING_STATUTORY_PRODUCT_DECISION_AND_ACCESSIBILITY_RUNTIME')
block=block.replace('lifecycle: PARTIAL_WORKFORCE_AND_DOCUMENT_DENIAL_RUNTIME_ADVANCED','lifecycle: PARTIAL_39_CURRENT_RUNTIME_CELLS_PASS_REQUIRED_EXTERNAL_GAPS')
block=block.replace('dod: NOT_MET_REQUIRED_SOURCE_DECISION_AND_ACTUAL_RUNTIME_GAPS','dod: NOT_MET_REQUIRED_STATUTORY_PRODUCT_AND_ACCESSIBILITY_RUNTIME')
bs=block.index('    blockers:\n');be=block.index('    completion_report:\n',bs)
new=yaml.safe_dump({'blockers':remaining,'remaining_utv':[
    'Finding016 statutory source package and accepted review; Finding032 Product persona-discovery decision',
    'Reduced-motion and native screen-reader runtime unexecuted; no fullWCAG conformance claim',
    'Prior REENTRY03 aggregate attribution and all original failures/limitations remain historical; current39cells do not requalify every older runtime assertion',
]},sort_keys=False,width=140,allow_unicode=True)
block=block[:bs]+''.join('    '+line for line in new.splitlines(True))+block[be:]
block=re.sub(r'evidence_presence: CURRENT12_ACTUAL_PASS_CELLS84_ASSERTIONS_PLUS_RETAINED_PARTIAL_EVIDENCE_REQUIRED_GAPS','evidence_presence: CURRENT39_PASS_CELLS469_ASSERTIONS_14_PRIOR_ATTEMPTS_RETAINED_REQUIRED_EXTERNAL_GAPS',block)
block=re.sub(r'(last_execution:\n      branch: main\n      sha: )[a-f0-9]+',r'\g<1>'+entry['head'],block,count=1)
block=block.replace("updated_at: '2026-10-25'","updated_at: '2026-10-26'",1)
block=block.replace('current_frontier_runtime: 12_NEW_CURRENT_PASS_CELLS84_ASSERTIONS;WORKFORCE_F031_RESOLVED;DOCUMENT_UNAUTHORIZED_ONLY','current_frontier_runtime: 39_CURRENT_PASS_CELLS469_ASSERTIONS_HOME_PO_DOCUMENT_COMMERCIAL_PORTAL;14_FAILED_ATTEMPTS_PRESERVED')
block=block.replace('current_frontier_evidence: docs/governance/cep/evidence/FRONTIER_069_078_20261025/CEP078_CLOSEOUT.json','current_frontier_evidence: docs/governance/cep/evidence/FRONTIER_20261026/CEP078_CLOSEOUT.json')
# All original history bytes are preserved; only append current material events.
history=[
    {'date':'2026-10-26','status':'RESUMED','reason':'Current Human frontier request; actual Chrome155/Edge156 and canonical scoped entry qualified; current dirty-source identity retained. Ordinary fixture/probe issues corrected within Development; no new business policy or tenant permission.'},
    {'date':'2026-10-26','status':'ATTRIBUTABLE_DEFECT_FIXED','reason':'Finding033: contract detail hid permitted project-scoped commercial review. Link now uses existing per-project permission predicate, same as source service.3focused tests+2scope subtestsPASS;6actual keyboard cellsPASS. No role/catalog/endpoint/business-rule change.'},
    {'date':'2026-10-26','status':'PARTIAL','reason':'39actualPASS cells469assertions;14initialfailedattempts retained and attributed. Home403/503 isolated faults, exactPO mismatch realPOST, documenterror, commercial keyboard and externalportal/receipt keyboard executed. Newsynthetic45minute portalgrant canonically revoked; zeroexternaltenantmemberships; noPOcreated; document-error rows unchanged. RemainingF016/F032/reduced-motion/native-screenreader;4of6AC,DoDNOT_MET.20ListDetail+24subtestsPASS;Django0,RuffPASS. No migrations/Git/Production/Signoff.','evidence':'docs/governance/cep/evidence/FRONTIER_20261026/CEP078_CLOSEOUT.json'},
]
block+=''.join('    '+line for line in yaml.safe_dump(history,sort_keys=False,width=140,allow_unicode=True).splitlines(True))
text=text[:start]+block+text[end:]

front=before['execution_frontier']
front['dependency_ready_current_governed']=[x for x in front['dependency_ready_current_governed'] if x!='CEP-077']
front.update(verified_build_eligible_unblocked=[],verified_verification_eligible_unblocked=[],next_executable_frontier=[],next_autonomous_cep=None,current_session_continuation='STOP_NO_EXECUTABLE_FRONTIER_REQUIRED_AUTHORITATIVE_INPUTS_AND_ACCESSIBILITY_RUNTIME',current_independent_cep=None,next_entry_review_candidate=None,next_candidate_full_entry_eligibility='NONE_UNBLOCKED_CURRENTLY',boundary_reason='069_STATUTORY;070_RECOVERY_POLICY;071_TOPOLOGY;072_OPERATING_INPUTS;073_GATE06_EXT0023;074_076_PREREQUISITE_EXT;078_F016_F032_REDUCED_MOTION_NATIVE_SCREENREADER',independent_candidates_entry_status='077_COMPLETE;07839CURRENT_PASS_CELLS469ASSERTIONS_PARTIAL_REQUIRED_EXTERNAL_GAPS;069_076_RECHECKED_NO_NEW_ELIGIBILITY;079_COMPLETE_SKIPPED')
front['unblock_conditions'].pop('CEP-077',None)
front['unblock_conditions']['CEP-078']='Finding016 accepted statutory data/review;Finding032 governed persona-discovery decision;actual supported reduced-motion and native screen-reader runtime'
text=text[:text.index('execution_frontier:\n')]+yaml.safe_dump({'execution_frontier':front},sort_keys=False,width=140,allow_unicode=True)
text=text.replace('      evidence: docs/governance/cep/evidence/FRONTIER_069_078_20261025/CEP077_RETRY.json','      evidence: docs/governance/cep/evidence/FRONTIER_069_078_20261025/CEP077_RETRY.json')
# Gate08 status is retained while its stale failure rationale is reconciled.
gs=text.index('  GATE-08:\n');ge=text.index('  GATE-07:\n',gs)
gate=before['gates']['GATE-08'];gate.update(evaluated_at='2026-10-26',evidence='docs/governance/cep/evidence/FRONTIER_20261026/CEP077_CLOSEOUT.json',note='CEP077 required contribution now PASS from actual fresh supply-chain gate. Global GATE08 NOT_PASSED:073..076 and078 remain incomplete; no production, certification or static-to-runtime inference.')
text=text[:gs]+''.join('  '+line for line in yaml.safe_dump({'GATE-08':gate},sort_keys=False,width=140).splitlines(True))+text[ge:]
after=yaml.safe_load(text)
for key,r in after['ceps'].items():
    if key not in ['CEP-077','CEP-078']: assert r==before['ceps'][key],key
assert after['ceps']['CEP-078']['history'][:-3]==before['ceps']['CEP-078']['history']
for key,value in after['gates'].items():assert value['status']==before['gates'][key]['status'],key
assert len([r for r in after['ceps'].values() if r['execution']['status']=='COMPLETE'])==70
registry_path.write_text(text,encoding='utf8')

with Path('docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md').open('a',encoding='utf8') as f:f.write('''

## Current frontier continuation — 2026-10-26

**EXECUTION PARTIAL.** Current main/origin `961e3fd942c668337012c22d42f59545c5e9fc0a`.
[Current evidence](../evidence/FRONTIER_20261026/CEP078_CLOSEOUT.json): **39actual PASS cells,
469assertions**, Chrome155.0.8059.82 / Edge156.0.4314.42, CSS1440x900/1024x768/390x844.
All14initial failed attempts remain:6actual missing-navigation failures fixed by the
bounded per-project link predicate;6stylesheet-probe assumptions and2mobile fixed-index
assumptions corrected without product changes. No unresolved attributable defect from
this continuation. The optional document-category technical label was observed as a
nonblocking adjacent limitation; no complete document semantic-conformance claim.

[Exact clause delta](../evidence/FRONTIER_20261026/CEP078_CLAUSE_DELTA.csv) records:
Home403/503 and keyboard recovery12cells; contract detail/review keyboard6cells;
document native400error6cells plus3Chrome rejected-upload cells; external portal/receipt
keyboard and native required-file error6cells; exactPO mismatch POST/error semantics6cells.
Home and PO use a labelled disposable loopback8002 current DjangoWSGI/static fixture:
Home exception seam and invalid-request generator only. PO response is from the unchanged
canonical endpoint with normal CSRF/auth/tenant enforcement; all test IDs were permitted,
cross-project mismatch rejected, **zero orders created**. These are controlled technical
fixture results, not a real outage or a claim that ordinary users can select a hidden option.

Finding033 fixed: project-scoped reviewer could reach commercial review directly while
the contract-detail template hid its link. The detail now calls the existing project-bound
permission predicate. No authorization semantics, role, default grant, workflow, domain
service or schema change.3focused tests+2scope subtestsPASS;20affected ListDetail tests+
24subtestsPASS; RuffPASS; Django0issues. Accepted UIUX closure master unchanged;
`List → Detail consistency: RESOLVED` retained. No broad regression rerun.

Document-error submissions preserve all preexisting Document/Version/Link fingerprints.
Expired external portal fixture replaced through the same canonical synthetic lifecycle;
new labelled RFQ/version/grant/quote/receipt/custody retained, old source/expiry untouched.
The new45minute grant was canonically revoked after verification; external tenant
memberships0, browser quote submissions0. Shared8000server unchanged;8002stopped.
Temporary viewport overrides reset; Edge original actor restored. Chrome test session
logged out: original02owner credential was not in custody, so its login cannot be restored
without user authentication; no credential reset or session injection occurred.

AC2/4/5/6 PASS, AC1/3 PARTIAL; scopedDoD NOT_MET. Remaining blockers are exactly
Finding016 accepted statutory values/bases/provenance/professional review, Finding032
governed global/unprovisioned persona-discovery representation, and actual reduced-motion/
native screen-reader execution unavailable on enabled browser-only controls. No WCAG
conformance, missing runtime PASS, blanket requalification of older144cells, Human
Sign-off or Production Certification is inferred. Prior observations and UTV remain.
069..076 entry rechecked; canonical prerequisites/authoritative-input gaps unchanged.
Gate statuses unchanged; next executable frontier empty. Git writes/Production NOT_EXECUTED.
''')

for cep in ['077','078']:
    p=Path(f'docs/governance/cep/manifests/CEP-{cep}_EXECUTION_MANIFEST.md')
    with p.open('a',encoding='utf8') as f:f.write(f'\n\n## Current20261026 closeout\n\nCurrent main/origin `{entry["head"]}`; current Human frontier/attributable Development repair authority. Actual touch set, source hashes, bounded fixtures, tests and limits are in [current entry](../evidence/FRONTIER_20261026/ENTRY.json), [result](../evidence/FRONTIER_20261026/CEP{cep}_CLOSEOUT.json) and the current Completion Report appendix. No schema/migration, Git write, Production or Human Sign-off. Prior artifacts/history retained.\n')

# Root evidence pointers stay usable while original dated result artifacts remain immutable.
p=BASE/'CEP-078_EVIDENCE_MANIFEST.csv'
with p.open(encoding='utf8',newline='') as f:fields=next(csv.reader(f))
with p.open('a',encoding='utf8',newline='') as f:
    w=csv.writer(f)
    for i,name,description in [
        (11,'CEP078_RUNTIME.json','39PASS469assertions;14initialfailures preserved'),
        (12,'CEP078_CLAUSE_DELTA.csv','Exact current seven-clause delta; no fullconformance claim'),
        (13,'CEP078_CLOSEOUT.json','Current PARTIAL; remaining source/Product/accessibility gaps'),
        (14,'FIXTURE_CLEANUP.json','Native grant revoked; zero tenant memberships/PO creation/browser quote submissions'),
    ]:w.writerow([f'CEP-078-EV-{i:03d}',str(OUT/name).replace('\\','/'),sha(OUT/name),description,'ACTUAL_BOUNDED_CURRENT_EVIDENCE'])

save('FINAL_STATE.json',{'head':entry['head'],'attempted':['CEP-077','CEP-078'],'eligibility_rechecked':['CEP-%03d'%n for n in range(69,77)],'completed':['CEP-077'],'advanced':['CEP-078'],'gate_status_changes':[],'next_executable_frontier':[],'remaining_blockers':{'CEP-078':remaining,'CEP-069..076':'FRONTIER_RECHECK.json'},'production_git_signoff':'NOT_EXECUTED'})
print('CEP077 COMPLETE; CEP078 PARTIAL39PASS469assertions; next_executable_frontier=[]; all gate statuses unchanged')
