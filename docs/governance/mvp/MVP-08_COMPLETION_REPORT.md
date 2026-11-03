# MVP-08 — Demo States, Final MVP Verification & Human UAT Handoff

## Current handoff status — 2026-11-03 (Asia/Tehran)

**MVP-08 READY FOR HUMAN UAT.** This is the current package status; the original
BLOCKED attempt and intermediate blocked continuation are superseded historical
records preserved below and in the unchanged original report copy.

| Status | Current value |
| --- | --- |
| Technical verification | PASS — completed bounded MVP-08 continuation |
| Human UAT package | READY FOR HUMAN UAT |
| Human UAT execution | PENDING — 15/15 scenarios NOT_EXECUTED |
| MVP-08 Human acceptance / sign-off | NOT_RECORDED / NOT_ISSUED |
| Production readiness / certification / cutover | NOT_ASSESSED / NOT_ISSUED / NOT_AUTHORIZED |
| Five-artifact replacement exception | EXPLICITLY ACCEPTED BY HUMAN, 2026-11-03; evidence disposition only |

### Handoff evidence reconciliation

Rechecked actual files on disk on 2026-11-03: all **318/318** files in the completed
continuation evidence manifest match their recorded SHA-256 hashes. The original
196-entry manifest has exactly the five accepted replacements; **191/196** original
files still match. The original BLOCKED report is preserved verbatim. Native
policy/history, independent decisions, J3 lineage and quantities, financial
checkpoints, zero-create seed retries, browser/isolation checks, reopened XLSX,
final PO/GRN prints and passing focused-test logs support this scoped readiness.
The final PO print is `print-currency-corrected/PO.pdf`; the GRN print is
`print/GRN.pdf`, both under `output/mvp-08/continuation-20261103/`.

The three handoff documents are reconciled together; their previous hashes remain
in the historical source manifest. This documentation-only reconciliation records
new document hashes separately in
[handoff-reconciliation-20261103.json](../../../output/mvp-08/continuation-20261103/handoff-reconciliation-20261103.json).
It does not rerun workflows, replace technical evidence, accept the product or
certify subsequent unrelated working-tree changes. Concurrent UI work is left
untouched; a changed separate claim-detail verification script is outside the
MVP-08 authored-source/evidence qualification.

### Accepted five-artifact replacement exception

A reused output regression mistakenly overwrote these independent-output artifacts:

- `output/mvp-08/positive-output-regression/results.json`
- `output/mvp-08/print-procurement/grn-screen.png`
- `output/mvp-08/print-procurement/grn.pdf`
- `output/mvp-08/print-procurement/po.pdf`
- `output/mvp-08/print-procurement/results.json`

Their original bytes are unavailable. Their original hashes and manifest remain;
the replacement bytes are separately retained. The Human explicitly answered
**“Accept the documented five-artifact replacement”** on 2026-11-03. The
[exception record](../../../output/mvp-08/continuation-20261103/EVIDENCE_PRESERVATION_EXCEPTION.json)
is `ACCEPTED_BY_HUMAN`; this permits the documented evidence replacement and does
**not** record Human UAT acceptance, sign-off or Production readiness. J1/J2 evidence
remains unchanged, and coherent J3 outputs were qualified separately. No claim
that all 196 original byte sequences survived is made.

## Continuation closeout — 2026-11-03

**MVP-08 READY FOR HUMAN UAT.** All required technical continuation gates pass.
Human UAT remains **PENDING**; this is not MVP-08 Human completion, Human Sign-off,
Production Certification or cutover authorization. The prior blocked report is
also preserved verbatim in
[INITIAL_BLOCKED_REPORT.md](../../../output/mvp-08/continuation-20261103/INITIAL_BLOCKED_REPORT.md).

### Governed configuration and demo authority

The explicit Human continuation preserved `allow_self_approval=false` for exactly
`rfq-admissibility-self-approval`, `rfq-comparison-self-finalization`, and
`rfq-sourcing-award-self-finalization`. Native create/publish/select/apply services
created the next historical version, **v2**, effective **2026-11-03 → no end date**.
Publisher: existing Platform Admin `admin`; selecting/applying tenant actor:
`mvp08.admin`. Only `mvp08-synthetic-demo` received the new selections. No policy
specification, schema, permission catalog or unrelated tenant selection changed.
Old v1 ranges remain 2026-10-22→2026-10-25 for admissibility and
2026-10-24→2026-10-26 for comparison/award; exclusive end dates were not extended.
Native current-clock resolution returns all three v2 policies with self-approval
false. Final hashes re-prove all pre-existing policy versions, tenant selections,
admissibility decisions, comparisons and awards unchanged.

The Human explicitly authorized the revised **five-account** fixture extension,
superseding the earlier three-account proposal. New synthetic project-scoped
accounts: `mvp08.rfq-custodian` (existing custodian role),
`mvp08.rfq-opening-approver` (existing opening-approver role), and
`mvp08.rfq-preparer`, `mvp08.rfq-reviewer`, `mvp08.rfq-evaluator` (existing
`tenant_manager` + `rfq_opener`). All are non-staff, non-superuser and scoped only
to MVP08-P01. Original personas, role definitions and permission definitions
remain unchanged. PR approval uses the original `mvp08.reviewer`, which is the
actual governed PR workflow candidate. The new RFQ reviewer was not granted
extra PR workflow authority. The extension rejects every other database before
any seed write.

### Coherent main journey and boundaries

Installed Chrome executed the customer-visible chain from the retained approved
**PR-F** through **MVP08-RFQ02 v1**, invitation, captured/submitted synthetic quote,
real-clock deadline, custody closure, sealed source attachment, independent
protected opening, version-specific confidential grants, admissibility,
comparison, independent evaluation and final supplier selection. Three real
self-decision submissions returned native **400** denials with no resulting
record; the independent reviewer then completed each decision under policy v2.
The opening approver is also distinct from its requester.

The chain continues through **MVP08-PO01 v1**, two partial receipts
**MVP08-GRN01/02**, explicitly created/posted stock **MVP08-IN01/02**, and explicit
reversal **MVP08-REV02** of the second stock transaction. PR/RFQ/quote/comparison/
allocation/PO/version/GRN/stock links are checked against persisted native records.

| Quantity checkpoint | Native quantity, m³ |
| --- | ---: |
| Requested / sourced | 10 / 10 |
| Awarded / unawarded | 6 / 4 |
| Ordered / received | 6 / 6 |
| Partial receipts / original stock posts | 2 + 4 / 2 + 4 |
| Explicit reversal / final stock balance | 4 / 2 |

GRN posting created no stock automatically. Both receipts remain final; original
stock transactions and reversal history remain. PO is completed after full
receipt. **126 financial model/table snapshots remain unchanged at zero**, covering
AP/AR/subledgers, Treasury/payment, GL/accounting, Payroll, inventory valuation and
downstream cost envelopes. No producer/posting/settlement/valuation authority was
added or activated.

Supplier evidence is a valid, rendered one-page generated **synthetic** PDF. Its
processing assessment is an exact-database, digest-bound non-production fixture,
following the accepted MVP-04 convention. No real scanner execution, real supplier
commercial evidence or new Platform Operations assignment is claimed.

### Verification, corrections and retained Human state

| Required gate | Final result / evidence under continuation-20261103 |
| --- | --- |
| RFQ successors / old policy history / tenant selections | PASS — policy-successors.json; policy-final-preservation.json |
| Self-approval and independent decisions | PASS — independent-decisions.json and three RFQ02 denial batches |
| Journey 3 E2E / lineage / quantity | PASS — main-RFQ02 logs; J3-lineage-quantity-reversal.json |
| Explicit Inventory post/reversal / financial boundary | PASS — lineage and financial-baseline-v3.json / financial-checkpoints.json |
| Technical leakage / responsive sourcing | PASS — 18 retained views at 1440/1024/390px, five current sourcing action forms; 69 retained sourcing browser scenarios plus 3 current Billing checks |
| Tenant / permission isolation | PASS — tenant-permission-denials.json; restricted and foreign source/detail/output/print and protected supplier-document checks |
| Coherent Procurement / PO / GRN / Inventory XLSX | PASS — workbook-integrity.json; four types downloaded in Chrome and reopened with openpyxl; retained files contain the main chain's business references |
| PO / GRN Print | PASS — final PO: print-currency-corrected/PO.pdf; GRN: print/GRN.pdf. A4, one page each; real native print preview, Persian font, source facts, layout and rendered pages inspected |
| Final demo states / two zero-create retries | PASS — demo-final-idempotency.json; final-demo-closeout-2.log |
| Human UAT package | READY — executable guide; all 15 Human results NOT_EXECUTED |

Two bounded sourcing presentation corrections were required: contextual forms now
show their Persian business labels instead of internal keys such as `comparison:`,
and linked PO prints identify **the source quote's currency** from the pinned award
assertions. This does not infer a legacy order currency or change amounts,
financial rules or domain transitions. The earlier Daily Report UUID correction
remains qualified without rerunning J1/J2.

Current regression: connected procurement plus demo suite **7 PASS + 3 subtests**;
context-language/isolation focus **4 PASS + 3 subtests**; the extended linked-currency
print test **1 PASS**; final fixture-boundary suite **4 PASS + 3 subtests**. These are
separate runs with overlap, not an invented distinct-test sum. Ruff, JavaScript
syntax, Django checks and whitespace checks pass. Earlier S10/S11 failures were
attributed to their pre-existing authority-fixture setup, before changed product
code; the FULL_ERP policy UI tests pass under their actual exposure profile. See
regression-attribution.json and the individual logs; no failing fixture was
silently granted new authority or counted as passing.

Retained Human starts include approved Daily Report/Billing history; fresh draft
**MVP08-UAT-PR** for submit/cancel/independent PR approval and draft RFQ setup;
completed source/decision history for UAT-12/13; and still-posted **MVP08-IN01** for
the optional Human reversal in UAT-14. The guide explicitly separates a review of
completed history from a fresh Human mutation and gives exact actor/record steps.
Seed retries preserve every owned business row and all 13 persona credential rows;
no Human state is reset. The existing Contracts List acceptance remains preserved;
no other Human acceptance is inferred.

### Attempts, evidence incident and explicit disposition

Earlier attempts are retained, including: a new reviewer correctly denied PR
workflow authority; a harness selector targeting a closed disclosure; an initial
RFQ deadline configuration and native addendum; and an indivisible group award
correctly refused PO handoff because it lacked an explicit material-line mapping.
**MVP08-RFQ01** and its history remain untouched. The lawful line-based RFQ02 uses
the same retained PR; no line mapping or financial behavior was invented. Harness
corrections for response-body type, temporary download directory names and a
`valuation` substring erroneously matching operational `Evaluation` records are
recorded in failed logs. Corrected financial baselines project the original
snapshot onto the required financial sources; they do not rebase changed financial
rows. A concurrent qualification login invalidated the first seed snapshot; the
quiet final two retries pass with full row hashes, including credentials.

**Evidence preservation exception:** a reused regression with hardcoded paths
erroneously overwrote five prior independent-output files. Original bytes are no
longer available; the original 196-entry manifest and original hashes remain.
**191 originals remain byte-identical**, including J1/J2. The five replacements
are separately retained and enumerated in
[EVIDENCE_PRESERVATION_EXCEPTION.json](../../../output/mvp-08/continuation-20261103/EVIDENCE_PRESERVATION_EXCEPTION.json).
The Human explicitly answered **“Accept the documented five-artifact replacement”**
on 2026-11-03, permitting readiness after final checks. This is acceptance of that
evidence exception only. The regression runner now routes subsequent outputs to
the continuation directory. No claim of preserving all 196 original bytes is made.
The coherent main J3 outputs were separately qualified, and the final currency
presentation correction was verified with its own new print artifact.

### Final scoped status and operational stop

```text
RFQ POLICY SUCCESSORS: PASS
HISTORICAL POLICY PRESERVATION: PASS
TENANT POLICY SELECTION: PASS
SELF-APPROVAL DENIALS: PASS
JOURNEY 3 E2E: PASS
LINEAGE / QUANTITY / EXPLICIT POST AND REVERSAL: PASS
FINANCIAL BOUNDARY: PASS
TECHNICAL LEAKAGE: PASS
DEMO STATES: PASS
DEMO STATE IDEMPOTENCY: PASS
P0 OUTPUTS FROM COHERENT DEMO: PASS
TENANT / PERMISSION ISOLATION: PASS
MVP-08 TECHNICAL STATUS: PASS
ATTRIBUTABLE BLOCKING IMPLEMENTATION DEFECTS: 0
HISTORICAL FIVE-ARTIFACT EXCEPTION: EXPLICITLY ACCEPTED BY HUMAN
HUMAN UAT PACKAGE: READY
HUMAN UAT: PENDING
MVP-08 READY FOR HUMAN UAT
```

Concurrent Billing claim-detail/journey-navigation templates and generated Tailwind CSS
were observed from a separate task and left untouched. Their files and separate
claim-detail verification output are excluded from this task’s authored touch set.
A bounded read-only check of the current approved claim at 1440/1024/390px passes
with one Excel and one print control; gross/net remain 50,000,000/36,700,000 IRR.
Original J2 evidence and approved business history were preserved. See
concurrent-billing-read-only.log and source-manifest.json.

Branch/HEAD remain main / 28a9896086faa50064bf6f8d53a66a4628657b22.
No branch/worktree, staging, commit, push, merge, production action, next package,
Human Sign-off or Production Certification. Development source DB was not mutated;
the retained test copy is used. Verification servers are stopped. Evidence and
source hashes are indexed in the continuation manifests. **STOP — await Human UAT.**

## Historical BLOCKED attempts — superseded, preserved verbatim

The following original attempt and intermediate continuation describe their own
historical state. Their BLOCKED/NOT_READY statements are not the current handoff
status. The immutable original copy remains at
[INITIAL_BLOCKED_REPORT.md](../../../output/mvp-08/continuation-20261103/INITIAL_BLOCKED_REPORT.md).

# MVP-08 — Demo States, Final MVP Verification & Human UAT Handoff

2026-11-03, Asia/Tehran. **PARTIAL TECHNICAL EXECUTION — BLOCKED.**
**Not ready for final Human UAT; MVP-08 is not complete.**

The current RFQ policy configuration prevents qualification of the complete third
journey. No expiry date, approval authority, permission catalog, statutory rate or
Product Surface rule was changed to obtain a PASS. The available Human guide and
results sheet are explicitly a blocked handoff, not an executable final acceptance
package for all three journeys.

## Authority and checkpoint

The [bounded Human request](../../../output/mvp-08/MVP-08_REQUEST.md), SHA-256
`da4beff70873e4ff2340ce52b274883f81411fa0331ffa659ee5f43975a8ec52`, authorizes
MVP-08 only. Entry was clean local `main`; HEAD, cached upstream and read-only
remote `main` verification all identified
`28a9896086faa50064bf6f8d53a66a4628657b22` (`mvp-07`). See
[entry and intended touch set](../../../output/mvp-08/entry.json).

Loaded the repository rules, Execution Policy, CEP Playbook/Registry, relevant
Roadmap MVP plan, D1–D7 strategy, UI/color guidelines, MVP-01..07 completion and
current remediation evidence, CEP-079 and the current Journey inventory/matrix.
This is a separately authorized MVP package, not a CEP. Registry lifecycle remains
unchanged: 79 current-governed CEPs complete; seven deferred Post-V1. Historical
CEP-079 44/44 results support only their original scope and do not prove this build
or issue Human acceptance. No Roadmap, canonical prompt or dependency change.

## Release-gate matrix

`TECHNICAL PASS` below is limited to the stated current evidence. `BLOCKED` is not
a deferred PASS; an unqualified third journey prevents overall technical release.

| Gate | Current result | Evidence / practical limit |
| --- | --- | --- |
| Default MVP Product Surface | TECHNICAL PASS | Current Home, navigation, shortcuts and Module Selector; all five groups; hidden Accounting/Treasury/Payroll/Financial/full-HR routes denied. Current Product Surface tests also retain the internal FULL_ERP boundary. |
| Journey 1 — Project/Site Operations | TECHNICAL PASS | Real Chrome Project → Sites → Site → Workers → Timekeeping navigation; report child-entry update, submission and independent approval; same project/site on equipment deployment, Safety and Quality. |
| Journey 2 — Contract/Billing | TECHNICAL PASS | Real Chrome Estimate → Contract → contextual Claim creation → existing deductions/recalculation → submission → independent approval. Current approved baseline and verified-progress pages, real XLSX and print additionally verified. |
| Journey 3 — Procurement/Inventory | BLOCKED | Current PR creation and material addition exercised; complete sourcing/award/PO/GRN/Inventory path not executed. Three required published policy versions are expired. |
| Tenant / permission isolation | TECHNICAL PASS | Authorized ordinary personas, restricted site-scoped member and second-tenant member. Representative Project, Daily Report, Claim and PR source/print/XLSX denials; native browser denial checks plus current affected scope/authorization regression. |
| P0 XLSX | TECHNICAL PASS | Actual Billing, PR, Inventory, Expenses downloads; additional positive PO and posted Inventory downloads in an independent output-regression fixture. This fixture does not substitute for Journey 3. |
| P1 XLSX | TECHNICAL PASS | Actual Daily Report, approved Estimate, Timekeeping and Equipment downloads; native source/permission/version tests. |
| Five critical print targets | TECHNICAL PASS | Current Billing, Daily Report, Expenses in the retained demo; PO/GRN in the independent output fixture. All five actual A4 PDFs reopened/rendered and visually inspected. |
| RTL / responsive | TECHNICAL PASS | Representative shell and key pages at 1440/1024/390; Worker, Claim and PR forms and PR confirmation/cancel at all three widths. RTL, contained table scrolling, no page-level overflow. Unexecuted sourcing pages remain unqualified. |
| Offline frontend | TECHNICAL PASS | Current representative Chrome probes intercept and reject nonlocal HTTP requests and fail on attempted external dependencies; no unexpected external requests. Print probes independently reject nonlocal resources. Shared frontend assets unchanged. |
| Critical technical leakage, complete MVP sweep | BLOCKED | Exercised surfaces pass after one bounded Daily Report correction. Full sourcing journey has not been exercised, so complete three-journey absence is not certified. |
| Absence of blocking MVP conditions | BLOCKED | One unresolved governed-configuration prerequisite; zero unresolved attributable implementation defects in the exercised scope. |
| Complete coherent three-journey demo | BLOCKED | Project/workforce/operations and legitimate Contract/Billing state exist; complete Procurement/Inventory demo chain is not prepared. |
| Repeatability of the implemented seed | TECHNICAL PASS | Actual serial clean-namespace first run: 321 tenant-related rows; second run: zero created, all counts identical after native on-commit workflow bootstrap. |
| Human UAT / prior pending visual acceptance | HUMAN PENDING | 15 scenarios; every result NOT_EXECUTED. Guide and result sheet exist, but final package is NOT_READY pending Journey 3 and its starting states. |
| Production Certification / Cutover | NOT APPLICABLE | Outside this package; not authorized and not executed. |

## Exact unresolved finding and safe resumption

**B01 — `BLOCKER-MVP08-RFQ-POLICY-EXPIRED`**

Classification: **REQUIRES_PRODUCT_DECISION / governed configuration prerequisite**.
This is an inherited runtime configuration blocker, not an attributable new
MVP-08 code defect. It blocks acceptance nonetheless.

| Published policy | Version | Exclusive effective-to | Current independent-review setting |
| --- | --- | --- | --- |
| `rfq-admissibility-self-approval` | 1 | 2026-10-25 | `allow_self_approval=false` |
| `rfq-comparison-self-finalization` | 1 | 2026-10-26 | `allow_self_approval=false` |
| `rfq-sourcing-award-self-finalization` | 1 | 2026-10-26 | `allow_self_approval=false` |

Reproduction: against the isolated current Development snapshot on 2026-11-03,
the native `select_tenant_policy_version` service rejects the existing published
version as not effective. A later read-only preflight confirms all three expired.
[Policy evidence](../../../output/mvp-08/sourcing-policy-blocker.json),
[native selection failure](../../../output/mvp-08/journey3-attempt-1.log),
[final preflight](../../../output/mvp-08/sourcing-preflight.log).

No statement is made that approved successor evidence cannot exist elsewhere;
there is no usable current successor in the inspected configured runtime.
Safe next action: provide the governed current published successors, preserving
the approved independence requirements, and their lawful tenant configuration.
Then complete and reverify the actual supplier source/custody, protected opening,
admissibility, evaluation, award, PO version, partial GRN, explicit Inventory
posting/reversal, source lineage and no-financial-side-effect chain. Prepare its
retained Human starting state and rerun its outputs/isolation/leakage checks.
Do not extend the old dates, invent a new policy, skip sourcing, or activate a
financial authority to bypass the blocker.

**No current PASS is claimed for that whole chain.** The historical MVP-04 sourcing
fixtures use explicit synthetic policies, clock and processing evidence. Those
historical fixture controls were not promoted into new current authority.

## Demo mechanism and current state

The broad `seed_demo_data` is unsuitable here: it includes Treasury preparation,
wide historical ERP scenarios and fixed-password output. `seed_workforce` is
narrower but cannot provide the three connected journeys. Existing verification
fixtures remain useful for isolated regression, not as a replacement for a
coherent lawful customer demo. The bounded
[seed_mvp_demo command](../../../apps/accounts/management/commands/seed_mvp_demo.py)
reuses the existing domain services and native roles; no parallel model, permission
system or general demo framework was introduced. Its current delivered coverage
is explicitly partial.

Safety: local PostgreSQL, exact Development settings and DEBUG are required;
Production/base/custom settings, DEBUG false and remote hosts fail closed before
seed mutation. The command is transactional and serializes seed retries with a
transaction advisory lock. Namespace/persona collisions fail closed. No reset,
delete, truncate, customer flush or password output is offered. Existing owned
state is preserved, including approved history, later browser changes and local
credentials. Native test cleanup is confined to the separate task-owned test DB.

The primary tenant is `mvp08-synthetic-demo`; the second tenant is
`mvp08-synthetic-demo-isolated`. Eight named synthetic personas use existing native
roles, effective assignments and organization/project/site scopes. None is staff
or Superuser; no broad custom permission role or default-grant change was made.
Personas have unusable passwords initially; the technical operator sets private
local passwords using the existing interactive command before Human review.

The primary project `MVP08-P01`, site `MVP08-S01`, active phase, WBS/activity,
non-login Person/WorkRelationship/legacy Employee link, Attendance, distinct
Timesheet, deployment/usage, Safety and Quality all share the intended context.
The Equipment operations screen currently shows usage counts; its XLSX supplies
the detailed source rows. Its project text filter is not a UUID selector.

Estimate `MVP08-EST01` is independently approved; Contract `MVP08-CTR01` has real
items, active state, an independently approved term version copied from existing
approved Development terms, an approved baseline and verified measurements.
No rate or financial calculation was invented in the harness. The source-owned
approved claim snapshot is gross **50,000,000**, net **36,700,000 IRR** with its
actual configured deductions/adjustments. These are synthetic demonstration
results, not a statement of current legal rates. Measurement evidence uses the
existing free-form source reference contract; no automatic Daily Report-to-Billing
conversion or accounting recognition is claimed.

The retained browser copy contains the approved Daily Report, approved claim and
`PR-F` draft with one material line. An old reused PR submit probe correctly opened
the current confirmation dialog and stopped before POST because its harness did
not confirm. Current three-width confirmation/cancel checks prove the draft is
preserved; that earlier attempt is not counted as completed procurement E2E.

[Current demo catalog](../../../output/mvp-08/demo-catalog.json),
[qualified first run](../../../output/mvp-08/seed-first-final.json),
[qualified second run](../../../output/mvp-08/seed-second-final.json),
[repeatability comparison](../../../output/mvp-08/seed-repeatability.json).
An additional [whole-namespace rerun](../../../output/mvp-08/seed-whole-namespace.json)
compares all owned model rows in both tenants and all eight demo users, including
credential state only in an aggregate digest: unchanged, zero created.

The repeatability pair ran serially in
`test_bonira_mvp08_seed_final_20261103`, a fresh isolated snapshot of configured
Development with the owned MVP namespace absent. It was not an empty database:
existing reviewed configuration was deliberately retained. Only the already
existing pending schema migration was applied in isolated copies; no new migration
file, Payroll activation or Development/production migration occurred.
`test_bonira_mvp08_demo_20261103` retains the browser state; the regression harness
uses `test_bonira_mvp08_20261103`. Earlier count attempts remain unqualified logs.

## Bounded correction and verification attribution

**D01 — Daily Report technical disclosure: corrected.** Current Chrome reproduced
the visible `شناسه فنی گزارش` disclosure and its raw UUID. Root cause: an internal
identifier panel in the ordinary detail template. The minimum correction removes
that panel and changes the existing summary grid from three to two columns. The
record ID, routes, schema, services, permissions and history are unchanged.
[Before capture](../../../output/mvp-08/browser/mvp08.operator-J1-report-leakage-inspection-diagnostic.png),
[after capture](../../../output/mvp-08/browser/mvp08.operator-J1-report-observed.png),
[affected native journey rerun](../../../output/mvp-08/journey1-final-2.log).
The focused HTTP regression verifies business context remains and visible text
contains neither the raw report UUID nor technical-identifier copy. The three-width
current report and print checks pass.

**Seed reporting: corrected TEST_OR_FIXTURE_DEFECT.** The first count report ran
inside the transaction, before Organization's native on-commit starter workflows.
The serial attempt showed extra workflow/audit rows on the next observation. Count
reporting now occurs after commit and callback completion. The final fresh serial
pair proves the actual rerun result; no business lifecycle guard was changed.
The first environment also hosted browser work, but no concurrent UI effect is
inferred as the cause of the observed workflow-only count difference.

Other corrected verifier assumptions, not product defects: Equipment project
filters accept business text; the operations workspace exposes a usage count;
PO Excel is on the list, not its detail page; legitimate object denials may be
403 or 404; the existing Claim denial may be a plain Persian business message.
The reusable Chrome driver accepts that last case only when explicitly requested
for a 403/404 response with Persian text and no technical identifiers/debug text.
Positive-page RTL/HTML checks stay strict. Qualified local runtime uses DEBUG false
and the existing safe error templates. No error-page or permission redesign.

| Current check | Actual result and evidence |
| --- | --- |
| Focused plus affected source/security/output regression | **56 unique methods / 25 subtests PASS across the recorded commands.** Initial command: 55 PASS, one fixture failure (PO detail lacks list export). Focused rerun: 5/5 PASS including the corrected output method; its other four methods overlap the initial passes. Do not sum these into 60/61 distinct tests. [Initial](../../../output/mvp-08/verification-regression.log), [focused rerun](../../../output/mvp-08/focused-final.log). |
| Final environment guards after count-reporting correction | **3/3 PASS / 3 subtests**, [log](../../../output/mvp-08/seed-guards-final.log). DEBUG/pytest presence cannot authorize Production seeding. The actual serial seed pair separately verifies count/report behavior. |
| Journey 1 | Current native mutations/approval and final views PASS, [log](../../../output/mvp-08/journey1-final-2.log). |
| Journey 2 | Native create/deductions/independent approval PASS, [log](../../../output/mvp-08/journey2-attempt-2.log); current baseline/progress review in [context rerun](../../../output/mvp-08/journey2-context-final.log). [Persisted values](../../../output/mvp-08/billing-source.json). |
| Native Chrome surfaces | Current successful per-scenario batches and screenshots in [browser evidence](../../../output/mvp-08/browser/), indexed in [summary](../../../output/mvp-08/browser-summary.json). Failed attempts remain failed and are excluded from the success index. |
| Authorization | Representative source/print/XLSX checks and native restricted/foreign denial PASS, [data](../../../output/mvp-08/authorization.json), [final native run](../../../output/mvp-08/isolation-final.log). Current unit/integration regression adds scoped child/version/write boundaries. |
| Actual Excel files | **10/10 reopened with openpyxl**, RTL sheets, valid headers and no formula cells. [Integrity/source inventory](../../../output/mvp-08/workbook-integrity.json). One main-demo Inventory export is correctly empty; the additional current positive Inventory fixture prevents treating an empty workbook as the only Inventory proof. |
| Actual critical prints | **5/5 current PDFs**, one A4 page each in these representative fixtures, visually inspected after Poppler rendering. [Integrity](../../../output/mvp-08/print-integrity.json), [main demo](../../../output/mvp-08/print/), [independent PO/GRN](../../../output/mvp-08/print-procurement/). Native preview and actual Chrome print-media PDF verified; no physical-printer or Human visual acceptance claim. |
| Forms/dialogs/responsive | **12 current scenarios PASS**, [log](../../../output/mvp-08/responsive-forms.log), in addition to the 18 shell/key-surface width scenarios and hidden-route checks. |
| Existing data/configuration preservation | **25 selected boundaries PASS** across inherited demo tenants and global configuration; [hash evidence](../../../output/mvp-08/inherited-data-preservation.json). Standard migration catalog bootstrap changes only role `updated_at`; other role fields and all role-permission links compare identically. Policy versions and business/financial source rows compare unchanged. |
| Static/runtime checks | Ruff check/format, Node syntax, Django check, template compile, no migration drift and Git whitespace. [Django](../../../output/mvp-08/django-check.log), [drift](../../../output/mvp-08/migration-drift.log), [final checks](../../../output/mvp-08/final-checks.json). |
| Local UAT launcher | Loopback-only retained copy; Persian login and local static response smoke PASS; helper terminated after check. [Evidence](../../../output/mvp-08/uat-server-smoke.json). No password or Human result was generated. |
| Available demo financial boundary | No AP/AR, Treasury, Accounting or Payroll records in the retained primary tenant after available browser work; [counts](../../../output/mvp-08/financial-boundary.json). This does not qualify unexecuted Journey 3. |

No unrelated full Full-ERP suite was run. Earlier baseline fixture debt is not
silently closed or represented as newly passing. F1–F4 source assets, dependencies,
Module Selector/interaction implementations, Product Surface and financial/domain
services are unchanged. Earlier accepted foundation evidence supports those
unchanged parts; current representative offline/navigation/form probes are new.
The test harness redirects reused evidence roots to MVP-08. One preliminary
regression process was stopped before it could reuse historical output locations;
the qualified run preserves prior-package evidence.

## Human handoff and stop

- [Human UAT guide](MVP-08_HUMAN_UAT_GUIDE.md): 15 business scenarios, exact actions,
  personas, current/blocked starts and visual expectations; includes local operator
  setup, without credentials.
- [Human UAT results](MVP-08_HUMAN_UAT_RESULTS.md): all 15 **NOT_EXECUTED**; Product
  Owner decisions are **NOT_RECORDED**.
- Earlier MVP-02..07 pending visual acceptance is carried forward. The explicit
  2026-11-01 Contracts List acceptance in MVP-03 remains preserved; it does not
  accept other surfaces or auto-pass a new UAT scenario. Only the Human can
  explicitly accept relevant surfaces and supersede repeated pending reviews.

```text
MVP-08 TECHNICAL VERIFICATION: BLOCKED
DEMO STATES: FAIL
DEMO STATE IDEMPOTENCY: PASS
JOURNEY 1 — PROJECT/SITE OPERATIONS E2E: PASS
JOURNEY 2 — CONTRACT/BILLING E2E: PASS
JOURNEY 3 — PROCUREMENT/INVENTORY E2E: FAIL
MVP PRODUCT SURFACE: PASS
TENANT / PERMISSION ISOLATION: PASS
P0 XLSX REGRESSION: PASS
P1 XLSX REGRESSION: PASS
CRITICAL PRINT REGRESSION: PASS
RTL / RESPONSIVE: PASS
OFFLINE FRONTEND: PASS
CRITICAL TECHNICAL LEAKAGE: FAIL
ATTRIBUTABLE BLOCKING MVP DEFECTS: 0
HUMAN UAT PACKAGE: NOT_READY
HUMAN UAT: PENDING
```

`FAIL` on the complete-demo/Journey-3/leakage requirements means their required
evidence is incomplete because of B01; it is not a fabricated completed test failure
or a claim that a new leak was found in unexecuted sourcing pages. The count zero
means unresolved attributable implementation defects, **not zero release blockers**.
There is one unresolved governed-configuration release blocker.

Actual changes are confined to the bounded seed command, verification tools/tests,
the single Daily Report presentation correction, this handoff and current evidence.
No models, migrations, rates, global grants, workflow/domain behavior, financial
authority, dependency locks, historical reports/evidence or CEP lifecycle changed.
Source/evidence manifests are retained in `output/mvp-08/`.

End branch/HEAD remain `main` / `28a9896086faa50064bf6f8d53a66a4628657b22`.
Branch/worktree created: NO. Git add/commit/push/merge: NOT EXECUTED. Changes remain
uncommitted. Human Sign-off, Production Certification and Cutover: NOT EXECUTED.
No next development package started. **STOP — BLOCKED.**

## Continuation — 2026-11-03: RFQ successors applied; demo-duty authority pending

**Current result: PARTIAL / BLOCKED.** B01 expiry is resolved. This continuation
does not qualify Journey 3 or mark MVP-08 ready for Human UAT. No existing persona,
permission, role definition, scope assignment, platform duty or workflow was changed.

### Human decision and governed configuration

The [continuation request](../../../output/mvp-08/continuation-20261103/HUMAN_CONTINUATION_REQUEST.md)
explicitly preserves `allow_self_approval=false` for the three existing RFQ policy
contracts, authorizes current indefinite successors and prohibits modifying the
expired history or widening persona authority. The original blocked report is
also preserved as a [byte-identical snapshot](../../../output/mvp-08/continuation-20261103/INITIAL_BLOCKED_REPORT.md).

Only `test_bonira_mvp08_demo_20261103`, the retained local Development/UAT copy,
received the changes. The ordinary configured Development database and unrelated
tenant selections were not changed. Existing Platform Admin `admin` published
through `create_platform_policy_version` and `publish_platform_policy_version`.
Demo tenant administrator `mvp08.admin` selected/applied through
`select_tenant_policy_version` and `apply_tenant_policy_selection`. Neither actor
received a new authority grant. No direct policy/version/selection inserts.

| Policy code | Old version and effective range | Successor and effective range | Parameters | Current tenant selection |
| --- | --- | --- | --- | --- |
| rfq-admissibility-self-approval | 1; 2026-10-22 ≤ date < 2026-10-25 | 2; 2026-11-03 onward, no end | allow_self_approval=false | mvp08-synthetic-demo → version 2, active |
| rfq-comparison-self-finalization | 1; 2026-10-24 ≤ date < 2026-10-26 | 2; 2026-11-03 onward, no end | allow_self_approval=false | mvp08-synthetic-demo → version 2, active |
| rfq-sourcing-award-self-finalization | 1; 2026-10-24 ≤ date < 2026-10-26 | 2; 2026-11-03 onward, no end | allow_self_approval=false | mvp08-synthetic-demo → version 2, active |

Version numbers were computed as the maximum existing history number plus one,
not assumed. Each successor explicitly supersedes its predecessor, uses the
existing product-defined contract and records the Human decision as its reason.
No old version was retired, extended or repointed. Every pre-existing policy
version, tenant selection, admissibility decision, comparison and award row
compares unchanged before/after the governed operation.
[Full publication/selection/history evidence](../../../output/mvp-08/continuation-20261103/policy-successors.json).

The current application date is 2026-11-03. All three native tenant-policy
resolutions succeed, with false self-approval parameters and no expiry. The old
verification helper was boundedly updated to resolve the active tenant selection
instead of assuming only one published version exists. Its successful preflight
is explicitly labeled as policy verification, **not** Journey-3 E2E acceptance;
it writes new evidence without overwriting the original expiry finding.

```text
RFQ ADMISSIBILITY POLICY: CURRENT
RFQ COMPARISON POLICY: CURRENT
RFQ SOURCING AWARD POLICY: CURRENT
ALLOW_SELF_APPROVAL: FALSE
```

[Publication preflight](../../../output/mvp-08/continuation-20261103/policy-publication.log),
[updated native preflight](../../../output/mvp-08/continuation-20261103/native-preflight.log),
[resolved versions](../../../output/mvp-08/continuation-20261103/policy-preflight.json).

### Separate retained-demo authority finding

**B02 — `MVP08-RFQ-DEMO-DUTIES-UNASSIGNED`**. Classification:
`TEST_OR_FIXTURE_DEFECT`, requiring bounded authority clarification before the
affected path can proceed. This is not a missing code-owned role or a new policy
design. Existing specialist role definitions are sufficient; lawful demo
assignments are absent.

All seven retained primary-tenant memberships lack these effective duties:
sealed custody/close, protected opening, independent opening approval,
confidential-access administration and confidential reading. In particular,
the buyer/reviewer/evaluator have business-stage permissions but lack
`rfq_quotes.view_confidential`. A per-quote grant alone cannot replace that
permission. An existing Platform Admin has no implicit tenant sourcing authority.
Using a different tenant's membership would violate isolation.
[Actual membership/catalog preflight](../../../output/mvp-08/continuation-20261103/demo-authority-preflight.json).

Continuation §8 says not to widen permissions when a persona lacks authority.
Accordingly, no new demo account, assignment, grant, custom role or role-permission
change was made. The retained PR-F remains draft with its existing source line;
approved Daily Report, Billing claim and all operations data remain intact.
Journey-3 protected actions and self-decision cases are NOT_EXECUTED, not PASS.

A concrete alternative is [documented for clarification](../../../output/mvp-08/continuation-20261103/DEMO_AUTHORITY_FINDING.md):
five **new**, separate synthetic project-scoped demo accounts using existing roles:
custodian; opening approver; and preparer/reviewer/evaluator with the existing
tenant_manager + rfq_opener roles. This would leave every existing persona and
permission/role definition unchanged and use the established explicit synthetic
fixture-bootstrap convention. The initial three-specialist-account proposal was
insufficient because it did not supply confidential reading to downstream business
actors; it was corrected before any assignment was performed. The revised option
is awaiting the Human response and has not been executed.

### Focused regression, attribution and preservation

- Initial bounded policy/sourcing regression: **6 PASS / 16 FAIL**. Two policy UI
  methods expected internal administration pages under MVP and were denied by the
  unchanged Product Surface middleware before view execution. The same two methods
  pass under test-only internal FULL_ERP verification: **2/2 PASS**. No customer
  profile switch or exposure change. Eight distinct policy methods have passing
  evidence across those commands.
- The remaining **14 failures are baseline fixture debt**, not PASS: S10/S11
  `_make_actor` creates legacy-role-only members without effective role assignment
  and scope. Setup fails at `approve_quote_opening` → native permission check,
  before admissibility/comparison/award policy behavior is reached. The fixtures,
  opening service, authorization and Product Surface middleware match HEAD.
  They were not silently repaired or used to bypass the demo authority finding.
- [Initial regression](../../../output/mvp-08/continuation-20261103/policy-sourcing-regression.log),
  [internal-profile recheck](../../../output/mvp-08/continuation-20261103/internal-policy-ui-regression.log),
  [failure attribution and unchanged source hashes](../../../output/mvp-08/continuation-20261103/regression-attribution.json).
- All **196 pre-existing evidence files** retain their original hashes; **zero**
  qualified Journey-1/2, output, isolation, responsive or offline artifacts were
  regenerated. Their prior qualifications remain unchanged within their original
  limits. [Preservation](../../../output/mvp-08/continuation-20261103/prior-evidence-preservation.json).
- No product/model/schema/migration, policy specification, role catalog, permission
  default, financial rule or production change. Actual continuation source changes
  are the bounded policy configuration utility and native preflight helper;
  handoff documentation and new evidence are separate from the historical attempt.
- Ruff check/format and focused document/reference/source/evidence checks are
  retained in [continuation checks](../../../output/mvp-08/continuation-20261103/final-checks.json).

No coherent-main-demo Procurement/PO/GRN/Inventory outputs, source/quantity
qualification, posting/reversal or complete leakage sweep is claimed from this
continuation. No downstream scenario was fabricated to substitute for unavailable
lawful actor authority. Additional seed mutations/reruns are deferred because no
Journey-3 fixture extension is authorized/applied yet; the earlier qualified seed
idempotency evidence is preserved.

### Current gates and Human handoff

| Current continuation gate | Result |
| --- | --- |
| RFQ policy successors | PASS |
| Historical policy/selection/sourcing preservation | PASS |
| Current tenant selection and native preflight | PASS |
| New self-approval/self-finalization denials and independent decisions | NOT_EXECUTED — B02 |
| Journey-3 complete browser E2E, lineage and quantities | BLOCKED — B02 |
| Explicit Inventory posting/reversal and financial boundary for Journey 3 | NOT_EXECUTED — B02 |
| Journey-3 leakage and coherent-main-demo outputs/isolation | NOT_EXECUTED — B02 |
| Complete demo and executable Human starts for 11–14 | BLOCKED — B02 |
| Prior qualified Journey 1/2, foundation outputs, isolation, RTL/offline | Preserved; no new PASS fabricated |
| Overall MVP-08 technical verification | BLOCKED |
| Human UAT package | NOT_READY |
| Human UAT | PENDING — all 15 results remain NOT_EXECUTED |

The guide/results now identify the current authority gap rather than claiming the
expiry is still unresolved. Previous pending visual acceptance and the explicit
Contracts List acceptance remain as recorded. No Human acceptance, Production
Certification or Cutover was issued. No next package, branch/worktree, commit or
push. Current `main` HEAD remains `28a9896086faa50064bf6f8d53a66a4628657b22`.

**STOP affected Journey-3 path pending clarification — MVP-08 remains BLOCKED.**
