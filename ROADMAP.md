# Product Development Roadmap

**Status date:** 2026-09-24

**Product stage:** pre-production

**Purpose:** dependency-ordered delivery plan; a listed item is not implementation authorization

**Current/target audit:** `docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`

Construction ERP is a Persian-first, multi-tenant construction SaaS. Models,
migrations, services, and tests remain the source of truth for current behavior.
This roadmap separates delivered capability, pre-production corrections, and
future target scope. Only a separately approved work package may be implemented.

## Authoritative planning references

- `docs/architecture/DOMAIN_MODEL.md`: target bounded contexts and ownership.
- `docs/architecture/DATA_MODEL.md`: target data/source-of-truth and lineage rules.
- `docs/architecture/BUSINESS_MODEL.md`: customers, value, packaging, operation and non-goals.
- `docs/architecture/USER_CAPABILITY_MAP.md`: user groups, goals and capability disposition.
- `docs/architecture/WORKFLOW_AND_PERMISSION_MATRIX.md`: lifecycle, permission,
  scope and separation policy.
- `docs/architecture/DOMAIN_AND_DATA_MODEL.md` plus code/migrations: current implementation.
- `docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`: evidence, gaps and readiness.
- `docs/ui-guidelines.md`: authoritative UI/UX interaction and accessibility standard.

Execution companion: `docs/ROADMAP_EXECUTION_PLAYBOOK.md` translates an approved
work package into resource-aware sessions and model/reasoning guidance; it does
not authorize implementation or override roadmap scope/status.

When these sources disagree, current code defines what exists; the target
documents define approved direction; this roadmap defines sequencing/disposition.

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
| F5 Workflow & Work Management | **DELIVERED** | Versioned definitions, bounded registries, runtime, candidate/assignment/delegation history, work items/workbench with due/overdue and escalation routing, position routing, domain adoption, PostgreSQL acceptance gates. |
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
10. explicit rollout, observability, recovery, and operator ownership; and
11. a Build-vs-Reuse decision for generic technical capability: consider the
    Python standard library, Django/PostgreSQL built-ins, existing dependencies,
    then mature maintained libraries before justified custom code. Significant
    dependencies require security, maintenance, adoption, documentation,
    compatibility, SaaS-license, transitive-dependency, architecture-fit, and
    exit-risk review. Strategic construction-ERP rules remain product-owned.

## Dependency overview

```text
P0 Decisions + Security/Operations Foundations
 ├─> P0 Tenant Lifecycle + Existing-UI Remediation
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

### P0.3 SaaS plans, entitlements, quotas, and tenant offboarding

- **Status / priority:** **PLANNED / MUST before commercial SaaS launch**
- **Outcome:** versioned plan/feature entitlements; user/project/storage and other
  justified quotas; usage visibility; controlled grace/suspension/cancellation;
  tenant export, retention, legal hold, and offboarding evidence. Commercial
  subscription invoicing is not implied by this package and remains a product
  decision.
- **Prerequisites:** P0.1 tenant-lifecycle/support-access ADR, P0.2 storage/export
  operations, and product-owner packaging/limit decisions.
- **Ownership/integration:** Organizations owns entitlement state; every consuming
  domain enforces it server-side. Identity, storage, projects, jobs, export,
  support and audit consume the same authority rather than local feature flags.
- **UI/security:** plan/usage/limit explanation, safe upgrade/contact path, export
  readiness and cancellation consequences; suspension never weakens retention,
  audit, security or owner access needed for lawful export/offboarding.
- **Migration/testing:** default existing development tenants explicitly; test
  quota races, suspended mutations, cancellation/export/retention, tenant
  isolation and entitlement changes without deleting business history.
- **Effort / risk:** **L / Critical**.

### P0.4 Existing UI consistency and accessibility remediation

- **Status / priority:** **NEXT-CANDIDATE / SHOULD; release gate for selected screens**
- **Outcome:** inventory already delivered screens against `docs/ui-guidelines.md`
  and remediate by reusable pattern: tenant/project/site context, cascading and
  searchable choices, list/filter/table consistency, workflow/cartable actions,
  responsive/mobile behavior, disabled/error/empty/loading states, financial
  labels, keyboard/focus/accessibility, and source/audit visibility.
- **Prerequisites:** authoritative UI guidelines; coordinate context/permission
  behavior with P1.1. Remediation may proceed incrementally by user journey.
- **Boundary:** prioritize correctness, task completion, error prevention and
  accessibility. Do not cosmetically rewrite working screens, fork page-local
  components, or change backend behavior under a presentation task.
- **Validation:** representative browser/device and keyboard review, RTL/LTR and
  Jalali/Rial-Toman checks, template/component tests, permission-safe states and
  visual regression evidence where a maintained approach is justified.
- **Migration/integration:** no data migration by default; backend gaps discovered
  during review become separately approved domain work rather than hidden UI fixes.
- **Effort / risk:** **L incremental / Medium-High**.

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
  terms; governed UOM conversions; canonical roles and separation-of-duties
  policy. `BusinessParty` remains the single counterparty master and gains
  tenant-scoped duplicate detection/canonicalization, controlled merge with
  alias/identifier/history preservation, categories/tags, authorized
  representative/signatory evidence, tax/bank/legal/qualification profiles,
  qualification state, restriction/blacklist and violation history, enforced
  transaction restrictions, and inactive/archive lifecycle. Regulatory scope explicitly
  includes annual VAT/tax, taxpayer-invoice schema, payroll-tax, monthly employee
  insurance, contractor-insurance/clearance parameters, calendars and rounding;
  every unverified rule remains **«نیازمند بررسی قانونی»**.
- **Prerequisites:** P0.1 and legal/accounting source register.
- **Models:** `RegulatoryRuleSet`/version (final naming by design), contract term
  versions, party profile/representative/alias/merge/restriction evidence, UOM
  conversions, effective grants. Split the current `BillingPolicy` into its
  correct owners; do not create supplier/customer/subcontractor masters beside
  `BusinessParty`.
- **Integration:** Billing, Payroll, taxpayer invoices, Treasury, Procurement,
  Inventory, reporting; historical documents store applied versions/snapshots.
- **UI:** effective date, provenance, reviewer, impact preview, dual control,
  clear Rial/Toman and Jalali/Gregorian display; explain duplicate/merge and
  restriction decisions, including transaction-block reason and retained history.
- **Migration/testing:** pre-production data may be discarded/backfilled if that
  is safer, but migrations remain; golden calculations by rule version and
  cross-tenant validation. Test merge lineage, alias resolution, representative
  validity, inactive/archive selection and restriction enforcement without
  rewriting historical transactions.
- **Effort / risk:** **L / Critical**.

### P1.3 DMS and audit extensibility

- **Status / priority:** **PLANNED / SHOULD**
- **Outcome:** explicit scalable domain links; governed document numbering,
  classification and confidentiality; access expiry; retention/legal hold/export;
  upload security pipeline; OCR and permission-scoped full-text search; versioning
  and version comparison; electronic/digital-signature integration boundary;
  audit correlation/change metadata; and immutable processing provenance.
- **Prerequisites:** P0.1 storage/link ADR and P0.2 private storage.
- **Models/integration:** domain-owned explicit link tables or approved registry;
  do not use `GenericForeignKey`. Reuse the version/blob authority for drawings,
  inspection documents and media rather than create parallel file stores. Audit
  remains evidence, not notification bus. Signature trust/legal effect and
  provider choice require an explicit decision; do not implement cryptography.
- **UI:** document workspace, upload/scan/OCR/signature state, searchable content,
  version compare, source/audit visibility, retention/hold/export controls.
- **Testing/migration:** preserve document hashes and versions; link parity,
  permission and search isolation, download, retention/hold/export, OCR failure,
  signature verification-state and malware-failure tests.
- **Effort / risk:** **M-L / High**.

### P1.4 Material catalogue and UOM governance

- **Status / priority:** **PLANNED / SHOULD before advanced estimating, sourcing, and valuation**
- **Outcome:** governed canonical tenant material codes and aliases; UOM families
  and explicit conversions; category-specific technical/dynamic attributes;
  brand/model/manufacturer/country; substitutes/equivalents; effective price
  history with source/currency/unit; technical documents; and technical/quality
  approval states.
- **Prerequisites:** existing Material/UOM masters, P1.3 document boundary, and
  product decisions on coding, conversion precision and approval ownership.
- **Ownership/integration:** Materials owns identity, attributes and conversions;
  Procurement owns quotes/purchases, Inventory owns movements/valuation,
  Estimates owns rate usage, and Quality owns approval evidence. Transactions
  snapshot the applied identity/unit/rate; price history is not a financial ledger.
- **UI/security:** context-aware material search, code/name/brand display,
  conversion explanation, duplicate/merge review, substitute approval and
  technical-document status; tenant scope remains authoritative.
- **Migration/testing:** reconcile text-only material/unit snapshots incrementally;
  test conversion precision/direction, duplicate aliases, inactive/approved
  selection, source history and cross-tenant isolation.
- **Build-vs-Reuse:** evaluate maintained attribute/search/import components only
  for commodity mechanics; retain material governance and construction semantics.
- **Effort / risk:** **L / High**.

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
- **Outcome:** bank/cash accounts including petty cash; payment requests,
  scheduling and proposals; receipts, payments and bank transfers; employee/vendor
  advances and advance settlement; cheque lifecycle, clearing, statement import,
  match suggestions, reconciliation, cash position and cash-flow forecast.
- **Prerequisites:** P2.1; party bank profiles; object scope; async decision for
  statement/import jobs.
- **Migration:** contain/rename current `Payment`; map it only with explicit
  semantics. `PaymentAllocation` is not a journal line.
- **Integration:** AP/AR, claims, payroll, guarantees and Accounting postings.
- **Boundary:** Treasury owns cash movement and instruments; AP/AR owns
  obligations/open items; Accounting owns journals. Petty cash, advances,
  allocations and bank matches must not become competing ledgers.
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

### P4.0 Estimate, BOQ, and budget-preparation depth

- **Status / priority:** **PLANNED; delivered approval/revision baseline retained**
- **Outcome:** extend current approved revisions with side-by-side revision and
  scenario comparison; material/activity links; labor/material/equipment resource
  analysis; overhead, regional, mobilization and other governed coefficients;
  escalation/inflation assumptions; reusable rate/price sources; previewed Excel
  import; and licensed/versioned Iranian price-book (فهرست‌بها) import where the
  product owner approves a lawful source.
- **Prerequisites:** P1.4 material/UOM governance, existing Estimate lifecycle and
  workflow foundation, plus decisions on price-book licensing/version, coefficient
  policy, resource-rate ownership and Excel templates.
- **Source of truth:** distinguish contractual BOQ, internal estimate/scenario and
  approved budget baseline. An estimate revision is calculation evidence; only an
  explicit accepted handoff creates a P4.1 budget baseline.
- **Integration/accounting:** WBS/activity/material/equipment/workforce inputs feed
  estimating; P4.1 consumes the accepted output. Estimates never post journals or
  silently change contract value.
- **UI/security:** large accessible line grid, grouped resources/coefficients,
  comparison and assumption traceability, import mapping/preview/error report,
  protected rate/price-book access and explicit unit/currency.
- **Migration/testing:** retain approved revisions; add links/snapshots through
  expand/backfill/switch. Golden calculations, coefficient order/rounding,
  scenario/revision immutability, duplicate import, formula-free safe Excel parse,
  tenant scope and representative-volume tests.
- **Build-vs-Reuse:** evaluate mature spreadsheet parsers and safe tabular import;
  own BOQ, coefficient, scenario and budget-handoff rules.
- **Effort / risk:** **XL / High**.

### P4.1 Budget/CBS/cost center and integrated project cost

- **Status / priority:** **PLANNED / MUST**
- **Outcome:** accepted estimate-to-budget handoff, explicit mapping among
  contractual BOQ/internal estimate/approved budget baseline, CBS/cost-center
  mappings, budget versions, commitments, accruals, actuals, forecast/ETC/EAC,
  variance, WIP and source drill-through.
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
- **Outcome:** schedule baseline/milestones/dependencies; issue, constraint, risk
  and delay registers; change control; approved rebaseline; distinct physical and
  financial progress; and earned metrics where input discipline supports them.
- **Prerequisites:** P4.1, mature progress capture, owner decision on scheduler
  depth and integrations.
- **Boundary:** do not build a full Primavera replacement or BIM authoring tool.
- **Ownership boundary:** Project Controls owns schedule/baseline, issue,
  constraint, delay and integrated impact views; P6.4 owns contractual entitlement,
  contract-value change and EOT evidence.
- **Integration/UI/testing:** WBS/progress/contracts/cost/forecast; baseline/version
  comparison, critical exceptions, import validation and reproducible calculations.
- **Effort / risk:** **L-XL / High**.

### P4.3 Expense approval, allocation, and budget control

- **Status / priority:** **PLANNED; delivered immutable Expense baseline retained**
- **Outcome:** workflow-backed draft/submission/approval/return/void; required
  invoice/source evidence; direct/indirect classification; recurring-expense
  templates that create reviewable drafts; allocation across projects; explicit
  Project/WBS/Activity/CBS/CostCenter coding; employee/vendor settlement status;
  and budget/period/duplicate controls.
- **Prerequisites:** P1.1 object scope, P4.1 coding/budget, DMS evidence and
  workflow foundation; P2/P3 for journal, payable and cash settlement completion.
- **Ownership/integration:** Expenses owns operational cost evidence; AP owns
  liability, Treasury owns cash, Accounting owns journals, and Project Cost
  consumes classified approved/posted facts. Recurrence is a proposal schedule,
  not an automatically finalized expense.
- **Compliance/UI/security:** tax/e-invoice relevance is rule-versioned and
  «نیازمند بررسی قانونی»; source preview, split-allocation grid, budget warning vs
  hard-stop policy, maker-checker and sensitive-evidence access.
- **Migration/testing:** preserve existing recorded/void history; introduce new
  lifecycle through explicit compatibility/backfill. Test allocation totals,
  duplicate evidence, budget race, recurrence idempotency, reversal/settlement,
  posting reconciliation and tenant/project isolation.
- **Effort / risk:** **L / Critical**.

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

### P5.2 Controlled supplier and subcontractor portal

- **Status / priority:** **PLANNED after internal source-to-pay boundaries stabilize**
- **Outcome:** invite-scoped external collaboration for party profile/document and
  qualification-evidence submission, RFQ participation, versioned quotation,
  supplier invoice/supporting documents, subcontractor claim/evidence submission,
  clarification and status visibility.
- **Prerequisites:** P1.1 authorization/object scope, P1.3 DMS/security, P5.1,
  P6.2 for subcontract claims, P9.3 qualification, identity/onboarding and external
  support decisions. Portal users receive least-privilege capabilities, not normal
  tenant membership or cross-tenant discovery.
- **Ownership/integration:** internal domains remain authoritative and convert an
  external submission into a reviewed draft/version. This private bilateral portal
  is separate from the deferred public/cross-tenant business network.
- **UI/security:** Persian responsive external journey, invitation expiry,
  organization/context clarity, safe upload, submission receipt, correction loop,
  rate limiting, MFA/risk controls where justified and no internal notes leakage.
- **Testing:** invitation replay/expiry, party impersonation, bid confidentiality,
  object/tenant isolation, duplicate submission/idempotency, malware/failure,
  withdrawal/version history and internal approval handoff.
- **Effort / risk:** **L-XL / Critical**.

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
- **Outcome:** subcontract administration, measured work, payable certificate,
  retention/advance recovery, back-charge, insurance clearance, bid/performance/
  advance/retention guarantees, expiry/renewal/release and exposure.
- **Prerequisites:** P6.1 terms model, AP/Treasury, project costing, partner master.
- **Integration:** commitments/actuals, AP, Treasury, DMS, notifications,
  partner performance and Accounting.
- **Boundary:** subcontract contractual changes, claims and EOT use P6.4; this
  package owns payable certification and guarantee/clearance operations.
- **Compliance/UI:** Article 38/clearance and guarantee rules require legal review;
  expiry workbench, exposure dashboard and evidence.
- **Testing:** contract caps, versioned terms, duplicate certification, releases,
  expired instruments, allocation and reconciliation.
- **Effort / risk:** **XL / Critical**.

### P6.3 Iranian tax and contractor-compliance integration

- **Status / priority:** **PLANNED / legally gated**
- **Outcome:** apply effective VAT/tax codes; produce and track سامانه مؤدیان
  electronic-invoice original/correction/cancellation submissions where approved;
  manage contractor-insurance facts, deductions, مفاصاحساب/clearance evidence and
  expiry/status; and provide versioned statutory export/submission evidence.
- **Prerequisites:** P1.2 regulatory rule/version authority, P6.1 corrected claim
  terms and snapshots, P1.3 DMS, async/idempotency decision, credentials/security,
  and confirmation of launch filing scope. Payroll tax and monthly employee
  insurance lists remain in P7.2 but share the rule/source registry.
- **Compliance:** all schemas, rates, thresholds, calendars and filing behavior are
  effective-dated with source/reviewer and are **«نیازمند بررسی قانونی»** until
  verified against current official authorities. Preserve request, response,
  correction chain, retry and human-resolution evidence.
- **Integration/accounting:** approved commercial documents feed AR/AP and
  posting proposals; external acceptance does not rewrite the source document or
  replace subledger/GL reconciliation.
- **UI/security/testing:** preflight validation, transmission status/error queue,
  controlled correction/cancellation, credential isolation, correlation ID and
  audit; certified-schema fixtures, idempotent retry, provider outage, period/rule
  rollover and source-to-submission reconciliation tests.
- **Build-vs-Reuse:** use official/provider protocols and maintained security/
  transport components; never custom-build cryptography or authentication.
- **Effort / risk:** **XL / Critical**.

### P6.4 Contractual changes, claims, and extension of time

- **Status / priority:** **PLANNED after contract-term and project-control boundaries stabilize**
- **Outcome:** governed Site Instruction, Variation Order/Change Order,
  contractual Claim and Extension of Time lifecycles with versioned evidence,
  entitlement/approval, valuation and cost impact, schedule impact, contract-value
  impact, amendment relationship, and relevant contract insurance/policy evidence.
- **Boundary:** these are contractual change/entitlement records, not ordinary
  `ProgressClaim`/Payment Certificate processing. Approved measurement may support
  either flow, but neither silently changes the other, the contract value, budget,
  schedule baseline, AP/AR or journals.
- **Prerequisites/integration:** P1.2 term versions, P4.2 controls, P6.1/P6.2
  commercial boundaries, DMS, workflow and project-cost/forecast handoffs.
- **UI/testing:** linked instruction-to-claim/change/EOT timeline, evidence and
  impact comparison; duplicate claim, concurrent change, rejected/withdrawn claim,
  cap, approval, amendment, baseline and posting-handoff tests.
- **Effort / risk:** **L-XL / High**.

## P7 — Time, payroll, and employee insurance

### P7.0 Workforce skills, qualifications, development, and labor rates

- **Status / priority:** **PLANNED; delivered workforce structure retained**
- **Outcome:** governed skill/competency catalogue; employee proficiency and
  evidence; certificates/licenses with issuer, validity and expiry escalation;
  required/attended training; role/project competency requirements; explainable
  performance evaluations; effective labor rates/cost components; and complete
  effective responsibility/assignment history.
- **Prerequisites:** current Employee/Position/assignment model, P1.1 scope,
  P1.3 documents/notifications and product decisions on evaluation privacy,
  labor-rate visibility and HSE/QA qualification ownership.
- **Ownership/integration:** Workforce owns employee capability/effective history;
  HSE/Quality references qualification requirements, P7.1 time references the
  effective assignment, Payroll owns pay calculation, and Project Cost consumes
  approved labor-cost distributions. Performance is not an authorization source.
- **UI/security:** expiry/training exception workbench, competency gap view,
  evidence and effective-history timeline; restrict compensation, evaluations and
  personal documents through dedicated permissions and project scope.
- **Migration/testing:** preserve existing assignment history; test date overlap,
  expired qualification routing, rate-version selection, privacy/export,
  evaluation evidence and cross-tenant/project isolation.
- **Effort / risk:** **L / High**.

### P7.1 Attendance, timesheets, and labor costing

- **Status / priority:** **PLANNED**
- **Outcome:** holiday/work calendars, shifts, site `AttendanceRecord`, device/file
  import and controlled manual correction; leave, mission and overtime; plus
  project/site/activity timesheets, approval and labor-cost distribution.
- **Prerequisites:** Workforce, P1.1/P1.2, project/CBS coding, device/integration
  scope decision. Add master-backed daily labor links while retaining snapshots.
- **Integration:** Daily Reports, Payroll, Project Cost, workflow/audit.
- **Boundary:** attendance records when a person was present; timesheets record
  where/how approved time was consumed. Payroll consumes approved time/attendance
  facts and adjustments rather than inventing or rewriting attendance history.
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
- **Outcome:** project/activity reservations and release; reorder-point/shortage
  policy and alerts; barcode/QR capture; bins; expiry where applicable; lot/batch
  and serial traceability where justified; physical/cycle count; issue/return to
  work; two-sided transfer dispatch/acceptance and in-transit state; approved
  valuation method; and GL/project-cost reconciliation.
- **Prerequisites:** master UOM conversions, P4 coding, P2 posting; product-owner
  valuation and traceability decisions.
- **Migration/UI/testing:** retain quantity ledger; add optional traceability and
  valuation layers without inventing historical costs. Mobile scan/count,
  reservation/shortage/expiry queues, transfer acceptance and variance approval;
  barcode uniqueness, lot/serial/expiry, reservation availability, count freeze,
  transfer custody, quantity/value conservation, concurrency, reversal and close tests.
- **Effort / risk:** **XL / High**.

### P8.2 Equipment usage, fuel, maintenance cost, and fixed assets

- **Status / priority:** **PLANNED / fixed assets retained target scope**
- **Outcome:** meter readings; operator qualification; equipment insurance,
  inspection and permit/license evidence with expiry; fuel, downtime, preventive
  maintenance plans, usage rates and cost allocation; asset acquisition,
  capitalization, depreciation, impairment, transfer and disposal.
- **Prerequisites:** P4, P2, P8.1 where spare parts apply; accounting policy and
  distinction between operational `Equipment` and financial `FixedAsset`.
- **Integration:** Daily Reports, Inventory/spare parts, Procurement/AP, Payroll,
  Project Cost, Accounting, DMS and expiry notifications/workbench.
- **UI/testing:** mobile readings/scan, maintenance plan, asset register and source
  cost drill-through; meter monotonicity, schedule, depreciation/reversal,
  disposal and reconciliation.
- **Effort / risk:** **XL / High**.

## P9 — Field, HSE/Quality, knowledge, partner, support, and AI

### P9.1 Field operations and paperless evidence

- **Status / priority:** **PLANNED**
- **Outcome:** context-aware mobile daily capture with structured weather, work
  fronts, visits, meetings, instructions, photos/video and source evidence;
  previous-day/template reuse; optional voice-assisted reviewed transcription;
  QR/barcode capture; and reviewed creation of progress/time/equipment/material
  facts. Operational document control covers Transmittal, RFI, Submittal, Method
  Statement, drawings/revisions/review, and inspection documents when approved.
- **Prerequisites:** P1 scopes, P1.3 DMS/search/version/signature boundary, P1.4
  materials, downstream ownership contracts and explicit offline/media decisions.
- **Boundary:** field input proposes downstream records; it does not silently
  finalize payroll, claims, inventory, or journals. `MediaAsset`/album/gallery
  behavior, thumbnails and previews must reuse the DMS blob/version/security
  authority rather than create a duplicate document store.
- **Integration/UI/testing:** visits/meetings/instructions retain actor/source and
  project context; QR/voice/OCR suggestions require confirmation. Use large touch
  targets, camera/upload progress, media gallery, intermittent-network state,
  duplicate sync, conflict resolution, accessibility and tenant/project isolation.
  Broad offline-first sync remains deferred unless the measured use case justifies it.
- **Effort / risk:** **L-XL / High**.

### P9.2 HSE/Quality extensions to governed knowledge

- **Status / priority:** **PLANNED**
- **Outcome:** HSE risk register, inspections, permit-to-work, toolbox meetings,
  PPE controls, training/qualification checks, witnesses, investigation/root cause,
  CAPA, due-date/escalation and performance metrics; plus QA/QC ITP, Inspection
  Request, checklists, laboratory/material/sample tests and approvals, Punch List,
  NCR/rework, root cause, CAPA and independent verification/closure. Closed cases
  generate reviewed knowledge candidates rather than automatic guidance.
- **Prerequisites:** current incidents/issues, DMS, notifications and knowledge
  governance/privacy; P7.0 qualification facts and P1.4 material approvals where used.
- **Integration:** workflow, project controls, workforce qualification, material
  approval, partner performance, DMS, P9.5 knowledge and BI.
- **UI/testing:** mobile inspections/checklists, witness/evidence, risk matrix,
  overdue/escalation and verification workbenches, metric drill-through and lesson
  provenance; closed-history immutability, separation of reporter/closer where
  required, due-date escalation and sensitive-case access.
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

### P9.4 Notifications and support platform

- **Status / priority:** **PLANNED**
- **Outcome:** tenant-aware in-app/email notification preferences and delivery,
  provider-backed SMS only for an approved justified use case, rule-based reminders
  and escalation delivery over existing work-item due/overdue facts, calendar
  aggregation, scheduled operational-task proposals, supervisory workbench and
  permission-safe bulk actions; support cases
  with SLA, `KnownIssue`/`FeatureRequest` classification, release/
  version linkage, Knowledge Base, page/module/object-aware issue reporting,
  correlation ID and permission-safe diagnostics, safe attachments, time-limited
  approved tenant support access, escalation and SLA analytics.
- **Prerequisites:** P0.2 operations, DMS, audit correlation, knowledge governance,
  async/outbox and privacy policy.
- **Boundary:** delivered workflow/work items, candidacy, due dates, overdue state,
  escalation routing and time-bounded delegation remain authoritative; delegation
  is the substitution mechanism unless a distinct policy is later approved within
  that same assignment history. Notifications and calendar views do not create a
  second task/workflow engine. Scheduled jobs and bulk actions invoke
  ordinary authorized domain services and retain per-item results. Audit is not
  notification.
- **Libraries:** evaluate mature queue/email integration components; no package is
  pre-approved.
- **UI/testing:** unified inbox/cartable distinction, delivery state, ticket
  timeline, known-issue/release status, diagnostic consent, support-access timer,
  SLA view; data leakage, stale knowledge, permission, delivery failure and
  human-escalation tests.
- **Effort / risk:** **L / High**.

### P9.5 Enterprise knowledge management and reuse

- **Status / priority:** **PLANNED after knowledge-producing workflows stabilize**
- **Outcome:** governed `LessonLearned`, `BestPractice`, `TechnicalNote`,
  `Procedure`, `KnowledgeArticle` and `CaseStudy` concepts; project-closeout
  knowledge review; repeated-issue and recurring-root-cause detection; reviewed
  promotion from Lesson to Procedure, Checklist, System Control, Training or
  Partner Performance input; contextual discovery, acknowledgement and reuse/
  effectiveness tracking.
- **Prerequisites:** P1.3 search/DMS, P9.2 HSE/QA taxonomy and evidence, project
  closeout ownership, P9.3 partner metrics and notification/search capability.
- **Ownership/integration:** source domains retain case truth; Knowledge owns
  reviewed reusable publication/version. Derived recurrence is explainable and
  links every contributing case. Publishing a control/training/evaluation invokes
  that owning domain's ordinary approval, never generic mutation.
- **UI/security:** author/reviewer/publisher roles, source citations, sensitivity/
  audience, effective/review/expiry dates, related-context suggestions and reuse
  feedback. Any AI clustering/summarization remains governed by the deferred AI
  capabilities and cannot publish knowledge.
- **Testing:** provenance completeness, version immutability, permission/search
  isolation, recurrence reproducibility, promotion approval, expiry/review,
  retraction and reuse-metric lineage.
- **Effort / risk:** **L / High**.

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
  subledger-GL, bank, claim-settlement and asset reconciliations; plus Employee
  Insurance List-to-payroll, payroll/insurance liabilities-to-Accounting,
  payroll/insurance payments-to-Treasury, Treasury bank/cash-to-GL, and contractor
  insurance/clearance-to-Contract/AP/Accounting reconciliation. Every exception
  has aging, assignment, resolution evidence and reopen controls.
- **Project closeout:** coordinate a status/checklist view over domain-owned
  contract closeout, outstanding claims/issues, document completeness,
  asset/material disposition where relevant, financial reconciliation, reviewed
  lessons learned/knowledge, and final project-performance reporting. This is not
  a generic closeout engine and does not duplicate domain balances or documents.
- **Prerequisites:** each producer/consumer pair stable; workflow foundation;
  closeout evidence from Contracts, DMS, Inventory/Equipment, P9.5 Knowledge and
  affected financial domains.
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
| Controlled B2B network and intelligence | Mature party/qualification governance, consent/privacy ADR, verified relationships, sufficient opt-in density, abuse/moderation and legal/commercial operations | Preserve future tenant recommendations, supplier/subcontractor discovery, RFQ/tender network, equipment/capacity and surplus-material marketplaces, group procurement, consortium/JV discovery, shared qualification, consented trust/reputation network, anonymous benchmarking and anonymized price/lead-time/performance intelligence; high privacy, identity, competition, trust and cold-start risk keeps the program deferred |
| Shared canonical material/party catalogue with tenant overlay | Proven cross-tenant deduplication/search pain, catalogue stewardship, merge/dispute/version model and consent decision | P1.4 provides tenant catalogues first; cross-tenant identity/overlay creates ownership, privacy and incorrect-merge risk |
| Enterprise SSO/federated identity (OIDC/SAML) | Proven enterprise customer demand, approved IdP/account-linking and tenant-discovery model, recovery/offboarding controls, and accepted MFA/assurance policy | MFA remains an independent privileged-access control; integrate a trusted maintained identity implementation rather than custom-build OAuth/OIDC/SAML protocols |
| Broad offline-first synchronization | Measured field connectivity need, bounded data set, device-loss policy and deterministic conflict model | P9.1 may preserve local drafts; general bidirectional sync has high conflict/security/operational complexity |
| AI Support Assistant | P10 core production certification, stable P9.4 support and P9.5 knowledge authorities, approved AI privacy/residency/retention policy, evaluated retrieval quality and authorization-safe diagnostics | Preserve cited troubleshooting, safe diagnostic gathering and human escalation, but stabilize the support platform and authoritative knowledge first; AI cannot bypass permissions or finalize consequential actions |
| Future governed ERP Assistant | Stable P10 semantic/read-model APIs, P9.5 tenant knowledge, AI privacy/residency policy, evaluated accuracy and authorization-safe tool contracts | Preserve natural-language management queries, KPI explanation, tenant-knowledge queries and guided operations, but prohibit unrestricted SQL and autonomous consequential actions; authoritative data and controls must stabilize first |
| GIS and map platform | Verified logistics, geofencing, portfolio/site-risk or spatial-analysis use case plus privacy/accuracy policy | Lightweight project/site coordinates may be approved separately; heavy GIS infrastructure is unjustified without spatial workflows |
| Equipment GPS/telematics | Proven fleet-utilization, geofence, theft-control or automated-meter need; approved device/provider contract, consent/privacy, retention, accuracy and failure model | P8.2 provides governed manual/imported usage, meter and cost facts first; premature live telemetry adds integration, privacy and operational burden |
| Predictive AI/autonomous optimization | Stable governed data, measurable decision and human override | Current priority is authoritative data and traceability |
| Public/mobile API platform | Approved consumers, OAuth/security/version/SLA model | DRF is not required for current server-rendered product |
| Microservices/event sourcing | Demonstrated scaling/team/deployment boundary | Modular monolith is currently appropriate |

## Rejected / not recommended under the current product strategy

| Capability | Disposition and reason |
| --- | --- |
| General-purpose CRM, tenant-authored BPMN/code, or BIM authoring suite | **REJECTED.** These dilute construction ERP ownership, expand the attack/support surface, and duplicate specialist products. Integrate with approved systems when a concrete workflow requires it. |
| Custom cryptography, password primitives, OAuth/OIDC/SAML or other security protocols | **REJECTED.** Use trusted maintained implementations and platform/framework capabilities after security and license review. |
| Parallel workflow engines, financial ledgers, partner/material masters, document stores, or KPI authorities inside consuming domains | **REJECTED.** They violate the single-source-of-truth and reconciliation model. |
| Unrestricted SQL/chatbot access or autonomous consequential AI actions | **REJECTED.** Use permission-scoped semantic/read APIs, cited output, validation and explicit human confirmation through ordinary domain services. |
| Feature-by-feature microservices or event sourcing without demonstrated constraint | **NOT RECOMMENDED.** The modular monolith is the preferred boundary; reconsider only under the deferred trigger above. |

## Product-owner decision register

The owner must decide, before the relevant phase: initial customer segment;
native vs integrated accounting boundary; initial statutory filing scope;
Rial-only vs multi-currency; inventory valuation method; payroll employment/pay
models and attendance providers; document signature/retention rules;
hosting/data-residency and RPO/RTO; project scope semantics; SaaS plans/limits and
whether commercial subscription billing is in-product; BOQ/price-book licensing,
coefficient and import-template policy; material coding/catalogue stewardship;
external portal identity/onboarding; electronic-signature legal/provider scope;
enterprise SSO trigger and IdP/account-linking/MFA policy; notification channels
including any SMS use; contractual claim/change/EOT governance; project-closeout
acceptance ownership; GIS/offline/media/equipment-telematics scope; AI provider/
data-residency/tool permissions; and future network consent/business model. These
are decision gates, not reasons to invent defaults.

## Roadmap governance

- `ROADMAP.md` governs delivery order and status, not detailed domain rules.
- The capability/readiness audit explains why; dedicated architecture documents
  define how after approval; models/migrations/tests define what exists.
- Update status only after implementation and acceptance evidence. Do not use a
  dated status snapshot as current authority.
- A future item remains unimplemented even when its target model is named here.
- Reuse commodity technical capability and own strategic ERP logic. Apply the
  Build-vs-Reuse order and dependency criteria in the mandatory delivery contract;
  no named candidate or roadmap entry pre-approves a package.
- Every accepted capability must remain scheduled in one work package, explicitly
  deferred with a trigger, or rejected/not recommended with a reason. Reconcile
  coverage when target-scope documents or product decisions change.
- Preserve unrelated working behavior. Use the pre-production window only for
  corrections with concrete ownership, integrity, security, compliance, or
  unavoidable future migration value.
