# Roadmap Execution Playbook

## 1. Purpose and authority

This document converts `ROADMAP.md` into resource-aware Codex execution sessions.
It does not add product scope, authorize implementation, replace architecture
documents, or change roadmap status. `ROADMAP.md` remains the delivery-order and
status authority; code, migrations, and tests remain the implementation authority.

The Product Owner owns product decisions, prioritization, acceptance, and manual
Admin/user UI testing. Codex owns the approved implementation slice, automated
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
| `T-M` | `gpt-5.6-terra` | medium | Routine Django implementation, forms/Admin/templates, ordinary service/tests |
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

## 7. P1 session map — 28 sessions

| Sessions | Count | Model | Outcome |
| --- | ---: | --- | --- |
| P1-S01..S04 | 4 | `A-H` | Object-scope model, permission intersection and migration design |
| P1-S05..S09 | 5 | `A-H` | Project/site authorization services, queryset/view enforcement and tests |
| P1-S10..S13 | 4 | `T-M` | Scoped forms/Admin/UI states without option leakage |
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
| P2-S23..S27 | 5 | `T-M` | Accounting Admin/UI, period controls and source drill-through |
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
8. Perform documentation closeout as the final work step.
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
