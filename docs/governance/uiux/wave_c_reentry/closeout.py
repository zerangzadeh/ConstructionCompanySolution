"""Reconcile current Wave C evidence while preserving the accepted initial pass."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
sys.path.insert(0, str(Path.home()/"AppData/Local/Temp/bonira-wave-c-tools"))
import yaml

def read(name):
    return json.loads((OUT/name).read_text(encoding="utf-8"))

for name in ("UIUX_RUNTIME_VALIDATION_RESULTS.yaml","UIUX_FINDINGS_REGISTER.yaml","UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md"):
    snapshot = OUT/"entry_reports"/name
    snapshot.parent.mkdir(exist_ok=True)
    assert not snapshot.exists(), "Closeout is single-use; never overwrite accepted entry copies"
    snapshot.write_bytes((BASE/name).read_bytes())
authority = Path(r"C:\Users\azera\.codex\attachments\40d6961a-5120-4e53-8d46-cb25b02bfc60\Pasted text.txt")
(OUT/"AUTHORIZATION.txt").write_bytes(authority.read_bytes())
timestamp = datetime.now(ZoneInfo("Asia/Tehran")).isoformat()
old_results = yaml.safe_load((BASE/"UIUX_RUNTIME_VALIDATION_RESULTS.yaml").read_text(encoding="utf-8"))
old_findings = yaml.safe_load((BASE/"UIUX_FINDINGS_REGISTER.yaml").read_text(encoding="utf-8"))
blockers = read("RESIDUAL_BLOCKERS.json")
http = read("HTTP.json")
browser = read("BROWSER.json") + read("BROWSER_DELTA.json")
assert all(r["metrics"]["mains"]==1 and not r["mobile"]["overflow"] for r in browser)
assert all(r["passed"] for r in http)
pass_ids = {"RV-009","RV-015","RV-017","RV-028","RV-031"}
outcomes = {
 "RV-007":"Bounded Buyer receiving/preparation role provisioned at Project A. Genuine synthetic source fingerprint captured/submitted canonically; same-tenant C, foreign X, site-only and manipulated actions deny. Protected opening/confidential first-grant remains unavailable; F-008 stage/prerequisite/unique-empty-stage guidance is implemented without an invented later-stage priority.",
 "RV-009":"Prior PASS retained; only necessary inherited isolation/valuation smoke coverage ran. No Inventory fixture or scope changes.",
 "RV-011":"Exact existing monetary defaults recovered, but both published policy dates are 2026-12-22. Current canonical selection rejects them and the attempt rolls back. No populated journal/statement is fabricated.",
 "RV-013":"Registered source adapters verified. No eligible AP/AR source, approved tolerance policy, Treasury approval-policy version or cash/clearing mapping exists. Accounting effective-date gate also persists. Workbench and negative controls observed; no fake obligation, cash movement or settlement.",
 "RV-015":"Least-privilege HR specialist completes structure/foundation/create surfaces. Canonical department/position/team/employee fixtures plus real CSRF department creation and existing-account Employee reuse verified. Explicit Employee.user/Person/WorkRelationship links retained. Sensitive performance/rate controls deny. New employee-detail nested main fixed as F-131; desktop/mobile final capture has one main.",
 "RV-017":"Least-privilege Timekeeping specialist completes calendar/setup/daily attendance journeys on isolated synthetic calendar. Canonical attendance and real CSRF holiday creation verified. Closed setup disclosure separates daily work; populated mobile overflow fixed. ISO weekday entry remains an observed existing form convention, not a change to calendar rules.",
 "RV-018":"Separate Payroll-only specialist with no Workforce-sensitive grants completes configuration, period/run preparation and draft/statutory/handoff surfaces. Canonical synthetic non-statutory example stops at active-monetary-policy input-lock gate. No statutory rules or downstream financial effects manufactured. Bounded presentation, project-site narrowing and generated retry-key changes validated; populated downstream journeys remain blocked.",
 "RV-028":"Project-scoped Document Specialist creates one benign synthetic document, two immutable versions and canonical Project link. Both byte-identical hashes receive genuine Microsoft Defender no-threat verdicts through canonical processing assessment; both downloads pass. C/X/unauthorized controls deny. Temporary independently assigned Platform Operations duty revoked; no CLEAN evidence synthesized.",
 "RV-029":"Governed internal management form/list/append-only command UI implemented. Isolated authorized creation, duplicate/invalid redisplay, cross-tenant/other-person history, missing/mismatched Employee.user and sensitive-metadata controls pass. Live management/own custom roles remain unassignable through tenant delegation. Explicit linked identity fixture is present, with fail-closed live own-history denial; no identity inference.",
 "RV-030":"Project-scoped Commercial specialist provisioned; tender creation form and contract reads available. Canonical tender activation lacks an approved policy reference/activation contract. No threshold, scoring, approval, award rule or test-policy activation invented.",
 "RV-031":"Project-scoped Controls Analyst reads WBS/activity and populated advanced comparison/reconciliation from the existing accepted budget (one coded line); exceptions remain a scoped read model. Same-tenant project C and foreign X controls deny. No Project Cost source fact added or source-authority inference. Canonical authorized reconciliation-view audit is preserved.",
 "RV-032":"Exact tenant custom Portal Manager role created but canonical tenant assignment rejects unavailable permission transfer. External invitation lifecycle remains blocked. F-060 also lacks an external original-payload custody/hash input contract; existing portal metadata hash is not substituted for file-integrity evidence. No external identity with tenant membership created.",
}
scenarios=[]
for original in old_results["wave_c"]["scenario_results"]:
    sid=original["scenario_id"]
    scenarios.append({"scenario_id":sid,"result":"PASS" if sid in pass_ids else "BLOCKED","actual_result":outcomes[sid],"expected_result":original["expected_result"],"http_observations":sum(r["scenario"]==sid for r in http),"browser_observations":sum(r["scenario"]==sid for r in browser),"evidence":"wave_c_reentry/; RV-009 retains wave_c_evidence prior PASS","residual_blocker":next((b for b in blockers if b["scenario"]==sid),None)})
summary={"decision":"WAVE_C_BLOCKED","recorded_at":timestamp,"authority":"wave_c_reentry/AUTHORIZATION.txt; PD-WC-01..08","supersedes":"Initial wave_c scenario dispositions; initial pass is preserved as history and in entry_reports","all_12_scenarios_dispositioned":True,"pass_count":5,"blocked_count":7,"scenario_results":scenarios,"residual_blockers":"wave_c_reentry/RESIDUAL_BLOCKERS.json","report":"UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md","evidence_directory":"wave_c_reentry/","validation":{"focused":"26 tests + 6 subtests PASS","combined_regression":"75 tests + 44 subtests PASS; 1 unchanged-source baseline registry failure; BASELINE_DEBT.json","http":"100 matrix observations, 35 CSRF-bearing POSTs; two successful retained writes in HTTP_INITIAL_COMPLETE.json; known-account reuse in EMPLOYMENT_IDENTITY.json","browser":"19 observations, 38 desktop/mobile screenshots plus bounded interaction captures; all final observations one main and no page overflow","direct":"21 expected controls; business rows unchanged; only canonical authorized reconciliation-view audit appended"},"full_required_execution_complete":False,"wave_closed":False,"migration":"NO","production":"UNTOUCHED","cep078079":"NOT_EXECUTED","git_writes":"NOT_EXECUTED","prior_closed_findings_preserved":True}
p=BASE/"UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
p.write_text(p.read_text(encoding="utf-8")+"\n# Current targeted re-entry; previous wave_c section is historical.\n"+yaml.safe_dump({"latest_wave_c_execution":"wave_c_targeted_reentry","wave_c_targeted_reentry":summary},allow_unicode=True,sort_keys=False,width=110),encoding="utf-8")

resolved={"UIUX-F-005","UIUX-F-006","UIUX-F-040","UIUX-F-058"}
partial={"UIUX-F-008","UIUX-F-059","UIUX-F-067","UIUX-F-068","UIUX-F-069"}
targets=resolved|partial|{"UIUX-F-060"}
p=BASE/"UIUX_FINDINGS_REGISTER.yaml"
s=p.read_text(encoding="utf-8")
for fid in sorted(targets,reverse=True):
    match=re.search(r"(?m)^- finding_id: "+re.escape(fid)+r"\s*$",s)
    assert match
    next_match=re.search(r"(?m)^- finding_id:",s[match.end():])
    assert next_match
    end=match.end()+next_match.start()
    status="RUNTIME_VERIFIED_RESOLVED" if fid in resolved else "PARTIAL_RUNTIME_VERIFICATION" if fid in partial else "BLOCKED_CANONICAL_INPUT_CONTRACT"
    note={"status":status,"recorded_at":timestamp,"evidence":"wave_c_reentry/","report":"UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md","scope":"Bounded presentation only; blocked statutory/source/external journeys do not inherit PASS"}
    if fid in resolved:
        note["scope"]={"UIUX-F-005":"Payroll task vocabulary and subordinate limitations; no rule changes","UIUX-F-006":"One visible run has a primary continuation link; multiple runs receive no invented priority","UIUX-F-040":"Daily actions separated from closed setup disclosure; mobile populated overflow resolved","UIUX-F-058":"Project-dependent authorized Site choices, preserved refresh inputs, server validation"}[fid]
    block="  wave_c_reentry:\n"+"".join("    "+line+"\n" for line in yaml.safe_dump(note,allow_unicode=True,sort_keys=False,width=100).splitlines())
    s=s[:end]+block+s[end:]
new_finding={"finding_id":"UIUX-F-131","module":"Workforce","surface_id":"RV-015-EMPLOYEE-DETAIL","route":"/workforce/employees/<uuid:employee_id>/","category":"ACCESSIBILITY","severity":"MEDIUM","status":"RUNTIME_VERIFIED_RESOLVED","problem":"The linked employee detail content introduces a nested main landmark inside the application main.","evidence":{"source_paths":["templates/workforce/employee_detail.html"],"runtime":"wave_c_reentry/BROWSER_DELTA.json","tests":"wave_c_reentry/focused_final.xml"},"remediation":"Inner main replaced with a labelled section; no permission, identity or domain change.","runtime_status":"RUNTIME_VERIFIED_RESOLVED"}
insert=s.index("\nruntime_wave_a:")
s=s[:insert]+"\n"+yaml.safe_dump([new_finding],allow_unicode=True,sort_keys=False,width=110)+s[insert:]
s=s.replace("  finding_count: 130\n","  finding_count: 131\n",1).replace("    MEDIUM: 48\n","    MEDIUM: 49\n",1)
s+="\n"+yaml.safe_dump({"latest_wave_c_execution":"wave_c_targeted_reentry","wave_c_targeted_reentry":{"decision":"WAVE_C_BLOCKED","new_finding":"UIUX-F-131","resolved_bounded_findings":sorted(resolved),"partial_runtime_findings":sorted(partial),"report":"UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md","residual_blockers":"wave_c_reentry/RESIDUAL_BLOCKERS.json","prior_closed_findings_preserved":True}},allow_unicode=True,sort_keys=False)
p.write_text(s,encoding="utf-8")

report="""# Wave C targeted re-entry — 22 October 2026

**WAVE_C_BLOCKED.** Five canonical scenarios PASS; seven retain precisely bounded
authority, policy or source-contract blockers. All twelve have current dispositions
under `wave_c_targeted_reentry` in [the canonical results](UIUX_RUNTIME_VALIDATION_RESULTS.yaml).
This pass does not close Wave C or authorize another wave.

## Authority and preserved baseline

[The Human decision pack](wave_c_reentry/AUTHORIZATION.txt), PD-WC-01 through
PD-WC-08, authorizes this Development-only re-entry. Local `main`, HEAD and local
upstream remain `43ac319c6e73e48ca9626461b73987922c498ec3`; the accepted dirty
source is preserved. [Entry fingerprints](wave_c_reentry/FILES_BEFORE.json) and
[exact initial report copies](wave_c_reentry/entry_reports/) retain the effective
baseline. The CEP Registry, Roadmap, canonical CEP prompts, built-in role defaults
and permission definitions are unchanged. No remote freshness claim is made.

Seven separate specialist accounts, ten exact-tenant custom roles and seven
explicit scopes were provisioned through canonical services. Three roles remain
unassigned after canonical transfer denial; their account transactions rolled back.
The Buyer receiving/preparation subset omits unavailable protected opening powers.
HR/Controls dependent permissions were refined by revoke → update → independent
reassignment, with held-permission and dual-control checks preserved. Payroll uses
its own Payroll-only persona; the existing assurance Owner is only a canonical
delegator. [Role evidence](wave_c_reentry/ROLES.json),
[original denial](wave_c_reentry/DELEGATION_ATTEMPT.json),
[explicit linked identity](wave_c_reentry/EMPLOYMENT_IDENTITY.json).

## Current scenario results

| Scenario | Current result | Material coverage |
| --- | --- | --- |
"""
for row in scenarios:
    report+=f"| {row['scenario_id']} | {row['result']} | {row['actual_result']} |\n"
report+="""
## Bounded remediation

RFQ guidance shows its real stage, receipt prerequisites and a primary capture link
only for the determinate empty-receipt state. Later concurrent choices retain an
explicit ambiguity rather than an invented purchasing priority. Timekeeping puts
setup in a closed disclosure and daily operations first. Payroll uses task terms,
one-run continuation, dependent Project/Site choices, hidden generated retry keys,
and closed digest/calculation details while preserving monetary results and hashes.
F-059's remaining caller-owned source snapshots are not silently manufactured.

The new Employment management surface binds relationships, safe linked DMS
versions and explicit supersession to the active organization, checks the existing
permissions, and calls `record_employment_version`. Own history additionally
requires the current relationship's explicit `Employee.user` link; existing
Person/relationship identity remains intact. The rehire test fixture now establishes
that explicit link, and historical same-Person records remain preserved. No schema
or identity model was introduced. The HR linked-detail nested main defect is
recorded separately as F-131 and runtime-resolved without reopening F-129.

F-005/F-006/F-040/F-058 have bounded runtime resolution records. F-008/F-059/
F-067/F-068/F-069 retain partial runtime verification where populated downstream
journeys are gated; F-060 remains blocked by the external payload contract. All
prior F111/BATCH-01–09, SP031/F-128, F-129 and F-130 closure records are preserved.

## Verification and integrity

- Final focused tests: **26 PASS + 6 subtests PASS**.
- Combined affected suite: **75 PASS + 44 subtests PASS; one BASELINE TEST DEBT**.
  The unchanged failing test checks `payroll.StatutorySourcePackage` against the
  model registry. Its function matches HEAD and all three dependencies match entry
  hashes; changed behavior is not reached by the failing assertion. The stale
  Payroll title assertion was updated for the authorized terminology and passes.
  This is affected-boundary coverage, not full-repository regression PASS.
- **100** real authenticated HTTP matrix observations, including **35**
  CSRF-bearing POSTs, have no unexpected statuses. Successful department/holiday
  writes are retained in the initial complete matrix; known-account reuse is
  separately verified. **19** genuine Edge observations / **38** desktop/mobile
  screenshots plus interaction captures show one main and no page-level overflow.
  Focus samples and invalid-form behavior are bounded checks, not accessibility
  certification. Initial diagnostic expectations/stale-process output are history.
- **21** direct-service controls have expected outcomes. Comparison and
  reconciliation read one existing accepted-budget line. No business row changes
  occurred during these controls; the canonical authorized reconciliation-view
  audit is expected and retained.
- Both synthetic document versions were genuinely scanned by Microsoft Defender
  4.18.26090.9 with `found no threats` output and matching pre/post byte hashes.
  Canonical assessment unlocked downloads. The temporary Platform Operations duty
  was independently assigned and revoked. No mocked scanner output is used.
- Django checks, focused Ruff lint/format and migration-drift checks PASS.
  **Migration: NO.** No schema, production configuration or dependency changed.
- All 519 model fingerprints were compared. The sole changed pre-existing business
  row is the expected DMS document-number sequence increment. Additions are
  bounded synthetic fixtures, exact role/account/scope and audit history; no
  journal, obligation, Treasury movement, settlement or Project Cost fact was
  added. Login timestamps are excluded; session credentials are never serialized.
  Credentials remain in current-user Windows DPAPI outside the repository.

[Focused output](wave_c_reentry/focused_final.txt),
[combined regression](wave_c_reentry/final_tests.txt),
[baseline attribution](wave_c_reentry/BASELINE_DEBT.json),
[HTTP summary](wave_c_reentry/HTTP_SUMMARY.json),
[direct services](wave_c_reentry/DIRECT_SERVICE.json),
[scanner evidence](wave_c_reentry/DOCUMENT_SCAN.json),
[integrity](wave_c_reentry/INTEGRITY.json).

## Residual blockers and minimum input

"""
for b in blockers:
    report+=f"**{b['scenario']} — {b['missing']}**\n\n{b['why']}\n\nMinimum Human/external input: {b['minimum_input']}\n\n"
report+="""The [machine-readable blockers](wave_c_reentry/RESIDUAL_BLOCKERS.json) and
[source-gate inventory](wave_c_reentry/SOURCE_GATES.json) retain exact boundaries.
None is scanner or general specialist-fixture debt after this pass.

Production, deployment, cutover, Human Sign-off, Production Certification and
CEP-078/079: **NOT_EXECUTED**. Git add/commit/push/merge and branch/worktree creation:
**NOT_EXECUTED**. The session's Development server is stopped at closeout.

**WAVE_C_BLOCKED — STOP.**
"""
(BASE/"UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md").write_text(report,encoding="utf-8")

new=yaml.safe_load(p.read_text(encoding="utf-8"))
old_by_id={f["finding_id"]:f for f in old_findings["findings"]}
new_by_id={f["finding_id"]:f for f in new["findings"]}
unchanged=[fid for fid,old in old_by_id.items() if fid not in targets and new_by_id[fid]!=old]
assert not unchanged, unchanged
assert len(new_by_id)==131
assert len(scenarios)==12 and len({r["scenario_id"] for r in scenarios})==12
(OUT/"DOCUMENT_VALIDATION.json").write_text(json.dumps({"twelve_current_scenarios":True,"pass_count":5,"blocked_count":7,"unchanged_other_findings":len(old_by_id)-len(targets),"prior_closed_findings_preserved":True,"new_finding":"UIUX-F-131","authority_sha256":hashlib.sha256(authority.read_bytes()).hexdigest()},indent=2)+"\n",encoding="utf-8")
print("Reconciled 12 current scenarios; 5 PASS, 7 BLOCKED; prior accepted records preserved")
