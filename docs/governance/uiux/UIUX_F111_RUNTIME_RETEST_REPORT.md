# UIUX-F-111 Runtime Security Re-test

## Baseline

Executed 2026-10-22, Asia/Tehran. Branch `main`; HEAD and upstream `origin/main` remain
`43ac319c6e73e48ca9626461b73987922c498ec3`, equal to the original frozen commit.
The remediation is uncommitted: **8 product files, 180 insertions / 50 deletions**.
Inspected changes are restricted to membership-aware scoped form choices and their
create/cascade views. No unrelated tracked product drift was found. Existing
untracked UIUX/Graphify evidence, focused test and generated PDFs were retained.

Actual implementation touch set (unchanged during this retest):

- `apps\daily_reports\forms.py`
- `apps\daily_reports\views.py`
- `apps\equipment\forms.py`
- `apps\equipment\views.py`
- `apps\procurement\forms.py`
- `apps\procurement\views.py`
- `apps\workforce\forms.py`
- `apps\workforce\views.py`

Final Development runtime: `http://127.0.0.1:8002`, freshly started with the current
checkout, `config.settings.development`, configured loopback PostgreSQL
`construction_erp`; **zero pending migrations**. No migration was executed.
Browser: **Codex in-app browser, Chromium 155.0.8059.80**;
host package `OpenAI.Codex_26.1013.4894.0_x64`. Version is grounded in the running
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
| Daily Report | Absent (C/D) | Absent | PASS | RV-EV-033 |
| Equipment Assignment | Absent (C/D) | Absent | PASS | RV-EV-034 |
| Purchase Order / approved request | Absent (C/D) | Absent | PASS | RV-EV-035 |
| Workforce assignment | Absent (C/D) | Absent | PASS | RV-EV-036 |
| Workforce site endpoint | Absent (C/D) | Absent | PASS | RV-EV-037 |

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
| daily reject C | project=`f61f52ed-3c85-4570-af2b-5e89c025ab4e`, site=`1dfe7a20-143b-4db2-92c7-929745d8e521`, phase=`0cb736a2-b504-4b2c-8294-2f2a40622041` | 200; invalid choice | NO | NO | PASS |
| daily reject D | project=`623b4e02-b751-495f-b0e7-7e1601b9ccdf`, site=`4f195bba-4013-4cb3-acfa-53edfb3ef357`, phase=`65945c1f-f1ec-4772-bd72-a65d599a0150` | 200; invalid choice | NO | NO | PASS |
| daily reject X | project=`63063dae-394e-46e4-9abb-09284e821561`, site=`6ed52845-54e4-4d7f-b777-0db6dde3e762`, phase=`ac0d4b53-3e82-4563-8f50-dfbeb6169df6` | 200; invalid choice | NO | NO | PASS |
| daily mixed A with C child | A project with C site/phase/request; exact fixture UUIDs in BEFORE/HTTP observations | 200; invalid choice | NO | NO | PASS |
| equipment reject C | project=`f61f52ed-3c85-4570-af2b-5e89c025ab4e`, site=`1dfe7a20-143b-4db2-92c7-929745d8e521` | 200; invalid choice | NO | NO | PASS |
| equipment reject D | project=`623b4e02-b751-495f-b0e7-7e1601b9ccdf`, site=`4f195bba-4013-4cb3-acfa-53edfb3ef357` | 200; invalid choice | NO | NO | PASS |
| equipment reject X | project=`63063dae-394e-46e4-9abb-09284e821561`, site=`6ed52845-54e4-4d7f-b777-0db6dde3e762` | 200; invalid choice | NO | NO | PASS |
| equipment mixed A with C child | A project with C site/phase/request; exact fixture UUIDs in BEFORE/HTTP observations | 200; invalid choice | NO | NO | PASS |
| order reject C | project=`f61f52ed-3c85-4570-af2b-5e89c025ab4e`, purchase_request=`ef85f56c-99a5-4969-b223-459ad6b1fbb8` | 200; invalid choice | NO | NO | PASS |
| order reject D | project=`623b4e02-b751-495f-b0e7-7e1601b9ccdf`, purchase_request=`d8233c7f-72aa-4edc-bdd9-65f6344972b8` | 200; invalid choice | NO | NO | PASS |
| order reject X | project=`63063dae-394e-46e4-9abb-09284e821561`, purchase_request=`045e3d64-0ced-42e2-83b1-7f29a053bf1f` | 200; invalid choice | NO | NO | PASS |
| order mixed A with C child | A project with C site/phase/request; exact fixture UUIDs in BEFORE/HTTP observations | 200; invalid choice | NO | NO | PASS |
| workforce reject C | project=`f61f52ed-3c85-4570-af2b-5e89c025ab4e`, site=`1dfe7a20-143b-4db2-92c7-929745d8e521` | 200; invalid choice | NO | NO | PASS |
| workforce reject D | project=`623b4e02-b751-495f-b0e7-7e1601b9ccdf`, site=`4f195bba-4013-4cb3-acfa-53edfb3ef357` | 200; invalid choice | NO | NO | PASS |
| workforce reject X | project=`63063dae-394e-46e4-9abb-09284e821561`, site=`6ed52845-54e4-4d7f-b777-0db6dde3e762` | 200; invalid choice | NO | NO | PASS |

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
  for A/B/C/D/X (15 requests). C/D/X return `{"options": []}`, HTTP 200.
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

- `protected_documents/organizations/9a252256-9434-41f2-8823-7bc6ae7de500/documents/a84890a6-2145-4d6c-a212-82af56693d57/versions/129a915c-14ff-4011-be64-4af2c667a447.pdf` — present, 11 bytes, untracked.
- `protected_documents/organizations/a6ee1035-4439-4daa-afb6-9c9a818ff953/documents/06e274d7-6376-4bf0-9f8b-1a5449824a1d/versions/79de05bc-78e3-43e9-868c-4f77abd8ce6d.pdf` — present, 11 bytes, untracked.
- `protected_documents/organizations/ca79bb2b-56a3-47ab-9a38-8f90f02f5dc6/documents/037d7c20-e2f2-4a36-98ac-af3ac891db17/versions/cbc01dec-9edd-4f00-bd26-f31f55b4e841.pdf` — present, 11 bytes, untracked.

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
