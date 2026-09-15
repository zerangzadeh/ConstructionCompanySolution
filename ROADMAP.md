# Product Development Roadmap

Construction ERP is a complete-product initiative and is no longer governed as
an MVP. This roadmap manages incremental delivery toward the complete,
production-oriented product; it does not imply that every listed capability is
already implemented or production-certified. Current system boundaries and
implemented entities are documented in
`docs/architecture/DOMAIN_AND_DATA_MODEL.md`; engineering and delivery rules are
defined in `AGENTS.md`. Django models and migrations remain the schema source of
truth.

Phases are dependency-ordered. Only the current/next phase—the one marked
**NEXT**—should be decomposed into detailed requirements and work packages before
implementation. A **PLANNED** phase records direction but does not authorize
implementation; each phase requires separate approval and must preserve tenant
isolation, permissions, financial precision, auditability, and finalized-record
immutability. Existing entities named below are integration boundaries, not
backlog items.

## Cross-cutting UI/UX workstream

This is not a numbered product-domain phase. It may proceed in parallel with
feature development and progressively update existing and future features to a
professional Persian-first, RTL ERP design. Its scope includes shared layout and
navigation, typography, reusable form/table/detail patterns, responsive behavior,
and accessibility. The approved Project List, Project Form, and Project Detail
patterns are the visual reference.

UI/UX work is presentation-only and must not change backend behavior,
permissions, tenant isolation, workflows, or financial logic.

## F1 — Workforce

- **Status:** IMPLEMENTED
- **Goal:** Establish optional tenant-scoped personnel and team management while
  keeping workforce identity separate from authenticated user identity.
- **Main scope/entities:** `Employee`, `Department`, `Position`, `WorkTeam`,
  `EmployeePositionAssignment`, `EmployeeProjectAssignment`, private employee
  images, optional `Employee.user`, and later daily-labor integration.
- **Done When:** Workforce ownership, roles, lifecycle, project/site assignment,
  permissions, migrations, audit events, and tenant-isolation tests are accepted;
  small tenants can operate without organizational structures.

## F2 — Procurement

- **Status:** IMPLEMENTED
- **Goal:** Control purchasing from internal request through supplier order and
  receipt against existing projects and masters.
- **Main scope/entities:** `PurchaseRequest`/items, `PurchaseOrder`/items,
  `GoodsReceipt`/items, supplier parties, and approved cost-coding prerequisites
  such as `CostCenter`.
- **Done When:** Request, approval, ordering, and receipt states are atomic,
  tenant-safe, auditable, Decimal-precise, and preserve finalized documents.
- **Current workflow boundary:** Procurement uses a fixed, permission-driven
  lifecycle with one request approval decision. It does not currently include
  configurable multi-stage approvals, amount thresholds, delegation,
  separation-of-duties rules, or routing from workforce/organizational-chart
  data; these require separately approved scope.

## F3 — Inventory

- **Status:** IMPLEMENTED
- **Goal:** Provide warehouse-level material control based on validated stock
  movements and procurement receipts.
- **Main scope/entities:** `Warehouse`, `StockTransaction`, material balances,
  receipts, issues, adjustments, and transfers.
- **Done When:** Every movement is tenant-scoped and traceable, negative or
  invalid stock transitions are controlled, and balances are derived or verified
  projections rather than arbitrary editable values.

## F4 — Equipment

- **Status:** IMPLEMENTED
- **Goal:** Manage equipment ownership, deployment, usage, maintenance, and
  related operational records.
- **Main scope/entities:** `Equipment`, `EquipmentAssignment`, and
  `MaintenanceRecord`, with project/site integration. Structured usage, full fuel
  management, and daily-report/cost integration remain deferred.
- **Done When:** Equipment lifecycle and assignments are conflict-safe,
  tenant-isolated, auditable, and existing free-text daily entries remain valid
  historical snapshots.

## F5 — Billing & Progress Claims

- **Status:** NEXT
- **Goal:** Support controlled project progress measurement and receivables from
  approved work through claim and settlement.
- **Main scope/entities:** `ProjectBaseline`, `ProgressRecord`, `ProgressClaim`,
  `ProgressClaimItem`, `ClaimAdjustment`, receivable contracts, payment
  allocations, retention, tax, insurance, deductions, and penalties.
- **Done When:** Progress and claim calculations are Decimal-precise; approval,
  revision, adjustment, and settlement preserve immutable history and reconcile
  to existing contracts and payments.

## F6 — Documents v2

- **Status:** IMPLEMENTED
- **Goal:** Generalize secure project files into versioned documents attachable
  to approved business records.
- **Implemented scope/entities:** `Document`, immutable `DocumentVersion`, and
  explicit-FK `DocumentLink` for projects, contracts, estimates, expenses,
  payments, and daily reports; context-aware access, secure download, audit, and
  archival.
- **Done:** Version history and links are tenant-safe and auditable, current
  versions are maintained atomically, and private storage validation remains
  enforced. Organization-scoped export and formal retention policies remain
  deferred.

## F7 — Safety & Quality

- **Status:** PARTIALLY IMPLEMENTED (Safety incidents and quality issues)
- **Goal:** Add optional standalone incident, inspection, corrective-action, and
  non-conformity workflows for tenants that require formal controls.
- **Implemented scope:** Tenant-scoped `SafetyIncident` reporting, review,
  assignment, corrective action, resolution, closure, RBAC, audit, and optional
  project-structure/daily-report/workforce/party links; tenant-scoped
  `QualityIssue` reporting, assignment, corrective action, verification, closure,
  RBAC, audit, and the same optional structural/responsibility links.
- **Remaining planned scope:** Inspections, risks, formal CAPA, and generalized
  document links.
- **Done When:** Workflows, permissions, severity/status rules, audit history,
  and tenant isolation are validated without making formal modules mandatory or
  replacing existing daily-report notes.

## F8 — Production Readiness

- **Status:** PLANNED
- **Goal:** Validate secure, recoverable, observable production operation of the
  complete approved product scope.
- **Main scope/entities:** Deployment configuration, PostgreSQL TLS, migrations,
  backup/restore, monitoring, structured logging, performance/security checks,
  retention/export operations, browser workflow verification, and tenant-aware
  `Notification` delivery where approved.
- **Done When:** Production deployment and rollback are repeatable, restore and
  migration procedures are proven, monitoring and security controls are active,
  and release validation passes on PostgreSQL 18.6 with Psycopg 3.
