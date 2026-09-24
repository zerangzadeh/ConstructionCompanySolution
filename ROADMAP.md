# Product Development Roadmap

**Status date:** 2026-09-24

**Product stage:** pre-production

**Purpose:** dependency-ordered delivery plan; a listed item is not implementation authorization
**Current/target audit:** `docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`

Construction ERP is a Persian-first, multi-tenant construction SaaS. Models,
migrations, services, and tests remain the source of truth for current behavior.
This roadmap separates delivered capability, pre-production corrections, and
future target scope. Only a separately approved work package may be implemented.

## Status and priority vocabulary

- **DELIVERED:** implemented and validated at its documented acceptance level;
  production certification is separate.
- **PARTIAL:** useful implementation exists but the target capability is not complete.
- **NEXT-CANDIDATE:** dependency-ready planning candidate, not approval.
- **PLANNED:** accepted product direction whose prerequisites are not complete.
- **DEFERRED:** intentionally postponed until a stated trigger.
- **MUST / SHOULD / DEFER:** pre-production correction priority.

Effort is relative: **S** (one bounded slice), **M** (several slices), **L**
(multi-domain program), **XL** (portfolio capability). Risk combines financial,
compliance, security, migration, and integration consequences.

## Delivered baseline — do not re-plan as missing

| ID | Status | Delivered boundary |
| --- | --- | --- |
| F1 Workforce | **DELIVERED** | Employees, departments, positions, teams, effective position/project assignments, optional `User` link, images, permission/audit/tenant checks. Attendance, time, payroll, skills, and rates are not delivered. |
| F2 Procurement | **DELIVERED baseline** | Purchase request/order/goods receipt lifecycles and workflow adoption. RFQ, quotes, supplier invoice, match, and accounting are not delivered. |
| F3 Inventory | **DELIVERED baseline** | Warehouse and posted/reversible stock-quantity ledger. Valuation, reservations, bins/lots/serials, and accounting are not delivered. |
| F4 Equipment | **DELIVERED baseline** | Equipment, conflict-safe assignments, maintenance. Usage/fuel/cost/fixed-asset integration is not delivered. |
| F5 Workflow & Work Management | **DELIVERED** | Versioned definitions, bounded registries, runtime, candidate/assignment/delegation history, work items/workbench, position routing, domain adoption, PostgreSQL acceptance gates. |
| F6 Billing & Progress Claims | **DELIVERED receivable baseline** | Baseline/progress/claims/items/sources/adjustments, workflow, settlements and payment allocation. Policy ownership needs pre-production correction; payable claims and posting are not delivered. |
| F7 Documents v2 | **DELIVERED baseline** | Private versioned documents and explicit links to supported records. Retention/export/object storage/scanning and broader links are not delivered. |
| F8 Safety & Quality | **PARTIAL** | Incident and quality-issue lifecycles/workflow exist. Inspections, formal CAPA, risk, and knowledge integration remain. |
| Foundation | **DELIVERED baseline** | Tenant/session/membership/RBAC, shared masters, projects/sites/phases/WBS/activities, contracts/amendments, estimates/revisions, expenses, payments/allocations, daily reports, audit, financial read models. |

Historic validation detail belongs in `docs/PROJECT_STATUS.md`, not in this
forward roadmap.

## Mandatory delivery contract for every future work package

Every approved package must define and test:

1. owner aggregate and source of truth; tenant/project/site scope; lifecycle,
   finalization, revision/reversal, concurrency, and idempotency;
2. `BusinessPermissionCode`, permission registration and default-role data
   migration, service/view enforcement, object scope, separation of duties, and
   cross-tenant/cross-project negative tests;
3. `Decimal`, currency/unit/timezone/date behavior; effective dating and snapshot
   rules; organization-scoped uniqueness and database constraints;
4. integration producer/consumer contract, source reference/version, failure and
   retry behavior, reconciliation, audit, and KPI lineage;
5. Persian-first RTL UI, context-aware cascading choices, accessibility,
   responsive/site behavior, empty/loading/error/disabled states, and evidence;
6. legal/accounting review where relevant; annual/regulatory values are data,
   never constants;
7. expand -> migrate/backfill -> switch -> validate -> separately approved
   contract/removal when existing schema changes;
8. smallest relevant unit/integration tests followed by `manage.py check`, full
   PostgreSQL tests where risk demands it, Ruff, migration/rollback rehearsal,
   performance and security checks;
9. documentation updates limited to authoritative active documents; and
10. explicit rollout, observability, recovery, and operator ownership.

## Dependency overview

```text
P0 Decisions + Security/Operations Foundations
 ├─> P1 Master/Data/Auth Corrections
 │    ├─> P2 Accounting Kernel ─> P3 Treasury + AP/AR
 │    │                          ├─> P4 Project Costing
 │    │                          ├─> P5 Source-to-Pay
 │    │                          └─> P7 Payroll/Insurance
 │    ├─> P6 Contract/Billing Expansion
 │    └─> P8 Inventory/Equipment/Fixed Assets
 ├─> P9 Field/HSE/Quality/DMS/Knowledge
 └─> P10 Production Certification

P3 + P4 + P5/P6/P7/P8 reconciliations -> governed BI/KPIs
Stable masters + consent/privacy + support operations -> future network/AI
```

## P0 — Pre-production decisions and operational foundation

### P0.1 Architecture decisions and correction plan

- **Status / priority:** **NEXT-CANDIDATE / MUST**
- **Outcome and rationale:** decide authoritative boundaries before real financial,
  payroll, document, and tenant history makes change expensive.
- **Prerequisites:** repository audit accepted; initial customer segment and
  native-vs-external accounting boundary decided by product owner.
- **Scope:** ADRs for Accounting/posting, Treasury/AP/AR, budget/CBS/cost center,
  regulatory configuration/contract terms, project authorization, storage/DMS,
  async/outbox, tenant lifecycle/support access, and future network privacy.
- **Data/migration:** inventory affected fields and compatibility bridges;
  migrations remain history. Any squash/reset is a separate decision before the
  first tenant and is not assumed.
- **Integration/accounting/compliance:** specify source/version/idempotency and
  reconciliation before downstream code.
- **Security/UI:** threat-model object scope and support access; define visible
  context and denied/disabled behavior.
- **Validation:** ADR review against code, sample posting/lineage walkthroughs,
  regulatory/accounting professional review plan.
- **Effort / risk:** **M / Critical**.

### P0.2 Reproducible delivery, security, and recovery baseline

- **Status / priority:** **NEXT-CANDIDATE / MUST**
- **Outcome:** CI, dependency lock/hashes/SBOM and vulnerability policy; MFA for
  privileged users; secure private object storage decision; secrets/key policy;
  structured correlation-aware logging, metrics/error tracking and alerting;
  backups and proven restore; migration/rollback deployment runbook; retention,
  export, incident and support-access operations.
- **Prerequisites:** P0.1 hosting/data-residency and RPO/RTO decisions.
- **Libraries to evaluate:** `django-allauth`, `django-storages`, `pip-audit`,
  `sentry-sdk` or equivalent, stable OpenTelemetry components. No package is pre-approved.
- **Data/migration:** production storage migration and backup compatibility plan;
  no movement until integrity checks and rollback exist.
- **UI/security:** MFA/recovery/session screens, export/job state, time-limited
  support grant and audit; prevent PII/secrets in telemetry.
- **Validation:** immutable build, clean-environment install, dependency and
  license gates, restore exercise, deployment rehearsal, security review,
  representative load budgets.
- **Effort / risk:** **L / Critical**.

## P1 — Authoritative masters, configuration, and authorization

### P1.1 Project/site object-scope authorization

- **Status / priority:** **PLANNED / MUST**
- **Outcome:** permissions are the intersection of active tenant membership,
  business permission, object scope, tenant status, and—only for workflow
  actions—assignment/candidacy. Positions continue to route, never grant.
- **Prerequisites:** P0.1 scope ADR and target role vocabulary.
- **Models/services:** effective project/site grants or restricted assignments,
  scope selectors, service checks, queryset helpers, grant history; decide owner
  and emergency/support access.
- **Integration:** every domain and workbench; payroll/finance scopes are stricter.
- **UI/security:** explicit tenant/project/site context, safe empty results,
  no unauthorized option leakage; UI visibility is never authorization.
- **Migration/testing:** backfill unrestricted scope only by explicit policy;
  exhaustive cross-tenant/cross-project tests and query/performance review.
- **Effort / risk:** **L / Critical**.

### P1.2 Configuration and master-governance corrections

- **Status / priority:** **PLANNED / MUST+SHOULD**
- **Outcome:** one owner for organization timezone/currency/fiscal settings;
  effective-dated approved regulatory rule sets; versioned contract commercial
  terms; richer party tax/bank/qualification profiles; governed UOM conversions;
  canonical roles and separation-of-duties policy.
- **Prerequisites:** P0.1 and legal/accounting source register.
- **Models:** `RegulatoryRuleSet`/version (final naming by design), contract term
  versions, party profiles, UOM conversions, effective grants. Split the current
  `BillingPolicy` into its correct owners.
- **Integration:** Billing, Payroll, taxpayer invoices, Treasury, Procurement,
  Inventory, reporting; historical documents store applied versions/snapshots.
- **UI:** effective date, provenance, reviewer, impact preview, dual control,
  clear Rial/Toman and Jalali/Gregorian display.
- **Migration/testing:** pre-production data may be discarded/backfilled if that
  is safer, but migrations remain; golden calculations by rule version and
  cross-tenant validation.
- **Effort / risk:** **L / Critical**.

### P1.3 DMS and audit extensibility

- **Status / priority:** **PLANNED / SHOULD**
- **Outcome:** explicit scalable domain links, classification, retention/legal
  hold/export, upload security pipeline, audit correlation/change metadata.
- **Prerequisites:** P0.1 storage/link ADR and P0.2 private storage.
- **Models/integration:** domain-owned explicit link tables or approved registry;
  do not use `GenericForeignKey`. Audit remains evidence, not notification bus.
- **UI:** document workspace, upload/scan state, version/source/audit visibility.
- **Testing/migration:** preserve document hashes and versions; link parity,
  permission, download, retention and malware-failure tests.
- **Effort / risk:** **M-L / High**.

## P2 — Accounting kernel

### P2.1 Ledger, fiscal periods, and posting registry

- **Status / priority:** **PLANNED / MUST before native financial go-live**
- **Outcome:** chart of accounts and dimensions; fiscal year/period; balanced
  immutable journal entries/lines; proposed vs posted state; numbering;
  close/reopen; reversal/replacement; source version and idempotency; opening
  balances; controlled posting-rule catalogue.
- **Prerequisites:** P0.1, P1.1, P1.2; product-owner decision on native books.
- **Ownership:** operational domains own source documents; Accounting alone owns
  journals. No posting from signals and no editable posted entries.
- **Integration:** initially controlled manual/opening journals and one pilot
  domain; add each producer only with its reconciliation contract.
- **Compliance:** professional review of Iranian accounting/tax book requirements;
  rule versions and fiscal locks.
- **UI/security:** Persian journal entry/review, balanced totals, dimension
  cascading, source drill-through, close/reopen and reversal reasons; strict SoD.
- **Migration/testing:** current `financials` read models remain projections;
  do not synthesize authoritative historical journals from demo totals. Property
  tests for balance/precision, concurrency/idempotency, close/reversal, tenant
  isolation, high-volume posting and migration rollback.
- **Effort / risk:** **XL / Critical**.

### P2.2 Accounting statements and close controls

- **Status / priority:** **PLANNED**
- **Outcome:** trial balance, general ledger, account turnover, balance sheet,
  profit/loss and controlled exports with drill-through and close checklist.
- **Prerequisites:** P2.1 stable postings and reconciled opening balances.
- **Data:** read models/caches are rebuildable; journal remains authoritative.
- **UI/testing:** filters state URL, Jalali period display, explicit currency,
  export permission/audit; statement tie-out and source-line lineage tests.
- **Effort / risk:** **L / High**.

## P3 — Treasury and subledgers

### P3.1 Treasury and bank reconciliation

- **Status / priority:** **PLANNED / MUST for native cash control**
- **Outcome:** bank/cash accounts, receipts/payments, transfers, cheque lifecycle,
  payment proposals, clearing, statement import, match suggestions, reconciliation,
  cash position and forecast.
- **Prerequisites:** P2.1; party bank profiles; object scope; async decision for
  statement/import jobs.
- **Migration:** contain/rename current `Payment`; map it only with explicit
  semantics. `PaymentAllocation` is not a journal line.
- **Integration:** AP/AR, claims, payroll, guarantees and Accounting postings.
- **UI/security:** sensitive account masking, maker-checker, batch approval,
  unmatched exception queue, bank evidence and reversal.
- **Testing:** duplicate import/idempotency, cheque/clearing states, match
  confidence, allocation caps, reconciliation and tenant isolation.
- **Effort / risk:** **XL / Critical**.

### P3.2 AP/AR obligations and settlement

- **Status / priority:** **PLANNED**
- **Outcome:** customer/supplier open items, due dates, credit/debit adjustments,
  allocations, aging, collection/payment status and subledger-to-GL reconciliation.
- **Prerequisites:** P2.1 and P3.1; producer contracts from Billing/Procurement.
- **Integration:** claims, supplier invoices, payroll liabilities, Treasury and GL.
- **Compliance/UI:** source document and tax identity snapshots; aging and
  settlement drill-through; controlled write-off/reversal.
- **Migration/testing:** reuse existing claim settlement evidence where semantic
  mapping is exact; reconciliation, over-allocation, void and closed-period tests.
- **Effort / risk:** **L / Critical**.

## P4 — Project costing and controls

### P4.1 Budget/CBS/cost center and integrated project cost

- **Status / priority:** **PLANNED / MUST**
- **Outcome:** accepted estimate-to-budget handoff, CBS/cost-center mappings,
  budget versions, commitments, accruals, actuals, forecast/ETC/EAC, variance,
  WIP and source drill-through.
- **Prerequisites:** P1.2; P2.1 dimension decision. Useful operational costing can
  start before all producers, but must not become a parallel ledger.
- **Migration:** retire `Project.estimated_budget`/`actual_budget` as authorities
  through expand/backfill/switch; preserve only clearly labelled snapshots if
  needed. Demo data need not block correction.
- **Integration:** Estimates, Contracts, Procurement, Inventory, Expenses,
  Payroll, Equipment, Claims and Accounting.
- **UI:** WBS/CBS mapping, baseline comparison, commitment/actual/paid distinction,
  exception-led forecast, source breadcrumb.
- **Testing:** mapping completeness, revision/concurrency, classification,
  multi-source reconciliation, Decimal/currency and volume tests.
- **Effort / risk:** **XL / Critical**.

### P4.2 Schedule, risk, change, and earned-value controls

- **Status / priority:** **PLANNED later**
- **Outcome:** schedule baseline/milestones/dependencies, risk register, change
  control, approved rebaseline and earned metrics where input discipline supports it.
- **Prerequisites:** P4.1, mature progress capture, owner decision on scheduler
  depth and integrations.
- **Boundary:** do not build a full Primavera replacement or BIM authoring tool.
- **Integration/UI/testing:** WBS/progress/contracts/cost/forecast; baseline/version
  comparison, critical exceptions, import validation and reproducible calculations.
- **Effort / risk:** **L-XL / High**.

## P5 — Source-to-pay

### P5.1 Sourcing and supplier invoice match

- **Status / priority:** **PLANNED**
- **Outcome:** RFQ, invited suppliers, versioned quotes, normalized comparison,
  sourcing approval/award, PO changes, service acceptance, supplier invoice,
  two/three-way match, tolerance and discrepancy workflow.
- **Prerequisites:** Parties/P1.2, P1.1, P4 cost coding; AP/GL for financial
  completion; workflow foundation already delivered.
- **Integration:** commitment to Project Cost, receipt to Inventory, invoice to
  AP/posting, payment proposal to Treasury, performance to partner profile.
- **Compliance/UI:** tax/invoice snapshots, attachment evidence; comparison grid,
  bid confidentiality, line-level match and exception queue.
- **Migration/testing:** existing PO/receipt remain valid; add links incrementally.
  Quote privacy, tolerance, duplicates, partial receipt/invoice, reversal and
  reconciliation tests.
- **Effort / risk:** **XL / High**.

## P6 — Contract, claim, guarantee, and revenue/cost control

### P6.1 Correct receivable Billing terms and accounting integration

- **Status / priority:** **PLANNED / MUST correction**
- **Outcome:** move retention/advance/insurance/other commercial rules to approved
  contract-term versions; apply effective regulatory versions; snapshot party,
  currency and rules; generate AR/posting proposals and taxpayer-invoice status.
- **Prerequisites:** P1.2; P2/P3 for posting/settlement; legal/accounting decision.
- **Migration:** map current `BillingPolicy` deliberately; pre-production claim
  data may be discarded/recreated, but finalized behavior changes need explicit
  migration and tests.
- **UI/testing:** calculation explanation and sources, amendment impact, prior
  certified quantities, deductions, correction/cancellation states; golden,
  rounding, cap, concurrency, version and reconciliation tests.
- **Effort / risk:** **L / Critical**.

### P6.2 Subcontracts, payable certificates, and guarantees

- **Status / priority:** **PLANNED**
- **Outcome:** subcontract/variation, measured work, payable certificate,
  retention/advance recovery, back-charge, insurance clearance, bid/performance/
  advance/retention guarantees, expiry/renewal/release and exposure.
- **Prerequisites:** P6.1 terms model, AP/Treasury, project costing, partner master.
- **Integration:** commitments/actuals, AP, Treasury, DMS, notifications,
  partner performance and Accounting.
- **Compliance/UI:** Article 38/clearance and guarantee rules require legal review;
  expiry workbench, exposure dashboard and evidence.
- **Testing:** contract caps, versioned terms, duplicate certification, releases,
  expired instruments, allocation and reconciliation.
- **Effort / risk:** **XL / Critical**.

## P7 — Time, payroll, and employee insurance

### P7.1 Attendance, timesheets, and labor costing

- **Status / priority:** **PLANNED**
- **Outcome:** work calendars/shifts, attendance import/manual correction,
  leave/absence, project/site/activity timesheets, approval, labor distribution.
- **Prerequisites:** Workforce, P1.1/P1.2, project/CBS coding, device/integration
  scope decision. Add master-backed daily labor links while retaining snapshots.
- **Integration:** Daily Reports, Payroll, Project Cost, workflow/audit.
- **UI/security:** mobile/site entry, supervisor bulk review, exception queue,
  employee privacy and scope.
- **Testing:** overlapping time, calendar/timezone, approval locks, import
  idempotency, allocation totals and cross-project access.
- **Effort / risk:** **L / High**.

### P7.2 Payroll, payroll tax, and employee insurance list

- **Status / priority:** **PLANNED / retained target scope**
- **Outcome:** effective employment/pay components, payroll run, arrears/
  adjustments, payslip, allocations, tax/insurance calculations, employee
  insurance-list generation/validation/status, liabilities and posting/payment.
- **Prerequisites:** P7.1; regulatory rule sets with legal review; P2/P3/P4;
  privacy/SoD model.
- **Compliance:** annual values and schemas are effective-dated data with source,
  review and applied-version snapshot; no constants. Confirm current Tax, Labor,
  Social Security, and filing requirements before release.
- **UI/security:** restricted payroll workspace, calculation explanation,
  preflight exceptions, dual approval, employee self-service only if approved.
- **Migration/testing:** no real history exists; prefer correct opening design.
  Golden cases, retroactivity, caps/rounding, run lock/reversal, file/schema,
  posting/reconciliation and privacy tests.
- **Effort / risk:** **XL / Critical**.

## P8 — Inventory, equipment, and fixed assets integration

### P8.1 Inventory valuation and operational depth

- **Status / priority:** **PLANNED**
- **Outcome:** reservations, issue/return to work, bins and optional lot/serial,
  counts/adjustments, approved valuation method, transfer-in-transit and GL/project
  cost reconciliation.
- **Prerequisites:** master UOM conversions, P4 coding, P2 posting; product-owner
  valuation and traceability decisions.
- **Migration/UI/testing:** retain quantity ledger; add valuation layers without
  inventing historical costs. Mobile scan/count, variance approval; quantity/value
  conservation, concurrency, reversal and close tests.
- **Effort / risk:** **XL / High**.

### P8.2 Equipment usage, fuel, maintenance cost, and fixed assets

- **Status / priority:** **PLANNED / fixed assets retained target scope**
- **Outcome:** meter readings, operators/certifications, fuel, downtime,
  preventive plans, usage rates, cost allocation; asset acquisition,
  capitalization, depreciation, impairment, transfer and disposal.
- **Prerequisites:** P4, P2, P8.1 where spare parts apply; accounting policy and
  distinction between operational `Equipment` and financial `FixedAsset`.
- **Integration:** Daily Reports, Inventory, Procurement/AP, Payroll, Project
  Cost, Accounting and DMS.
- **UI/testing:** mobile readings/scan, maintenance plan, asset register and source
  cost drill-through; meter monotonicity, schedule, depreciation/reversal,
  disposal and reconciliation.
- **Effort / risk:** **XL / High**.

## P9 — Field, HSE/Quality, knowledge, partner, support, and AI

### P9.1 Field operations and paperless evidence

- **Status / priority:** **PLANNED**
- **Outcome:** context-aware mobile daily capture, media/evidence, controlled
  offline drafts if justified, reviewed creation of progress/time/equipment/
  material facts, RFIs/submittals and correspondence where product fit is proven.
- **Prerequisites:** P1 scopes, P1.3 DMS, downstream ownership contracts.
- **Boundary:** field input proposes downstream records; it does not silently
  finalize payroll, claims, inventory, or journals.
- **UI/testing:** large touch targets, intermittent-network state, duplicate sync,
  conflict resolution, upload progress, accessibility, tenant/project isolation.
- **Effort / risk:** **L-XL / High**.

### P9.2 HSE/Quality extensions to governed knowledge

- **Status / priority:** **PLANNED**
- **Outcome:** inspections, risk/permit/toolbox processes, ITP/tests, formal CAPA,
  root-cause taxonomy, lesson candidates, reviewed publication and contextual reuse.
- **Prerequisites:** current incidents/issues, DMS, notifications and knowledge
  governance/privacy.
- **Integration:** workflow, project controls, partner performance, DMS and BI.
- **UI/testing:** site checklists, evidence, overdue action workbench, lesson
  provenance and acknowledgement; closed-history immutability and sensitive-case access.
- **Effort / risk:** **L / Medium-High**.

### P9.3 Partner performance and prequalification

- **Status / priority:** **PLANNED**
- **Outcome:** qualification, expiring evidence, approved vendor/category status,
  project evaluations and explainable delivery/quality/safety/commercial metrics.
- **Prerequisites:** mature party master, Procurement/Contracts/HSE/Quality facts,
  scope/privacy decision.
- **Boundary:** extend `BusinessParty`; avoid duplicate partner masters and opaque
  unchallengeable scores.
- **UI/testing:** evidence/expiry workbench, score drill-through, reviewer conflict
  controls and tenant isolation.
- **Effort / risk:** **L / Medium-High**.

### P9.4 Notifications, support ticketing, and AI support assistant

- **Status / priority:** **PLANNED**
- **Outcome:** tenant-aware in-app/email notification preferences and delivery;
  support cases with SLA, safe attachments and time-limited tenant access;
  knowledge-backed assistant with citations, feedback, escalation and audited
  reviewed actions.
- **Prerequisites:** P0.2 operations, DMS, audit correlation, knowledge governance,
  async/outbox and privacy/AI policy.
- **Boundary:** audit is not notification; AI cannot bypass permissions or directly
  finalize consequential actions. Domain services remain authoritative.
- **Libraries:** evaluate mature queue/email/LLM integration components; do not
  expose tenant data to a model without contract, retention and residency review.
- **UI/testing:** unified inbox/cartable distinction, delivery state, ticket
  timeline, AI source/confidence/confirmation; prompt injection, data leakage,
  permission, failure and human-escalation tests.
- **Effort / risk:** **L-XL / High**.

## P10 — Reporting, reconciliation, and first production certification

### P10.1 Governed metrics and management reporting

- **Status / priority:** **PLANNED**
- **Outcome:** semantic metric catalogue, project/portfolio dashboards, scheduled
  reports/exports, saved views, source drill-through and freshness indicators.
- **Prerequisites:** stable authoritative transactions from P2-P8 and explicit
  metric owner/definition. A separate warehouse is not assumed.
- **Integration:** rebuildable read models, reconciliation controls and DMS/export.
- **UI/testing:** Persian RTL dashboards, accessible charts and table fallback,
  currency/unit/period clarity; tie-out, lineage and permission tests.
- **Effort / risk:** **L / High**.

### P10.2 Reconciliation and close workbench

- **Status / priority:** **PLANNED / release-critical for affected modules**
- **Outcome:** estimate-budget, commitment, PO-receipt-invoice, inventory value,
  subledger-GL, bank, claim-settlement, payroll and asset reconciliations with
  aging, assignment, resolution evidence and reopen controls.
- **Prerequisites:** each producer/consumer pair stable; workflow foundation.
- **Data:** discrepancies are evidence-backed exceptions, not alternate balances.
- **UI/testing:** exception-driven workbench and drill-through; deliberately
  injected mismatch, rebuild and period-close acceptance tests.
- **Effort / risk:** **L / Critical**.

### P10.3 First production release certification

- **Status / priority:** **PLANNED / MUST**
- **Outcome:** certify only the explicitly selected release scope, not the entire
  long-term roadmap.
- **Prerequisites:** P0 gates; all MUST corrections affecting selected scope;
  legal/accounting/security approvals; reconciliations for every included
  financial flow.
- **Evidence:** clean build and locked dependencies, full PostgreSQL suite,
  migration and rollback rehearsal, restore test, RPO/RTO, performance budgets,
  tenant/object penetration review, storage/export/retention, observability and
  alert exercise, browser/mobile accessibility, runbooks, support/on-call,
  release/rollback decision owners.
- **Effort / risk:** **L / Critical**.

## Deferred until explicit triggers

| Capability | Trigger | Reason for deferral |
| --- | --- | --- |
| Cross-tenant business network/recommendations | Mature party governance, consent/privacy ADR, sufficient opted-in supply and abuse operations | High privacy, identity, moderation and cold-start cost |
| Shared canonical material/party catalogue | Proven tenant deduplication pain and governance owner | Cross-tenant merge/ownership risk |
| Marketplace/tender network | Network trust, legal/commercial model and fraud controls | Not required for core ERP integrity |
| Broad offline-first sync | Measured field connectivity need and conflict policy | High data-conflict/security complexity |
| Predictive AI/autonomous optimization | Stable governed data, measurable decision and human override | Current priority is authoritative data and traceability |
| Public/mobile API platform | Approved consumers, OAuth/security/version/SLA model | DRF is not required for current server-rendered product |
| Microservices/event sourcing | Demonstrated scaling/team/deployment boundary | Modular monolith is currently appropriate |
| General-purpose CRM/BPMN/BIM authoring | Proven strategic contractor use case unavailable from existing domains/integrations | Commodity breadth would dilute construction ERP focus |

## Product-owner decision register

The owner must decide, before the relevant phase: initial customer segment;
native vs integrated accounting boundary; initial statutory filing scope;
Rial-only vs multi-currency; inventory valuation method; payroll employment/pay
models and attendance providers; document signature/retention rules;
hosting/data-residency and RPO/RTO; project scope semantics; and future network
consent/business model. These are decision gates, not reasons to invent defaults.

## Roadmap governance

- `ROADMAP.md` governs delivery order and status, not detailed domain rules.
- The capability/readiness audit explains why; dedicated architecture documents
  define how after approval; models/migrations/tests define what exists.
- Update status only after implementation and acceptance evidence. Do not use a
  dated status snapshot as current authority.
- A future item remains unimplemented even when its target model is named here.
- Preserve unrelated working behavior. Use the pre-production window only for
  corrections with concrete ownership, integrity, security, compliance, or
  unavoidable future migration value.
