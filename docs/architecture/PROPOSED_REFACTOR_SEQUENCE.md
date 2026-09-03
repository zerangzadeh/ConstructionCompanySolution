# Proposed Incremental Refactor Sequence

> Planning baseline: repository inspected on 2026-09-03  
> Target: approved Construction ERP Domain Model v1.0 in `AGENTS.md`  
> Constraint: every phase must be independently testable, deployable, and
> reversible before a later contract/removal migration.

## 1. Sequencing principles

1. Preserve the modular Django monolith, Django templates, service layer,
   SQL Server, UUID identifiers, Decimal values, and existing tenant resolution.
2. Close tenant/admin/history bypasses before adding many new cross-domain FKs.
3. Introduce shared master data before dependent transactions.
4. Use **EXPAND -> BACKFILL/MIGRATE -> SWITCH READS/WRITES -> VALIDATE ->
   CONTRACT** for every existing field replacement.
5. Treat a contract/removal migration as a later, separately approved deployment.
6. Preserve historical text snapshots even after adding relational identities
   when those snapshots explain what users originally entered.
7. Do not infer structured history from narrative text unless deterministic
   mapping rules are approved.
8. Keep service boundaries explicit; do not introduce a generic repository,
   workflow engine, CQRS, event sourcing, microservices, DRF, React, Celery/Redis,
   a database replacement, general ledger, or payroll engine.

## 2. Dependency-driven overview

```text
R0 Baseline
 └─> R1 Tenant/history hardening
      ├─> R2 OrganizationSettings
      ├─> R3A BusinessParty
      └─> R3B UnitOfMeasure
           └─> R4 Material master

R1 + R3B ─> R5 Project controls
R4 + R5  ─> R6 DailyReport evolution (material/activity/delay)
R3A + R3B + R5 ─> R7A Contract evolution ─> R7B Estimate evolution
R3A + R7A ─> R8 Expense/Payment references and allocations
R1 + projects ─> R9 Workforce ─> daily labor integration
R3A + R4 + R5 + R9 ─> R10 Procurement
R4 + R10 ─> R11 Inventory
R5 + R9 ─> R12 Equipment ─> daily equipment integration
R7A + R8 + R5 ─> R13 Billing / Progress Claims
Stable target identities ─> R14 Documents v2
Approved requirements only ─> R15 Safety / Quality
```

R3 and R7 are expressed as A/B work packages because the paired domains have
different dependencies and must remain independently deployable. R6 intentionally
does not force team/equipment links before R9/R12 exist; it keeps legacy snapshot
fields until those later phases.

## 3. Phase plans

## R0 — Baseline validation

- **Objective:** establish a reproducible pre-refactor baseline for schema,
  migrations, tenant invariants, tests, and SQL Server behavior.
- **Why needed:** later data migrations need a trusted source-state and measurable
  regression boundary; the working repository has real migrations and may have
  development data.
- **Prerequisites:** approved database credentials in the environment and a safe
  development/test database; no schema changes.
- **Apps affected:** all installed apps, read-only validation only.
- **Models added:** none.
- **Models modified:** none.
- **Services affected:** none.
- **Migrations required:** none; run migration-plan/history checks only.
- **Backfill needs:** none. Produce integrity counts for cross-tenant FK chains,
  lifecycle metadata, duplicate legacy names/units, and unmapped statuses.
- **Legacy compatibility:** capture fixtures/counts and current route/report
  behavior without changing it.
- **Tenant risks:** scans must be read-only and results must not expose sensitive
  tenant data; prefer counts and UUIDs over names.
- **Business risks:** a failing baseline can obscure whether a later phase caused
  a regression.
- **Tests required:** `manage.py check`, complete pytest suite, Ruff checks,
  migration graph/plan, and targeted SQL Server execution. Record exact results.
- **Acceptance criteria:** clean system check; understood migration graph; test and
  lint baseline recorded; current integrity exceptions enumerated and triaged.
- **Out of scope:** any fix, model change, migration generation, or data repair.
- **Primary type:** REFACTOR preparation.

## R1 — Tenant isolation and finalized-history hardening

- **Objective:** make existing service, admin, model-validation, and finalized
  state boundaries safe before adding new relationships.
- **Why needed:** current user-facing services are scoped, but admin/direct-save
  paths can create cross-tenant links and silently change approved/posted data.
- **Prerequisites:** R0 baseline and explicit decision on whether admin is
  superuser-operations-only or tenant-staff-facing.
- **Apps affected:** organizations, projects, contracts, estimates, expenses,
  payments, documents, daily_reports, audit, financials.
- **Models added:** none expected.
- **Models modified:** only narrowly scoped validation/constraint changes if
  approved after integrity scan; do not introduce a generic base domain model.
- **Services affected:** reusable explicit same-organization and hierarchy checks;
  contract/daily/estimate final-state guards; audit actor-scope assertion.
- **Migrations required:** only if practical check constraints are added for local
  lifecycle invariants. Cross-table tenant equality generally remains an
  application/service invariant on SQL Server.
- **Backfill needs:** repair pre-existing inconsistent rows only through a separate
  reviewed data migration; never silently reassign tenant ownership.
- **Legacy compatibility:** route/form behavior remains; admin may become scoped
  or read-only rather than changing public workflows.
- **Tenant risks:** HIGH; this phase directly addresses the highest-impact bypass
  surface. Admin FK choices, inline saves, and queryset visibility require tests.
- **Business risks:** locking previously editable finalized records may affect
  informal correction habits; document the supported void/revision path.
- **Tests required:** every tenant-owned FK with tenant A/tenant B combinations;
  admin queryset/choice/save tests; direct mutation attempts; approval/post/void
  concurrency; no regression in normal services.
- **Acceptance criteria:** no supported write path creates a cross-tenant
  relationship; finalized rows cannot be silently edited through UI/admin;
  tenant-scoped reads remain correct; all current workflows pass.
- **Out of scope:** new party/material/workforce models and broad permission-engine
  redesign.
- **Primary type:** REFACTOR.

## R2 — OrganizationSettings

- **Objective:** introduce one organization-owned settings record without
  destabilizing Organization identity or access resolution.
- **Why needed:** v1.0 places tenant configuration such as timezone, currency,
  fiscal settings, and numbering policy in an explicit settings boundary.
- **Prerequisites:** R1 tenant guard patterns; decisions on required settings and
  defaults.
- **Apps affected:** organizations; consumers only after settings is populated.
- **Models added:** OrganizationSettings.
- **Models modified:** Organization may gain a convenience relation only; keep
  timezone/currency columns during compatibility.
- **Services affected:** get/create defaults and authorized settings update with
  audit; current organization creation should create settings atomically after
  the additive migration is deployed.
- **Migrations required:** schema expansion, nullable/default-safe population,
  data migration, then one-to-one/non-null validation where appropriate.
- **Backfill needs:** one settings row per organization from current timezone and
  currency, plus approved defaults for new fields.
- **Legacy compatibility:** reads fall back to Organization columns until complete;
  dual-write only if both columns remain mutable during transition.
- **Tenant risks:** settings must always be resolved from active organization,
  never an organization ID from the request.
- **Business risks:** wrong timezone/currency defaults corrupt presentation and
  numbering; values require validation before switch.
- **Tests required:** atomic organization creation, one-per-tenant, fallback and
  switched reads, permissions, audit, isolation, and suspended/cancelled behavior.
- **Acceptance criteria:** every organization has exactly one settings record;
  current outputs are unchanged; no cross-tenant settings access.
- **Out of scope:** subscription billing, generic feature-flag service, and quotas
  not backed by approved requirements.
- **Primary type:** BOTH.

## R3A — BusinessParty, PartyRole, and PartyContact

- **Objective:** establish a tenant-owned counterparty master before converting
  contracts, expenses, payments, procurement, or billing.
- **Why needed:** repeated names cannot support reliable identity, roles, contacts,
  or tenant-safe relationships.
- **Prerequisites:** R1; approved party-kind, matching, duplicate, role, and archive
  rules.
- **Apps affected:** introduce a clearly owned parties app (or another explicitly
  approved domain owner); contracts/expenses/payments remain unchanged initially.
- **Models added:** BusinessParty, PartyRole, PartyContact.
- **Models modified:** none in the first deployable expansion.
- **Services affected:** create/update/archive party, assign role, manage primary
  contact, and tenant-scoped search/matching.
- **Migrations required:** additive schema and constraints; no legacy column
  changes.
- **Backfill needs:** produce reviewable per-tenant candidates from
  `counterparty_name` and `vendor_name`; do not auto-link ambiguous values.
- **Legacy compatibility:** all current screens continue using text until each
  consumer's later phase.
- **Tenant risks:** parties/roles/contacts are tenant owned; uniqueness and all FK
  chains must include or validate organization.
- **Business risks:** over-aggressive name normalization can merge distinct legal
  parties; under-aggressive matching can create duplicates.
- **Tests required:** scoped uniqueness, roles, primary contacts, archive, matching
  ambiguity, permissions, admin scope, and tenant isolation.
- **Acceptance criteria:** party master is independently usable; candidates and
  ambiguity metrics are available; no current transaction behavior changes.
- **Out of scope:** changing Contract, Expense, Payment, PurchaseOrder, or claim
  writes.
- **Primary type:** NEW DEVELOPMENT.

## R3B — UnitOfMeasure

- **Objective:** create the canonical unit vocabulary needed by materials,
  activities, estimate/contract lines, and daily usage.
- **Why needed:** current free-text units are inconsistent and cannot safely drive
  quantity behavior.
- **Prerequisites:** R1 and a business decision on global versus tenant-owned UOMs,
  alias rules, precision, and whether conversions are in v1.0 scope.
- **Apps affected:** a materials/shared-reference owner; no consumer app switches
  in the first deployment.
- **Models added:** UnitOfMeasure.
- **Models modified:** none initially.
- **Services affected:** controlled listing, lookup, activation/archive, and alias
  resolution if approved.
- **Migrations required:** additive catalog schema and seed/data migration.
- **Backfill needs:** inventory distinct EstimateItem and daily material unit
  strings; prepare reviewed aliases without updating consumers yet.
- **Legacy compatibility:** text units remain authoritative until consumer phases.
- **Tenant risks:** ownership policy must be explicit; a mixed global/tenant model
  must prevent one tenant from editing global units.
- **Business risks:** incorrect conversion assumptions can alter quantities; do
  not implement conversion without requirements.
- **Tests required:** uniqueness, symbol normalization, precision, ownership,
  archive, and lookup isolation.
- **Acceptance criteria:** approved units and aliases cover agreed current values;
  current estimates/reports remain unchanged.
- **Out of scope:** generic measurement/conversion engine.
- **Primary type:** NEW DEVELOPMENT.

## R4 — Material master

- **Objective:** introduce MaterialCategory and Material using the approved UOM
  policy.
- **Why needed:** daily material usage, procurement, and inventory need a canonical
  material identity.
- **Prerequisites:** R3B; category hierarchy and material uniqueness decisions.
- **Apps affected:** new materials domain owner; daily_reports remains compatible.
- **Models added:** MaterialCategory, Material.
- **Models modified:** none during initial expansion.
- **Services affected:** category/material create/update/archive, dependency-safe
  UOM changes, and tenant-scoped search.
- **Migrations required:** additive schemas and tenant-scoped constraints.
- **Backfill needs:** reviewed material candidates from daily entry names plus UOM;
  do not merge differing specifications.
- **Legacy compatibility:** daily names/units remain unchanged until R6.
- **Tenant risks:** material and category organizations must agree; UOM ownership
  policy must be enforced.
- **Business risks:** material identity/code rules can vary by contractor and need
  business confirmation.
- **Tests required:** scoped uniqueness, category/UOM relationships, archive,
  permissions, admin scope, and isolation.
- **Acceptance criteria:** material master is deployable independently and can map
  agreed legacy candidates without changing daily reports.
- **Out of scope:** stock quantities, purchasing, valuation, and warehouse logic.
- **Primary type:** NEW DEVELOPMENT.

## R5 — Project controls: cost centers, WBS, activities, baselines, progress

- **Objective:** add project-control structures while preserving existing
  Project -> Site -> Phase semantics.
- **Why needed:** procurement, contract lines, progress, billing, and structured
  daily work require common project scope and control references.
- **Prerequisites:** R1, R3B, and approved definitions separating phase, WBS,
  activity, and cost center.
- **Apps affected:** projects (or an explicitly approved project_controls app),
  audit.
- **Models added:** CostCenter, WBSNode, Activity, ProjectBaseline, ProgressRecord.
- **Models modified:** Project/Site/Phase only for optional reverse navigation or
  validated references; no replacement.
- **Services affected:** hierarchy/cycle-safe WBS management, activity lifecycle,
  baseline version/approval, and progress recording/correction.
- **Migrations required:** additive schemas, scoped uniqueness/indexes, and any
  later nullable references.
- **Backfill needs:** none from phases or narrative progress unless business
  mapping is explicitly approved.
- **Legacy compatibility:** existing projects, phases, reports, and financial pages
  continue without WBS data.
- **Tenant risks:** organization/project/parent/site/phase chains require explicit
  same-tenant validation and admin restrictions.
- **Business risks:** conflating phase with WBS or overwriting approved baselines
  would create inaccurate history.
- **Tests required:** WBS cycle prevention, hierarchy scope, baseline versioning
  and immutability, Decimal progress, concurrency, permissions, and isolation.
- **Acceptance criteria:** empty controls are optional for existing projects;
  approved baselines are immutable; quantitative progress is auditable and scoped.
- **Out of scope:** scheduling optimizer, earned-value engine, and external project
  management integrations.
- **Primary type:** NEW DEVELOPMENT.

## R6 — DailyReport evolution

- **Objective:** add structured DailyActivity, material integration, and
  DelayEvent while preserving current report records and workflow.
- **Why needed:** DailyReport is the main operational source and can consume the
  stable Material/UOM/Activity masters now available.
- **Prerequisites:** R4 and R5; approved correction policy for approved reports.
- **Apps affected:** daily_reports, projects/materials, audit.
- **Models added:** DailyActivity and DelayEvent.
- **Models modified:** DailyReport and DailyReportMaterialEntry; add nullable
  material/UOM references and keep text snapshots. Labor/equipment names remain
  untouched until R9/R12.
- **Services affected:** draft-only structured entry creation, hierarchy checks,
  submit/approve lock across all children, and explicit correction behavior.
- **Migrations required:** additive child schemas and nullable FKs; later validated
  constraints after mapping.
- **Backfill needs:** reviewed material/UOM links only. Do not parse
  work/progress/delay narratives into structured rows.
- **Legacy compatibility:** existing text sections and URLs remain; new sections
  are optional during rollout.
- **Tenant risks:** report/project/site/phase/activity/material chains must all
  match; child admin saves cannot bypass checks.
- **Business risks:** structured totals must not double-count narrative data;
  approved history must remain stable.
- **Tests required:** current workflow regression, material/UOM/activity scope,
  draft/final locks, backfill parity, permissions, concurrency, and isolation.
- **Acceptance criteria:** old reports render identically; new reports can record
  structured activities/materials/delays; approved reports cannot be silently
  changed.
- **Out of scope:** team links, equipment links, SafetyIncident, QualityIssue,
  and automatic progress posting unless separately approved.
- **Primary type:** BOTH.

## R7A — Contract evolution

- **Objective:** evolve Contract to a directional, party-linked, line-based root
  with explicit amendment history.
- **Why needed:** estimates, procurement, payments, and billing need a reliable
  contract identity and immutable commercial history.
- **Prerequisites:** R3A, R3B, R5, and business decisions for direction/type and
  lifecycle transitions.
- **Apps affected:** contracts, parties, projects, audit; financial read layer only
  after validated.
- **Models added:** ContractItem, ContractAmendment.
- **Models modified:** Contract gains nullable BusinessParty and direction/type;
  legacy name/value columns remain.
- **Services affected:** party-aware create, draft editing, activate/complete/
  terminate, item management, and atomic amendment approval.
- **Migrations required:** expand fields/tables; backfill parties; direction data
  migration only when mapping is known; later non-null/constraints.
- **Backfill needs:** reviewed party links. Do not invent direction or synthesize
  contract items from header totals without approval.
- **Legacy compatibility:** dual-read/write counterparty snapshot; current header
  contract value remains authoritative until item/amendment calculation is
  explicitly switched.
- **Tenant risks:** party, project, item control references, and amendments must
  match contract organization/project.
- **Business risks:** direction misclassification and changing finalized contract
  value are high impact.
- **Tests required:** lifecycle transition matrix, Decimal totals, amendments,
  concurrency, legacy parity, admin immutability, and all cross-tenant links.
- **Acceptance criteria:** new contracts use party/direction; old contracts remain
  readable; finalized terms change only through approved amendments.
- **Out of scope:** procurement order workflow, progress claims, general ledger,
  and deletion of `counterparty_name`.
- **Primary type:** BOTH.

## R7B — Estimate revision evolution

- **Objective:** introduce explicit EstimateRevision and attach items/UOMs to a
  revision without losing current approvals.
- **Why needed:** current `revised` status does not preserve versioned history and
  approved items are not universally immutable.
- **Prerequisites:** R3B, R5, R7A where contract association is used, and approved
  revision/supersession semantics.
- **Apps affected:** estimates, projects, contracts, audit, financials.
- **Models added:** EstimateRevision.
- **Models modified:** Estimate and EstimateItem; add current-revision/revision and
  UOM references while retaining current columns/FKs.
- **Services affected:** create revision, copy lines, edit draft revision, approve
  under row lock, supersede rules, and read current/approved revision.
- **Migrations required:** additive revision schema/FKs, data migration creating
  revision 1, validation, then later constraint tightening.
- **Backfill needs:** preserve existing status, approver, approval time, notes,
  line ordering, quantities, prices, and totals in revision 1; map UOM separately.
- **Legacy compatibility:** adapters/read fallbacks keep current URLs and totals;
  dual-write only during a short controlled window.
- **Tenant risks:** estimate/revision/item/UOM/project/phase/contract chain must be
  explicitly validated.
- **Business risks:** choosing the wrong approved/current revision changes
  financial reports; run parity checks before switching.
- **Tests required:** migration fidelity, total parity, revision numbering,
  concurrent revisions/approvals, finalized lock, financial report parity,
  permissions, and isolation.
- **Acceptance criteria:** every estimate has a valid revision; approved history is
  immutable; dashboard totals match the approved legacy baseline.
- **Out of scope:** deleting current Estimate approval fields, automatic estimate
  to contract conversion, and generic revision framework.
- **Primary type:** REFACTOR.

## R8 — Expense and Payment reference evolution

- **Objective:** connect Expense/Payment to party/category masters and add explicit
  PaymentAllocation while preserving void history.
- **Why needed:** financial records need relational identity and allocation without
  weakening current immutable void workflows.
- **Prerequisites:** R3A, R7A for contract allocations, approved ExpenseCategory
  and payment-allocation rules.
- **Apps affected:** expenses, payments, parties, contracts, financials, audit.
- **Models added:** ExpenseCategory, PaymentAllocation.
- **Models modified:** Expense gains nullable party/category FKs; Payment gains
  nullable party FK; legacy names/category/direct links remain.
- **Services affected:** force Expense creation as recorded; scoped reference
  validation; atomic allocation/reversal with no over-allocation; preserve void.
- **Migrations required:** additive masters/FKs, idempotent category seed/backfill,
  reviewed party mapping, later validation constraints.
- **Backfill needs:** exact category mapping; reviewed parties. Do not manufacture
  allocation amounts from optional contract/phase references.
- **Legacy compatibility:** financial reports continue current sources until
  relational parity is proven; names/category codes remain snapshots.
- **Tenant risks:** category/party/payment/allocation/target organization equality;
  allocation object lookup must always be tenant scoped.
- **Business risks:** allocations can double-count cash; void must reverse or
  exclude allocations under an explicit rule.
- **Tests required:** reporting parity, categories, parties, over-allocation,
  concurrency, void/allocation interaction, admin immutability, and isolation.
- **Acceptance criteria:** new records use relational references; current totals do
  not change; posted/void records cannot be silently edited; allocations balance.
- **Out of scope:** claims until R13, bank reconciliation, accounting ledger, and
  removal of legacy text/direct links.
- **Primary type:** BOTH.

## R9 — Workforce and daily labor integration

- **Objective:** add employment structure and project assignments, then link daily
  labor entries to teams/assignments.
- **Why needed:** User is correctly an identity, not an employee; daily team text
  cannot support staffing or labor accountability.
- **Prerequisites:** R1, stable Project/Site, and decisions on employee identity,
  department/position structure, team membership, and assignment overlap.
- **Apps affected:** new workforce app, accounts only via optional User FK,
  projects, daily_reports, audit.
- **Models added:** Employee, Department, Position, WorkTeam,
  EmployeeProjectAssignment.
- **Models modified:** DailyReportLaborEntry gains nullable team/assignment
  references while retaining `team_name`.
- **Services affected:** employee lifecycle, team management, assign/release, and
  draft daily labor validation against project/site/date.
- **Migrations required:** additive workforce schemas and nullable daily FKs;
  later constraints after reviewed mapping.
- **Backfill needs:** do not create Employees from Users automatically; map
  reviewed team names only and preserve labels.
- **Legacy compatibility:** login/membership logic is unchanged; daily free text
  remains available.
- **Tenant risks:** every workforce hierarchy and assignment reference must match
  organization/project/site.
- **Business risks:** employment and login identity may be many-to-zero/one; labor
  cost and payroll semantics remain intentionally excluded.
- **Tests required:** User/Employee separation, scoped employee codes, assignment
  overlap/hierarchy, team mapping, daily finalization, permissions, and isolation.
- **Acceptance criteria:** employees need no login; users need no employee record;
  new daily labor can reference valid assignments; old reports remain intact.
- **Out of scope:** payroll, attendance engine, employee self-service, and generic
  project permission redesign.
- **Primary type:** BOTH.

## R10 — Procurement

- **Objective:** implement request-to-order procurement using party, material,
  project-control, and workforce identities.
- **Why needed:** purchase commitments must exist before reliable receiving and
  inventory workflows.
- **Prerequisites:** R3A, R4, R5, and enough R9 identity policy to define requester/
  approver references.
- **Apps affected:** new procurement app, parties, materials, projects, workforce,
  audit, optionally contracts.
- **Models added:** PurchaseRequest, PurchaseRequestItem, PurchaseOrder,
  PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem.
- **Models modified:** none initially outside optional navigation.
- **Services affected:** request draft/submit/approve/reject; order draft/approve/
  issue/close/void; receive/post/void with transactions and idempotency.
- **Migrations required:** additive schemas, scoped business-number constraints,
  statuses, indexes, and source idempotency keys.
- **Backfill needs:** none; do not reinterpret expenses or contracts as historical
  purchase orders.
- **Legacy compatibility:** existing expense/payment workflows continue; optional
  links are added only after procurement stabilizes.
- **Tenant risks:** supplier role, project/site/control/material/UOM, and all parent
  line relationships require same-tenant validation.
- **Business risks:** approval thresholds, partial ordering/receiving, cancellation,
  tax, and quantity tolerance need explicit rules.
- **Tests required:** state matrices, line locks, totals/rounding, partial receipts,
  over-receipt policy, idempotency, concurrency, permissions, and isolation.
- **Acceptance criteria:** each workflow is independently auditable; posted receipt
  is immutable; no stock effect is introduced before R11's agreed integration.
- **Out of scope:** vendor portal, automated sourcing, background notifications,
  and accounts payable ledger.
- **Primary type:** NEW DEVELOPMENT.

## R11 — Inventory

- **Objective:** add warehouses and immutable material stock transactions, then
  integrate posted goods receipts safely.
- **Why needed:** material master and procurement provide the identities/source
  events required for reliable stock movement.
- **Prerequisites:** R4, R10, and decisions on negative stock, transfer, valuation,
  and reversal rules.
- **Apps affected:** new inventory app, procurement, materials, projects, audit.
- **Models added:** Warehouse, StockTransaction.
- **Models modified:** GoodsReceipt may gain posting linkage/status metadata only
  if not already present.
- **Services affected:** warehouse lifecycle; atomic receive/issue/return/transfer/
  reverse; idempotent goods-receipt posting; read-only balance calculation.
- **Migrations required:** additive schemas, scoped warehouse codes, source
  idempotency constraints, and movement indexes.
- **Backfill needs:** none; current daily material entries are usage evidence, not
  safe stock-issue transactions.
- **Legacy compatibility:** daily material reporting remains independent until an
  explicit stock-issue integration is approved.
- **Tenant risks:** material/source/destination/project/site organizations must
  match; transfers cannot cross tenants.
- **Business risks:** stock is history-sensitive; never update posted quantities.
  Reversal must be an explicit compensating transaction.
- **Tests required:** balance calculations, transfer symmetry, negative-stock
  policy, idempotency, concurrent posting, reversal, permissions, and isolation.
- **Acceptance criteria:** balances derive from immutable posted transactions;
  duplicate receipt posting cannot duplicate stock.
- **Out of scope:** full costing/valuation, barcode/WMS optimization, and general
  ledger integration.
- **Primary type:** NEW DEVELOPMENT.

## R12 — Equipment and daily equipment integration

- **Objective:** add equipment master, assignments, maintenance history, and link
  daily equipment usage.
- **Why needed:** daily equipment text cannot support availability, project
  assignment, or maintenance records.
- **Prerequisites:** R5, R9 where employee responsibility is needed, and approved
  equipment/assignment/maintenance lifecycle rules.
- **Apps affected:** new equipment app, projects, workforce, daily_reports, audit;
  expenses only through optional later references.
- **Models added:** Equipment, EquipmentAssignment, MaintenanceRecord.
- **Models modified:** DailyReportEquipmentEntry gains nullable equipment and
  assignment FKs while retaining `equipment_name`.
- **Services affected:** equipment lifecycle, assign/release, maintenance
  schedule/complete/void, and daily usage validation.
- **Migrations required:** additive schemas/FKs/constraints; later validation
  after mapping.
- **Backfill needs:** reviewed per-tenant equipment candidates and links; do not
  infer assignments from a name alone.
- **Legacy compatibility:** historical equipment label remains; existing daily
  reports render unchanged.
- **Tenant risks:** equipment/assignment/project/site/report organization chains
  and effective dates require explicit checks.
- **Business risks:** assignment overlap and retroactive maintenance/history edits
  can invalidate utilization reporting.
- **Tests required:** scoped codes, overlap, lifecycle, maintenance immutability,
  daily report linkage/finalization, permissions, and isolation.
- **Acceptance criteria:** new usage references valid assigned equipment; old
  usage is preserved; completed maintenance cannot be silently altered.
- **Out of scope:** IoT/telematics, fuel automation, depreciation, and fleet
  accounting.
- **Primary type:** BOTH.

## R13 — Billing and progress claims

- **Objective:** implement contract-backed progress claims, lines, adjustments,
  and payment allocation integration.
- **Why needed:** v1.0 requires explicit receivable/payable claim history rather
  than treating payments or contracts as invoices.
- **Prerequisites:** R7A, R8, R5, and approved claim direction, certification,
  retention, adjustment, and numbering rules.
- **Apps affected:** new billing app, contracts, projects/project controls,
  payments, parties, audit, financials.
- **Models added:** ProgressClaim, ProgressClaimItem, ClaimAdjustment.
- **Models modified:** PaymentAllocation gains approved claim target support;
  financial read models add claim metrics after validation.
- **Services affected:** claim draft/submit/approve/post/void, line calculation,
  adjustment apply/void, and allocation eligibility.
- **Migrations required:** additive schemas, scoped claim numbering, statuses,
  approval/posting metadata, and allocation target constraints.
- **Backfill needs:** none from existing payments/contracts unless the business can
  prove an exact historical claim; do not manufacture claims.
- **Legacy compatibility:** existing financial dashboards remain until new claim
  metrics are introduced explicitly and reconciled.
- **Tenant risks:** party/contract/project/control/payment links must all share
  tenant and compatible direction.
- **Business risks:** cumulative quantities, retention, taxes, adjustments, and
  payment allocation can materially affect financial results.
- **Tests required:** Decimal/rounding, cumulative caps, transition matrix,
  concurrency, immutable posted history, allocation/void interaction, reports,
  permissions, and isolation.
- **Acceptance criteria:** posted claims are immutable; corrections use adjustment
  or void; allocations cannot exceed eligible claim/payment balances.
- **Out of scope:** full invoicing tax engine, accounts receivable/payable ledger,
  and external accounting integration.
- **Primary type:** NEW DEVELOPMENT.

## R14 — Documents v2

- **Objective:** evolve ProjectDocument into stable Document identity,
  DocumentVersion history, and approved DocumentLink relationships while reusing
  existing security validation.
- **Why needed:** current attachments are single-version and fixed to project plus
  optional payment; target domains need secure versioned links.
- **Prerequisites:** R1 and stable identifiers for the first approved link targets.
  This phase may start earlier for versioning, but broad link migration should
  wait for target entities to stabilize.
- **Apps affected:** documents and each explicitly allowed linked app; audit.
- **Models added:** Document, DocumentVersion, DocumentLink, unless Document is
  introduced as an additive successor while ProjectDocument remains temporarily.
- **Models modified:** ProjectDocument only through a compatibility bridge; no
  destructive rename in the expansion.
- **Services affected:** reuse file validation/hash/path rules for version create;
  tenant-scoped link/unlink; current download/detail compatibility resolver.
- **Migrations required:** additive tables, one Document + version 1 per current
  row, project/payment link backfill, validation, later contract.
- **Backfill needs:** preserve file path, filename, MIME, size, hash, uploader,
  archive metadata, project link, payment link, and original public UUID mapping.
- **Legacy compatibility:** existing URLs/public IDs must resolve throughout;
  physical files should not be copied unnecessarily.
- **Tenant risks:** link targets must be resolved under organization; generic
  content-type links must not become a cross-tenant escape hatch.
- **Business risks:** broken file paths or identifier changes can make evidence
  inaccessible; test restoration and rollback before switch.
- **Tests required:** migration fidelity, byte/hash parity, version sequencing,
  MIME/signature/size checks, download authorization/audit, links, archive,
  compatibility URLs, and isolation.
- **Acceptance criteria:** every legacy file downloads under the same authorization;
  new versions are immutable; links cannot cross tenants; old consumers still work.
- **Out of scope:** OCR, antivirus services requiring new packages, external object
  storage migration, and unrestricted generic attachment targets.
- **Primary type:** BOTH.

## R15 — Safety and Quality (deferred optional modules)

- **Objective:** implement SafetyIncident and QualityIssue only after their
  workflows, access, retention, and reporting requirements are approved.
- **Why needed:** daily free-text notes are insufficient for formal EHS/QMS cases,
  but premature modeling creates compliance and privacy risk.
- **Prerequisites:** approved business requirements; R5/R6, and preferably R9/R14
  for responsible persons and evidence documents.
- **Apps affected:** separate safety and quality domain apps, daily_reports,
  projects, workforce, documents, audit.
- **Models added:** SafetyIncident and QualityIssue; corrective-action child models
  only if requirements demonstrate them.
- **Models modified:** optional links from DailyReport/DocumentLink, not replacement
  of historical notes.
- **Services affected:** explicit report/investigate/resolve/close or
  open/disposition/close transitions, permissions, audit, and immutable closure.
- **Migrations required:** additive only.
- **Backfill needs:** none; do not parse safety or quality narratives.
- **Legacy compatibility:** notes remain visible as historical narrative.
- **Tenant risks:** sensitive incidents may need stricter object permissions than
  broad tenant roles; all project/site/person links remain tenant scoped.
- **Business risks:** severity, notification duties, privacy, legal retention, and
  reversible/irreversible transitions need domain-owner approval.
- **Tests required:** state/permission matrices, sensitive visibility, retention,
  document links, closure immutability, audit, and isolation.
- **Acceptance criteria:** defined separately for each module; neither begins until
  requirements and retention rules are signed off.
- **Out of scope:** generic BPM engine, regulatory automation, and background
  notification infrastructure.
- **Primary type:** NEW DEVELOPMENT (DEFERRED).

## 4. Cross-phase contract gates

A legacy field or table may enter a contract/removal phase only when all of these
are true:

1. The replacement schema has been deployed separately and is stable.
2. Existing rows have been backfilled or explicitly classified as unmappable.
3. All application reads and writes have switched and compatibility telemetry
   shows no legacy dependence.
4. Cross-tenant integrity checks pass for every new relationship.
5. Financial/history totals and public identifiers are reconciled.
6. Rollback no longer requires the legacy write path, or a tested reverse mapping
   exists.
7. Removal is explicitly approved as its own scope.

This applies specifically to `counterparty_name`, `vendor_name`, `material_name`,
`equipment_name`, `team_name`, `unit`, Expense `category`, direct estimate-item
ownership, ProjectDocument file fields, and any legacy status/approval fields
moved into revisions.

## 5. Recommended first approved implementation

Run **R0 Baseline validation** first and preserve its evidence. The first code
change should then be **R1 Tenant isolation and finalized-history hardening**.
Adding new master/transaction models before R1 would multiply the current admin
and cross-table integrity risks.

The first feature-bearing phase after hardening should be **R2
OrganizationSettings**, followed by independently deployable **R3A BusinessParty**
and **R3B UnitOfMeasure**. This order creates the stable tenant configuration and
reference identities required by later migrations without changing current
financial totals.

## 6. Approval checkpoints

Explicit business approval is required before:

- selecting UOM ownership and conversion policy;
- defining party deduplication and legal-name snapshot policy;
- backfilling Contract direction/type;
- defining EstimateRevision current/approved/superseded semantics;
- defining payment allocation targets and reversal behavior;
- separating phase, WBS, activity, baseline, and progress responsibilities;
- deciding project/site-specific access beyond organization RBAC;
- defining procurement partial-order/receipt tolerances;
- choosing inventory negative-stock and reversal rules;
- defining claim retention, adjustment, tax, and cumulative-value rules;
- choosing DocumentLink target mechanics; and
- starting either Safety or Quality module.
