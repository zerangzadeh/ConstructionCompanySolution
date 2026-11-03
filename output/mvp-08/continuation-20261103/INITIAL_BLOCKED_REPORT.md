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
