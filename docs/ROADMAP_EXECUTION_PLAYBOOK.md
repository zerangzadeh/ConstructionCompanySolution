# Roadmap Execution Playbook

## 1. Purpose and authority

This document converts `ROADMAP.md` into resource-aware Codex execution sessions.
It does not add product scope, authorize implementation, replace architecture
documents, or change roadmap status. `ROADMAP.md` remains the delivery-order and
status authority; code, migrations, and tests remain the implementation authority.

The Product Owner owns product decisions, prioritization, acceptance, and manual
Django Admin/user UI testing. Codex owns the approved implementation slice, automated
tests, migrations, technical validation, and documentation closeout.

This is a rolling-wave plan:

1. P0-P10 have stable planning envelopes and session classes.
2. Only the next approved phase is expanded into final session cards.
3. Actual session usage recalibrates later phases.
4. Model names and reasoning levels are revalidated at every phase boundary.

The plan is based on the repository and model availability reviewed on
2026-09-24. Model availability and usage limits can change.

## 2. Scope boundary

### Core-completion track

The 344-session baseline covers the production-ready construction ERP core in
P0-P10, including security/operations, authoritative masters, Accounting,
Treasury/AP/AR, project controls, procurement, contracts/claims, payroll,
inventory/equipment/assets, field/HSE/QA, non-AI notifications/support,
knowledge, reporting, reconciliation, and release certification.

### Future-trigger track

The baseline excludes post-core AI assistance, controlled B2B network, enterprise
SSO, broad offline synchronization, GIS, GPS/telematics, and any microservice or
event-sourcing transition. They remain visible with explicit triggers in
`ROADMAP.md`; their planning envelopes in this document are not implementation
authorization.

## 3. Definition of one session

A session is one bounded Codex task targeting one primary acceptance outcome.

- **Target duration:** 3-5 active hours.
- **Hard planning limit:** 8 hours; split the task before exceeding it.
- **Scope:** normally one service boundary, migration slice, UI journey, test
  family, integration seam, or review gate.
- **Required finish:** relevant tests/checks, documentation closeout, changed-file
  report, assumptions, and a compact handoff for the next session.
- **Not allowed:** mixing unrelated roadmap items, speculative refactors, broad
  audits, unapproved packages, or continuing only to obtain cosmetic completeness.

A session may end early when its acceptance criteria pass. A failed session is
not silently extended: record the evidence, narrow the blocker, and create a
separate recovery session if necessary.

### 3.1 Minimum sufficient context policy

Every session uses the smallest context that can still establish all material
facts needed for a correct change. Context reduction is never allowed to remove a
business invariant, tenant/permission boundary, migration dependency, acceptance
criterion, or known risk.

OpenAI's long-horizon Codex guidance emphasizes durable repository memory,
checkpointed milestones, structured repository/diff/tool context, continuous
verification, and a clear definition of done rather than one oversized prompt:
<https://developers.openai.com/blog/run-long-horizon-tasks-with-codex>.

Context is loaded progressively in three layers:

| Layer | Loaded when | Required content |
| --- | --- | --- |
| C0 — session contract | Every session | Applicable `AGENTS.md`; session card; exact roadmap subsection; previous compact handoff; current `git status`/target diff; acceptance and stop conditions |
| C1 — direct implementation | Every implementation/review session | Relevant architecture sections; directly affected models, migrations, services, permissions, views/forms/templates and tests; current behavior evidence |
| C2 — risk expansion | Only when a trigger is observed | Adjacent domain contracts, older migrations/history, operations/UI guidance, external official sources, wider tests or performance/security evidence |

Repository instructions and any selected Skill are read according to their own
mandatory rules. Large project documents are not pasted wholesale into prompts;
the session card names the authoritative file and relevant section, and Codex reads
the smallest sufficient ranges unless the governing instruction requires the full
resource.

Before changing code, the session must be able to answer all of these from C0/C1:

1. What exact outcome is authorized, and what is explicitly out of scope?
2. What current code/migration/test evidence defines existing behavior?
3. Which tenant, permission, lifecycle, financial or historical invariants apply?
4. Which upstream/downstream contracts can be affected?
5. What files are expected to change, and why?
6. What objective checks prove completion?
7. Which Product Owner decision or external validation remains unresolved?

If every answer is evidence-backed, further context collection stops. Context
expands to C2 only for a concrete trigger:

- documentation and current code disagree;
- a relevant test fails outside the initially inspected boundary;
- the change crosses an atomic transaction, domain ownership or posting boundary;
- migration history, backfill, compatibility or rollback safety is unclear;
- authorization, tenant isolation, privacy, financial history, concurrency,
  idempotency, compliance or data retention is materially involved;
- the intended UI behavior depends on an uninspected shared component/standard;
- an external protocol, provider, law or version-sensitive fact must be verified.

Context must not expand merely because more files exist, a broad search is easy,
or theoretical completeness is possible. Conversely, token saving never justifies
acting on an unverified handoff when the authoritative source can materially alter
the decision.

### 3.2 Compact handoff between sessions

The closing handoff is durable project memory and normally stays within 250-600
words, excluding file paths and command names. It contains:

- session ID, achieved outcome and acceptance status;
- changed files and migration identifiers;
- decisions/invariants established, with authoritative paths;
- validations run and exact failures intentionally left open;
- worktree state or relevant diff boundary;
- next session ID, minimum context manifest and first recommended action;
- unresolved Product Owner decision or blocker.

Do not paste full source files, large logs, full test output, or previously settled
analysis into the handoff. Link to repository artifacts and retain only the facts
needed to resume safely.

## 4. Model and reasoning policy

Official OpenAI model-selection guidance describes Astra as the strongest option
for ambiguous/deep work, Sol as the everyday judgment-oriented option, and Luna
as the efficient option for scoped work. It recommends experimenting and keeping
the lightest setting that meets the quality bar:
<https://developers.openai.com/api/docs/guides/model-selection>.

This repository currently exposes `gpt-6-astra`, `gpt-5.6-terra`, and
`gpt-5.6-luna` among its usable choices. The mappings below are starting points,
not permanent model approvals.

| Code | Model | Reasoning | Use |
| --- | --- | --- | --- |
| `L-L` | `gpt-5.6-luna` | low | Narrow inspection, mechanical edits, documentation formatting, simple fixtures |
| `L-M` | `gpt-5.6-luna` | medium | Coordinated documentation, deterministic cleanup, bounded verification |
| `T-M` | `gpt-5.6-terra` | medium | Routine Django implementation, forms/Django Admin/templates, ordinary service/tests |
| `A-M` | `gpt-6-astra` | medium | Cross-file implementation requiring broad repository context |
| `A-H` | `gpt-6-astra` | high | Architecture, domain invariants, authorization, migrations, integrations, difficult debugging |
| `A-X` | `gpt-6-astra` | xhigh | Security/financial correctness review, concurrency, recovery, final certification |

Rules:

- Default routine coding to `T-M`; promote only for a concrete risk.
- Use `A-H` for tenant isolation, object authorization, financial ownership,
  payroll/compliance rules, schema transitions, idempotency, and cross-domain
  integration.
- Use `A-X` only for a named high-impact review or a problem that survived an
  adequate lower-effort attempt. Do not use it for ordinary CRUD or documentation.
- Use `L-L`/`L-M` only after scope and acceptance criteria are already clear.
- `max`/`ultra` are not baseline settings. They require an explicit, documented
  reason and a session-specific stop condition.
- If a recommended model is unavailable, use the closest available tier while
  preserving the required reasoning and verification level.

## 5. Core session budget

| Phase | Baseline sessions | Planning range | Main risk concentration |
| --- | ---: | ---: | --- |
| P0 | 22 | 18-28 | Architecture decisions, production security, recovery |
| P1 | 28 | 23-36 | Object scope, party/master governance, DMS |
| P2 | 38 | 31-48 | Ledger, posting, close, immutable history |
| P3 | 32 | 26-41 | Cash instruments, AP/AR, reconciliation |
| P4 | 38 | 31-48 | Budget/CBS, cost lineage, forecasts, controls |
| P5 | 28 | 23-36 | Sourcing, matching, external portal security |
| P6 | 42 | 34-54 | Billing correction, claims/EOT, guarantees, compliance |
| P7 | 36 | 29-46 | Time, payroll, tax and employee insurance |
| P8 | 30 | 24-39 | Valuation, equipment cost, fixed assets |
| P9 core | 26 | 21-34 | Field evidence, HSE/QA, notifications, knowledge |
| P10 | 24 | 19-31 | Metrics, reconciliation, closeout, certification |
| **Total** | **344** | **279-441** | Core only; future-trigger capabilities excluded |

At 3-5 active hours per session, the baseline represents approximately
1,032-1,720 hours before recovery/contingency. Reserve 10-15% for failed
assumptions, integration defects, and production-gate remediation. The resulting
planning envelope is consistent with roughly 1,200-1,900 active Codex hours.

## 6. P0 session map — 22 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P0-S01..S03 | 3 | `A-H` | Confirm current evidence, Product Owner decision packet, release-scope assumptions |
| P0-S04..S08 | 5 | `A-H` | Required ADRs and correction sequencing without application implementation |
| P0-S09..S11 | 3 | `A-X` | Threat model, secrets/dependency/storage/recovery design and adversarial review |
| P0-S12..S15 | 4 | `T-M` | CI, reproducible environment, operational checks, observability scaffolding |
| P0-S16..S18 | 3 | `A-H` | Entitlements, quota and tenant offboarding services/invariants |
| P0-S19..S20 | 2 | `T-M` | Selected UI consistency/accessibility remediation and automated checks |
| P0-S21 | 1 | `A-H` | P0 integrated acceptance and unresolved-risk review |
| P0-S22 | 1 | `L-M` | Documentation closeout and P1 handoff packet |

**Product Owner gates:** financial boundary, hosting/data residency, RPO/RTO,
initial release scope, plan/quota policy, and acceptance of the P0 correction set.

**Calibration after S12 (2026-09-25):** actual S04-S12 sessions prepared nine
proposed ADRs; the original session ranges above remain estimates, not delivery
status or implementation authority. The [S12 closeout](#37-p0-s12-future-network-privacy-adr-proposal-and-handoff)
hands off to Product Owner review of the proposals and unresolved decisions. Do
not enter the estimated S12 implementation group by session number; ADR acceptance
and explicit package authorization still gate it. Re-estimate remaining P0
implementation sessions when those gates resolve; no extra budget is approved.

**Calibration after S20 (2026-09-26):** P0-S13 through P0-S19 were used for the
bounded ADR/Q04 decision and accountable-review records described in sections
38-47; P0-S20 records the documentation-only UI/accessibility assessment in
section 48. The estimated P0-S16..S20 implementation ranges above are not delivery status
or implementation authority. Re-estimate and renumber remaining P0 implementation
sessions only after the applicable ADR and Product Owner gates resolve.

**Calibration after S21 (2026-09-26):** P0-S21 is the documentation-only
readiness and unresolved-risk review in section 49. It did not achieve integrated
acceptance: Q04 reviews, every P0.1 ADR disposition, P1.1 authorization,
D03-D05/Q03 parameters, P0.2/P0.3 prerequisites and P0.4 remediation remain OPEN.
P0-S22 may record documentation closeout and a conditional handoff, but remains no
authority to close P0 or start P1.

**Calibration after S22 (2026-09-26):** P0-S22 completed the documentation-only
closeout and conditional P1 handoff packet in section 50. This is an actual
session result, but it does not satisfy P0 exit criteria: P0 remains incomplete,
the release contract is not frozen and P1 entry remains blocked pending the
decision/evidence queue recorded in the packet.

## 7. P1 session map — 28 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P1-S01..S04 | 4 | `A-H` | Object-scope model, permission intersection and migration design |
| P1-S05..S09 | 5 | `A-H` | Project/site authorization services, queryset/view enforcement and tests |
| P1-S10..S13 | 4 | `T-M` | Scoped forms/Django Admin/UI states without option leakage |
| P1-S14..S18 | 5 | `A-H` | Configuration authority, BusinessParty governance and regulatory-version boundary |
| P1-S19..S22 | 4 | `A-H` | DMS numbering/classification/confidentiality/link/search/retention slices |
| P1-S23..S26 | 4 | `T-M` | Material catalogue, UOM conversion and approval workflow slices |
| P1-S27 | 1 | `A-X` | Cross-tenant, privilege, merge/history and document-security review |
| P1-S28 | 1 | `L-M` | Documentation closeout and P2 handoff packet |

**Product Owner gates:** role/scope semantics, party merge/restriction ownership,
material coding, document signature/retention policy, and regulatory source owners.

## 8. P2 session map — 38 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P2-S01..S04 | 4 | `A-X` | Accounting policies, COA/dimensions, period and posting ADR validation |
| P2-S05..S12 | 8 | `A-H` | Ledger schema, constraints, migrations and opening-data strategy |
| P2-S13..S22 | 10 | `A-H` | Posting registry, idempotency, balanced journals, reversal and source lineage |
| P2-S23..S27 | 5 | `T-M` | Accounting Django Admin/UI, period controls and source drill-through |
| P2-S28..S34 | 7 | `A-H` | Trial balance, statements, close/reopen and controlled adjustments |
| P2-S35..S36 | 2 | `A-X` | Concurrency, closed-period, duplicate-posting and financial-invariant review |
| P2-S37 | 1 | `A-H` | Integrated PostgreSQL regression and migration rehearsal |
| P2-S38 | 1 | `L-M` | Documentation closeout and P3 handoff packet |

**Product Owner gates:** native accounting scope, COA policy, fiscal calendar,
currency, opening balances, close authority, and accountant sign-off.

## 9. P3 session map — 32 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P3-S01..S04 | 4 | `A-H` | Treasury/AP/AR ownership, legacy Payment containment and transition design |
| P3-S05..S11 | 7 | `A-H` | Bank/cash/petty-cash accounts, receipts, payments, transfers and cheques |
| P3-S12..S17 | 6 | `A-H` | Payment requests/scheduling, employee/vendor advances and settlement |
| P3-S18..S22 | 5 | `A-H` | Statement import, matching, clearing and bank reconciliation |
| P3-S23..S27 | 5 | `A-H` | AP/AR obligations, allocations, aging and controlled write-off/reversal |
| P3-S28..S29 | 2 | `T-M` | Treasury/subledger UI and exception workbenches |
| P3-S30..S31 | 2 | `A-X` | Maker-checker, duplicate import, cash-to-GL and subledger reconciliation review |
| P3-S32 | 1 | `L-M` | Documentation closeout and P4 handoff packet |

**Product Owner gates:** bank integration/import sources, cheque policy, approval
limits, cash-account structure, payment scheduling, and write-off authority.

## 10. P4 session map — 38 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P4-S01..S06 | 6 | `T-M` | Estimate/BOQ comparison, resources, coefficients and safe import slices |
| P4-S07..S13 | 7 | `A-H` | Budget baseline/version, CBS/cost center and WBS mapping |
| P4-S14..S20 | 7 | `A-H` | Commitment/accrual/actual/forecast cost facts and source lineage |
| P4-S21..S25 | 5 | `A-H` | Schedule, milestones, constraints, risk, delay, change and rebaseline controls |
| P4-S26..S30 | 5 | `A-H` | Expense lifecycle, allocation, recurrence proposals and budget controls |
| P4-S31..S34 | 4 | `T-M` | Project-control UI, comparisons, exception views and exports |
| P4-S35..S37 | 3 | `A-X` | Cost conservation, concurrency, performance and multi-source reconciliation |
| P4-S38 | 1 | `L-M` | Documentation closeout and P5 handoff packet |

**Product Owner gates:** price-book licensing, budget authority, CBS policy,
forecast cadence, schedule depth/integration, and budget warning versus hard stop.

## 11. P5 session map — 28 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P5-S01..S04 | 4 | `A-H` | Source-to-pay lifecycle, SoD, confidentiality and integration design |
| P5-S05..S11 | 7 | `T-M` | RFQ, invitation, quote revision, comparison, approval and award |
| P5-S12..S17 | 6 | `A-H` | PO change, service acceptance, supplier invoice and match/tolerance |
| P5-S18..S22 | 5 | `A-H` | External portal identity, invitation, submission and least-privilege boundary |
| P5-S23..S25 | 3 | `T-M` | Internal/external UI journeys, correction loops and evidence handling |
| P5-S26..S27 | 2 | `A-X` | Bid privacy, impersonation, duplicate submission and match reconciliation review |
| P5-S28 | 1 | `L-M` | Documentation closeout and P6 handoff packet |

**Product Owner gates:** sourcing SoD, tolerance policy, portal onboarding,
external identity, withdrawal rules, and supplier support ownership.

## 12. P6 session map — 42 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P6-S01..S06 | 6 | `A-X` | BillingPolicy correction, term/regulatory ownership and safe migration design |
| P6-S07..S13 | 7 | `A-H` | Receivable claim recalculation, snapshots, corrections and AR/posting handoff |
| P6-S14..S20 | 7 | `A-H` | Subcontracts, measurement, payable certificates and recoveries |
| P6-S21..S25 | 5 | `A-H` | Guarantees, insurance/clearance, expiry, exposure and release |
| P6-S26..S32 | 7 | `A-X` | Taxpayer invoice and Iranian contractor-compliance integration/failure handling |
| P6-S33..S38 | 6 | `A-H` | Site Instruction, Variation/Change Order, contractual Claim and EOT |
| P6-S39..S40 | 2 | `T-M` | Commercial timelines, evidence, impact comparison and exception UI |
| P6-S41 | 1 | `A-X` | Financial/legal lineage, idempotency, tenant and workflow final review |
| P6-S42 | 1 | `L-M` | Documentation closeout and P7 handoff packet |

**Product Owner gates:** contract-term policy, payable/receivable separation,
claim/EOT governance, statutory launch scope, provider credentials, guarantee and
insurance-clearance rules, all with legal/accounting review.

## 13. P7 session map — 36 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P7-S01..S05 | 5 | `T-M` | Skills, qualifications, training, labor-rate versions and privacy UI |
| P7-S06..S12 | 7 | `A-H` | Calendars/shifts, attendance, leave, mission, overtime and timesheets |
| P7-S13..S22 | 10 | `A-X` | Payroll rule/run/result engine, locks, adjustments and reversal |
| P7-S23..S28 | 6 | `A-X` | Payroll tax and employee-insurance list generation/submission evidence |
| P7-S29..S32 | 4 | `A-H` | Payroll liability, Treasury payment, Accounting posting and Project Cost distribution |
| P7-S33..S35 | 3 | `A-X` | Privacy, retroactivity, rule-version, reconciliation and golden-case review |
| P7-S36 | 1 | `L-M` | Documentation closeout and P8 handoff packet |

**Product Owner gates:** employment/pay models, attendance providers, overtime and
leave policy, payroll privacy/SoD, statutory schemas and professional sign-off.

## 14. P8 session map — 30 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P8-S01..S04 | 4 | `A-H` | Inventory/equipment/asset ownership and valuation-policy design |
| P8-S05..S11 | 7 | `T-M` | Reservations, bins, lots/serials, count and transfer custody |
| P8-S12..S17 | 6 | `A-H` | Valuation layers, issue/return costing and GL/Project Cost handoff |
| P8-S18..S23 | 6 | `T-M` | Equipment meters, operator qualification, expiry, fuel, downtime and maintenance |
| P8-S24..S27 | 4 | `A-H` | Equipment cost allocation and fixed-asset lifecycle/depreciation |
| P8-S28..S29 | 2 | `A-X` | Quantity/value conservation, depreciation and reconciliation review |
| P8-S30 | 1 | `L-M` | Documentation closeout and P9 handoff packet |

**Product Owner gates:** valuation method, traceability depth, capitalization and
depreciation policy, maintenance ownership, expiry policy, and spare-parts usage.

## 15. P9 core session map — 26 sessions

This core map deliberately excludes every AI assistant. P9.4's notification and
support-platform scope remains core; its AI portion belongs to the future-trigger
track.

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P9-S01..S05 | 5 | `T-M` | Mobile/context field capture, media/evidence and reviewed downstream proposals |
| P9-S06..S11 | 6 | `A-H` | HSE/QA inspections, permits, tests, CAPA and verification lifecycles |
| P9-S12..S15 | 4 | `T-M` | BusinessParty qualification/performance evidence and explainable evaluation |
| P9-S16..S20 | 5 | `A-H` | In-app/email/SMS policy, reminders, calendar, supervisory workbench and support cases |
| P9-S21..S24 | 4 | `A-H` | Reviewed knowledge publication, provenance, recurrence and reuse evidence |
| P9-S25 | 1 | `A-X` | Field privacy, evidence integrity, notification/workflow and knowledge final review |
| P9-S26 | 1 | `L-M` | Documentation closeout and P10 handoff packet |

**Product Owner gates:** offline boundary, media policy, HSE/QA ownership,
evaluation privacy, notification/SMS channels, support SLA and knowledge roles.

## 16. P10 session map — 24 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P10-S01..S06 | 6 | `A-H` | Metric catalogue, governed read models, dashboards and source drill-through |
| P10-S07..S13 | 7 | `A-X` | Financial/operational reconciliation pairs, exception evidence and rebuild checks |
| P10-S14..S17 | 4 | `A-H` | Project-closeout coordination across contracts, claims, documents, assets and knowledge |
| P10-S18..S21 | 4 | `A-X` | Release certification: migration, restore, performance, tenant and security gates |
| P10-S22 | 1 | `A-X` | Independent final risk and production-readiness review |
| P10-S23 | 1 | `A-H` | Product Owner UAT finding triage and release/rollback recommendation |
| P10-S24 | 1 | `L-M` | Final documentation closeout and approval packet preparation |

**Product Owner gates:** metric definitions/owners, selected first-release scope,
closeout acceptance ownership, tolerated open risks, release and rollback decision.

## 17. Future-trigger planning envelopes

These items start only after the core is certified and their roadmap trigger is
satisfied. Session counts are early envelopes and must be re-estimated at trigger
time.

| Future capability | Initial sessions | Default model/reasoning | Required trigger |
| --- | ---: | --- | --- |
| AI Support Assistant | 10-18 | `A-H`; final security review `A-X` | Stable support/knowledge base, AI privacy/residency policy, evaluated retrieval quality |
| Governed ERP Assistant | 14-24 | `A-H`/`A-X` | Stable P10 semantic APIs, authorized tool contracts, human-confirmation policy |
| Predictive AI/optimization | 12-24 | `A-X` | Governed historical data, measurable decision, baseline evaluation and override |
| Controlled B2B network | 30-50 | `A-H`/`A-X` | Opt-in density, identity/consent/privacy ADR and operating model |
| Enterprise SSO | 8-14 | `A-H`; threat review `A-X` | Enterprise demand, approved IdP/account-linking/MFA/recovery policy |
| Broad offline synchronization | 18-30 | `A-H`/`A-X` | Measured connectivity need, bounded dataset, device-loss and conflict policy |
| GIS platform | 12-20 | `T-M`/`A-H` | Proven spatial workflow and privacy/accuracy policy |
| Equipment GPS/telematics | 10-18 | `A-H` | Proven fleet use case, provider/device contract, retention and failure model |
| Microservices/event sourcing assessment | 4-8 assessment only | `A-X` | Demonstrated scaling, deployment or team boundary; implementation estimate follows ADR |

## 18. Session card template

Before starting any session, create a task card with this minimum content:

```text
Session ID:
Roadmap item:
Goal:
In scope:
Out of scope:
Authoritative references:
Previous session handoff:
Minimum context manifest (C0/C1):
Context intentionally excluded:
Context-expansion triggers (C2):
Files expected to change:
Model / reasoning:
Why this tier is justified:
Acceptance criteria:
Targeted validation:
Product Owner decision/input, if any:
Stop conditions:
Documentation closeout:
```

The session prompt must authorize only that card's scope. A planned future item is
not authorization to implement it.

## 19. Standard session workflow

1. Load C0, then the direct C1 manifest; confirm the seven context-sufficiency
   questions before changing files.
2. Confirm the session card, current code and relevant authoritative references.
3. State the short plan and expected files.
4. Implement the smallest complete vertical slice.
5. Add or update targeted tests, including tenant/permission/concurrency coverage
   where applicable.
6. Run the smallest proportionate checks; expand context/validation to C2 only
   for a documented trigger.
7. Prepare the Product Owner UI/UAT handoff when the slice is user-visible.
8. Perform documentation closeout as the final work step. Always reconcile
   `ROADMAP.md` with verified session progress, explicit approval evidence,
   dependencies and open decisions; update only affected entries and link to
   session evidence instead of copying the full record. If no entry needs changing,
   explicitly report that the roadmap was checked and remains current. Completing
   a session does not by itself complete a roadmap package or approve a decision.
9. Produce the compact handoff and report actual duration, deviations, remaining
   risks and the recommended next
   session ID.

## 20. Product Owner UI/UAT handoff

For every user-visible session, provide:

- tested URL/menu path and required role;
- tenant/project/site prerequisites;
- setup data or fixture assumptions;
- happy path and at least one denied/error path;
- expected Persian/RTL, currency, date and status behavior;
- destructive/reversal/approval consequences;
- screenshots only when they materially reduce ambiguity;
- a short defect-report template containing session ID, actor, context, steps,
  expected result and actual result.

UAT findings are classified before implementation:

- **Defect in accepted session:** fix in a bounded recovery session.
- **Missing acceptance criterion:** update the session card, then fix.
- **New product scope:** return to Product Owner/roadmap disposition; do not hide it
  inside defect work.
- **Cosmetic preference:** batch only when it does not block correct task completion.

## 21. Validation and escalation rules

- Documentation-only sessions: references, stale-claim search, link/heading review,
  `git diff --check`; no application suite without executable risk.
- Routine Django slice: focused pytest module plus Ruff on touched code.
- Model/config/migration slice: focused tests, `manage.py check`, migration-plan or
  rehearsal appropriate to the risk.
- Authorization/tenant slice: cross-tenant, cross-project, role and object-scope
  denial tests are mandatory.
- Financial/payroll slice: golden calculations, idempotency, reversal, period lock,
  concurrency and reconciliation tests as applicable.
- Phase gate: affected integration suites first; broaden to the full PostgreSQL
  suite only when the phase is a release gate or evidence requires it.

Escalate from `T-M` to `A-H` when ownership, migration safety, concurrency,
security, tenant scope, financial history, or three or more interacting domains are
material. Escalate to `A-X` only for the named critical review or after an adequate
attempt remains unresolved. De-escalate once the ambiguity/risk has been removed.

## 22. Token and time controls

- Use headings, `rg`, narrow diffs and targeted tests before broad reads/runs.
- Start from the session's C0/C1 context manifest. Record the trigger before any
  C2 expansion and stop reading once the sufficiency questions are answered.
- Treat repository files, tests, migrations and compact handoffs as durable memory;
  do not repaste information that can be reliably re-opened at its source.
- Never spend a high-reasoning session on already-settled scope or mechanical work.
- Reuse the prior session's compact handoff; do not repaste full documents.
- Cap command output and avoid repeated polling.
- **Product Owner communication preference (2026-09-25):** use concise English
  for execution responses, progress updates, session cards, handoffs, and closeout
  reports unless requested otherwise. Lead with outcome and include only material
  decisions, changed artifacts, validation, blockers, and the next action. Link to
  evidence instead of repeating it; suppress unchanged context, raw routine output
  and generic caveats. Never compress away an approval state, material risk, failed
  validation, unresolved decision, or required acceptance criterion.
- Announce a materially expensive validation before running it.
- If the expected session duration grows by more than 50%, stop and split unless
  stopping would leave data or the worktree unsafe.
- Keep one implementation thread per session unless the work is safely independent
  and explicit parallelism is requested.
- End when acceptance criteria pass; theoretical completeness moves to a later,
  explicitly approved session.

## 23. Phase entry and exit gates

### Entry

- predecessor gates passed;
- Product Owner decisions listed for the phase are resolved or explicitly scoped
  out;
- relevant ADRs accepted;
- session cards for the first five sessions are ready;
- migration, rollback and test environment assumptions are known.

### Exit

- every accepted session outcome is implemented and validated;
- no critical tenant/security/financial invariant is open;
- Product Owner completes applicable UI/UAT;
- documentation closeout is complete;
- actual session count and variance are recorded;
- `ROADMAP.md` status changes only when acceptance evidence supports it.

## 24. Calibration record

Update this table only at a phase boundary. It records execution accuracy, not
product implementation status.

| Phase | Planned sessions | Actual sessions | Variance reason | Remaining estimate adjustment |
| --- | ---: | ---: | --- | --- |
| P0 | 22 | — | — | — |
| P1 | 28 | — | — | — |
| P2 | 38 | — | — | — |
| P3 | 32 | — | — | — |
| P4 | 38 | — | — | — |
| P5 | 28 | — | — | — |
| P6 | 42 | — | — | — |
| P7 | 36 | — | — | — |
| P8 | 30 | — | — | — |
| P9 core | 26 | — | — | — |
| P10 | 24 | — | — | — |

## 25. First operating rule

Do not generate all 344 detailed prompts now. Before beginning P0, expand only
P0-S01..S05 into session cards. After P0-S05, compare actual duration, token use,
defects and decision latency, then calibrate P0-S06 onward. This preserves roadmap
coverage without creating hundreds of stale prompts or consuming tokens before the
work is authorized.

## 26. P0-S01 — Entry baseline evidence and S02 handoff

**Recorded:** 2026-09-24. **Outcome:** S01 evidence collection complete; ready for
P0-S02 decision preparation. This is not P0 entry-gate acceptance, completion of
P0.1, Product Owner approval, or production certification.

**Objective/scope:** verify the five requested entry concerns using static
repository evidence. The supplied S01 request was the session contract; no prior
implementation handoff was assumed. C0/C1 comprised the applicable repository
instructions, working-tree state, [Roadmap](../ROADMAP.md) authority/status,
Delivered baseline, dependency overview, P0.1 and decision register; this
Playbook's authority/context/session/handoff rules; and the
[audit](architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md) sections 1, 3.2,
19 and 20. Direct code/test reads below were sufficient. Targeted Roadmap P1.1,
P2.1, P3.1/P3.2 and P4.1 reads resolved future scope/ownership; no wider architecture
collection, external research, implementation, S02 packet or S03 scope decision
was required or performed.

### Findings

Classifications apply to the stated claims: **confirmed** by inspected evidence,
**contradicted** by inspected evidence, or **unverified** where evidence is
insufficient. Static confirmation is not a passing runtime test.

1. **BillingPolicy ownership — confirmed.**
   [BillingPolicy](../apps/billing/models.py) is one mutable row per organization,
   combining numbering/precision/period controls, tax/insurance rates and
   retention/advance-recovery terms. In
   [billing services](../apps/billing/services.py), `update_billing_policy` updates
   that row; `_policy_snapshot`, `create_progress_claim` and
   `recalculate_progress_claim` show claims capture and consume their own policy
   snapshot. Thus mixed ownership is confirmed, but changing policy does not
   imply recalculating existing claims from the live row. **Planning consequence:**
   retain snapshots while planning PPC-01/PPC-06 separation into tenant settings,
   versioned contract terms and effective-dated regulatory rules. **Open:** approve
   ownership/effective-date and professional-review decisions; legal validity of
   current rates was not verified.

2. **Project budget/actual authority — confirmed.**
   [Project](../apps/projects/models.py) stores `estimated_budget` and
   `actual_budget` as independent Decimal fields;
   [create_project](../apps/projects/services.py) accepts them directly and
   [project_create](../apps/projects/views.py) passes form values. Separately,
   [Estimate.total_amount / EstimateRevision.total_amount](../apps/estimates/models.py)
   calculate revision/item totals, while
   [get_project_financial_report / _build_report](../apps/financials/services.py)
   derive approved-estimate totals, recorded expenses and posted receipt/disbursement
   totals without using those Project budget fields. These operational projections
   are not comprehensive accounting actuals or an accepted budget baseline.
   **Planning consequence:** PPC-03/P4.1 must define estimate-to-budget handoff and
   actual-cost lineage, preserving compatibility until an approved transition.
   **Open:** authoritative budget/CBS/cost-center and actual-versus-paid semantics.

3. **Payment and PaymentAllocation boundary — confirmed.**
   [Payment / PaymentAllocation](../apps/payments/models.py) represent a posted
   receipt/disbursement cash record and its allocation to a contract, respectively.
   [create_payment / allocate_payment / void_payment](../apps/payments/services.py)
   validate tenant/project context, cap active allocations at payment amount and
   preserve reversal evidence; `_reverse_locked_payment_allocation` also invokes
   dependent claim-settlement reversal. In
   [billing services](../apps/billing/services.py), `_validate_settlement_context`
   restricts claim settlement to posted receipts with matching context/party.
   Neither record is a journal or journal line. **Planning consequence:** preserve
   this delivered cash/receivable evidence under PPC-02. Roadmap P2.1/P3.1/P3.2
   plan Accounting-owned journals, Treasury-owned cash/instruments and AP/AR-owned
   obligations/open items; these remain future scope. **Open:** native versus
   external accounting and the explicit Payment migration/containment mapping.

4. **Authorization scope — confirmed, with a privileged-path qualification.**
   [resolve_session_organization / get_valid_memberships](../apps/organizations/services.py)
   and [OrganizationMiddleware](../apps/organizations/middleware.py) resolve tenant
   context through session and active membership.
   [has_business_permission / require_business_permission](../apps/organizations/authorization.py)
   check active user/organization and ordinary users' active membership/role grants;
   they explicitly allow an active `superuser` without membership at that service
   boundary. [get_organization_projects / get_organization_project_sites / get_organization_sites](../apps/projects/services.py)
   constrain tenant and parent relationships but do not intersect results with
   per-user project/site grants. **Planning consequence:** tenant isolation and
   relationship validation must not be mistaken for object-scope authorization;
   PPC-04/P1.1 remains planned. **Open:** project/site scope semantics, owner and
   privileged/support exceptions, and intersection with workflow candidacy. This
   was not an audit of every endpoint or workflow.

5. **P0 Product Owner decision approval — unverified; keep open.**
   [Roadmap P0.1 and Product-owner decision register](../ROADMAP.md),
   [audit section 20](architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md) and
   Playbook section 6 identify customer segment, native/external financial boundary,
   hosting/data residency and RPO/RTO as required decisions. The inspected sources
   contain no recorded approval for these choices. **Planning consequence:** S02
   can prepare decisions, but no segment, provider, residency or recovery target
   may be treated as approved. **Open:** all four choices and evidence of acceptance
   of the audit/correction set required by P0.1/P0 gates. This does not establish
   whether approval exists outside the inspected sources.

### Verification and change boundary

Code inspection above is distinct from **test definitions inspected, not run**:
[billing tests](../apps/billing/tests.py)
`test_policy_drives_rounding_and_adjustments`;
[financials tests](../apps/financials/tests.py)
`test_report_uses_approved_estimates_and_recorded_expenses` and
`test_report_rejects_cross_tenant_project`;
[payments tests](../apps/payments/tests.py)
`test_payment_allocation_cannot_exceed_payment_and_reverses_on_void`;
[projects tests](../apps/projects/tests.py)
`test_project_queryset_excludes_other_organization`; and
[permission decorator tests](../apps/organizations/test_permission_decorators.py)
`test_denies_request_when_active_role_lacks_permission` (mocked permission helper).
These establish intended assertions, not current passing results.

Documentation validation passed: added-text/diff and heading/status review,
19 local link targets, 34 source/test symbol references, append-only preservation
against the pre-edit file, and `git diff --check -- docs/ROADMAP_EXECUTION_PLAYBOOK.md`.
No application tests, builds, migrations, database diagnostics/mutations or runtime
readiness checks were run; static evidence was sufficient for S01. No directly
proven stale claim in the inspected authoritative sections required correction.
Initial S01 closeout added only this record. A Product Owner-requested follow-up
added an evidence/handoff reference under Roadmap P0.1; its link and diff were
checked with `git diff --check -- ROADMAP.md docs/ROADMAP_EXECUTION_PLAYBOOK.md`.
Roadmap statuses and open approval gates remain unchanged.

The worktree initially contained existing documentation changes, including an
untracked Playbook. Before this edit it was clean at `dba90ec` and the Playbook was
tracked; this session did not create that commit. The session edit is append-only
relative to the pre-edit file. No application/configuration/dependency changes,
branches, commits or remote actions were made by this session.

### Compact P0-S02 handoff

**Next:** P0-S02 — prepare the Product Owner decision packet; do not implement or
decide S03 release assumptions. First reconcile any supplied approval evidence
against the open choices in finding 5, then prepare the decision packet. Missing
approvals do not block completion of S01 or preparation in S02; they remain gates
for affected downstream work.

**Minimum read set:** this record; Roadmap P0.1 and Product-owner decision register;
audit sections 19-20; Playbook sections 1, 3.1-3.2 and 6. Use the five source/symbol
groups above only when a decision needs deeper implementation evidence. Consult
Roadmap P1.1, P2.1, P3.1/P3.2 or P4.1 only for the corresponding boundary. Do not
reload the full audit or reconstruct earlier conversation history. Preserve claim
snapshots, payment/allocation reversals, tenant checks and existing Project fields;
their replacement needs separately approved scope. S01 provides evidence and open
decisions, not approved ADRs or a production-readiness result.

## 27. P0-S02 decision packet and S03 handoff

**Recorded:** 2026-09-24. **Outcome:** six decisions prepared for Product Owner
review; P0-S02 preparation complete. No ADR, release scope, implementation package
or P0/P0.1 completion is approved by this record.

**Confirmed direction:** the Product Owner's explicit P0-S02 instruction places
advanced AI, B2B network, GPS/telematics, GIS, enterprise SSO, broad offline work
and architectural distribution after the core. Preserve this sequencing; it does
not approve a reduced core or select any option below. Exact release assumptions
belong to S03.

**Decision convention:** P0-D01 through P0-D06 are stable IDs introduced here; no
existing IDs for these choices were found in the inspected planning references.
At S02 close, all six were **OPEN**, with no explicit option approval recorded.
The comparisons below preserve that historical proposal state. Subsequent Product
Owner acceptance and current decision dispositions are recorded in
[S03 approval evidence](#s03-approval-evidence-and-current-decisions) and the Roadmap
register. Approval applies to the recommended choices, not to unspecified parameters.

### P0-D01 Initial customer segment

**Question:** which customer group should lead initial onboarding, validation and
support design, while retaining one core model for small and larger contractors?

| Choice | Tradeoff |
| --- | --- |
| A. Small contractors first | Emphasizes simple setup and Tenant Owner fallback; supplies less initial evidence for multi-project access and separation of duties. |
| B. Growing multi-project contractors first | Exercises shared masters, project scope, cost and claim handoffs; needs more demanding onboarding and control validation. |
| C. Both groups from the outset | Validates breadth immediately; requires parallel onboarding and acceptance examples. |

**Evidence:** [S01](#26-p0-s01--entry-baseline-evidence-and-s02-handoff), findings
2/4/5; [Business Model section 2](architecture/BUSINESS_MODEL.md#2-target-customer-segments);
[audit section 20](architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md#20-adr-candidates-and-product-owner-decisions).
**Recommendation:** B, retaining optional workforce structures and simple workflows
for small contractors. It tests the integration and scope boundaries S01 identified
without treating enterprise features as prerequisites.
**Assumptions/needed:** access to representative multi-project users is unverified;
confirm pilot candidates, project/user scale, buyer and onboarding capacity. Segment
focus does not remove core capabilities. **Affected:** P0.1, P1.1, P4 and P10
acceptance examples. **Latest gate:** before accepting the segment-dependent P0.1
ADRs; provide the choice to S03 before release assumptions are frozen.
**Status at S02 close: OPEN. Approval evidence then: none recorded.**

### P0-D02 Financial authority boundary

**Question:** where should authoritative Accounting, Treasury and AP/AR records
reside for the intended core offering?

| Choice | Tradeoff |
| --- | --- |
| A. Native Accounting, Treasury and AP/AR | Coherent product-owned journals, cash and obligations; requires the planned financial kernel, reconciliation and professional acceptance. |
| B. External Accounting, Treasury and AP/AR | External suite owns all financial books/cash/open items; ERP retains operational sources and references. Requires a selected suite and reliable integration/reconciliation contracts. |
| C. External Accounting; native Treasury and AP/AR | Retains construction cash/settlement control; creates an explicit cross-system posting, close and reconciliation boundary. |

**Evidence:** S01 finding 3 establishes that current Payment/allocation records are
not journals or a complete Treasury/AP/AR implementation; audit PPC-02 and section
20 require an explicit choice. S01 records the planned P2/P3 ownership split.
**Recommendation:** A, for coherent construction financial traceability and alignment
with the accepted target direction. This is a design recommendation, not a claim of
readiness or approval. If external books are mandatory for target customers, revise
the choice with a named system and ownership map; do not keep duplicate authorities.
**Assumptions/needed:** confirm customer accounting obligations, professional-review
capacity, any mandatory external system, and posting/reversal/close ownership for
each of the four domains. B/C need an interface feasibility assessment; none was
performed. **Affected:** P0.1, P2/P3 and downstream financial integrations.
**Latest gate:** before accepting financial P0.1 ADRs or authorizing P2/P3 work;
S03 needs the explicit boundary. **Status at S02 close: OPEN. Approval evidence then:
none recorded.**

### P0-D03 Hosting, residency and operational ownership

**Question:** who operates the service and where may primary data, documents,
replicas, backups, logs and support-access data reside?

| Choice | Tradeoff |
| --- | --- |
| A. Product-accountable SaaS using managed infrastructure/services | Provider operates contracted infrastructure; product team remains accountable for configuration, releases, incidents and recovery verification. Depends on provider/residency suitability. |
| B. Product-operated SaaS on rented infrastructure | More direct operating control; product team also owns database/storage maintenance, backup execution and infrastructure incident response. |

**Evidence:** [Roadmap P0.2](../ROADMAP.md#p02-reproducible-delivery-security-and-recovery-baseline),
audit PPC-05/section 20 and S01 finding 5 leave operations and residency unresolved.
**Recommendation:** A, conditional on verified residency, compatibility, access,
backup/export and recovery requirements. It assigns infrastructure operations to a
provider while keeping product accountability explicit; no provider is selected.
**Assumptions/needed:** identify permitted countries/regions and any cross-border
restrictions, operator and incident/recovery owner, support coverage, budget and
provider evidence. Confirm where support staff may access data. Neither option
approves architectural distribution or a deployment contract.
**Affected:** P0.1 storage/support ADRs, P0.2, P0.3 export/offboarding and P10.
**Latest gate:** before P0.2 implementation or any hosting commitment/data placement;
align the choice with D04. **Status at S02 close: OPEN. Approval evidence then:
none recorded.**

### P0-D04 Recovery objectives

**Question:** what maximum loss of acknowledged business data (RPO) and maximum
service outage before usable recovery (RTO) will the business accept, for which
failure scenarios and service hours?

| Choice | Tradeoff |
| --- | --- |
| A. One recovery baseline for core tenants | Consistent recovery validation and service terms; one chosen target must be affordable and demonstrably achievable before any contractual commitment. |
| B. Differentiated recovery service levels | Can fit differing customer needs; adds entitlement, operations and contract complexity, and requires separate proof for each level. |

**Evidence:** Roadmap P0.2 requires backups and proven restore; audit PPC-05/section
20 and S01 finding 5 record no approved RPO/RTO. **Recommendation:** A initially;
set business tolerances before selecting the recovery design. No numeric target,
zero-loss guarantee or availability commitment is proposed here.
**Assumptions/needed:** Product Owner supplies maximum tolerable data loss and
downtime with units, covered incident scenarios/service hours and whether targets
are contractual. D03's operator must demonstrate feasibility and consistent recovery
of database, documents and audit evidence, with an accountable recovery owner.
Backup frequency alone does not prove either objective.
**Affected:** P0.2, P0.3 service terms and P10 recovery certification.
**Latest gate:** before P0.2 recovery implementation and any customer commitment;
measured restore evidence remains a separate go-live gate.
**Status at S02 close: OPEN. Approval evidence then: none recorded.**

### P0-D05 SaaS packaging, entitlements and quotas

**Question:** how should the initial commercial offer package capabilities and
capacity, enforce limits and handle subscription administration?

| Choice | Tradeoff |
| --- | --- |
| A. One core plan with explicit capacity limits | Easier to explain and operate; fewer commercial differentiation options. |
| B. A small set of named capability/capacity tiers | More differentiation; increases entitlement, upgrade and support combinations to validate. |
| C. Negotiated enterprise entitlements | Fits contract-specific needs; adds manual commercial governance and risks inconsistent promises. |

**Evidence:** [Business Model section 6](architecture/BUSINESS_MODEL.md#6-packaging-and-monetization-direction)
leaves commercial terms open; [Roadmap P0.3](../ROADMAP.md#p03-saas-plans-entitlements-quotas-and-tenant-offboarding)
owns versioned entitlements, quotas and offboarding. **Recommendation:** A with
versioned entitlements and justified user/project/storage limits. Show usage and
warnings before limits; at the agreed cap, reject operations increasing usage while
preserving authorized work on existing records, history and export. Treat payment
delinquency, suspension and cancellation as separately defined lifecycle rules.
Propose externally administered subscription invoicing initially, subject to owner
approval; P0.3 does not imply an in-product subscription billing engine.
**Assumptions/needed:** select metric definitions and actual limits, warning/grace
rules, overage/upgrade handling, trial policy, support terms, pricing and invoicing
owner. No values or prices are invented. Packaging does not authorize reducing core
scope or weakening permissions, retention or recovery obligations.
**Affected:** P0.3 and consuming domains; D03/D04 service terms.
**Latest gate:** before P0.3 policy implementation; commercial terms must be resolved
before selling the offer. **Status at S02 close: OPEN. Approval evidence then:
none recorded.**

### P0-D06 Audit findings, priorities and implementation authority

**Question:** does the Product Owner accept the audit findings and their correction
priorities, and which separately bounded work, if any, is authorized next?

| Separate response | Viable choices and consequence |
| --- | --- |
| Findings | Accept the audit as the planning baseline, or revise named findings with evidence. Acceptance does not certify every finding through fresh testing. |
| Priorities | Accept PPC-01–06 MUST, PPC-07–12 SHOULD and PPC-13 DEFER, or revise specific priorities with rationale and affected gates. |
| Implementation | Keep authorization pending, or authorize only a separately specified package with scope and acceptance criteria. The packet itself is not such a package. |

**Evidence:** [audit section 19](architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md#19-pre-production-correction-register)
defines PPC-01–13; S01 statically confirms only its five bounded concerns, and
Roadmap P0.1 requires audit acceptance. **Recommendation:** accept the audit as a
planning baseline and the recorded priorities, carrying S01's verification limits;
retain PPC-13 as deferred. Keep implementation authorization separate and pending
until an explicit package is reviewed. **Assumptions/needed:** respond separately
on findings and priorities; identify disputed PPC IDs, acceptance owner and any
evidence required. Any later implementation approval must name its package, scope,
dependencies and acceptance criteria. **Affected:** P0.1 and correction sequencing
across P0/P1 and the financial work packages. **Latest gate:** baseline/priority
acceptance before affected P0.1 ADR acceptance; package authorization before any
implementation. **Status at S02 close: OPEN. Approval evidence then: none recorded**
for any of the three responses. No application implementation was authorized in S02.

### S02 verification and closeout

Context used: this Playbook's authority, minimum-context policy, P0 session map and
S01 record/handoff; Roadmap P0.1–P0.3, decision register and governance; audit
sections 19–20; Business Model sections 2/6 for customer/packaging comparisons.
Unchanged instructions and S01 evidence were reused. The changed repository
instructions add mandatory Roadmap reconciliation; that addition was read.
No relevant application file had a working-tree change and no material
contradiction required reopening code. This is not a repeat audit or new passing
test evidence. No external/provider claims were researched or verified; provider,
commercial and recovery feasibility remain inputs, not asserted facts.

Only this S02 record and affected Roadmap planning/register entries were changed.
Existing Agents.md changes, the Playbook workflow-rule change and all S01 text were
preserved. Parent statuses, dependencies and phase numbering remain unchanged:
the evidence did not require dependency corrections. Validation passed: scoped
diff review, S01/pre-existing-text preservation, all six IDs/statuses, 15 local
link/anchor references, affected roadmap references and `git diff --check` on both
changed documents. Application paths also have no diff from the S01 baseline
commit `dba90ec`.
No application tests, builds, migrations, database operations, packages, ADR
finalization, commits or remote actions were performed.

### Compact P0-S03 handoff

**Historical handoff written at S02 close; current progress is in section 28.**

**Next:** P0-S03 — clarify release-scope assumptions; not executed here. Read this
packet, Roadmap P0.1–P0.3 and the decision register first. Reuse S01 only for a
specific evidence question. Carry forward the confirmed after-core direction and
all six OPEN decision statuses. S02 prepared the packet; it did not obtain approval.

Obtain responses to D01–D06, including numeric business tolerances for D04 and
named operational/commercial owners. D01/D02/D06 are upstream inputs to P0.1;
D03/D04 gate P0.2 and D05 gates P0.3. Missing answers permit clarification work
but must remain unresolved rather than silently becoming release assumptions.
Before scope is frozen, distinguish required core journeys from later features,
record the chosen financial authority and service commitments, and identify the
relevant statutory filing, currency, valuation, payroll, document-retention and
project-scope decisions already listed in the Roadmap. Do not settle those extra
decisions in S02 or assume that an external-finance option reduces the approved
core. No ADR or implementation is authorized by this handoff.

## 28. P0-S03 release assumptions and S04 handoff

**Recorded:** 2026-09-24. **Outcome:** P0-S03 clarification complete: accepted
choices, the core planning boundary, acceptance journeys and unresolved release
parameters are explicit. The final release contract is **NOT FROZEN**. No P0/P0.1
completion, production certification, finalized ADR or application implementation
is implied.

**Session contract:** the Product Owner accepted the S02 recommendations and
requested P0-S03. Use the existing P0-P10 core-completion track and S01/S02 evidence;
record approval without inventing missing parameters or re-auditing code. Change
only affected planning/business documents, validate their consistency and hand off
to S04. Do not execute S04 or implement a roadmap package.

### S03 approval evidence and current decisions

**Approver/source:** Product Owner, explicit message in this task on 2026-09-24:
"I accept the recommendations. Execute P0-S03." (English translation of the Persian
message.) This accepts the recommended choices in section 27. It authorizes this
planning session; it does not supply missing numeric/commercial parameters or
authorize application implementation. The S02 OPEN statuses remain historical.

| ID | Current disposition | Accepted choice and remaining boundary |
| --- | --- | --- |
| P0-D01 | APPROVED | B: growing multi-project contractors lead initial onboarding/validation; retain one model and optional structures for small contractors. Pilot customers and workload sizes remain to be named. |
| P0-D02 | APPROVED | A: native Accounting, Treasury and AP/AR are the financial authorities. Detailed posting/close/migration ADRs and professional validation remain required. |
| P0-D03 | DIRECTION APPROVED; PARAMETERS OPEN | A: product-accountable SaaS using managed infrastructure/services, conditional on suitability. Residency, provider, named operator, access/support coverage and budget are not selected. |
| P0-D04 | DIRECTION APPROVED; PARAMETERS OPEN | A: one recovery baseline for core tenants. No numeric RPO/RTO, scenario coverage or contractual availability commitment has been approved. |
| P0-D05 | POLICY APPROVED; PARAMETERS OPEN | A: one core plan, versioned entitlements and justified user/project/storage limits; warn before the cap, block usage-increasing operations at the cap while preserving authorized existing work/history/export. Subscription invoicing is initially administered externally. Exact commercial values and lifecycle parameters remain open. |
| P0-D06 | FINDINGS/PRIORITIES APPROVED; IMPLEMENTATION NOT AUTHORIZED | Accept the audit as the planning baseline, PPC-01–06 MUST, PPC-07–12 SHOULD and PPC-13 DEFER, with S01 verification limits. Application implementation still requires a separately approved package. |

### Release planning boundary

The following distinctions clarify existing direction; they do not remove roadmap
capabilities or approve previously unresolved options.

| Assumption | Disposition and consequence | Source |
| --- | --- | --- |
| Core-completion envelope | Retain the existing P0-P10 core: operations/security, masters, native finance, project controls, procurement, contracts/claims, payroll, inventory/equipment/assets, field/HSE/QA, non-AI support/notifications, knowledge, reporting, reconciliation and certification. This is the planning envelope, not evidence of delivery or a frozen detailed release scope. | Playbook section 2; D01/D02; Roadmap P0-P10 |
| After-core boundary | Advanced AI, B2B network, GPS/telematics, GIS, enterprise SSO, broad offline synchronization and architectural distribution stay after the core under their existing triggers. Deferred SSO does not defer privileged-user MFA; the B2B network does not replace the separately planned controlled partner portal. | Explicit S02 direction; Roadmap P0.2 and Deferred until explicit triggers; Business Model section 7 |
| Initial user/tenant profile | Lead with growing multi-project contractors; retain small-contractor usability. Shared masters, tenant isolation, project/site scope and optional workforce routing remain necessary. No headcount, project count or workload volume is assumed. | D01; S01 finding 4; Business Model section 2 |
| Financial authority | Operational domains own source facts; Accounting owns journals, Treasury cash/instruments and AP/AR obligations/open items. Current Payment/allocation evidence and manual Project fields are compatibility inputs, not substitutes for the target authorities. | D02; S01 findings 2/3; PPC-02/PPC-03 |
| Service and commercial shape | Use the accepted managed SaaS direction, one recovery baseline and one core plan. External administration of the SaaS subscription does not remove customer construction Billing, claims or financial control from the ERP. | D03-D05; Roadmap P0.2/P0.3 |
| Certification boundary | P10.3 must certify the explicitly resolved core release scope and all applicable controls. S03 does not turn unverified legal rules, parameter gaps or unimplemented capabilities into accepted release behavior. | Roadmap P10.3; audit PPC-01–06 |

### Planned acceptance journeys

These are release-planning checks over existing roadmap scope, not new test results,
implementation tasks or a replacement backlog. Detailed variants remain with each
work package; every applicable journey must retain tenant/object authorization,
source history and auditable failure/reversal behavior.

| Journey to demonstrate before certification | Existing roadmap ownership |
| --- | --- |
| Onboard a tenant, configure masters/roles/project-site access, apply the plan, operate safely at limits and exercise authorized export/offboarding. | P0/P1 |
| Carry approved estimate/revision evidence into an accepted budget; procure, receive, value/use materials and reconcile commitments, actual cost, cash and GL without conflating them. | P4/P5/P8 with P2/P3 |
| Carry versioned contract terms and verified progress through claim approval, receivable/payable obligations, settlement, posting and correction/reversal. | P6 with P2/P3/P4 |
| Carry workforce/time evidence into reviewed payroll and insurance outputs, liabilities, payment and project-cost reconciliation. | P7 with P2/P3/P4 |
| Retain protected field/document evidence, close HSE/quality issues, publish reviewed knowledge and support users through non-AI support/notifications; reconcile governed reports to their sources. | P1.3/P9/P10 |
| Demonstrate migration/rollback, coherent restore, monitoring/incident response, accessible Persian RTL journeys and release/rollback ownership at the approved scale. | P0.2/P0.4/P10.3 |

### Unresolved parameters and latest gates

Rows below retain their stated gates unless a later session records a current
status. They are inputs to affected design/acceptance, not reasons to reduce the
core silently. Product Owner supplies business choices and names accountable
reviewers/operators; professional and operational feasibility must then be
established where required. No prices, durations, rates, providers, numeric quotas
or recovery commitments are assumed.

| Reference | Information still needed | Latest gate / affected scope |
| --- | --- | --- |
| P0-D01 details | Pilot contacts, buyer/UAT owner, representative projects/users, transaction/document volumes and onboarding capacity. | Before representative workload/support commitments and P10 acceptance criteria are frozen; informs P0.2 sizing. |
| P0-D03 parameters | Permitted primary/backup/log/document locations and support-access jurisdictions; selected provider, named operator/incident owner, support hours and operating budget. | Before P0.2 implementation, hosting commitment or production data placement. |
| P0-D04 parameters | Maximum acceptable lost acknowledged data and outage, with units; incident scenarios/service hours, contractual applicability and recovery owner. | Before P0.2 recovery implementation/customer promises; measured restore evidence before P10.3. |
| P0-D05 parameters | Definitions and values for user/project/storage limits; warning/overage/upgrade, trial, grace/suspension/cancellation rules, price/support terms and external invoicing operator. | Before P0.3 policy implementation; commercial terms before sale. |
| P0-S03-Q01 | IRR-only versus multi-currency requirements, fiscal/calendar settings, and approved inventory valuation/traceability policy. | Before affected P1.2/P2/P8.1 design acceptance and financial implementation. |
| P0-S03-Q02 | Exact statutory filing versus export/submission scope; employment/pay components, attendance-integration scope, named accounting/legal reviewer and source validation. | Before affected P1.2/P6.3/P7 design/implementation; professional acceptance before release. P6.3 remains legally gated. |
| P0-S03-Q03 | Required signatures/evidence standards, retention/hold/export obligations and responsible approver. | Before affected P0.2/P0.3/P1.3 storage/DMS design acceptance or data placement. |
| P0-S03-Q04 | Product Owner selections A1/B1/C1/D1/E1, revised F2, final G3 — Revised with Protected Operations, and H1 are recorded. P0-S18 assigns Azam Zerangzadeh every review responsibility and explicitly overrides the independence expectation; every review/evidence field remains OPEN and the concentration risk is recorded. | Completed named review before accepting S07/affected ADR clauses or implementing P1.1; external professional/statutory independence obligations are not waived; tenant-wide permissions remain insufficient. |

Other conditional scope already in the Roadmap decision register (for example
licensed price-book imports, portal identity and notification channels) retains its
phase-specific approval requirement. S03 neither promotes optional integrations to
mandatory launch scope nor removes their parent core capabilities. Selecting
native finance does not certify statutory filing behavior or assign legal validity
to current BillingPolicy rates.

### S03 verification and documentation closeout

S01 code evidence was reused; no application changes since its recorded baseline
required reopening code. Context was limited to the session map/core envelope,
S01/S02 handoff, Roadmap planning/register/certification sections, targeted P6.3,
P7.2/P8.1 gate text and Business Model customer/packaging/operating sections.
The last targeted reads resolved why native finance cannot settle filing/valuation
scope automatically. No external research or legal/provider verification occurred.

Closeout updates the Playbook's current approval references and S03 record, Roadmap
P0.1 progress/decision statuses and P0.2/P0.3 parameter notes, and the affected
Business Model choices. S01 and the historical S02 comparisons/results remain
intact; pre-existing repository-instruction changes are preserved. The dated audit
remains historical evidence, linked through the accepted PPC IDs; no audit rewrite
or model/schema change is needed. Roadmap dependencies and parent implementation
statuses remain unchanged.

Validation passed: session-scoped diff review, six synchronized current decision
statuses and approval evidence, 20 local link/anchor references, roadmap references,
S01/prior-rule and Agents.md preservation, and `git diff --check` on the three
changed documents. S02 changes are limited to historical-status labels/current
approval references; its comparisons and validation evidence were preserved.
No application tests, builds, migrations, database operations, dependency changes,
commits or remote actions were performed.

### Compact P0-S04 handoff

**Next:** P0-S04, within P0.1's ADR/correction-planning group; not executed here.
Start from this record's accepted-decision table, unresolved gates and Roadmap
P0.1. Use S01's five source/symbol groups only when the selected ADR needs them.
Do not repeat the audit or re-ask whether D01-B/D02-A/the D06 baseline are accepted.

Suggested first bounded focus: the native Accounting/posting authority and its
Treasury/AP/AR source contracts, including Payment containment, source/version
identity, reversal/close and reconciliation responsibilities. P0-S04 can prepare
that ADR from accepted direction, exposing Q01/Q02 choices wherever they affect
design; this handoff does not accept the ADR or authorize implementation. Hosting,
recovery and entitlement ADRs cannot be finalized with invented D03-D05 values.
Carry every open row forward to its stated gate. S03 clarification is complete;
the release contract and P0/P0.1 are not complete.

## 29. P0-S04 Accounting posting ADR proposal and S05 handoff

**Prepared:** 2026-09-24; **closeout verified:** 2026-09-25.
**Session contract:** the Product Owner explicitly
requested P0-S04, first reading section 28 and Roadmap status, and limited work to
that handoff. This authorizes ADR preparation only; it does not accept the ADR or
authorize application implementation.

| Card field | Bounded contract |
| --- | --- |
| Roadmap item / goal | P0.1 / PPC-02: prepare the native Accounting/posting ADR and Treasury/AP/AR source interface, preserving current Payment evidence. |
| In scope | Authority, source/version/event identity, idempotency, reversal/close, reconciliation, Payment containment and gated correction sequence; static posting walkthroughs. |
| Out of scope | Application/schema/migration changes, new dependencies, full Treasury/budget/authorization ADRs, legal/provider research, frozen currency/filing decisions, final ADR acceptance and S05 execution. |
| C0 / previous handoff | Repository instructions; section 28 accepted choices/open inputs/compact S04 handoff; Roadmap P0.1, P2/P3 and decision register; starting worktree diff. |
| C1 / direct evidence | Target Domain Model aggregate boundaries; Data Model sections 2, 6-8; audit PPC-02 and ADR candidates; S01 Payment/project/authorization findings; Payment/Billing settlement models/services, relevant test symbols and financial projection service. |
| C2 trigger / response | Financial-history migration and correction cross the Payment/Billing boundary: inspect dependent settlement reversal and payments 0004/0005 plus billing 0005 migration evidence. No broader re-audit. |
| Context intentionally excluded | Unrelated domains, full test collections, UI files, production environment and external legal/provider sources. |
| Expected files | New `docs/architecture/ADR_P0_S04_ACCOUNTING_POSTING.md`; limited progress/links in `ROADMAP.md`; this session record and handoff. |
| Model / reasoning policy | A-H architecture tier in section 4: financial ownership, idempotency, tenant boundaries and historical migration justify focused architecture reasoning; no delegated agents required. |
| Acceptance criteria | Clearly proposed ADR grounded in current evidence; explicit owner/interface/lifecycle and compatibility rules; illustrative balanced postings; all affected open gates retained; synchronized Roadmap and compact S05 handoff. |
| Targeted validation | Local links/anchors and source symbols, posting arithmetic, session-only diff/preservation checks and `git diff --check`; no application tests for documentation-only changes. |
| Product Owner input | D02 native direction already accepted; Q01/Q02/Q04 and migration/professional review choices remain open. Every other section 28 row retains its gate. |
| Stop / closeout | Stop after proposal, static validation and affected-document closeout. Do not mark P0/P0.1 complete, accept the ADR, or execute downstream work. |

### S04 outcome and verification

**Outcome:** bounded ADR preparation complete; architectural acceptance remains
open. [ADR P0-S04](architecture/ADR_P0_S04_ACCOUNTING_POSTING.md) is **PROPOSED**.
It specifies proposed financial owners, source/version/event identity, retry and
rule-upgrade behavior, atomic financial transitions, authorization gates,
reversal/close, reconciliation responsibilities and legacy Payment containment.
The illustrative receivable and payable journeys distinguish cash, allocation,
obligation and journal, including allocation reversal versus real cash refund.

Static validation passed: 15 local link/anchor references in the ADR/session card,
13 referenced service/test symbols, eight balanced illustrative journals and
intermediate AR/AP/cash/clearing balances. Existing tests are evidence references,
not new passing runs. Session-boundary review confirms the original Playbook
through section 28, pre-existing Agents.md and Business Model edits are preserved;
Roadmap changes are confined to P0.1 planning progress. Final closeout passed:
19 local links/anchors including the new handoff, unchanged open-input/decision
tables, `git diff --check` for edited files and the equivalent whitespace check
for the new ADR. No application tests, Django checks, migrations, database
operations, dependency changes, commits or remote actions were performed.

Documentation closeout adds the ADR, this session record and the Roadmap P0.1
progress link. Target Domain/Data Model documents already express these ownership
boundaries and remain current; an unaccepted proposal does not revise their
authority or the current-model document. Business Model decisions, the dated
audit/PPC classifications, package dependencies and implementation statuses remain
unchanged. All S03 open inputs remain open at their existing gates; no accounting,
legal, currency, hosting, recovery or commercial choice was invented. No scope
deviation or runtime validation failure occurred; professional review and ADR
acceptance are intentionally outstanding.

### Compact P0-S05 handoff

**Session/outcome:** P0-S04 prepared the Accounting/posting ADR and Treasury/AP/AR
source interface under P0.1/PPC-02. Preparation acceptance criteria are met;
the ADR remains **PROPOSED, NOT ACCEPTED**, and no implementation is authorized.
The user explicitly requested only S04 within section 28's handoff. D02's native
authority choice remains accepted; it must not be re-asked as an undecided choice.

**Changed files:** new `docs/architecture/ADR_P0_S04_ACCOUNTING_POSTING.md`,
section 29 here, and P0.1 planning progress in `ROADMAP.md`. No migration IDs or
application changes. The starting worktree already had changes to Agents.md,
Roadmap, this Playbook and Business Model; all pre-session content is preserved
except the intentionally updated current P0.1 progress paragraph.

**Resume invariants:** operational domains own source facts, Accounting journals,
Treasury cash/instruments, AP/AR obligations/settlement. A contract cash allocation
is not a journal line. Proposed posting identity excludes rule upgrades as a
duplicate-posting escape; linked reversal preserves source/journal history.
Legacy Payment and Billing settlement history must survive a reviewed mapping,
cutover and reconciliation. Detailed design lives in the ADR, not this handoff.

**Validation:** static source/test references, links, sample posting arithmetic,
preservation and whitespace checks; no runtime test claim. No external legal or
provider validation. Currency/fiscal/valuation Q01, statutory/professional Q02,
scope/separation Q04, pilot/cutover/opening-history choices and named reviewers
remain unresolved. Carry the entire section 28 open-input register, including
D01 and D03-D05/Q03, to its original gates. Do not treat session completion as
ADR acceptance, PPC-02 closure, a frozen release contract or P0/P0.1 completion.

**Next:** P0-S05 is a separate planning session, not executed here. Recommended
bounded continuation within P0.1: budget/CBS/cost-center and actual-cost authority
(PPC-03), using this proposal's financial-source boundary. Minimum context is
this handoff, ADR sections 2/5/6/8, section 28's open inputs, Roadmap P0.1/P4.1
and S01 finding 2. First define the S05 card, then inspect only the referenced
Project/Estimate/financial-report symbols and relevant target ownership rules.
If review feedback instead requires revising S04, record that bounded scope before
editing. Do not implement P2/P3/P4 or silently accept financial policy. No new
Product Owner approval is recorded by this suggested sequence.

## 30. P0-S05 Budget and project-cost ADR proposal and S06 handoff

**Recorded:** 2026-09-25. **Session contract:** the Product Owner requested
"do P0-S05" after S04. Follow section 29's bounded continuation: prepare the
budget/CBS/cost-center and actual-cost authority proposal within P0.1/PPC-03.
The request authorizes this planning session, not ADR acceptance or P4 implementation.

| Card field | Bounded contract |
| --- | --- |
| Roadmap item / goal | P0.1 / PPC-03, informing P4.1: one accepted budget authority and traceable project-cost projections. |
| In scope | Estimate/BOQ-to-budget mapping, budget revisions, WBS/CBS/cost-center distinctions, commitment/actual/paid and forecast semantics, source classification/reconciliation, legacy Project-field containment and correction sequencing. |
| Out of scope | Application/schema changes, implementation of P2/P3/P4 or cost producers, full financial/valuation policy, UI redesign, external legal research, accepting S04/S05 ADRs and executing S06. |
| C0 / previous handoff | Repository instructions; section 29 handoff and S04 ADR sections 2/5/6/8; section 28 open gates; Roadmap P0.1/P4.1; starting worktree and target diff. |
| C1 / minimum context | S01 finding 2; relevant Domain/Data Model ownership; Project fields and creation, Estimate/revision totals and lifecycle, financial report filters/calculation and directly related tests. |
| C2 triggers | Follow a source-revision or double-counting ambiguity into its direct consumer or migration evidence; record the trigger. No broad repository audit or full test collection. |
| Context intentionally excluded | Unrelated roadmap domains, production data/settings, complete producer implementations and external accounting/legal sources. |
| Expected files | New `docs/architecture/ADR_P0_S05_BUDGET_PROJECT_COST.md`; this session card/result/handoff; Roadmap P0.1 progress only. |
| Model / reasoning policy | A-H architecture tier: source ownership, financial history, revision and tenant-boundary risks require focused architecture reasoning. |
| Acceptance criteria | Proposed design grounded in current code; separate commercial estimate/budget/actual/cash; explicit mapping, lifecycle, lineage, migration and unresolved gates; worked reconciliation examples; synchronized Roadmap and S06 handoff. |
| Targeted validation | Source-symbol and local link/anchor checks, Decimal walkthrough arithmetic, session-diff preservation and whitespace checks; no runtime tests for documentation-only work. |
| Product Owner input | Preserve section 28 decisions/gates; budget approval/rebaseline, classification, forecast/WIP and conversion policies require later acceptance and professional review as applicable. |
| Stop / closeout | Stop after proposed ADR, proportionate static validation and documentation closeout. No PPC-03/P0.1 completion or implementation authorization follows from session completion. |

### S05 outcome and verification

**Outcome:** bounded preparation complete;
[ADR P0-S05](architecture/ADR_P0_S05_BUDGET_PROJECT_COST.md) remains **PROPOSED**.
It defines proposed cost-budget ownership, estimate/BOQ handoff and line mappings,
WBS/CBS/cost-center distinctions, accepted-version lifecycle and concurrency,
commitment/actual/accrual/paid/forecast semantics, source reconciliation and legacy
Project-field containment. Four worked cases cover version pinning, cost versus
cash, accrual replacement and reclassification/reversal without duplicate costs.

Material evidence: Estimate revision creation moves the current pointer/root
status to draft while the financial report filters approved roots. Therefore a
governing budget must pin source revisions rather than reuse that live projection.
This is a static inference, not a newly executed report test or authorization to
change report behavior. C2 expansion was limited to Estimate revision approval/test
and migration provenance, the existing Billing measurement baseline's distinct
meaning, and direct legacy Project field consumers needed for safe containment.
No other cost producers were audited; their contracts are proposed requirements.

Initial static checks passed: 24 local links/anchors, 16 code/test symbols and all
four Decimal walkthroughs, including unchanged cash on allocation/performance
correction, split conservation and non-duplicated invoice recognition. Existing
test bodies were inspected without execution. Session preservation checks confirm
the prior Playbook through section 29 and pre-existing Agents.md, Business Model
and S04 ADR content are unchanged. No application/configuration, migration or
dependency changes; no database operations, runtime tests, commits or remote work.

Documentation closeout adds the ADR and this record/handoff, and updates only
Roadmap P0.1 progress. Target Domain/Data Model and current-model documents already
distinguish estimates, cost budgets, Billing measurement and financial authorities;
no approved ownership or implemented behavior changed, so no edits there are
required. The dated audit/PPC priorities and Business Model remain unchanged.
P4.0/P4.1 and financial dependencies retain their status; S04 is not accepted by
S05 completion. All section 28 open rows retain their original gates. New detailed
budget/forecast/classification policy questions are explicit in the ADR and do
not create assumed defaults or authorize implementation. No scope deviation.

Final closeout passed: 30 local links/anchors, Roadmap changes limited to P0.1
progress, unchanged prior decision/open-input tables, and whitespace checks for
the edited documents and new ADR. Measured elapsed time from the evidence snapshot
through final link/preservation validation was 7.7 minutes; initial contract reads
were not timed. This is documentation validation, not application test duration.

### Compact P0-S06 handoff

**Session/outcome:** P0-S05 prepared the budget/CBS/cost-center and project-cost
authority proposal under P0.1/PPC-03. Preparation acceptance criteria are met;
the ADR remains **PROPOSED, NOT ACCEPTED**. User authorization was "do P0-S05"
following section 29's handoff. It does not accept either S04 or S05, close PPC-03,
freeze release scope or complete P0/P0.1.

**Changed files:** new `docs/architecture/ADR_P0_S05_BUDGET_PROJECT_COST.md`,
section 30 here and Roadmap P0.1 progress. No application changes or migration IDs.
Starting changes in Agents.md, Roadmap, Playbook, Business Model and the untracked
S04 ADR were preserved; only the current P0.1 progress paragraph was intentionally
updated. Target ownership/current-schema references remain unchanged.

**Resume invariants:** accepted budget versions pin approved Estimate revisions and
mapped source lines; current estimate pointers and approval alone never rebaseline.
Commercial BOQ/Billing ProjectBaseline, internal estimate and cost budget are
different facts. Project Controls owns cost classification/projections; financial
owners remain as in accepted D02 and the proposed S04 contract. Commitments,
accruals/actuals, forecasts and cash remain distinct; invoice replacement and
classification changes preserve lineage without double counting. Manual Project
fields are retained until an approved, reconciled transition and separate removal
approval. Detailed rules and examples stay in the ADR.

**Validation/limits:** local links/anchors, source/test-symbol checks, four Decimal
walkthroughs, session-diff preservation and whitespace checks. No runtime or
professional accounting/legal validation occurred. Q01/Q02/Q04 and detailed budget,
allocation, recognition/WIP, forecast and migration policies remain open; carry
all other section 28 rows, including D01/D03-D05/Q03, to their existing gates.
Passing static checks do not prove concurrency, permissions or financial runtime.

**Next:** P0-S06, separate and not executed here. Recommended bounded continuation
within P0.1: effective-dated regulatory configuration versus contract commercial
terms and tenant billing settings (PPC-01/PPC-06). Minimum context: this handoff,
section 28 open inputs, Roadmap P0.1/P1.2, S01 finding 1, and the S04/S05 source-
snapshot/recognition gates. First define its card, then inspect only BillingPolicy,
policy update/snapshot and claim creation/recalculation symbols plus relevant
ownership rules and tests. Prepare a proposal preserving approved claim snapshots;
do not implement settings/contract/regulatory packages or certify legal rates.
Existing Q01/Q02 and professional-review gates apply; no new acceptance is implied
by this suggested sequence.

## 31. P0-S06 Regulatory and commercial policy ADR proposal and S07 handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner: "continue and do S06".
Execute section 30's handoff within P0.1/PPC-01/PPC-06; prepare a proposal, not
application changes or certification of legal rules.

| Card | Contract |
| --- | --- |
| Goal / scope | Separate tenant billing settings, versioned contract terms and effective-dated regulatory configuration; define resolution, snapshots, correction and legacy containment. |
| Excluded | Implementing P1.2/P6.3, choosing legal rates/providers, accepting ADRs, changing claim history or executing S07. |
| C0/C1 | Section 30 handoff; section 28 gates; Roadmap P0.1/P1.2; S01 finding 1; relevant Domain/Data/Billing references; BillingPolicy, snapshot/update, claim creation/recalculation/revision and direct tests. |
| C2 triggers | Stored policy fields differ from calculation behavior, or snapshot/revision/migration lineage is ambiguous; inspect only the affected consumer/history. |
| Files | New `docs/architecture/ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md`; this record/handoff; Roadmap P0.1 progress. |
| Model policy | A-H: financial history, effective dates and cross-domain ownership; no agents or broad audit. |
| Acceptance / validation | Complete field ownership map, deterministic version selection, history/tenant safeguards, correction sequence, worked cases and open gates; static source/link/preservation/whitespace checks. |
| Stop / closeout | Proposal prepared and validated; preserve unresolved choices and synchronize Roadmap. No package completion or implementation approval. |

### S06 outcome and verification

Prepared [ADR P0-S06](architecture/ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md): all
14 policy fields have proposed owners; effective-version resolution, snapshot
contents, lifecycle/authorization, cumulative-cap concurrency and migration gates
are explicit. The current calculation uses gross despite stored basis choices;
partial/late flags have no consuming Billing Python branch. This triggered narrow
C2 inspection of field references, claim revision/return paths and migration 0003.
Existing results are preserved; unsupported options are future acceptance gaps.

Initial validation passed: 12 links/anchors, 14-field coverage, six service symbols,
Decimal legacy/cap examples and preservation of pre-session content. Relevant test
bodies were inspected, not executed. No application/configuration/schema changes,
database operations, external legal research, dependency changes or remote actions.

**S06 onward calibration (section 25):** S01-S05 delivered bounded planning
artifacts; S05 recorded 7.7 minutes from snapshot through static checks, excluding
initial reads. Comparable complete durations, token totals, defect rates and
decision-latency measurements are unavailable; no aggregate or implementation-time
estimate is inferred. Keep the 22-session P0 envelope and phase table unchanged.
Continue one scoped proposal per authorized session, concise English, direct code
evidence and static checks. Professional review/decision latency remains open;
planning speed is not evidence of implementation or release readiness.

Documentation closeout adds this ADR/session record and updates Roadmap P0.1 only.
Domain/Data/Billing references already distinguish these owners and preserve
snapshots; no accepted target or implemented behavior changed. Prior S04/S05 ADRs,
historical audit, business decisions, parent statuses and dependencies remain intact.
Section 28's open inputs retain their gates. S06 preparation is complete; the ADR
is proposed and PPC-01/PPC-06/P0.1 remain incomplete.

Final validation passed: 20 links/anchors, three additional test-symbol references,
session-only preservation and whitespace checks. Measured elapsed time from the
evidence snapshot through final validation: 5.8 minutes, excluding initial reads.

### Compact P0-S07 handoff

**Outcome:** P0-S06 prepared the regulatory/contract/tenant-policy ADR under
P0.1/PPC-01/PPC-06. User authorization was "continue and do S06". Preparation
criteria are met; this does not accept S04-S06 ADRs, certify rules, authorize
implementation or complete their parent work packages.

**Files:** new `docs/architecture/ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md`, section
31 here and Roadmap P0.1 progress. No migration IDs or application changes.
Pre-existing edits in Agents.md, Roadmap, Playbook and Business Model, plus the
untracked S04/S05 ADRs, were preserved except the intended current progress update.

**Invariants:** resolve tenant settings, accepted commercial terms and reviewed
regulatory versions into an explicit package. Existing draft recalculation uses
its saved policy; revisions retain original policy unless an explicit reviewed
correction changes it. Finalized/submitted evidence stays immutable. Legacy
tax/insurance basis metadata is not proof that the calculation used that basis;
partial/late flags are not currently consumed in the inspected Billing Python.
Legacy caps are per calculation; cumulative meaning requires a separate accepted
policy and concurrency control. Never migrate current rates as reviewed law or
signed contract terms. Detailed findings and correction rules remain in the ADR.

**Validation/limits:** static links, complete field mapping, service/test references,
worked arithmetic, preservation and whitespace checks; no runtime, legal or
professional accounting validation. Q01/Q02/Q04, applicability dates, basis/order,
insurance classification, cap meaning and retroactive correction remain open.
Carry the entire section 28 register, including D01/D03-D05/Q03, to its original
gates. Section 31 records the limited post-S05 calibration; do not infer measured
token savings or implementation estimates from planning-session duration.

**Next:** P0-S07, separate and not executed here. Recommended P0.1 continuation:
project/site authorization and its intersection with tenant permissions/workflow
(PPC-04). Start with this handoff, S01 finding 4, Q04, Roadmap P0.1/P1.1 and the
financial ADR access constraints. Define the card, then inspect only active-tenant
resolution, authorization, project/site selectors and workflow actor/candidate
checks with direct tests. Prepare explicit scope/privileged-path options while
preserving current behavior; do not implement P1.1 or invent owner/support exceptions.

## 32. P0-S07 Project/site authorization ADR proposal and handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner requested execution of
P0-S07, starting with section 31 and current Roadmap, to prepare the authorization
ADR only, preserve behavior, avoid P1.1 and invented privileged/support exceptions,
update affected documentation and run proportionate static validation.

| Card | Contract |
| --- | --- |
| Goal / scope | P0.1/PPC-04 proposal for project/site scope intersected with tenant permissions and workflow authority. |
| Excluded | Runtime/schema/grant changes, P1.1 implementation, accepted privileged/support exceptions, ADR acceptance or parent-package completion. |
| C0/C1 | Section 31 handoff; current Roadmap P0.1/P1.1; S01 finding 4 and section 28 Q04; permission matrix and S04-S06 access constraints; tenant resolution, authorization helpers, project/site selectors, workflow actor/candidate checks and direct tests. |
| C2 trigger / response | Differing superuser and claim/completion behavior required narrow runtime/workbench and direct-test inspection; no endpoint-wide audit. |
| Files | New `architecture/ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md`; this session record; Roadmap P0.1 progress; permission-matrix proposal cross-reference. |
| Model policy | A-H authorization reasoning; no agents, broad repository audit or external research. |
| Acceptance / validation | Distinguish current/target, explicit scope alternatives and privileged gates, workflow/revocation intersection, compatibility sequence and negative cases; static link/source-reference, preservation and whitespace checks. |
| Stop / closeout | Proposal prepared and checked; Q04 unresolved, no implementation authorization; parent statuses/dependencies preserved. |

### S07 outcome and verification

Prepared [ADR P0-S07](architecture/ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md).
Current permission helpers allow active superusers without membership; workbench
and runtime require membership, and completion checks the role's domain permission.
Project/site selectors constrain tenants/parents but do not implement per-user
grants. An inspected test distinguishes permitted claim from denied completion
without domain permission and denies an owner who is not a candidate. These are
bounded findings, not certification of every privileged path or endpoint.

The proposal defines membership-linked scope alternatives, hierarchy and mixed
record handling, query/service enforcement, workflow eligibility/rechecks,
revocation serialization, grant history and migration gates. Owner, privileged,
support, fallback and separation choices remain open under Q04. No exception was
invented or accepted. No application/configuration/schema changes, migrations,
database operations, packages, branches, commits or remote actions were performed.

Static validation passed: 28 local Markdown links/anchors, 19 source/test symbols,
10 design cases, preservation of all three edited pre-existing documents and
whitespace checks (including the untracked ADR). An initial symbol checker
misattributed runtime `_check_sod` to routing; an explicit file/symbol map corrected
the checker and passed. Test bodies were read, not executed; no Django/Ruff/full-suite run is
needed for this documentation-only change. This is not runtime/security approval.

Documentation closeout updates Roadmap P0.1 progress and links the proposal from
the permission matrix. Domain/Data and financial ADRs already state the applicable
target intersections; no accepted policy/ownership changed, so they need no rewrite.
P0/P0.1/PPC-04 remain incomplete; P1.1 remains PLANNED. Section 28's entire open
register and prior ADR acceptance gates remain unchanged. No budget recalibration
or measured implementation/token-efficiency claim follows from this session.

### Compact continuation handoff

**Outcome/acceptance:** S07 preparation is complete within the explicit Product
Owner instruction above. The new authorization ADR is PROPOSED. It does not accept
S04-S07, resolve Q04, freeze the release contract or authorize implementation.

**Artifacts:** the S07 ADR, Roadmap P0.1 progress, this section and the permission
matrix cross-reference. No migration identifiers. Pre-existing edits in Agents.md,
Roadmap, Playbook and Business Model and untracked S04-S06 ADRs remain preserved;
only the intended progress replacement/appended record changes earlier working
documents. No code was modified.

**Invariants:** tenant isolation, capability, object scope and domain validity are
independent checks. Workflow assignment/position/delegation never grants a business
permission. Proposed grants are explicit; missing scope is not unrestricted.
Scope revocation must be rechecked at action time without rewriting completed
history. Mixed-project actions require complete authority; sensitive source access
is separately checked. Current helper, workbench and runtime privileged differences
are recorded rather than changed. Q04 must decide grants/inheritance, owner and
superuser disposition, support/emergency paths, separation and eligible fallback.
Do not treat proposal options as accepted exceptions or backfill policy.

**Validation/limits:** static links/anchors, source symbols, design-case coverage,
preservation and whitespace only; relevant test bodies inspected but not run.
No endpoint-wide audit, runtime/concurrency/performance certification or database
validation. P1.1's negative, migration and race tests remain future acceptance work.
Carry D01/D03-D05/Q01-Q04 from section 28 to their existing gates; support-access
jurisdiction also depends on D03, and retention/export on Q03/D05. Financial ADR
access constraints remain intact.

**Next:** P0-S08 is the next session label, not executed or authorized here. Confirm
its bounded P0.1 ADR topic from current Roadmap with the Product Owner before
implementation planning. Minimum context is this handoff, Roadmap P0.1 and section
28's applicable gates; load only the selected boundary's references/direct evidence.
If continuing authorization review, use the S07 ADR's Q04 choices and acceptance
cases first. Session preparation does not complete P0.1/PPC-04 or permit P1.1.

## 33. P0-S08 Private document storage ADR proposal and S09 handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner: “Continue and do S08”.
Selected private storage as the next listed P0.1 ADR topic after authorization;
this is proposal preparation, not implementation planning or ADR acceptance.

| Card | Contract |
| --- | --- |
| Goal / scope | P0.1/PPC-05 storage proposal: private bytes, upload quarantine/availability, retention/hold/export, migration and recovery boundaries. |
| Excluded | Provider/location selection, dependencies, runtime/schema/configuration changes, data movement, async/scanning implementation, P0.2/P0.3/P1.3 execution, DMS link replacement or privileged exceptions. |
| C0/C1 | Section 32 handoff; Roadmap P0.1/P0.2/P0.3/P1.3; audit ADR order; section 28 D03-D05/Q03/Q04; Data Model evidence ownership; current document models/services/views, storage settings and direct tests. |
| C2 trigger / response | Latest-version compatibility, raw media serving and legacy lineage required narrow reads of Document.clean, URLs and migration 0004; no deployment or broad security audit. |
| Files | New `architecture/ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md`; this record/handoff; Roadmap P0.1 progress. |
| Model policy | A-H storage integrity/authorization reasoning; no agents, provider research or package evaluation beyond the reuse boundary. |
| Acceptance / validation | Evidence-grounded current/target distinction; failure/availability contract; holds/export and recovery safeguards; open policy gates and static design cases. Check local links/anchors, referenced symbols, preservation and whitespace. |
| Stop / closeout | Proposed ADR prepared and statically checked; parent packages and all unresolved decisions retain their status. |

### S08 outcome and verification

Prepared [ADR P0-S08](architecture/ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md).
Current document services validate size/MIME/prefix and hash bytes, retain versions,
check all linked contexts and audit downloads. They do not establish malware safety
or production object-storage privacy. Current-version validation requires latest
identity; the proposal separates it from delivery eligibility, with an alternative
staging design explicitly left for acceptance. Debug media serving and migration
0004's model replacement without a data-copy operation are recorded as bounded
compatibility findings, not proof of production exposure or historical data loss.

The proposal covers private storage and delivery alternatives, failure-closed
quarantine, DB/blob reconciliation, retention/hold/disposal races, complete scoped
exports and coherent recovery. D03 provider/residency/operator, D04 recovery,
D05 quota/lifecycle and Q03 evidence obligations remain open; Q04 still gates
scope and privileged decisions. No duration, provider, legal effect, support
exception or implementation approval is inferred.

Static validation passed: 24 local links/anchors, 13 source symbols, seven test
symbols, ten design cases, preservation of both edited pre-existing documents,
seven unchanged pre-existing file hashes and whitespace checks including the new
ADR. Test bodies were inspected, not run. No Django/Ruff/full-suite or database checks are appropriate to this
documentation-only change; no runtime/security/recovery certification is claimed.

Documentation closeout changes Roadmap P0.1 progress and adds this record and ADR.
Domain/Data already define the shared blob/version authority; their accepted target
is unchanged. The historical audit, prior ADRs, permission matrix, P0.2/P0.3/P1.3
statuses and decision gates need no rewrite. PPC-05/P0.1 remain incomplete, and
PPC-10 is not closed by discussing existing links. No runtime/config/schema,
dependency, migration, data, branch, commit or remote changes were made.

### Compact P0-S09 handoff

**Outcome/acceptance:** S08 preparation is complete under “Continue and do S08”.
The private-storage ADR is PROPOSED, alongside S04-S07. It does not accept policy,
freeze the release contract, certify retention law or authorize implementation.

**Artifacts/worktree:** the S08 ADR, Roadmap P0.1 progress and section 33 here.
No migration identifiers. Preserve all pre-existing edits in Agents.md, Roadmap,
Playbook, Business Model and permission matrix, plus the untracked S04-S07 ADRs.
Only this session's progress replacement and appended record alter earlier files.

**Invariants:** one version/blob authority; private storage policy rather than key
secrecy; authorization across every linked context; no unscanned-byte delivery or
silent old-version substitution; immutable original bytes and processing evidence.
Database and storage outcomes need explicit reconciliation. Retention expiry,
cancellation and quota never override a hold. Export completeness and authorization
are rechecked; backups, keys, DB metadata and byte manifests form one recovery
boundary. Current latest-version rules and migration 0004's missing data-copy step
require environment-specific compatibility evidence before future migration.

**Validation/limits:** static links, source/test symbols, ten design cases,
preservation and whitespace; direct test bodies inspected, no tests executed.
Production ingress/bucket configuration, historical environment data, scan vendors,
restore timing and legal retention were not audited. Keep D01/D03-D05/Q01-Q04 at
their section 28 gates; no new provider, duration, quota or authority was selected.

**Next:** recommend P0-S09 within P0.1/PPC-10: extensible explicit DMS cross-domain
links without GenericForeignKey. Not executed here; a continuation request may
authorize preparation, not P1.3 implementation. Start with this handoff, Roadmap
P0.1/P1.3, S08 ownership/compatibility rules and S07 scope constraints. Define the
card, then inspect DocumentLink, its target registry/services/forms, direct tests
and only consumers needed to resolve a concrete link/permission/history ambiguity.
Prepare alternatives and a preservation/migration contract; do not replace the
six-target schema, relax all-linked-context authorization or invent support access.
Async/outbox and tenant lifecycle/support ADRs remain subsequent separate topics.

## 34. P0-S09 DMS domain-link ADR proposal and S10 handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner: “continue and do S09”.
Execute section 33's bounded P0.1/PPC-10 proposal preparation; no P1.3 implementation.

| Card | Contract |
| --- | --- |
| Goal / scope | Explicit extensible domain-link ownership, registry alternatives, authorization/version/history invariants and migration acceptance. |
| Excluded | Replacing the six-target schema, GenericForeignKey, relaxing all-context checks, new support/privileged paths, P1.3 implementation, storage/async work or ADR acceptance. |
| C0/C1 | Section 33 handoff; Roadmap P0.1/P1.3; S07 scope/S08 storage boundaries; Data Model evidence ownership; DocumentLink, target maps/services/forms and direct tests. |
| C2 trigger / response | Link immutability claim and list/detail parity required narrow model/Django Admin/list/template inspection; no broad endpoint audit. |
| Files | New `architecture/ADR_P0_S09_DMS_DOMAIN_LINKS.md`; this session record; Roadmap progress; targeted current-enforcement qualifications in Domain and Data Model and permission matrix. |
| Model policy | A-H domain/authorization/history reasoning; no agents or external research. |
| Acceptance / validation | Explicit alternatives/recommendation, six-target preservation, all-context authority, pinned evidence/correction contract, expand/migrate/switch/rollback gates and negative cases; static links/symbols/map coverage/preservation/whitespace. |
| Stop / closeout | Proposed ADR prepared and checked; PPC-10/P0.1/P1.3 remain incomplete, Q03/Q04 and prior ADR acceptance gates stay open. |

### S09 outcome and verification

Prepared [ADR P0-S09](architecture/ADR_P0_S09_DMS_DOMAIN_LINKS.md), recommending
domain-owned typed FK tables coordinated by a closed platform registry, pending
acceptance. The registry is not generic foreign-key dispatch and cannot omit
unknown/retired links to widen access. Legacy links remain document associations,
not fabricated approval of a file version. Proposed corrections preserve history
and cannot automatically remove restrictive contexts from authorization.

Current six-target constraints, maps, forms, services and tests support the bounded
evidence. Model/Django Admin review qualifies a current gap: DocumentLink validates saves
but lacks the existing-row update guard used for versions. List filtering checks
target-type permissions but does not mirror the detail validator's deleted-project
check. These remain explicit future acceptance gaps, not runtime fixes or a claim
that comprehensive object authorization is implemented.

Static validation passed: 28 local links/anchors, ten source and five test symbols,
all six targets across five maps, ten design cases, preservation checks for four
edited documents, seven unchanged pre-existing file hashes and whitespace including
the new ADR. Direct test bodies were read, not executed. No Django/Ruff/full-suite/database run is warranted
by this documentation-only change; no runtime/concurrency/query certification.

Documentation closeout updates Roadmap P0.1, adds the ADR/session record and narrowly
qualifies the delivered link-immutability description in Domain and Data Model and
the permission matrix. Target Domain/Data ownership already supports this direction
and requires no rewrite. Historical audit and S04-S08 ADRs remain intact. Parent
statuses, dependencies and section 28's open register remain unchanged. No code,
schema/configuration, migrations, dependencies, data, branch, commit or remote
changes were made; no implementation or token-efficiency estimate is inferred.

### Compact P0-S10 handoff

**Outcome/acceptance:** S09 proposal preparation is complete under “continue and do
S09”. The DMS link ADR remains PROPOSED, as do S04-S08. No acceptance of the typed
schema, permission policy, corrected-link access release or P1.3 implementation
is implied. PPC-10/P0.1 remain incomplete and the release contract is not frozen.

**Artifacts/worktree:** new S09 ADR, Roadmap P0.1 progress, section 34 and two narrow
current-enforcement qualifications in Domain and Data Model/permission matrix.
No migration identifiers. Pre-existing changes in Agents.md, Roadmap, Playbook,
Business Model and permission matrix, plus untracked S04-S08 ADRs, are preserved
outside these intended edits. Models, services, forms and tests remain unchanged.

**Invariants:** explicit typed FKs, one document/version authority and complete
registered-link enumeration. All linked contexts govern access; neither an allowed
link nor an unknown/retired adapter may bypass a restriction. Preserve same-tenant
multi-project legacy links without silent reparenting; each action still needs all
applicable authority. Existing document-only links do not identify approved bytes.
Pin future finalized evidence explicitly under its domain contract. Corrections
retain history and require a separately accepted access-release policy before
dropping a restrictive context. Schema transitions retain stable mapping, audit,
all link types and rollback coverage. Known model-update and list/detail gaps are
future scoped corrections, not fixed or certified here.

**Validation/limits:** static links/anchors, symbols, six-target map coverage,
design cases, preservation and whitespace; direct tests inspected but not run.
No complete endpoint/bulk-write audit, DB migration, concurrency or performance
validation. Retain section 28's entire D01/D03-D05/Q01-Q04 register; Q03/Q04 gate
evidence/correction/scope semantics and S08 retains storage/recovery/lifecycle gates.

**Next:** recommend P0-S10 within P0.1: async job/outbox/idempotency boundaries for
integrations and notifications, the next listed ADR topic. Not executed here;
continuation authorizes proposal preparation, not Celery/Redis, providers or jobs.
Start with this handoff, Roadmap P0.1 and the affected delivery packages; use S08's
scan/storage failure contract and existing synchronous workflow/audit/idempotency
evidence only where needed. Define the card, inspect actual transaction/side-effect
boundaries, and distinguish durable job delivery from domain/work-item authority.
Audit must remain evidence, not a notification bus. Tenant lifecycle/support and
future network privacy remain separate topics; invent no privileged exceptions.

## 35. P0-S10 Async/outbox ADR proposal and S11 handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner: “continue and do S10”.
The subsequent “continue” steered completion of this active session. Execute section
34's bounded P0.1 proposal preparation; no worker, integration or notification rollout.

| Card | Contract |
| --- | --- |
| Goal / scope | Async job/outbox/idempotency boundaries: atomic intent, separate delivery state, retry/uncertainty, authority and recovery contracts. |
| Excluded | Celery/Redis/broker/provider selection or installation, jobs/schedulers/channels, P0.2/P1.3/P6.3/P9.4 implementation, changing synchronous workflows/callbacks or inventing worker/support exceptions. |
| C0/C1 | Section 34 handoff; Roadmap P0.1 and affected delivery packages; S08 storage failure/scan contract; workflow completion/models/direct tests; audit service/models/tests; current side-effect/dependency search. |
| C2 trigger / response | Found on_commit setup/image-cleanup callbacks and local key short-circuit; read their callers and completion branch to distinguish post-commit timing, local idempotency and durable delivery. |
| Files | New `architecture/ADR_P0_S10_ASYNC_OUTBOX_IDEMPOTENCY.md`; Roadmap P0.1 progress; this record/handoff. |
| Model policy | A-H transaction, authority and external-failure reasoning; no agents, external provider research or broad audit. |
| Acceptance / validation | Evidence-grounded current/target distinction; ownership/options, durable-intent contract, payload/key/retry/ordering policy, authority gates, recovery/rollout and negative cases; static link/symbol/preservation/whitespace checks. |
| Stop / closeout | Proposed ADR prepared and checked; P0.1 and consuming packages stay incomplete, no prior ADR or unresolved policy is accepted. |

### S10 outcome and verification

Prepared [ADR P0-S10](architecture/ADR_P0_S10_ASYNC_OUTBOX_IDEMPOTENCY.md).
Current workflow commands run synchronously within completion transactions; direct
tests cover sample-command rollback and repeated completion. Audit persists
append-only evidence at the application boundary. Post-commit starter-workflow and
image-cleanup callbacks are not durable pending-work records. These findings do
not certify deployed infrastructure or every external side effect.

The proposal recommends domain-owned delivery contracts with platform-owned
transactional intent and separately approved transport. It distinguishes business
approval, dispatch, provider receipt and business acceptance; defines same-key
payload conflicts, duplicate delivery, lease limits, ordering and uncertain-outcome
reconciliation; and requires recovery to account for external effects after a DB
restore. Background authority, recipient visibility and tenant lifecycle remain
explicit gates, with no synthetic membership or superuser default. Existing
callbacks and workflows are unchanged.

Static validation passed: 33 local links/anchors, ten source and three test symbols,
ten design cases, preservation of both edited pre-existing documents, ten unchanged
pre-existing file hashes and whitespace including the new ADR. A duplicated-root
path label in the temporary hash checker was corrected before the successful run.
Relevant test bodies were inspected, not executed. No Django/Ruff/full-suite/database run is needed for this
documentation-only change; no broker/provider, concurrency or restore certification.

Documentation closeout adds this ADR/session record and updates Roadmap P0.1 only.
Workflow, Domain/Data and S08 references already separate domain/work-item/audit
authority and storage recovery; their accepted target/current behavior did not
change. Prior ADRs, existing qualifications and historical audit remain intact.
Section 28's open inputs retain their gates, and P6.3 remains legally gated.
No code/config/schema, dependency, migration, data, branch, commit or remote action
was performed. P0.1 and affected delivery packages remain incomplete.

### Compact P0-S11 handoff

**Outcome/acceptance:** S10 proposal preparation is complete under “continue and do
S10”; the follow-up “continue” completed this session. The ADR remains PROPOSED,
alongside S04-S09. No runtime queue, channel, provider, job authority, SLA or replay
policy is accepted. The release contract and P0/P0.1 remain incomplete.

**Artifacts/worktree:** new S10 ADR, Roadmap P0.1 progress and section 35 here.
No migration identifiers. Preserve pre-existing edits in Agents.md, Roadmap,
Playbook, Business Model, Domain and Data Model and permission matrix, plus
untracked S04-S09 ADRs. Only the intended progress replacement and appended record
alter earlier files; application behavior remains synchronous and unchanged.

**Invariants:** domain transition/work-item/audit remain atomic and authoritative.
Future outbox intent joins the source transaction; external I/O and attempt state
are separate. Audit is neither a queue nor notification store. Post-commit callbacks
do not supply durable recovery. Reuse stable tenant/operation/source/destination
identity, reject changed payload under the same key, and reconcile uncertain
external acceptance rather than resubmitting blindly. No exactly-once external
guarantee follows from an outbox or lease. Restores pause dispatch until receipts
and deduplication keys are reconciled. Notifications never act on WorkItems.

**Validation/limits:** static links/anchors, source/test references, ten design
cases, preservation and whitespace; direct tests inspected but not run. No deployed
infrastructure, full side-effect inventory, worker crashes, provider protocols,
performance or recovery exercise was validated. D01/D03-D05/Q01-Q04 from section 28
retain original gates. Q02 gates statutory delivery; Q03 evidence retention; Q04
execution authority. Channel/provider/dependency decisions need separate approval.

**Next:** recommend P0-S11 within P0.1: tenant lifecycle, subscription/entitlements,
quotas, offboarding and support-access boundaries. Not executed here; continuation
may authorize ADR preparation, not P0.3 implementation or privileged exceptions.
Start with this handoff, Roadmap P0.1/P0.3, section 28's D05 approved direction and
open D03-D05/Q03/Q04 parameters, S07 privileged-path evidence and S08/S10 retention,
export and pending-obligation boundaries. Define the card, then inspect current
organization states, membership/session access and lifecycle services/direct tests.
Preserve existing behavior; do not invent limit values, cancellation/retention
durations, support grants or background authority. Network privacy remains a later
separate topic, and every implementation package still needs explicit authorization.

## 36. P0-S11 Tenant lifecycle ADR proposal and S12 handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner explicitly requested
“Execute P0-S11” and tenant lifecycle, subscription/entitlements, quotas,
offboarding and support-access ADR preparation within P0.1/P0.3 only.

### Session card and result

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Prepare the P0.1 tenant lifecycle/support ADR informing P0.3; preserve current behavior and all existing worktree changes. |
| Excluded | P0.3 implementation, schema/dependencies, invented limits/durations/support grants/privileged exceptions/background authority; future-network privacy remains separate. |
| C0/C1 | Section 35 compact S11 handoff; current Roadmap P0.1/P0.3 and decision register; section 28 D05 direction and open inputs; S07/S08/S10 contracts; Organizations models/services/authorization/middleware and direct test bodies; relevant Business/Data/Domain and permission references. |
| C2 trigger / expansion | Current active-only access versus target lawful inactive-Tenant export required narrow Django Admin/archive-migration inspection to distinguish state markers from transition/disposal services. No endpoint-wide audit, deployment inspection or legal research. |
| Files | New `architecture/ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md`; Roadmap P0.1 progress and P0.3 proposal reference; this record/handoff and session-map calibration note; permission-matrix proposal reference. |
| Validation | Local links/anchors, cited symbols/test names, status/open-gate consistency, static design cases, whitespace and session-baseline preservation. No application tests or Django checks for documentation-only changes. |
| Open inputs | D03/D04 operating/recovery parameters; D05 metric/commercial/lifecycle values; Q03 retention/hold/export; Q04 privileged/support/separation and operation authority. All other S03 gates persist. |
| Stop / closeout | Proposal prepared and statically checked; P0/P0.1/P0.3 remain incomplete, no ADR acceptance or implementation authorization. Next session is separate. |

Prepared the [S11 ADR](architecture/ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md).
The inspection confirms that existing tenant state/active guards and membership
services do not deliver P0.3. Suspended/cancelled tenants are excluded from ordinary
selection and shared permission helpers; there is no inspected controlled export
path for them. Superuser service access remains different from the membership-
required workflow paths recorded in S07; none is promoted to support authority.

The proposal separates tenant state, commercial phase, entitlement assignment,
capacity and retention disposition. It develops D05 without selecting values:
effective policy history, transactional admission/reservations, traceable usage,
protected existing work/history/export, offboarding manifests, hold/disposal and
support-control choices. Operations that append history/bytes while completing
existing work need explicit D05 accounting before cap enforcement. S08 and S10
remain authoritative proposals for storage and pending delivery; cancellation
neither erases a committed obligation nor grants execution authority.

### Validation and documentation closeout

Static validation passed: 18 local Markdown links/anchors in the new/changed S11
blocks, 25 cited source/test symbols (including 12 test names), thirteen reviewed
design cases and unchanged parent/decision gates. Whitespace/encoding checks and
targeted `git diff --check` passed; Git emitted only existing LF/CRLF conversion
notices. Preservation checks against a pre-edit worktree baseline confirmed 4,108
files outside the three intentionally edited documents byte-for-byte unchanged,
with only the S11 ADR added. Earlier Playbook records remain intact; Roadmap edits are
limited to P0.1/P0.3; the permission-matrix edit is an inserted proposal reference;
pre-existing user changes and S04-S10 ADRs are retained. Whitespace checks include
the untracked S11 ADR. Direct tests were inspected, not run. No Django check,
database migration, runtime/load/recovery exercise or commercial/legal validation
was performed.

Closeout updates only the four files named in the card. The Business Model already
records accepted D05 and unresolved values; target Domain/Data documents already
label entitlements/support/offboarding as future. They need no directional or
implemented-status rewrite. The historical audit, operations/UI standards and
prior ADRs remain unchanged. Roadmap P0.3 stays PLANNED, P0.1 stays NEXT-CANDIDATE;
P0/P0.1 are not complete and the release contract is not frozen. The calibration
note prevents the original S12 session-number estimate from implying authorization.

### Compact P0-S12 handoff

**Outcome/acceptance:** P0-S11 proposal preparation is complete under the explicit
“Execute P0-S11” request. The ADR remains PROPOSED, alongside S04-S10. D05's one
core plan/external subscription administration is accepted direction; metric values,
commercial phases, transition authority and operating policies remain unresolved.
No P0.3 implementation, support grant, privileged exception or background authority
is approved. P0/P0.1 and the release contract remain incomplete.

**Artifacts/worktree:** the S11 ADR, Roadmap P0.1/P0.3 planning notes, section 36
and the section 6 calibration note here, plus one permission-matrix cross-reference.
No application/configuration/dependency edits or migration identifiers. Preserve
existing changes in Agents.md, Roadmap, Playbook, Business Model, Domain and Data
Model and permission matrix, plus untracked S04-S10 and now S11 ADRs. Earlier
session records remain historical; only current progress and narrow additions
changed in this session.

**Invariants:** ordinary current access requires an active tenant. The future
inactive-tenant export/control path needs explicit accepted authority; owner,
superuser, support ticket and worker credential are not new grants. Entitlements
never replace membership/permission/object/workflow checks. Quotas require defined
metrics, serialized admission, idempotent reservations and source reconciliation;
resolve capacity treatment for protected completions before implementation.
Cancellation does not delete history, release holds, discharge liabilities or
authorize pending delivery. S08 governs byte integrity/export/disposal; S10 requires
operation-specific authority and reconciliation of uncertain effects. Offboarding
one tenant must preserve unrelated memberships/global User identity.

**Validation/limits:** documentation static checks cover links/anchors, source/test
references, thirteen design walkthroughs, whitespace and preservation. Tests were
read, not executed. No live offboarding, quota race, support grant, recovery,
infrastructure or legal/commercial assurance follows. D03/D04 still gate provider,
residency/operator and recovery commitments; D05 gates metric definitions/values,
trial/grace/cancellation and commercial terms; Q03/Q04 gate evidence/retention/export
and privilege/separation. Carry D01/Q01/Q02 and every other section 28 input to its
original gate. No numerical parameter or approving actor was inferred.

**Next:** recommend P0-S12 as a separate bounded P0.1 future-network privacy ADR
preparation session, not network implementation or P0.2/P0.3 rollout. Await explicit
session authorization. Minimum context: this handoff, Roadmap P0.1 and deferred
network trigger, section 28 open inputs, Domain/Data/Business Model target network
boundaries, and S07/S08/S11 scope, retention and support constraints. First define
the session card and verify only direct tenant/shared-data boundary evidence needed
for that proposal. Keep tenant-private transactions/evaluations private by default;
do not infer consent, cross-tenant grants, shared claims or a network launch. If
the Product Owner instead resolves lifecycle inputs, use S11 section 7 as the
bounded decision packet before any separately authorized implementation slice.

## 37. P0-S12 Future-network privacy ADR proposal and handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner explicitly requested
“Execute P0-S12” and a separate future-network privacy ADR within P0.1 planning
scope only.

### Session card and result

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Prepare the P0.1 future-network privacy proposal; define ownership/control, consent, sharing, revocation, provenance, cross-tenant isolation, retention, support and acceptance boundaries while preserving current behavior and worktree changes. |
| Excluded | Network/P0.2/P0.3 implementation, schema/dependencies, launch activation, consent terms, shared claims, partner grants, retention periods, privileged exceptions or background authority. |
| C0/C1 | Section 36 compact handoff; current Roadmap P0.1/deferred trigger and section 28 open inputs; Domain/Data/Business target boundaries; S07/S08/S11 proposals; tenant party/document/membership evidence and direct negative-test names. |
| C2 trigger / expansion | No expansion was required. Direct evidence established tenant-local party/document ownership and absence of network runtime; no endpoint-wide privacy audit, infrastructure inspection or external legal research was justified. |
| Files | New `architecture/ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md`; narrow proposal references in Domain/Data/Business Model; Roadmap P0.1 progress; this record/handoff. |
| Validation | Local Markdown links/anchors, cited code/test symbols, status/open-gate consistency, static design cases, whitespace and targeted diff review. No application tests or Django checks for documentation-only changes. |
| Open inputs | Network purpose/business model; participant/subject identity and consenting authority/terms; claim/relationship verification; moderation/fraud/appeal; reputation/aggregation/privacy/competition controls; D03/D04 data placement/recovery; Q03 retention/export; Q04 permissions/support/separation; S11 lifecycle interaction. |
| Stop / closeout | Stop after proposed ADR, static validation and documentation closeout. P0/P0.1 remain incomplete; network stays deferred; no prior ADR acceptance or implementation authorization. |

Prepared the [S12 ADR](architecture/ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md).
Current `BusinessParty`, contact and document authorities remain organization-owned,
and current services/tests deny relevant cross-tenant operations. No network claim,
relationship, publication-consent, discovery or recommendation runtime was found.
The proposal therefore uses a separate future platform-publication boundary rather
than treating matching tenant masters, bilateral portal activity or existing
transactions as network identity or consent.

The proposal keeps transactions, evaluations, documents, contacts, identities and
operational data tenant-private by default. It separates publication from bilateral
sharing; consent from relationship; revocation from disposal; source authority from
platform claim/verification; and support/moderation duties from tenant access. It
adds no terms, roles, grants, durations, claims, thresholds or permissions. Shared
qualification, reputation and anonymous intelligence remain blocked on explicit
identity, provenance, dispute, privacy, competition and re-identification decisions.

### Validation and documentation closeout

Static validation passed: 85 local Markdown file/anchor links across the six S12
documents, ten cited current model/test symbols, thirteen design walkthroughs,
status/open-gate searches and `git diff --check`. Git emitted only existing
LF/CRLF conversion notices. A scoped status check found no application,
configuration, core or dependency-file change. Tests were inspected, not run; no
Django check, runtime privacy test, infrastructure exercise, legal/privacy opinion
or competition review was performed.

Documentation closeout is limited to the new ADR, this session record, Roadmap
P0.1 progress and narrow cross-references in the three source models. Their approved
target direction is unchanged. Current runtime/schema authority, the deferred-
network trigger, P0.2/P0.3 statuses, all S03 gates and S07/S08/S11 proposal status
remain unchanged. Existing worktree entries were retained; no file was reverted,
removed or contracted.

### Compact next handoff

**Outcome/acceptance:** P0-S12 proposal preparation is complete under the explicit
request. The ADR is PROPOSED, not accepted. The controlled B2B network remains
deferred, P0/P0.1 remain incomplete and the release contract is not frozen.

**Invariants:** tenant-local sources remain private and authoritative; matching
identifiers, portal invitations, relationships, transactions, subscription/support
state or public facts do not infer participation or consent. A future platform
claim is separate, purpose/audience/version-bound and revocable. It grants no
membership, tenant/project scope, workflow authority, document access, partner
grant, support path or background authority. Revocation is not retroactive history
rewriting or automatic disposal; retention/hold/export remain policy-gated.

**Open decisions:** Product Owner must first decide whether/when the Roadmap trigger
is met and select a bounded network purpose/business model. Named privacy/legal,
security, party-domain, operations, competition and metric reviewers must resolve
participant/subject identity, consent authority/terms, claim/relationship rules,
moderation/fraud/appeal, reputation/aggregation thresholds, prohibited uses and
operating ownership. D03/D04, Q03, Q04 and S11 lifecycle choices remain at their
existing gates; no value, actor, exception or legal conclusion was inferred.

**Next:** bounded Product Owner review of the nine proposed P0.1 ADRs and unresolved
decision packets. Accept, revise or reject proposals and name decision owners;
do not start network, P0.2 or P0.3 implementation from this handoff. If a single
decision packet is selected, read that ADR's acceptance section plus section 28
and current Roadmap status, then stop at the explicit authorization boundary.

## 38. P0-S13 P0.1 ADR review packet and handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner explicitly requested
“execute P0-S13”. Under section 37's bounded next handoff, this authorizes a
consolidated review/decision packet, not ADR acceptance or implementation.

### Session card and result

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Consolidate S04-S12 proposed directions, acceptance blockers, downstream dependencies, cross-ADR consistency and an explicit Product Owner disposition template. |
| Excluded | Supplying Product Owner choices, accepting/rejecting ADRs, naming people, resolving D03-D05/Q01-Q04, changing runtime/schema/dependencies or authorizing P0.2/P0.3/downstream/network work. |
| C0/C1 | Section 37 handoff; current Roadmap P0.1 and decision register; S03 open inputs; S04-S12 status and acceptance sections; audit PPC/ADR register. |
| C2 trigger / expansion | No source-code or wider architecture expansion was needed: S13 reviews already prepared proposals and current status, not implementation evidence. |
| Files | New `architecture/P0_S13_P01_ADR_REVIEW_PACKET.md`; Roadmap P0.1 planning progress; this record/handoff. |
| Validation | Local links/anchors, all nine ADR statuses/references, decision/PPC traceability, cross-ADR authority review, OPEN disposition preservation, whitespace and scoped status. |
| Stop / closeout | Stop with all nine ADRs PROPOSED and every S13 disposition/owner field OPEN. P0/P0.1 and release contract remain incomplete; no implementation authority. |

Prepared the [S13 review packet](architecture/P0_S13_P01_ADR_REVIEW_PACKET.md).
It separates direction disposition, formal ADR acceptance and implementation
authorization; summarizes each proposal and gate; and groups decisions by the
shared blockers Q04, Q01/Q02, D03/D04, Q03 and D05 before ADR-specific rollout.

The integrated review found no direct authority collision: S04-S06 separate
financial/project-cost/policy ownership; S07 and S11 intersect authorization with
tenant lifecycle; S08 and S09 separate byte/version from domain-link authority;
S10 carries committed intent without granting authority; and S12 creates no route
around tenant privacy. This is conditional on every recorded gate remaining open.

### Validation and documentation closeout

Static validation passed: 81 local Markdown file/anchor links across the three S13
documents, all nine ADR files retained a PROPOSED/not-accepted status, all nine
disposition and owner rows remained OPEN, seven decision clusters retained their
source gates, and `git diff --check` passed. Git emitted only existing LF/CRLF
conversion notices. A scoped status check found no application, configuration,
core or dependency-file change. No application tests or Django checks were run for
this documentation-only consolidation.

Documentation closeout is limited to the new packet, Roadmap P0.1 planning progress
and this session record. Domain, Data, Business, workflow/permission, operational
and UI authorities were checked for material change; none requires a status or
direction rewrite because S13 makes no product decision. Existing worktree changes
were retained; no file was reverted, removed or contracted.

### Compact next handoff

**Outcome/acceptance:** P0-S13 packet preparation is complete. Every S04-S12 ADR
remains PROPOSED; no disposition, owner assignment, parameter, implementation or
release-scope decision was inferred from the execution request.

**Next:** Product Owner supplies explicit dispositions and named accountable
reviewers using the packet. If review is incremental, begin with Q04 because it
blocks S07 and constrains every sensitive downstream path. A separately authorized
session may record the supplied decisions and update affected ADR/Roadmap statuses;
it must not implement P0.2, P0.3 or downstream packages unless separately approved.

## 39. P0-S14 Q04 Product Owner decision packet and handoff

**Recorded:** 2026-09-25. **Authorization:** Product Owner explicitly requested
“Execute P0-S14” and bounded it to the Q04 decision packet. This authorizes decision
preparation and documentation closeout only; it supplies none of the decisions.

### Session card and result

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Prepare clear Q04 options, tradeoffs, recommendations, accountable-review requirements, affected-ADR traceability and latest gates for grants, inheritance/delegation, Tenant Owner/Tenant Admin/Platform Admin/Superuser/support, maker-checker and workflow fallback. |
| Excluded | Product Owner choices, reviewer names, ADR acceptance, P1.1/P0.2/P0.3 implementation, schema, permissions, migrations, dependencies, privileged exceptions or background authority. |
| C0/C1 | Section 38 handoff; current Roadmap P0.1 and decision register; S13 packet; S03 Q04 gate; S07 proposed scope/privileged/workflow clauses; directly affected S04-S12 clauses and workflow/permission policy. |
| C2 trigger / expansion | Narrow cross-ADR inspection was required to map each Q04 choice to its existing acceptance gate; no source-code expansion was needed because current-behavior evidence is already bounded in S07/S11. |
| Files | New `architecture/P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md`; Roadmap P0.1/decision-register references; S13 successor handoff; this record/handoff. |
| Validation | Local Markdown links/anchors, A-H response fields and reviewer names remaining OPEN, affected-ADR/Q04 traceability, prohibited-scope searches, whitespace and scoped status. |
| Stop / closeout | Stop with Q04 OPEN, S04-S12 PROPOSED, P1.1/P0.2/P0.3 unchanged and no runtime authority or behavior changed. |

Prepared the [bounded Q04 packet](architecture/P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md).
It separates eight choices so the Product Owner can accept an option or request a
specific revision without accidentally supplying answers for adjacent decisions.
The recommended direction is explicit membership-linked scope; project-to-site but
not site-to-project inheritance; bounded non-transitive delegation; auditable owner
bootstrap without role bypass; no superuser business authority; no standing support
access with controlled tenant-authorized grants if accepted; protected-action
maker-checker separation; and fallback only after eligibility filtering. These are
recommendations, not recorded decisions.

The packet requires actual named Product Owner, security/authorization,
workflow/control and conditional accounting/operations/privacy/domain review as
applicable. Every selection, rationale, reviewer-name and evidence field remains
OPEN. It maps Q04 primarily to S07 and records the constrained clauses and retained
gates across S04-S06 and S08-S12.

### Validation and documentation closeout

Documentation-only static validation passed for local file/anchor links, Q04 A-H
coverage, all eight OPEN response rows, S04-S12 PROPOSED status preservation,
prohibited implementation/authority claims, whitespace and scoped repository
status. No Django, application or migration tests were run because no executable,
schema, settings or dependency file changed.

Documentation closeout is limited to the new Q04 packet, Roadmap P0.1/decision
register references, the S13 successor handoff and this session record. Existing
architecture authorities remain unchanged because this session selects no policy.
Existing worktree changes were preserved; no file was reverted, removed or
contracted.

### Compact next handoff

**Outcome/acceptance:** P0-S14 packet preparation is complete. Q04 remains OPEN;
all nine P0.1 ADRs remain PROPOSED, P1.1/P0.2/P0.3 remain unimplemented by this
session, and current authorization/workflow behavior remains unchanged.

**Next:** Product Owner supplies explicit choices or revisions for Q04-A through
Q04-H and actual accountable reviewer names. A separately authorized bounded
session may record those supplied answers and review outcomes, then update affected
proposal/Roadmap statuses. It must not infer unanswered defaults, accept an ADR or
begin implementation without separate authority after the applicable gates pass.

## 40. P0-S15 Q04 decision recording and review handoff

**Recorded:** 2026-09-25. **Authorization:** the Product Owner supplied explicit
Q04-A through Q04-H decisions and requested their recording in the Q04 packet and
affected documentation. This authorizes documentation reconciliation only.

**Later Q04-G revision:** section 41 records the final 2026-09-26 Product Owner
decision and supersedes only this section's earlier G3 wording. Other Q04 choices
and this historical execution evidence remain unchanged.

### Session card and result

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Record A1/B1/C1/D1/E1/revised F2/revised G3/H1 exactly; preserve original recommendations and tradeoffs; identify compatibility risks, affected ADRs, remaining reviewers and latest gates. |
| Excluded | Inventing reviewer names/outcomes, accepting ADRs, implementing P1.1/P0.2/P0.3, or adding schema, permissions, migrations, dependencies, privileged mechanisms or background authority. |
| C0/C1 | Section 39 handoff; Product Owner decision text; Q04 packet; S07/S11 proposals; S04-S12 Q04 gates; workflow/permission, workflow architecture, capability, domain/data and business policy references; current Roadmap status. |
| C2 trigger / expansion | Narrow architecture expansion was required only where revised G3 contradicted the former protected-action/small-tenant wording or E1/F2 affected authoritative access/support descriptions. No code inspection was needed because runtime behavior is unchanged. |
| Files | Q04 and S13 packets; S04-S12 proposals; workflow/permission matrix; tenant-workflow, capability, domain/data and business references; Roadmap P0.1/decision register; this record/handoff. |
| Validation | Local Markdown links/anchors; exact A-H selections/revisions; F2/G3 revision markers; all required reviewer names/evidence OPEN; nine ADRs PROPOSED; stale Q04-decision searches; whitespace and scoped status. |
| Stop / closeout | Stop with Product Owner policy selected but accountable review open, all ADRs PROPOSED, current behavior unchanged and no implementation authority. |

The [Q04 packet](architecture/P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md)
records A1, B1, C1, D1, E1, revised F2, revised G3 and H1 with concise rationale.
Original recommendations remain visible. F2 now includes a separately controlled
emergency path when tenant approval is practically impossible. Section 41's final
Protected Operations decision supersedes this session's earlier G3 wording while
retaining G1 as the intentionally rejected original recommendation.

Compatibility and review implications are explicit. E1 conflicts with current
membership-free superuser helper behavior and therefore needs a path inventory and
cutover plan before any change. Revised F2 needs security, operations/privacy and
conditional legal review plus D03/Q03 decisions before enablement. Final revised
G3 mandates Protected Operations separation and leaves non-protected business
Self-Approval configurable, with security, workflow, accounting/control,
conditional legal and affected-domain review still required. Section 41 supersedes
the earlier C1/F2/G3 precedence question and records the remaining classification
and business-control risks.

### Validation and documentation closeout

Documentation-only static validation passed for local links/anchors, recorded
selection/revision coverage, all reviewer-name/evidence fields remaining OPEN,
all nine ADRs remaining PROPOSED, stale current-status claims, whitespace and
scoped repository status. No Django, application, migration or dependency tests
were run because no executable or configuration artifact changed.

Documentation closeout reconciles the decision packet, affected proposed ADRs,
cross-domain authorization/workflow/support references, S13 review packet,
Roadmap P0.1/decision register and this session record. Historical session records
remain historical except the S03 open-input row, which now points to the later
decision status. Existing worktree changes were preserved.

### Compact next handoff

**Outcome/acceptance:** P0-S15 decision recording is complete. Product Owner Q04
policy selections are authoritative for this round. Reviewer names/outcomes remain
OPEN; S04-S12 remain PROPOSED; S07/PPC-04/P0.1 remain incomplete; P1.1/P0.2/P0.3
are not implemented or authorized by this session.

**Next:** supply actual accountable reviewer names and review evidence by Q04 item.
Prioritize security/workflow review across A-H, operations/privacy/legal review of
revised F2, and security/workflow/accounting/legal/domain review of revised G3. A
separately authorized session may record those reviews and determine whether S07
or affected ADR clauses need revision; it must not infer acceptance or implement.

## 41. Final Q04-G Product Owner decision and handoff

**Recorded/reconfirmed:** 2026-09-26. **Authorization:** the Product Owner supplied
the final and authoritative Q04-G decision. It explicitly revises the original G1
recommendation and replaces every earlier Q04-G response. This is a documentation-
only revision; Q04-A through Q04-F and Q04-H are unchanged.

### Decision and affected boundary

The final decision is **G3 — Revised with Protected Operations**. Platform-level
`Protected Operations` cover system, security, authorization, privileged-access
and access-management operations where Self-Approval could elevate the actor or
bypass a security control. Self-Approval is never allowed for these operations and
Tenant configuration cannot override that restriction. The minimum set includes
self-grant/access increase, own privileged-role
assignment/approval, own support/emergency access, same-actor authorization or
security-policy change/approval, same-actor audit/security-control weakening and
approval, and equivalent system-level self-elevation/control bypass.

Other functional/business operations—including financial, contractual, project,
procurement, administrative and workflow approvals—may support configurable
Self-Approval. Superuser defines at platform level which business operation types
support it; Platform Admin remains a separate operational role and receives no
implicit Superuser authority. Where permitted, the Tenant Owner or another Tenant
actor with explicit policy-management permission may enable or disable it according
to that Tenant's policy. Tenant Owner status alone enables no Self-Approval. No
single-user-Tenant mode exists. Every policy change and actual use is audited. Tenant
enablement remains subject to its internal-control, contractual, accounting, audit,
legal and regulatory obligations.

This final revision replaces every earlier Q04-G response, retains original G1 as
the rejected packet recommendation, and resolves the earlier C1/F2/G3 precedence
tension by classifying self-elevation and support/emergency self-approval as
Protected Operations. Classification completeness and business-operation control/
compliance risks still require named review.

### Validation, status and next handoff

Documentation-only static validation passed for local links/anchors, final Q04-G
wording and supersession markers, Protected Operations minimum coverage, retained
OPEN reviewer fields, nine PROPOSED ADR statuses, whitespace and scoped status. No
application, runtime, schema, permission, migration or dependency validation was
run because none changed.

All required reviewer names and review outcomes/evidence remain OPEN. Next, supply
the named security/authorization, workflow/control, accounting/control,
legal/compliance where applicable and affected-domain reviewers plus their review
evidence. No ADR acceptance or P1.1/P0.2/P0.3 implementation is inferred.

## 42. Authorization role terminology normalization

**Recorded:** 2026-09-26. **Authorization:** the Product Owner supplied an
authoritative platform/Tenant role model and requested documentation review and
normalization only.

### Normalized vocabulary and findings

- **Superuser** is exceptional highest technical/system authority and owns
  Protected Operations; it receives no automatic Tenant business-data access.
- **Platform Admin** owns permitted operational platform administration, Tenant
  provisioning and global configuration. It is independent from Superuser; one
  user may explicitly hold both, but neither implies the other.
- Q04-G classifies changes to platform Self-Approval policy as authorization-
  policy changes and therefore Protected Operations controlled by Superuser;
  Platform Admin assignment alone does not confer that capability.
- **Tenant Owner** owns Tenant business/policy authority but does not imply
  Tenant Admin.
- **Tenant Admin / Local Admin** operates one Tenant's users, delegated access,
  workflow administration and first-line support without global, other-Tenant or
  automatic unrestricted business-data authority.
- **Tenant Manager** is business/operational management and is independent from
  Tenant and platform administration.
- Multiple roles require explicit independent assignment; no merge or implicit
  inheritance is documented.

The review found four inconsistent terminology classes: combined `Owner/Admin`
labels that merged Tenant ownership and administration; standalone `Admin` labels
that could mean Platform Admin, Tenant Admin or Django Admin; `system
administrator` wording that conflated the current Superuser path with target
Platform Admin; and generic `Manager` wording that could merge Tenant Manager with
membership administration. Directly affected current-policy documents were
normalized. Historical code symbols and role codes remain verbatim and are labeled
as current compatibility evidence; technical UI references now say `Django Admin`.

### Status and handoff

This normalization changes no current role code, assignment, permission, schema,
migration, service, workflow runtime or default grant. The target Platform Admin
role and canonical Tenant-role mapping remain unimplemented and require a separate
approved P1.1 design/migration package. All P0.1 ADRs remain PROPOSED and Q04
reviewer names/evidence remain OPEN.

Next, accountable reviewers must verify the normalized role boundaries together
with Q04 scope, Protected Operations, support/emergency access and current-code
compatibility. No ADR acceptance or implementation follows from terminology
normalization.

## 43. Membership-scoped multi-role authorization rule

**Recorded:** 2026-09-26. **Authorization:** the Product Owner supplied an
authoritative multi-role policy and authorized documentation updates only.

### Authoritative target rule

- A User may hold multiple independent roles simultaneously. Common combinations
  such as Tenant Owner, Tenant Admin and Project Manager remain separate
  assignments; no composite role is created merely for convenience.
- Tenant/business roles belong to the User's Tenant Membership. The same User may
  therefore hold different role sets in different Tenants.
- The target relation is many-to-many, conceptually
  `User -> Membership -> MembershipRoleAssignment -> Role`, or an equivalent
  Tenant-preserving representation.
- Effective role permissions are unioned across all active applicable role
  assignments and then intersected with active Membership, explicit Grants,
  Project/Site Scope, Delegation, Workflow eligibility and policy constraints.
  Role assignment alone never supplies unrestricted scope.
- Adding or revoking one role changes no other independent role assignment. Every
  assignment/revocation retains actor, Tenant, role, timestamp and relevant
  reason/context.

### Current compatibility finding and gate

The current `OrganizationMembership.role_definition` is a single foreign key and
current services replace that role when it changes. The delivered runtime is
therefore single-role-per-Membership and does not yet satisfy the target rule.
Documentation now labels that limitation explicitly rather than treating it as the
target or inventing composite roles.

Implementation remains a separately approved P1.1 package. It must design an
expand/backfill/switch/validate path, preserve Tenant context and existing audit/
Tenant Owner protections, define compatibility-field disposition, and test independent
role addition/removal, permission union, cross-Tenant isolation, scope
intersection, delegation/workflow rechecks and concurrency. No schema, migration,
permission, runtime or application change is authorized by this record. All P0.1
ADRs remain PROPOSED and Q04 reviewer names/evidence remain OPEN.

## 44. P0-S16 Q04 accountable-review pending record

**Recorded:** 2026-09-26. **Authorization:** the Product Owner confirmed that the
Q04-A through Q04-H decisions have been supplied, but the accountable reviewer
reviews have not been completed. This authorizes documentation recording only.

### Session card and recorded result

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Record the existing Product Owner decisions and the explicitly supplied pending-review state; identify the still-required reviewer responsibilities for each Q04 item. |
| Excluded | Inferring reviewer identities, approvals, outcomes, evidence, dates, objections or reviewer-driven revisions; accepting an ADR; starting implementation or changing code/schema/runtime behavior. |
| C0/C1 | Sections 40-43; S13/S14 packets; affected S04-S12 proposed ADR gates; current Roadmap status and scoped worktree state. |
| Files | Q04 and S13 packets; Roadmap P0.1; this session record and session-map calibration note. |
| Validation | Exact A-H selections retained; five review-record fields remain OPEN for every item; required responsibilities match the decision packet; nine ADRs remain PROPOSED; links/anchors, whitespace and scoped status. |
| Stop / closeout | Stop with every accountable review pending, Q04 review gate OPEN, current behavior unchanged and no implementation authority. |

P0-S15's Product Owner selections remain A1, B1, C1, D1, E1, revised F2,
final G3 — Revised with Protected Operations, and H1. P0-S16 adds no decision and
does not reinterpret them. For every Q04 item, reviewer names, review outcomes,
evidence/version and review dates, unresolved objections, and resulting revisions
from reviewer feedback are `OPEN`.

The required responsibilities remain:

| Q04 item | Reviewer responsibilities still required |
| --- | --- |
| A | Security/authorization; affected domain owner |
| B | Security/authorization; affected domain owner |
| C | Security/authorization; workflow/control |
| D | Security/authorization; affected tenant/access domain owner |
| E | Security/authorization; operations/privacy |
| F revised | Security/authorization; operations/privacy; legal/compliance where applicable |
| G final revision | Security/authorization; workflow/control; accounting/control and legal/compliance where applicable; affected domain owner |
| H | Security/authorization; workflow/control; affected domain owner |

### Status and next bounded handoff

The Q04 accountable-review gate remains OPEN. All nine P0.1 ADRs remain PROPOSED;
P0/P0.1/PPC-04 remain incomplete; P1.1/P0.2/P0.3 remain unimplemented and are not
authorized by this session. Absence of reviewer information is not approval.

Next, the Product Owner may assign actual named reviewers to the responsibilities
above. A later separately authorized recording session may enter only the reviews
actually supplied, including version/date, outcome, unresolved objections and any
resulting revisions. It must not infer missing evidence, accept an ADR or begin
implementation without separate explicit authority.

## 45. P0-S17 Q04 reviewer-assignment record

**Recorded:** 2026-09-26. **Authorization:** the Product Owner supplied four
reviewer-responsibility assignments for named Q04 items and authorized
documentation recording only.

### Session card and recorded assignments

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Record only the supplied reviewer name, responsibilities and Q04 items; reconcile the Q04 packet, Roadmap and Playbook. |
| Excluded | Inferring or recording review outcomes, evidence/version, dates, unresolved objections, reviewer-feedback revisions, independence rationale, approvals or ADR dispositions; authorizing implementation or changing runtime behavior. |
| C0/C1 | Section 44 handoff; Q04 packet accountable-review register; current Roadmap P0.1 and Q04 decision register; scoped worktree state. |
| Files | Q04 packet; Roadmap; this session record and session-map calibration note. |
| Validation | Exact supplied name/responsibility/item mappings; all other reviewer responsibilities and review fields OPEN; nine ADRs PROPOSED; links/anchors, whitespace and scoped status. |
| Stop / closeout | Stop after documentation reconciliation with the Q04 review gate OPEN, current behavior unchanged and no implementation authority. |

| Reviewer name | Assigned responsibility | Q04 items |
| --- | --- | --- |
| Azam Zerangzadeh | Security / Authorization Reviewer | Q04-A, Q04-B, Q04-C, Q04-D, Q04-E, Q04-F, Q04-H |
| Azam Zerangzadeh | Workflow / Control Reviewer | Q04-C, Q04-G, Q04-H |
| Azam Zerangzadeh | Accounting / Control Reviewer | Q04-G |
| Azam Zerangzadeh | Operations / Privacy Reviewer | Q04-E, Q04-F |

These assignments record responsibility only. They do not state that any review
was started or completed, do not resolve the packet's multi-responsibility
independence requirement, and do not provide approval. Required affected-domain
owner assignments remain OPEN for Q04-A, Q04-B, Q04-D, Q04-G and Q04-H;
Security / Authorization Reviewer remains OPEN for Q04-G; and Legal / Compliance
Reviewer remains OPEN where applicable for Q04-F and Q04-G.

### Status and next bounded handoff

Every review outcome, evidence/version, review date, unresolved objection and
resulting revision remains `OPEN`. The Q04 accountable-review gate remains OPEN;
all nine P0.1 ADRs remain PROPOSED; P0/P0.1/PPC-04 remain incomplete; and
P1.1/P0.2/P0.3 remain unimplemented and unauthorized. No code, schema, permission,
migration, dependency or runtime behavior changed.

Next, the Product Owner may supply the remaining reviewer assignments and the
required independence rationale. Later bounded sessions may record only review
facts actually supplied. Reviewer assignment or review evidence alone does not
accept an ADR or authorize implementation.

## 46. P0-S18 Q04 final accountable reviewer and independence override

**Recorded:** 2026-09-26. **Authorization:** the Product Owner explicitly decided
that Azam Zerangzadeh is the final accountable reviewer for all Q04-A through
Q04-H review responsibilities and explicitly overrode the current
reviewer-independence expectation where applicable. This authorizes documentation
recording only.

### Session card and decision record

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Record the final accountable reviewer for every Q04 review responsibility, the Product Owner independence override, and the resulting conflict/risk; reconcile the Q04 packet, Roadmap and Playbook. |
| Excluded | Inventing additional reviewers, review outcomes, evidence/version, dates, objections or reviewer-driven revisions; rejecting or replacing the Product Owner decision; accepting ADRs, authorizing implementation or changing runtime behavior. |
| C0/C1 | Section 45 handoff; Q04 packet responsibility register and independence rule; affected ADR review gates; current Roadmap P0.1/Q04 status and scoped worktree state. |
| Files | Q04 packet; Roadmap; this decision record and session-map calibration note. |
| Validation | One named final accountable reviewer across all A-H responsibilities; explicit independence override and concentration risk; every review-result field OPEN; nine ADRs PROPOSED; links/anchors, whitespace and scoped status. |
| Stop / closeout | Stop after documentation reconciliation with the Q04 review gate OPEN, current behavior unchanged and no implementation authority. |

### Final accountable reviewer decision

Azam Zerangzadeh is the final accountable reviewer for every required review
responsibility across Q04-A through Q04-H. This includes Security / Authorization,
Workflow / Control, Accounting / Control and Operations / Privacy responsibilities
for all relevant items, together with the packet's affected-domain and conditional
legal/compliance responsibilities where required. No additional reviewer is
created or inferred.

This is an explicit Product Owner override of the packet's prior expectation for
independent review where one person holds multiple responsibilities. It does not
record a review, provide evidence, or waive an external professional, statutory or
contractual independence obligation.

### Conflict and associated risk

The decision conflicts with the packet's independent-challenge expectation by
concentrating all Q04 review accountability in one person. The recorded risks are
reduced separation and independent challenge, confirmation bias, key-person
dependency, and the possibility that specialist or external independence
requirements remain unsatisfied. The assignment does not demonstrate reviewer
qualification, professional acceptance or review completion. These risks do not
replace or reject the Product Owner decision; they remain explicit constraints for
review evidence, ADR acceptance and release readiness.

### Status and next bounded handoff

Every review outcome, evidence/version, review date, unresolved objection and
resulting revision remains `OPEN`. The Q04 accountable-review gate remains OPEN;
all nine P0.1 ADRs remain PROPOSED; P0/P0.1/PPC-04 remain incomplete; and
P1.1/P0.2/P0.3 remain unimplemented and unauthorized. No code, schema, permission,
migration, dependency or runtime behavior changed.

Next, the Product Owner may supply actual review outcomes and evidence. A later
bounded session may record only supplied review facts and must preserve the
conflict/risk unless an explicit Product Owner revision changes it. Review evidence
alone does not accept an ADR or authorize implementation.

## 47. P0-S19 Q04 review-outcome recording from S18 handoff

**Recorded:** 2026-09-26. **Authorization:** the Product Owner authorized a
documentation-only P0-S19 session from the P0-S18 handoff. No completed Q04 review
fact was supplied; this record preserves unprovided fields as `OPEN`.

### Session card and recorded result

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Record only supplied Q04-A through Q04-H review outcomes, evidence/version, dates, unresolved objections and resulting revisions; reconcile the Q04 packet, Roadmap and Playbook. |
| Excluded | Inferring a review, outcome, evidence/version, date, objection or revision; changing reviewer accountability or the recorded independence override; accepting ADRs, authorizing implementation or changing runtime behavior. |
| C0/C1 | Section 46 handoff; Q04 packet accountability register; current Roadmap P0.1/Q04 status and scoped worktree state. |
| Files | Q04 packet; Roadmap; this session record and session-map calibration note. |
| Validation | Q04-A through Q04-H retain `OPEN` for every unprovided review-result field; Azam Zerangzadeh remains final accountable reviewer; independence, concentration and external-independence risks remain explicit; nine ADRs remain PROPOSED; links/anchors, whitespace and scoped status. |
| Stop / closeout | Stop after documentation reconciliation with the Q04 review gate OPEN, current behavior unchanged and no implementation authority. |

### Per-item review register

| Q04 item | Final accountable reviewer | Review outcome | Evidence/version | Review date | Unresolved objections | Resulting revisions |
| --- | --- | --- | --- | --- | --- | --- |
| Q04-A | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN | OPEN |
| Q04-B | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN | OPEN |
| Q04-C | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN | OPEN |
| Q04-D | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN | OPEN |
| Q04-E | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN | OPEN |
| Q04-F revised | Azam Zerangzadeh — all required responsibilities, including legal/compliance where applicable | OPEN | OPEN | OPEN | OPEN | OPEN |
| Q04-G final revision | Azam Zerangzadeh — all required responsibilities, including legal/compliance where applicable | OPEN | OPEN | OPEN | OPEN | OPEN |
| Q04-H | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN | OPEN |

Azam Zerangzadeh remains the final accountable reviewer for every Q04
responsibility under the explicit Product Owner independence override recorded in
P0-S18. That override does not waive external professional, statutory or
contractual independence obligations. The concentration, reduced independent
challenge, confirmation-bias, key-person and unsatisfied-specialist-or-external-
independence risks remain explicit constraints for review evidence, ADR acceptance
and release readiness.

### Status and next bounded handoff

The Q04 accountable-review gate remains `OPEN`. All nine P0.1 ADRs remain
`PROPOSED`; P0/P0.1/PPC-04 remain incomplete; and P1.1/P0.2/P0.3 remain
unimplemented and unauthorized. No code, schema, permission, migration,
dependency or runtime behavior changed. This record accepts no ADR and provides no
implementation authority.

Next, a separately authorized session may record only actual subsequently supplied
review facts, retaining `OPEN` for every omitted field and preserving the recorded
independence/concentration risks unless the Product Owner explicitly revises them.

## 48. P0-S20 workbench UI/accessibility assessment and deferred-remediation handoff

**Recorded:** 2026-09-26. **Authorization:** after reviewing the workbench journey
against the recent Q04 decisions and current runtime, the Product Owner directed
continuation and related-document updates. This session records assessment and
handoff only; it does not implement UI or backend behavior.

### Session card

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Decide whether bounded workbench UI/accessibility remediation should proceed before the target authorization model; record safe-now and blocked UI debt. |
| Excluded | Template, CSS, JavaScript, view, service, permission, model, migration, dependency or runtime changes; Q04 review inference; ADR acceptance; P1.1 or P0.4 implementation. |
| C0/C1 | Section 47 handoff; Roadmap P0.4/P1.1; UI-guideline workbench/accessibility contracts; Q04/S07 records; current membership/workbench code, templates and direct tests. |
| C2 trigger / response | Current single-role and tenant-wide project/site filter behavior differs materially from target multi-role and object-scope semantics, so the assessment inspected only the direct model/workbench boundaries and did not broaden into a UI rewrite. |
| Files | New `architecture/P0_S20_UI_ACCESSIBILITY_ASSESSMENT.md`; Roadmap P0.4; capability/readiness UI audit; this record and calibration note. |
| Validation | Current/target separation, stable safe-now backlog, authorization-dependent deferrals, Q04 fields OPEN, S07 PROPOSED, no runtime-authority claim, local links and whitespace. |
| Stop / closeout | Stop after documentation reconciliation; actual remediation deferred, P0.4 not complete and P0 integrated acceptance not started. |

### Result and handoff

The [P0-S20 assessment](architecture/P0_S20_UI_ACCESSIBILITY_ASSESSMENT.md)
retains the centralized personal workbench as the recommended first UI journey but
selects deferral of actual remediation. Current membership has one role relation;
project/site filter choices are tenant-scoped rather than effective-grant-scoped;
and final multi-role, Tenant-role, Q04-G and Q04-H UI states lack authoritative
implemented server semantics. Building those states now would create medium-high
rework and could imply authority the server does not enforce.

Semantic table markup, active-view state, focus/live feedback, touch targets,
duplicate-submit feedback, responsive containment, distinct empty states and
existing Jalali/direction conventions are recorded as safe future work. P0-S20
implements none of them. Multi-role UI, role-specific authority, grant-aware
project/site context, Self-Approval/Protected Operations and unresolved-work
recovery remain blocked on their accepted and implemented backend contracts.

All Q04 review-result fields remain `OPEN`; Azam Zerangzadeh remains the final
accountable reviewer under the recorded independence override; concentration and
external-independence risks remain explicit. S07 and the other P0.1 ADRs remain
`PROPOSED`. No ADR is accepted, no implementation is authorized and no runtime or
UI behavior changes.

Next, record actual Q04 accountable-review evidence and ADR dispositions, or—only
after those gates close—start a separately approved P1.1 package. Re-estimate and
renumber remaining P0 work after the gates resolve; do not treat P0-S21 as
integrated acceptance merely because P0-S20 assessment is complete.

## 49. P0-S21 readiness and unresolved-risk review

**Recorded:** 2026-09-26. **Authorization:** the Product Owner requested a
documentation-only P0 readiness and unresolved-risk review from the P0-S20
handoff. This authorizes evidence verification and documentation reconciliation,
not approval inference, ADR acceptance, P0 completion, implementation or runtime
change.

### Session card

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Verify and classify Q04 reviews, all S04-S12 dispositions, P1.1 authorization, D03-D05/Q03 gates, P0.2/P0.3 prerequisites and deferred P0.4 remediation as VERIFIED CLOSED or OPEN. |
| Excluded | Supplying missing evidence, accepting ADRs, resolving parameters, approving packages, completing P0, changing runtime/schema/dependencies or performing UI remediation. |
| C0/C1 | Section 48 handoff; Roadmap P0.1-P0.4/P1.1 and decision register; S13 disposition matrix; Q04 packet and S19 register; S04-S12 status/gates; capability/readiness release and UI sections. |
| C2 trigger / response | No code expansion was needed: the requested result concerns recorded approvals, dispositions and prerequisites, for which the current authoritative documentation is direct evidence. |
| Files | New `architecture/P0_S21_READINESS_AND_UNRESOLVED_RISK_REVIEW.md`; Roadmap; capability/readiness audit; this record and session-map calibration note. |
| Validation | Binary gate completeness, links/anchors, stale acceptance/authorization claims, reviewer-concentration and external-independence risk retention, whitespace and scoped documentation-only status. |
| Stop / closeout | Stop with the review recorded and every unsupported gate OPEN. A later P0-S22 documentation closeout may carry the blocked conditional handoff; it cannot be treated as P0 exit or P1 authorization. |

### Result and bounded handoff

The [P0-S21 review](architecture/P0_S21_READINESS_AND_UNRESOLVED_RISK_REVIEW.md)
finds P0 **not ready for integrated acceptance or phase exit**. Q04 selections,
the final accountable-reviewer assignment, the D03/D04 directions, the D05 policy
direction and the P0-S20 assessment/deferral decision are VERIFIED CLOSED only as
narrow decision/preparation records. They do not close their downstream gates.

All Q04-A through Q04-H accountable reviews remain OPEN. Every S04-S12 Product
Owner ADR disposition remains OPEN and every ADR remains PROPOSED. P1.1
implementation authorization, D03-D05 parameters, Q03, P0.2/P0.3 prerequisites
and authorization, P0.4 prerequisites/remediation evidence and P0 integrated
acceptance remain OPEN. No application, schema, permission, migration, dependency,
template or runtime behavior changed.

Azam Zerangzadeh remains the final accountable reviewer under the explicit
Product Owner independence override. Reviewer concentration, reduced independent
challenge, confirmation-bias and key-person risk remain unresolved. The override
does not waive an external professional, statutory or contractual independence
requirement.

**Minimum next evidence:** actual Q04 review results/evidence/dates/objections/
revisions; explicit S04-S12 dispositions and remaining owners; D03 provider,
location and operator parameters; D04 numeric objectives/scenarios/owner; Q03
evidence/retention/hold/export decisions and approver; and D05 limit/lifecycle/
commercial parameters. Only after the applicable gates close may separately
authorized P1.1/P0.2/P0.3 packages proceed. Re-estimate the remaining P0 work
before P0.4 remediation or a later evidence-based phase closeout/P1 handoff.

## 50. P0-S22 documentation closeout and conditional P1 handoff

**Recorded:** 2026-09-26. **Authorization:** the Product Owner requested P0-S22
from the P0-S21 handoff. This authorizes documentation closeout and a conditional
P1 handoff packet only; it does not authorize P0 acceptance, ADR acceptance, P1.1
implementation or any runtime change.

### Session card

| Field | Bounded contract |
| --- | --- |
| Goal / scope | Reconcile P0-S21 evidence, close the documentation sequence and record the minimum prerequisites for a later P1 handoff. |
| Excluded | Resolving OPEN decisions, accepting ADRs, freezing release scope, authorizing P1/P0.2/P0.3/P0.4 implementation, changing code/schema/dependencies or claiming P0 phase exit. |
| C0/C1 | Section 49; P0-S21 review; Roadmap P0/P1 status and decision register; S13 ADR disposition packet; Q04 packet; capability/readiness audit. |
| Files | New `architecture/P0_S22_DOCUMENTATION_CLOSEOUT_AND_P1_HANDOFF.md`; Roadmap; this record and calibration note; affected readiness reference only if needed. |
| Validation | Gate/status consistency, conditional-handoff boundary, local links/anchors, stale-authorization search, whitespace and scoped documentation-only status. |
| Stop / closeout | Close documentation with P0 and P1 entry explicitly blocked; hand off the decision/evidence queue to the Product Owner. |

### Result and handoff

The [P0-S22 closeout and handoff packet](architecture/P0_S22_DOCUMENTATION_CLOSEOUT_AND_P1_HANDOFF.md)
records the P0 gate state without changing it. Q04 selections and reviewer
assignment are closed only as narrow records; Q04 accountable reviews, S04-S12
dispositions, P1.1 authorization, D03-D05/Q03 parameters, P0.2/P0.3
prerequisites and P0.4 remediation remain OPEN. P0 integrated acceptance and
phase exit are not achieved.

The P1 handoff is conditional and blocked. Before a separately authorized P1.1
package, the Product Owner must receive completed Q04 review evidence, affected
ADR dispositions, resolved operational/commercial/evidence parameters, a
tenant-preserving multi-role migration/design boundary and explicit package
authorization. This packet does not authorize P1 or downstream packages.

Azam Zerangzadeh remains the final accountable reviewer under the recorded
independence override. Reviewer concentration, reduced independent challenge,
confirmation-bias, key-person and external-independence risks remain explicit.
No application, schema, permission, migration, dependency, template or runtime
behavior changed.
