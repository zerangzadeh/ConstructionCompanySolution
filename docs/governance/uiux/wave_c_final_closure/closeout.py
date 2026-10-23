"""Append current Wave C disposition; retain historical evidence and closed findings."""
import copy,hashlib,json,re,sys,textwrap,xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent;BASE=OUT.parent
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/bonira-wave-c-tools'))
import yaml
stamp=datetime.now(ZoneInfo('Asia/Tehran')).isoformat();decision='WAVE_C_PENDING_REAL_TIME_CONDITION'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def save(name,data):(OUT/name).write_text(json.dumps(data,default=str,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def dump(data):return yaml.safe_dump(data,allow_unicode=True,sort_keys=False,width=110)
attr=read('REGRESSION_ATTRIBUTION.json');assert attr['counts']=={'BASELINE_PREEXISTING':3,'ATTRIBUTABLE_REGRESSION':7,'INDETERMINATE':0} and attr['unresolved_attributable_regressions']==0
cases=list(ET.parse(OUT/'affected_final.xml').iter('testcase'));failures=[c for c in cases if c.find('failure') is not None];assert len(cases)==47 and len(failures)==2 and all('test_p5_s26_s27_match_review' in c.attrib['classname'] for c in failures)
http=read('EMPLOYMENT_HTTP.json');assert len(http)==10 and all(r['passed'] for r in http)
controls=read('EMPLOYMENT_CONTROLS.json');assert len(controls['identity_probes'])==2 and controls['explicit_identity_preserved']
assert read('INTEGRITY.json')['rfq_dates_and_state_unchanged']
browser=read('BROWSER.json');required=['tender_list_desktop','tender_list_mobile','tender_create_desktop','tender_create_mobile','tender_draft_desktop','tender_review_desktop','tender_review_mobile','tender_final_desktop','tender_final_mobile','tender_project_context_desktop','employment_manage_desktop','employment_manage_mobile','employment_employee_detail_desktop','employment_employee_detail_mobile','employment_invalid_desktop','employment_invalid_mobile','employment_own_actual_desktop','employment_own_actual_mobile','employment_own_history_lower_mobile']
selected=[]
for label in required:
 row=next(r for r in reversed(browser) if r['label']==label and not r.get('verification_status'))
 assert row['main_count']==1 and not row['overflow'] and not row['duplicate_ids'],label
 assert row['viewport']['width']==(390 if 'mobile' in label else 1440),label
 assert (OUT/(label+'.png')).is_file(),label
 if label.startswith('employment_own_'):assert row['path']=='/workforce/ess/employment/' and 'تاریخی' in row['visible_text'] and 'مؤثر' in row['visible_text']
 if label.startswith('employment_manage'):assert 'Person object (' not in row['visible_text']
 selected.append(row)
save('BROWSER_RECONCILIATION.json',{'recorded_at':stamp,'browser':'Chrome extension, browser ID 3','required_captures':required,'representative_capture_count':len(selected),'desktop':[1440,1000],'mobile':[390,844],'all_selected_one_main_no_overflow_unique_ids':True,'RV-030':'PASS','RV-029':'PASS','temporary_timeouts':'Recovered using documented APIs/fresh tab; superseded wrong-tab/viewport attempts are explicitly flagged in BROWSER.json','environment_settings_changed':False,'remaining_browser_blocker':None,'keyboard_observations':{'Tender':'Tab moved from transition_reason to transition_submission_reference; blue border rgb(37,99,235) and 3px rgb(219,234,254) focus shadow','Own history':'Tab moved to own Requests link; visible rgb(59,130,246) solid 1.6px outline','scope':'Basic keyboard/focus only; no comprehensive accessibility certification'}})
prior={'RV-009':'wave_c_evidence/VERIFICATION.json','RV-015':'wave_c_reentry/FINAL_VERIFICATION.json','RV-017':'wave_c_reentry/FINAL_VERIFICATION.json','RV-028':'wave_c_reentry/FINAL_VERIFICATION.json','RV-031':'wave_c_reentry/FINAL_VERIFICATION.json'}
details={
 'RV-007':('PENDING_REAL_TIME_CONDITION','Issued canonical RFQ unchanged. Close 2026-10-24 14:46:11 Tehran; earliest opening 2026-10-25 14:46:11 Tehran. Protected opening/comparison and post-close browser controls not executed.','RFQ_REAL_TIME.json'),
 'RV-009':('PASS','Prior accepted Inventory result retained; no Inventory changes.','../'+prior['RV-009']),
 'RV-011':('PASS','D01 effective Development monetary bridge and populated statements; prior evidence retained.','../wave_c_domain_resolution/FINAL_VERIFICATION.json'),
 'RV-013':('PASS','Approved AP source, compatible posted Treasury source and settlement; prior evidence retained.','../wave_c_domain_resolution/FINAL_VERIFICATION.json'),
 'RV-015':('PASS','Prior workforce foundation result retained; explicit identity unchanged.','../'+prior['RV-015']),
 'RV-017':('PASS','Prior Timekeeping result retained; no changed producer/identity semantics.','../'+prior['RV-017']),
 'RV-018':('PASS','Ordinary Payroll/Timesheet producer/payslip/handoff preparation and fail-closed prerequisites only. Official statutory success is OUT_OF_WAVE_C_CERTIFICATION under D03.','../wave_c_domain_resolution/FINAL_VERIFICATION.json'),
 'RV-028':('PASS','Prior DMS result retained; additional genuine synthetic-source scans preserve safety.','../'+prior['RV-028']),
 'RV-029':('PASS','Two canonical immutable Employment versions; own current/history runtime; explicit identity; management/detail, denial and invalid-POST controls; desktop/mobile verification.','EMPLOYMENT_HTTP.json'),
 'RV-030':('PASS','Authenticated create/list/detail and state-dependent transitions through lost; terminal mutation denied; unique IDs; business labels, named project context, responsive/focus evidence. Prior contract counterparty evidence retained.','BROWSER_RECONCILIATION.json'),
 'RV-031':('PASS','Prior accepted result retained; no related product change.','../'+prior['RV-031']),
 'RV-032':('PASS','Retained original payload/server hash/quarantine/replay/external non-membership evidence retained under D04.','../wave_c_domain_resolution/FINAL_VERIFICATION.json'),
}
matrix=[{'scenario_id':k,'result':v[0],'coverage':v[1],'evidence':v[2]} for k,v in details.items()]
assert sum(r['result']=='PASS' for r in matrix)==11
save('WAVE_C_FINAL_MATRIX.json',{'decision':decision,'recorded_at':stamp,'pass_count':11,'pending_real_time_count':1,'blocked_environment_count':0,'unresolved_attributable_regressions':0,'original_baseline_failures':3,'additional_unmasked_baseline_conditions':1,'all_12_scenarios_dispositioned':True,'full_required_execution_complete':False,'wave_closed':False,'scenario_results':matrix,'out_of_wave_c_certification':['Successful official statutory calculation/export/filing acceptance under D03','Production financial/legal/provider certification and activation','Human Sign-off, Production Certification/Cutover, CEP-078/079 and Wave D']})
current={'decision':decision,'recorded_at':stamp,'scope':'Final Wave C evidence closure only','report':'wave_c_final_closure/COMPLETION_REPORT.md','matrix':'wave_c_final_closure/WAVE_C_FINAL_MATRIX.json','regression_attribution':'wave_c_final_closure/REGRESSION_ATTRIBUTION.json','pass_count':11,'pending_real_time_count':1,'blocked_environment_count':0,'original_failure_classification':attr['counts'],'unresolved_attributable_regressions':0,'final_focused':'6 PASS / 4 baseline FAIL (3 original baseline cases + unmasked HEAD schema condition)','final_affected':'45 tests + 10 subtests PASS / 2 baseline fixture FAIL','RV-029':'PASS: populated management/own history, identity, source, denial and browser controls','RV-030':'PASS: authenticated desktop/mobile current-source Tender journey','RV-007':'RV-007_PENDING_REAL_CLOSE_CONDITION; unchanged close and earliest-opening schedule','official_statutory_success':'OUT_OF_WAVE_C_CERTIFICATION / NOT_VALIDATED (PD-WC-D03)','temporary_scanner_duty':read('INTEGRITY.json')['temporary_scanner_duty'],'full_required_execution_complete':False,'wave_closed':False,'prior_closed_findings_preserved':True,'CEP_registry':'UNCHANGED; no CEP lifecycle authorization inferred','production':'UNTOUCHED','human_signoff':'NOT_EXECUTED','cep078079_and_wave_d':'NOT_EXECUTED','git_writes':'NOT_EXECUTED'}
# One current-state addendum, preserving all earlier wave sections verbatim.
p=BASE/'UIUX_RUNTIME_VALIDATION_RESULTS.yaml';s=p.read_text(encoding='utf-8');before=yaml.safe_load(s);assert 'wave_c_final_closure' not in before
s=s.replace('latest_wave_c_execution: wave_c_role_reconciliation','latest_wave_c_execution: wave_c_final_closure',1);s=s.rstrip()+'\n\n'+dump({'wave_c_final_closure':current});p.write_text(s,encoding='utf-8')
# Touch only the affected finding records; preserve every previously closed record.
p=BASE/'UIUX_FINDINGS_REGISTER.yaml';s=p.read_text(encoding='utf-8');old=yaml.safe_load(s);old_findings={f['finding_id']:copy.deepcopy(f) for f in old['findings']}
for fid,status in [('UIUX-F-008','PARTIAL_PENDING_REAL_TIME_CONDITION'),('UIUX-F-009','PARTIAL_PENDING_REAL_TIME_CONDITION'),('UIUX-F-038','RUNTIME_VERIFIED_RESOLVED')]:
 start=s.index('- finding_id: '+fid+'\n');nxt=s.find('\n- finding_id:',start+1);end=nxt if nxt>=0 else s.index('\nruntime_wave_a:',start)
 fragment=s[start:end];previous=old_findings[fid]['status']
 # A previously closed finding is never reopened by a scenario evidence gap.
 if fid!='UIUX-F-038' and 'RESOLVED' in previous:continue
 if fid=='UIUX-F-038':fragment=re.sub(r'^  status: .+$','  status: RUNTIME_VERIFIED_RESOLVED',fragment,count=1,flags=re.M)
 addition={'wave_c_final_closure':{'status':status,'previous_primary_status':previous,'recorded_at':stamp,'evidence':'wave_c_final_closure/','scope':'Current Tender browser closure and retained contract evidence' if fid=='UIUX-F-038' else 'Opening-stage verification awaits real close/opening prerequisites; no lifecycle/date/source override'}}
 fragment=fragment.rstrip()+'\n'+textwrap.indent(dump(addition),'  ');s=s[:start]+fragment+s[end:]
new={'finding_id':'UIUX-F-133','module':'Workforce','surface_id':'RV-029-EMPLOYMENT-MANAGEMENT','route':'/workforce/employment/','category':'TERMINOLOGY','severity':'MEDIUM','status':'RUNTIME_VERIFIED_RESOLVED','runtime_status':'RUNTIME_VERIFIED_RESOLVED','problem':'New Wave C relationship choices and populated list render the default Person object (UUID) representation as primary business text.','remediation':'Use explicit tenant-owned person first/last names and work-relationship employee number for presentation. Identity, tenant scope, permissions and record services are unchanged.','evidence':{'source_paths':['apps/workforce/employment_forms.py','templates/workforce/employment_manage.html'],'tests':'wave_c_final_closure/affected_final.xml','http':'wave_c_final_closure/FINAL_HTTP_DELTA.json','browser':'wave_c_final_closure/BROWSER_RECONCILIATION.json'},'business_logic_impact':'NONE'}
assert 'UIUX-F-133' not in old_findings
idx=s.index('runtime_wave_a:');s=s[:idx]+dump([new])+'\n'+s[idx:]
s=s.replace('latest_wave_c_execution: wave_c_role_reconciliation','latest_wave_c_execution: wave_c_final_closure',1);s=s.rstrip()+'\n\n'+dump({'wave_c_final_closure':{'decision':decision,'recorded_at':stamp,'report':'wave_c_final_closure/COMPLETION_REPORT.md','resolved_current':['UIUX-F-038','UIUX-F-133'],'pending_current':['RV-007 / applicable UIUX-F-008 and UIUX-F-009 opening-stage evidence'],'regression_attribution':'wave_c_final_closure/REGRESSION_ATTRIBUTION.json','previous_closed_findings_preserved':True,'official_statutory_success':'OUT_OF_WAVE_C_CERTIFICATION under PD-WC-D03'}})
p.write_text(s,encoding='utf-8');now=yaml.safe_load(s);new_findings={f['finding_id']:f for f in now['findings']}
for fid,f in old_findings.items():
 if fid not in {'UIUX-F-008','UIUX-F-009','UIUX-F-038'}:assert f==new_findings[fid],fid
 assert 'RESOLVED' not in f['status'] or 'RESOLVED' in new_findings[fid]['status'],fid
# Detailed report is evidence, not a new CEP-state authority.
table='\n'.join('| '+r['test'].rsplit('.',1)[1]+' | '+r['classification']+' | '+('Retained' if r['classification']=='BASELINE_PREEXISTING' else ('AP permission regression fixed; HEAD schema debt retained' if 'InvoiceAPMigrationTests' in r['test'] else 'Fixed'))+' |' for r in attr['rows'])
mtable='\n'.join('| '+r['scenario_id']+' | '+r['result']+' | '+r['coverage']+' |' for r in matrix)
report=f'''# Wave C final closure pass — 2026-10-23

Decision: **{decision}**. Wave C cannot yet be declared complete.

Bounded authority: [attached Human request](AUTHORIZATION.txt), existing D01–D05 and existing PD-WC-07 scanner procedure. No Authorization architecture, catalogue/default-role reconciliation, business decisions, Waves A/B, Production or CEP execution was reopened. Branch `main`; entry/end HEAD `43ac319c6e73e48ca9626461b73987922c498ec3`, matching upstream. [Entry state](ENTRY.json) preserves accepted dirty-source hashes; [integrity](INTEGRITY.json) verifies the bounded delta.

## 1. REGRESSION_ATTRIBUTION

All ten original failure conditions are classified in [REGRESSION_ATTRIBUTION.json](REGRESSION_ATTRIBUTION.json): **7 ATTRIBUTABLE_REGRESSION, fixed; 3 BASELINE_PREEXISTING, retained; 0 INDETERMINATE; 0 unresolved attributable regressions**. Counts classify causes, rather than subtracting totals of failed test methods.

| Original case | Classification | Final disposition |
|---|---|---|
{table}

Immutable HEAD export: **5 PASS / 5 FAIL** ([frozen.xml](frozen.xml)); accepted entry: **0 PASS / 10 FAIL** ([entry_before.xml](entry_before.xml), replayed from saved entry modules). Some HEAD tests fail at an earlier legacy-authority setup barrier. The unchanged incomplete Match Review approver is separately proved denied at its exact policy guard under frozen HEAD in [FROZEN_APPROVER_PROBE.json](FROZEN_APPROVER_PROBE.json), with [AST/source attribution](SOURCE_ATTRIBUTION.json). Its temporary repair was restored byte-for-byte; unrelated baseline debt was not absorbed.

Final focused selection: **6 PASS / 4 baseline FAIL** ([fixed_final.xml](fixed_final.xml)). Final affected regression: **45 main tests + 10 subtests PASS / 2 baseline fixture FAIL** ([affected_final.xml](affected_final.xml)). Full repository regression was not run and is not claimed green. Earlier `fixed_10.xml`/`affected.xml` are superseded because they temporarily included the baseline-only approver repair.

The AP migration case's new permission failure is fixed. It now reaches the same **pre-existing `WriteOffProposal.corrects_id` schema mismatch** as immutable HEAD: the test pins `subledgers.0005` but calls current services requiring the field introduced by unchanged migration `0007`. This is one additional unmasked baseline condition, not an unresolved attributable regression. It is preserved without changing domain services, schema or the migration target. The other retained final failures are the Payroll registry omission and the two incomplete approver-fixture cases.

The bounded fixes reuse the sealed-custody test's already active role assignment, remove its organization scope before the unrelated-project denial, assign the AP fixture's intended custom role explicitly after migration, and assert only the approved `accountant` reversal default. Product authorization and financial services are unchanged. Scoped Ruff lint/format, Django check and migration drift pass. A pre-existing formatting issue in the restored, unchanged Match Review file was not repaired.

## 2. RV-029_FINAL

**PASS.** No qualifying populated Development history existed ([discovery](DATA_DISCOVERY.json)). Canonical DMS/category and Employment services produced one labelled synthetic document with two genuinely scanned versions and two append-only Employment records for the existing explicitly linked actor. No person, employee, identity link or work relationship was inferred or created. The old Employment version remains unchanged and explicitly superseded; current/historical states and effective dates are visible.

[Real HTTP](EMPLOYMENT_HTTP.json): **10/10 PASS** for populated management list, named source selection, synthetic employee detail, invalid POST/no write, populated own history, management denial, another-employee denial, cross-tenant denial, same-tenant unauthorized denial and forged own-history selector containment. Missing/mismatched `Employee.user` service and HTTP-layer probes both deny and roll back ([controls](EMPLOYMENT_CONTROLS.json)); source bytes/hash pins and immutable-history denial pass. Document download remains unavailable under its explicit category policy; safety was not bypassed.

Representative desktop **1440×1000** and mobile **390×844** management/detail/error/own-history views pass. The newly populated page exposed **UIUX-F-133**, an attributable presentation defect: raw `Person object (UUID)` labels. Its scoped form/template correction uses existing person names and employee number, with regression assertions and [current HTTP](FINAL_HTTP_DELTA.json). Identity resolution and permissions are unchanged.

[Fixture provenance and scanner results](EMPLOYMENT_FIXTURE.json), [browser reconciliation](BROWSER_RECONCILIATION.json), [mobile current/history](employment_own_history_lower_mobile.png).

## 3. RV-030_FINAL

**PASS.** Existing Development activation and Commercial specialist were reused. Authenticated browser verification covers list/create/detail, named project selection/context, invalid required-reference redisplay, draft → submitted → under review → lost, preserved revisions and state-dependent actions. Terminal mutation is denied with HTTP 400 and four revisions retained ([delta](FINAL_HTTP_DELTA.json)). Corrected form IDs are unique; selected captures have one main and no page overflow. Basic Tab/focus visibility is verified in both representative layouts. No raw policy/UUID metadata dominates the ordinary flow.

Tender has no separate counterparty field. Existing contract/commercial-review counterparty evidence is retained; no new counterparty or policy semantics were invented. Earlier service/HTTP evidence is reused. Browser timeouts/autoreload transients were recovered through documented browser APIs. Incorrect-tab/viewport attempts are explicitly superseded; final evidence uses verified paths and actual dimensions. No environment setting or product requirement was weakened. No browser blocker remains.

[Desktop terminal](tender_final_desktop.png), [mobile terminal](tender_final_mobile.png), [browser reconciliation](BROWSER_RECONCILIATION.json).

## 4. RV-007_FINAL

**RV-007_PENDING_REAL_CLOSE_CONDITION.** Canonical `WAVE-C-RFQ-A` remains issued. Real close: **2026-10-24 14:46:11 Tehran**. Earliest opening: **2026-10-25 14:46:11 Tehran**. Dates/state match discovery and data fingerprints ([real-time evidence](RFQ_REAL_TIME.json)).

No close, custody/opening transition, confidential comparison, date adjustment, scan/CLEAN fabrication or duty bypass was performed. Close manifest/custody, protected and independent opening, confidential comparison access, unauthorized/site/cross-tenant/manipulated-action denials, source/hash/scan integrity, stage/next-action UI and desktop/mobile post-close verification remain required after the real prerequisites pass. Reaching the scheduled time alone does not prove those prerequisites or authorize early opening.

## 5. REMAINING_EVIDENCE_GAPS

- **PENDING_REAL_TIME_CONDITION:** RV-007's legally/time-valid close and subsequent protected opening/comparison journey.
- **BLOCKED_ENVIRONMENT:** none remaining for the required executable browser/runtime work.
- **BASELINE_DEBT:** three original baseline cases and the separately unmasked HEAD schema mismatch, as detailed above. Other repository baseline debt is outside this selected validation.
- **ATTRIBUTABLE_REGRESSION:** none unresolved; UIUX-F-133 is also resolved.
- **OUT_OF_WAVE_C_CERTIFICATION:** successful official statutory calculation/export/filing acceptance under PD-WC-D03, Production policies/providers/legal certification, Human Sign-off and Production Certification/Cutover. These are not converted to PASS.

## 6. WAVE_C_FINAL_MATRIX

**11 PASS / 1 PENDING_REAL_TIME_CONDITION; Wave C remains open.** Retained PASS rows reuse accepted evidence whose implementation/configuration assumptions remain unchanged; this pass does not claim to re-execute all historical scenarios.

| Scenario | Current result | Coverage / boundary |
|---|---|---|
{mtable}

[Machine-readable matrix](WAVE_C_FINAL_MATRIX.json). RV-018 PASS covers ordinary Payroll and fail-closed prerequisites only; official statutory success remains unvalidated and outside this wave.

## 7. MIGRATION_AND_DATA_INTEGRITY

No new schema/data migration was created or applied by this pass. Accepted Development procurement migration `0016` remains applied; configured Development migration graph is current and drift check reports no changes. Production was untouched.

Synthetic additions are limited to the labelled Tender/browser and Employment/source fixtures, genuine assessments, required typed link and append-only audit. All pre-existing business rows remain; the document numbering counter is the only changed pre-existing row in the Employment-entry snapshot. Workforce identity, RFQ state/dates, future policy versions and unrelated financial/Payroll/Inventory rows are unchanged. Identity-negative probes roll back; no finalized history was overwritten. Statutory calculations/outputs remain zero. [Data/source integrity](INTEGRITY.json).

The approved, existing PD-WC-07 platform-duty service provisioned a separate scanner target using the existing single-Superuser grant contract. Genuine Defender scans passed. **The time-bounded scanner duty remains active until 2026-10-23 02:03:51 Tehran** unless independently revoked. Early revocation was denied because that service requires a second active Superuser, which is absent. No second Superuser, policy bypass, direct role edit or false revocation claim was introduced. Expiry is enforced by the unchanged authorization service; the exact assignment/expiry is recorded in integrity evidence. This is disclosed Development fixture authority, not Production authority or a change to the role matrix.

## 8. GIT_AND_PRODUCTION_BOUNDARY

`main` / HEAD and upstream unchanged. Branch/worktree creation: **NO**. Git add/commit/push/merge/rebase/reset/stash: **NOT_EXECUTED**. The frozen source is a read-only Git archive export without Git metadata, not a worktree. Unrelated accepted dirty files and previous closed findings are preserved. CEP Registry and Roadmap are unchanged.

Production deployment/migration/data change/cutover, Human Sign-off and Production Certification: **NOT_EXECUTED**. Wave D and CEP-078/079: **NOT_EXECUTED**. No automatic continuation or new monitor was created. Existing Development processes were preserved.

## 9. FINAL_DECISION

**{decision}**

STOP. No full Wave C completion or certification is claimed.
'''
(OUT/'COMPLETION_REPORT.md').write_text(report,encoding='utf-8')
p=BASE/'UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md';s=p.read_text(encoding='utf-8');s=s.rstrip()+f'''\n\n## Final closure reconciliation — 2026-10-23\n\nCurrent result: **{decision}**. [Final report](wave_c_final_closure/COMPLETION_REPORT.md) and [matrix](wave_c_final_closure/WAVE_C_FINAL_MATRIX.json) supersede only current Wave C dispositions; previous evidence remains historical.\n\nRV-029 populated explicit-identity Employment history and RV-030 authenticated desktop/mobile Tender verification **PASS**. The raw Person/UUID management labels are corrected as UIUX-F-133. Of ten recorded failures, **7 attributable failure conditions are fixed, 3 baseline cases retained, 0 indeterminate**. Final focused selection: **6 PASS / 4 baseline FAIL**, including one separately unmasked HEAD schema mismatch. Final affected selection: **45 tests + 10 subtests PASS / 2 baseline fixture FAIL**. Full regression is not claimed green.\n\n**11 scenarios PASS; RV-007 remains pending the real close/opening lifecycle.** Its unchanged Tehran close is October 24 at 14:46:11 and earliest opening October 25 at 14:46:11. No early close/opening or fabricated source/scan evidence occurred. Official statutory success remains **OUT_OF_WAVE_C_CERTIFICATION** under D03.\n\nAll existing business rows/identity links and unrelated dirty source are preserved; no new migration was introduced. The bounded scanner duty has a recorded October 23 02:03:51 Tehran expiry; independent early revocation was denied and not bypassed. Production, Human Sign-off, Wave D, CEP-078/079 and Git writes: **NOT_EXECUTED**.\n\n**{decision} — STOP.**\n''';p.write_text(s,encoding='utf-8')
save('FINAL_VERIFICATION.json',{'recorded_at':stamp,'decision':decision,'regression_classification':attr['counts'],'unresolved_attributable':0,'rv029':'PASS','rv030':'PASS','rv007':'PENDING_REAL_TIME_CONDITION','matrix':'11 PASS / 1 pending','focused_final':'6 PASS / 4 baseline FAIL','affected_final':'45 main + 10 subtests PASS / 2 baseline FAIL','browser_selected_captures':len(selected),'full_wave_closed':False,'official_statutory_success':'OUT_OF_WAVE_C_CERTIFICATION','production':'UNTOUCHED','git_writes':'NOT_EXECUTED','cep078079_wave_d':'NOT_EXECUTED'})
print('Final Wave C documents reconciled: 11 PASS, 1 real-time pending; 7 attributable failures fixed, 3 baseline cases retained; no unresolved attributable regression.')

