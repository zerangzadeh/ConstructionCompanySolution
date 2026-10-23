"""Summarize retained runtime observations without repeating HTTP mutations."""
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone, timedelta

OUT=Path(__file__).parent
UIUX=OUT.parents[1]
ROOT=UIUX.parents[2]
before=json.loads((OUT/'F111_RETEST_BEFORE.json').read_text(encoding='utf-8'))
after=json.loads((OUT/'F111_RETEST_AFTER.json').read_text(encoding='utf-8'))
http=json.loads((OUT/'F111_RETEST_HTTP.json').read_text(encoding='utf-8'))
dom=json.loads((OUT/'F111_RETEST_BROWSER_DOM.json').read_text(encoding='utf-8'))
version=json.loads((OUT/'F111_RETEST_BROWSER_VERSION.json').read_text(encoding='utf-8-sig'))
now=datetime.now(timezone(timedelta(hours=3,minutes=30))).isoformat()
assert after['authority_unchanged'] and not after['product_changes'] and not after['historical_changes']
assert set(after['model_deltas'])=={'sessions.Session'}
posts=[r for r in http if r['method']=='POST']
assert len(posts)==15 and len(http)==48
assert all(r['business_unchanged'] and r['errors'] and r['status']==200 for r in posts)
assert all(not any(r['unauthorized_matches'].values()) for r in http)
assert all(not r['unauthorized_matches'] for r in dom)
# Keep only scope-relevant metadata; employee, supplier, and equipment names are unnecessary.
allowed={'project','site','phase','purchase_request','contract','project_id','site_id'}
for r in http: r['fields']={k:v for k,v in r['fields'].items() if k in allowed}
for r in dom: r['fields']=[f for f in r['fields'] if f['name'] in allowed]
(OUT/'F111_RETEST_HTTP.json').write_text(json.dumps(http,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'F111_RETEST_BROWSER_DOM.json').write_text(json.dumps(dom,ensure_ascii=False,indent=2),encoding='utf-8')
titles={32:'Stale runtime exception',33:'Daily Report create',34:'Equipment Assignment create',35:'Purchase Order create/from approved request',36:'Workforce assignment selectors',37:'Workforce site endpoint',38:'Manipulated POST and invalid redisplay',39:'Direct URL/search/context regression controls',40:'Expense/Estimate known-good controls'}
notes={32:'Port 8001 served old in-memory code. Process 28704 started 2026-10-21 09:41:29 +03:30 with --noreload, before the remediation files changed. C/D project/site/phase UUIDs observed. No business POST to this process. Preserved exception; not a test of current remediation.',33:'A/B projects and sites; active A/B phase UUIDs only. C/D/X project and child UUIDs/codes absent from entire HTML.',34:'A/B project/site choices only; C/D/X identifying metadata absent from entire HTML.',35:'A/B projects and approved A/B request options only; C/D/X request UUIDs/numbers and option identities absent. Shared generic request titles are identical across fixtures; authorized options may legitimately contain the same text. No unauthorized title-bearing option exists.',36:'Initial sites empty/disabled; selecting A then B returns only the selected authorized parent sites. Settled captures govern; transient loading captures retained.',37:'A/B HTTP 200 with only their child site options. C/D/X HTTP 200 with blank placeholder only; complete safe response bodies retained.',38:'15 final HTTP POSTs: C/D/X against Daily, Equipment, PO and Workforce (12), plus A with C site/phase/request on original three surfaces (3). All HTTP 200 invalid, no rejected metadata redisplayed, no business/audit change. Otherwise-valid A payload checked without save for each form.',39:'A/B direct read 200, C/D/X 403; PRJ-01 search returns A/B, PRJ-02 search empty. Three context variants tested for A/B/C/D/X; forbidden parents return {options: []}. Direct-read navigation can echo the caller-supplied project UUID in next; fetched forbidden labels/children remain absent.',40:'Expense and Estimate initial projects exactly A/B. Expense A phases and Estimate B phase/contract cascade checked; C/D/X absent. Known-good product files unchanged.'}
for number,title in titles.items():
    eid=f'RV-EV-{number:03}'
    screenshots=sorted('screenshots/'+p.name for p in (UIUX/'runtime_evidence/screenshots').glob(eid+'__*.png'))
    record={'schema_version':'1.0','record':{'evidence_id':eid,'scenario_id':'UIUX-F-111_RUNTIME_RETEST','target':title,'executed_at':now,'runtime':{'environment_name':'Development','base_url':'http://127.0.0.1:8001' if number==32 else 'http://127.0.0.1:8002','git_sha':'43ac319c6e73e48ca9626461b73987922c498ec3','branch':'main','browser':'Codex in-app browser','browser_version':version['chromium_version'],'browser_version_source':'diagnostics/F111_RETEST_BROWSER_VERSION.json','source_dirty':True},'persona':{'persona_id':'P-17','test_user_alias':'uiux.persona.project-manager','organization_alias':'demo-construction-01','authorized_projects':['PRJ-01-01','PRJ-01-02'],'authority_reference':'diagnostics/F111_RETEST_BEFORE.json#authority'},'result':'STALE_RUNTIME_EXCLUDED_FROM_REMEDIATION_ASSESSMENT' if number==32 else 'PASS','actual_result':notes[number],'screenshots':screenshots,'diagnostics':['diagnostics/F111_RETEST_INITIAL_RUNTIME_DOM.json'] if number==32 else ['diagnostics/F111_RETEST_BROWSER_DOM.json','diagnostics/F111_RETEST_HTTP.json','diagnostics/F111_RETEST_BEFORE.json','diagnostics/F111_RETEST_AFTER.json'],'product_mutation':False,'business_mutation':False,'historical_evidence_overwritten':False}}
    target=UIUX/'runtime_evidence/records'/f'{eid}.yaml'
    assert not target.exists()
    # JSON is valid YAML 1.2; no new dependency is required for evidence authoring.
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')

cleanup=json.loads((UIUX/'f111_remediation_evidence/cleanup_boundary.json').read_text(encoding='utf-8'))
pdfs=[]
for name in cleanup['remaining_generated_files']:
    p=ROOT/name
    tracked=subprocess.run(['git','ls-files','--error-unmatch',name],cwd=ROOT,capture_output=True).returncode==0
    assert p.exists() and p.stat().st_size==11 and not tracked
    pdfs.append({'path':name,'exists':True,'bytes':11,'tracked':False,'added_to_git':False})
(OUT/'F111_RETEST_PDF_STATUS.json').write_text(json.dumps(pdfs,indent=2),encoding='utf-8')

rows=[]
for surface,nums in [('Daily Report','033'),('Equipment Assignment','034'),('Purchase Order / approved request','035'),('Workforce assignment','036'),('Workforce site endpoint','037')]:
    rows.append(f'| {surface} | Absent (C/D) | Absent | PASS | RV-EV-{nums} |')
postrows=[]
for r in posts:
    ids=', '.join(f'{k}=`{v}`' for k,v in r.get('submitted_protected_ids',{}).items())
    if not ids: ids='A project with C site/phase/request; exact fixture UUIDs in BEFORE/HTTP observations'
    postrows.append(f"| {r['label']} | {ids} | 200; invalid choice | NO | NO | PASS |")
touch='\n'.join('- `'+p+'`' for p in before['product_files'])
pdfrows='\n'.join('- `'+p['path']+'` — present, 11 bytes, untracked.' for p in pdfs)
report=f'''# UIUX-F-111 Runtime Security Re-test

## Baseline

Executed 2026-10-22, Asia/Tehran. Branch `main`; HEAD and upstream `origin/main` remain
`43ac319c6e73e48ca9626461b73987922c498ec3`, equal to the original frozen commit.
The remediation is uncommitted: **8 product files, 180 insertions / 50 deletions**.
Inspected changes are restricted to membership-aware scoped form choices and their
create/cascade views. No unrelated tracked product drift was found. Existing
untracked UIUX/Graphify evidence, focused test and generated PDFs were retained.

Actual implementation touch set (unchanged during this retest):

{touch}

Final Development runtime: `http://127.0.0.1:8002`, freshly started with the current
checkout, `config.settings.development`, configured loopback PostgreSQL
`construction_erp`; **zero pending migrations**. No migration was executed.
Browser: **Codex in-app browser, Chromium {version['chromium_version']}**;
host package `{version['host_package']}`. Version is grounded in the running
installed app's executable/Chromium DLL metadata, not a claimed User-Agent read.
See [browser metadata](runtime_evidence/diagnostics/F111_RETEST_BROWSER_VERSION.json).

**Preserved runtime exception (RV-EV-032):** port 8001's process 28704 started
2026-10-21 09:41:29 +03:30 with `--noreload`, before remediation file updates
(Daily Report form 2026-10-21 19:58:59 UTC). Its initial Daily Report DOM still
exposed C/D. This old in-memory process was left untouched. A fresh isolated
Development process on port 8002 loaded the remediation and governs the final
assessment. No remediation or settings change was needed.

The before/after collectors cover **519 concrete models**, including Django
infrastructure. **518 model digests match**; only `sessions.Session` changed
(43 to 46 rows). User digests exclude only `last_login`; passwords, account flags,
authority, tenant/business state and audit digests are covered. No business,
lifecycle, role, permission, scope, or audit record changed. The collector uses a
read-only database connection; HTTP verification uses real authenticated requests,
CSRF, middleware, views and services rather than Django's test client.

## Actor / Scope

P-17, `uiux.persona.project-manager`, active nonstaff/nonsuperuser, active
membership in `demo-construction-01`, effective `project_manager` role.
Only explicit project grants A (`PRJ-01-01`) and B (`PRJ-01-02`) are effective.
C/D and representative Tenant B project X (`PRJ-02-01`) are unauthorized.
All six required create capabilities were checked before execution. Authority
before/after matches; no persona or fixture change was made.

Fixture identifiers and effective grants:
[before](runtime_evidence/diagnostics/F111_RETEST_BEFORE.json).
Final integrity: [after](runtime_evidence/diagnostics/F111_RETEST_AFTER.json).

## Per-Surface Results

| Surface | Same-tenant unauthorized choices | Cross-tenant choices | Result | Evidence |
| --- | --- | --- | --- | --- |
{chr(10).join(rows)}

Actual rendered option labels **and UUID values** were retained, and complete
HTML was scanned in memory for forbidden project/child/request identifiers and
distinctive codes/names. No raw token-bearing HTML was saved.
Daily Report and Equipment expose A/B only; PO exposes A/B plus approved A/B
requests only. Workforce initial site options are empty; settled A/B cascades
contain only the selected authorized parent's site.

All seeded projects share generic site/phase names and approved requests share
the same generic title. Those authorized strings may appear; unauthorized
UUIDs, request numbers, project codes/names and title-bearing unauthorized options
are absent. Duplicate generic text is not evidence of an unauthorized object.
PO still uses project-level authority; no site-parent authority was inferred.

[Browser DOM observations](runtime_evidence/diagnostics/F111_RETEST_BROWSER_DOM.json)
and [HTTP observations](runtime_evidence/diagnostics/F111_RETEST_HTTP.json).

## Manipulated POST Results

| Surface | Unauthorized ID | Response | Object created | Metadata redisplayed | Result |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(postrows)}

**15/15 final negative POSTs PASS.** Each form's otherwise-valid A payload was
validated without saving before the negative controls. Per-request business and
audit counts/digests match; full-database comparison also excludes any lifecycle
transition or success audit/event. Invalid redisplay contains only authorized
options and generic invalid-choice errors, without rejected UUIDs or labels.
The final run includes four cross-tenant manipulated POSTs.

One earlier Daily/C request safely returned an invalid response, but the evidence
parser expected Django `ul.errorlist` rather than BONIRA `p.erp-field-error`.
That attempt is retained in `F111_RETEST_HTTP_PARSER_ATTEMPT.json`; only the
evidence parser was corrected. It is excluded from the 15 final controls
(**16 actual negative POST attempts total**, no business/audit changes).

## Workforce Endpoint

`GET /workforce/assignments/sites/?project=<UUID>`: A/B/C/D/X all returned 200.
A returns site `eef2f5d7-dc51-44d3-8414-8dc480f500c0`; B returns
`b83c65c4-5739-4076-b0aa-d892a14b8d60`. C/D/X bodies contain only:

```html
<option value="">بدون کارگاه</option>
```

Complete safe endpoint bodies are in the HTTP observations; RV-EV-037.
Initial, transient loading, and settled Workforce browser captures are retained;
settled captures govern the successful cascade result. Workforce's existing
organization-scope mutation-service restriction was not changed or bypassed.

## Direct URL / Search Controls

- A/B direct Project reads: 200; C/D/X: 403.
- Global `PRJ-01` search: A/B only; `PRJ-02`: no results.
- Shared context: Expense phase, Estimate phase and Estimate contract endpoints
  for A/B/C/D/X (15 requests). C/D/X return `{{"options": []}}`, HTTP 200.
- Direct denial navigation may echo the caller-supplied project UUID in `next`;
  no fetched forbidden labels, child UUIDs or other identifying metadata appears.

RV-EV-039; **48 final HTTP observations PASS**, including 15 negative POSTs.

## Known-Good Regression Controls

Expense and Estimate initial project options are exactly A/B. Browser selection
of Expense A and Estimate B populates only their scope-authorized phase choices;
Estimate's contract cascade was also exercised through its real endpoint.
C/D/X remain absent. RV-EV-040. These product files were not modified.
Existing implementation test results and attributed baseline debt remain in the
[remediation report](UIUX_F111_REMEDIATION_REPORT.md); no broad suite was rerun.

## Security Assessment

Same-tenant metadata leakage: **NO** on the freshly loaded remediated runtime.
The stale-process disclosure is explicitly preserved in RV-EV-032.

Cross-tenant metadata leakage: **NO**.

Unauthorized mutation: **NO**.

Object-scope enforcement: **PASS**.

No attributable authorization regression was found in the bounded closure paths.
This closes F-111's scoped remediation verification; it does not certify all
selectors, broader product security, financial posting, or Production readiness.
The separate `SAME_PATTERN_REVIEW_REQUIRED` inventory remains unchanged.

## Finding Status

UIUX-F-111: **RUNTIME_VERIFIED_RESOLVED**.

The canonical register adds the resolved runtime status and new evidence links.
Original finding/status/classification, RV-EV-026/027/028/030, root-cause and
implementation evidence remain intact. RV-EV-032 through RV-EV-040 are new
sequential records. No historical evidence was overwritten; hash verification
covers the earlier evidence files.

## Untracked Generated PDFs

{pdfrows}

ADDED_TO_GIT: NO

No deletion was attempted. The prior automatic policy-review cleanup restriction
was honored. [Path/status verification](runtime_evidence/diagnostics/F111_RETEST_PDF_STATUS.json).

## Safety Boundary

PRODUCT CODE CHANGED DURING RETEST: NO  
AUTHORIZATION SEMANTICS CHANGED DURING RETEST: NO  
ROLE/PERMISSION CHANGED: NO  
SCOPE BROADENED: NO  
PRODUCTION ACTION: NO  
CEP-078 EXECUTION: NO  
CEP-079 EXECUTION: NO  
GIT ADD/COMMIT/PUSH: NO

No Wave C, broad sweep, provisioning, reference-account cleanup, or successful
business creation. Authentication/session bookkeeping only. Credentials remained
in the existing DPAPI store and process memory; no password, cookie, session
value or CSRF token was persisted in evidence. The newly created isolated
port-8002 process is stopped after verification; pre-existing processes remain.

## Final Decision

F111_RUNTIME_VERIFIED_RESOLVED
'''
(UIUX/'UIUX_F111_RUNTIME_RETEST_REPORT.md').write_text(report,encoding='utf-8')
print('Created RV-EV-032 through RV-EV-040 and retest report; closure criteria PASS.')
