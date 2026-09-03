# Current Domain Model

> Repository state inspected: 2026-09-03  
> Scope: the implementation that exists in source code and migrations today  
> Authority for current state: application code and migrations, not `PROJECT_SNAPSHOT.md`

## 1. Purpose and evidence

This document reconstructs the current Construction ERP domain model before any
Domain Model v1.0 refactor. It is descriptive, not aspirational. The inspection
covered `AGENTS.md`, settings, all installed applications, model and migration
files, services, forms, views, middleware, decorators, administration classes,
URLs, behaviorally relevant templates, and tests.

The current product is a modular Django monolith. Business mutations generally
run through application services, HTML is rendered with Django templates, and
tenant context is resolved from the authenticated user's active organization.
No HTMX-specific endpoint or `hx-*` behavior currently exists.

There are 18 application/domain models registered by Django, excluding Django's
built-in authentication, admin, content-type, and session models. The
`financials` app is intentionally a service/read-model layer and owns no model.

## 2. Current high-level relationships

```text
User
├── Organization.created_by / updated_by
├── OrganizationMembership ──> Organization
└── OrganizationInvitation ──> Organization

Organization
├── Project
│   ├── ProjectSite
│   │   ├── ProjectPhase
│   │   └── DailyReport
│   │       ├── DailyReportLaborEntry
│   │       ├── DailyReportMaterialEntry
│   │       └── DailyReportEquipmentEntry
│   ├── Contract
│   ├── Estimate ──> EstimateItem
│   ├── Expense
│   ├── Payment
│   └── ProjectDocument
└── AuditEvent
```

Additional optional links are:

```text
Estimate ──> ProjectPhase (nullable)
Estimate ──> Contract (nullable)
Expense ──> ProjectPhase (nullable)
Payment ──> Contract (nullable)
Payment ──> ProjectPhase (nullable)
ProjectDocument ──> Payment (nullable)
DailyReport ──> ProjectPhase (nullable)
```

All business models use a UUID primary key. `Organization` and most mutable
business roots include created/updated timestamps. Immutable-style child records
use a created timestamp only in a few places. Every tenant-owned record has an
explicit `organization` foreign key, but the database does not enforce equality
between that field and the organization of related parent records.

## 3. Shared model primitives

### `UUIDModel` — `core`

- **Purpose:** abstract primary-key mixin.
- **Important fields:** `id`, a UUID generated with `uuid4`, non-editable and
  primary key.
- **Tenant ownership:** none; abstract infrastructure.

### `CreatedAtModel` — `core`

- **Purpose:** abstract creation timestamp mixin.
- **Important fields:** timezone-aware `created_at` populated on insertion.

### `TimeStampedModel` — `core`

- **Purpose:** abstract creation/update timestamp mixin.
- **Important fields:** `created_at` and `updated_at`.

These primitives are stable and already used consistently enough to preserve.
They do not currently provide soft deletion, actor fields, or tenant-scoped
managers.

## 4. Model catalog

### 4.1 Identity and tenancy

#### `User` — `apps.accounts`

- **Business purpose:** global login identity. It is not an employee or a tenant
  record; tenancy is expressed through memberships.
- **Aggregate relationship:** independent identity root; referenced by tenant
  records as actor, inviter, approver, uploader, or voider.
- **Fields:** Django `AbstractUser` fields, required unique `username`, optional
  `email` and `phone_number`, and created/updated timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** none by design.
- **Constraints/indexes:** unique username; inherited authentication indexes and
  constraints apply.
- **Lifecycle:** Django active/staff/superuser flags; no application soft delete.
- **Mutation services:** standard authentication/user manager behavior; tenant
  assignment is handled by organization membership services.
- **Authorization/isolation:** a user gains tenant access only through an active
  `OrganizationMembership` to an active, non-deleted organization.
- **Important tests:** username login, optional email behavior, authentication
  form behavior, and user creation/manager tests.
- **Assessment:** correctly separated as global identity; must not be overloaded
  with workforce/employment data.

#### `Organization` — `apps.organizations`

- **Business purpose:** tenant root and company identity.
- **Aggregate relationship:** root of almost every business aggregate.
- **Fields:** `name`, `legal_name`, globally unique `slug`, `status`, `timezone`,
  `currency`, `created_by`, `updated_by`, `deleted_at`, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** the tenant itself.
- **Nullable relationships:** creator/updater are nullable `User` references with
  `SET_NULL`; `deleted_at` is nullable.
- **Constraints/indexes:** `slug` is globally unique; `status` is indexed.
- **Lifecycle:** `active`, `suspended`, `cancelled`, and `archived`; `deleted_at`
  supplies soft-deletion state. Access helpers admit only active, non-deleted
  organizations.
- **Mutation services:** atomic organization creation creates the initial owner
  membership; organization switching is session based.
- **Invariants:** creation and initial owner membership occur in one transaction.
- **Authorization/isolation:** active membership is required before resolution as
  the current tenant.
- **Important tests:** atomic owner creation, organization status access,
  switching, session behavior, and tenant separation.
- **Free-text/configuration fields:** timezone and currency currently live on the
  root rather than a separate settings aggregate.

#### `OrganizationMembership` — `apps.organizations`

- **Business purpose:** joins a global user to a tenant and assigns broad RBAC.
- **Aggregate relationship:** child of `Organization`; access-control source of
  truth.
- **Fields:** organization, user, `role`, `status`, `joined_at`, `invited_by`, and
  timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Foreign keys:** organization and user use `CASCADE`; `invited_by` is nullable
  and uses `SET_NULL`.
- **Constraints/indexes:** unique `(user, organization)`.
- **Lifecycle:** `invited`, `active`, `suspended`, `revoked`.
- **Role values:** `owner`, `admin`, `manager`, `member`, `viewer`.
- **Mutation services:** membership lookup, owner creation, invitation acceptance,
  member listing, and active-organization resolution.
- **Authorization/isolation:** all tenant entry points depend on active membership
  plus active/non-deleted organization status.
- **Important tests:** duplicate membership protection, membership status,
  cross-tenant access, and active-organization behavior.

#### `OrganizationInvitation` — `apps.organizations`

- **Business purpose:** controlled invitation of an existing user identity to an
  organization.
- **Aggregate relationship:** child workflow of `Organization`.
- **Fields:** organization, invitee, inviter, role, status, globally unique
  `token_hash`, expiration, and acceptance timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Nullable relationships:** inviter and accepted timestamp are nullable.
- **Constraints/indexes:** globally unique token hash; indexed status.
- **Lifecycle:** `pending`, `accepted`, `expired`, `revoked`.
- **Role values:** `admin`, `manager`, `member`, `viewer`; owner is not invitational.
- **Mutation services:** invitation creation and atomic acceptance using row
  locking. Acceptance creates or activates the membership and is audited.
- **Authorization/isolation:** creation is owner/admin only; invitee identity,
  expiry, organization state, and current status are rechecked in the service.
- **Important tests:** duplicate pending invitations, authorization, expiry,
  invitee mismatch, acceptance, and audit events.

### 4.2 Audit

#### `AuditEvent` — `apps.audit`

- **Business purpose:** application audit trail for important business and
  security actions.
- **Aggregate relationship:** append-only system record; optionally belongs to an
  organization and references a subject through string fields.
- **Fields:** nullable organization and actor, choice-backed `action`, free-text
  `entity_type`, free-text `entity_id`, JSON metadata, and created timestamp.
- **Primary key:** UUID.
- **Tenant ownership:** organization is nullable to allow system/global events.
- **Constraints/indexes:** indexes on `(organization, -created_at)` and
  `(action, -created_at)`.
- **Lifecycle:** no update/delete workflow. QuerySet, manager, and instance
  update/delete methods reject mutation; bulk creation is also rejected.
- **Mutation services:** `record_audit_event` is the intended creation path and
  rejects metadata keys resembling passwords, tokens, secrets, credentials, or
  authorization data.
- **Authorization/isolation:** audit-list queries are tenant scoped. The low-level
  recording helper accepts its organization and actor arguments without itself
  proving actor membership, so caller correctness remains important.
- **Important tests:** append-only behavior, blocked bulk operations, metadata
  redaction/rejection, and tenant-scoped visibility.
- **Known free-text references:** entity type and entity ID are intentionally
  polymorphic strings rather than database foreign keys.

### 4.3 Projects and sites

#### `Project` — `apps.projects`

- **Business purpose:** tenant-owned construction project root.
- **Aggregate relationship:** parent of sites and the principal project reference
  for operational and financial records.
- **Fields:** organization, code, name, description, status, planned/actual dates,
  Decimal budget, creator/updater, deletion timestamp, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Nullable relationships/fields:** actual dates, creator/updater, and
  `deleted_at` are nullable.
- **Constraints/indexes:** unique `(organization, code)`; indexes on
  `(organization, status)` and `(organization, deleted_at)`.
- **Lifecycle:** `planning`, `active`, `on_hold`, `completed`, `cancelled`; soft
  archive uses `deleted_at`.
- **Mutation services:** atomic create and archive services; role checks and audit
  events are applied.
- **Invariants:** budget is converted to `Decimal` and must be nonnegative; date
  ordering is validated in service code.
- **Authorization/isolation:** owner/admin/manager may create or archive; list and
  detail querysets include organization and non-deleted scope.
- **Important tests:** Decimal validation, roles, archive, organization status,
  cross-tenant access, and scoped uniqueness.

#### `ProjectSite` — `apps.projects`

- **Business purpose:** physical/operational site within a project.
- **Aggregate relationship:** child of `Project`; parent of phases and daily
  reports.
- **Fields:** organization, project, code, name, address, active flag,
  creator/updater, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Nullable relationships:** creator/updater are nullable.
- **Constraints/indexes:** unique `(organization, project, code)`; index on
  `(organization, project, is_active)`.
- **Lifecycle:** active flag; no soft-delete timestamp.
- **Mutation services:** atomic site creation validates the project tenant and
  actor role.
- **Authorization/isolation:** service and read querysets scope organization and
  project. No database rule guarantees `site.organization == project.organization`.
- **Important tests:** cross-tenant project rejection, scoped listing, roles, and
  active organization behavior.

#### `ProjectPhase` — `apps.projects`

- **Business purpose:** planned execution phase under a project site.
- **Aggregate relationship:** child of `ProjectSite`; project is reached through
  the site.
- **Fields:** organization, site, code, name, status, planned dates,
  creator/updater, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Nullable relationships/fields:** planned dates and actor fields are nullable.
- **Constraints/indexes:** unique `(organization, site, code)`; index on
  `(organization, site, status)`.
- **Lifecycle:** `planning`, `active`, `on_hold`, `completed`; transitions are
  restricted by an explicit transition map.
- **Mutation services:** atomic creation and transition service; transition uses
  `select_for_update` and emits audit events.
- **Authorization/isolation:** direct organization and site checks exist. Creation
  verifies the site's organization and that its project is available, but does
  not independently compare `site.project.organization_id` with the requested
  organization; this matters if inconsistent rows were inserted outside services.
- **Important tests:** transition rules, roles, tenant isolation, site ownership,
  and project availability.

### 4.4 Contracts and estimates

#### `Contract` — `apps.contracts`

- **Business purpose:** project contract header.
- **Aggregate relationship:** tenant-owned project child and optional parent
  reference for estimates, payments, and documents.
- **Fields:** organization, project, contract number, title, free-text
  `counterparty_name`, status, Decimal `contract_value`, signed/start/end dates,
  notes, creator/updater, deletion timestamp, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Nullable fields:** dates, actor fields, and deletion timestamp.
- **Constraints/indexes:** unique `(organization, contract_number)`; indexes on
  `(organization, status)` and `(organization, deleted_at)`.
- **Lifecycle:** `draft`, `active`, `completed`, `terminated`; no service-level
  transition, amendment, or immutable-final-state workflow exists.
- **Mutation services:** atomic create only; validates active tenant, manager-level
  role, project tenant, nonnegative Decimal value, date order, and uniqueness.
- **Authorization/isolation:** creation and all normal reads are scoped. The admin
  path can bypass service checks.
- **Important tests:** creation, Decimal behavior, role checks, uniqueness,
  organization state, and cross-tenant project rejection.
- **Known free-text business references:** `counterparty_name`. There is no
  `BusinessParty` FK and no explicit contract direction/type.

#### `Estimate` — `apps.estimates`

- **Business purpose:** project estimate header and approval state.
- **Aggregate relationship:** parent of estimate items; optionally associated with
  one phase and one contract.
- **Fields:** organization, project, nullable phase and contract, estimate number,
  title, status, notes, creator/updater, approver and approval time, deletion
  timestamp, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Nullable relationships:** phase and contract use `SET_NULL`; actor fields,
  approval time, and deletion timestamp are nullable.
- **Constraints/indexes:** unique `(organization, estimate_number)`; indexes on
  `(organization, status)`, `(organization, deleted_at)`, and
  `(organization, phase, status)`.
- **Lifecycle:** `draft`, `approved`, `revised`, `archived`.
- **Mutation services:** atomic header creation, item addition, and approval.
  Approval uses row locking, is owner/admin only, only accepts draft estimates,
  and records approver/time plus audit event.
- **Invariants:** optional phase must belong to the same project via its site;
  optional contract must belong to the same organization/project and be active
  in the soft-delete sense. Total amount is the Decimal sum of items, rounded
  with `ROUND_HALF_UP`.
- **History behavior:** service item creation blocks `approved` estimates, but it
  does not block the `revised` or `archived` statuses. Admin and direct ORM paths
  can still modify approved headers/items. No revision aggregate exists.
- **Authorization/isolation:** tenant checks exist in services/forms/views; admin
  is not tenant scoped.
- **Important tests:** cross-tenant contract/phase rejection, item totals, approval
  roles, repeated approval rejection, and approved-item service lock.
- **Known free-text fields:** status is a choice-backed string.

#### `EstimateItem` — `apps.estimates`

- **Business purpose:** priced line within an estimate.
- **Aggregate relationship:** child of `Estimate`.
- **Fields:** organization, estimate, description, Decimal quantity, free-text
  `unit`, Decimal unit price, sort order, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Constraints/indexes:** index on `(organization, estimate)`; no line-level
  business uniqueness constraint.
- **Lifecycle:** inherits the estimate's intended lifecycle, but the database does
  not enforce the lock.
- **Mutation services:** item creation validates tenant, draft-like mutability,
  positive quantity, nonnegative price, and rounds the calculated total using
  `ROUND_HALF_UP`.
- **Authorization/isolation:** service retrieves the estimate under organization
  scope. No database rule guarantees item and estimate organizations match.
- **Important tests:** Decimal calculation, organization scoping, and approved
  estimate lock.
- **Known free-text business references:** `unit`.

### 4.5 Expenses and payments

#### `Expense` — `apps.expenses`

- **Business purpose:** actual project cost record.
- **Aggregate relationship:** tenant-owned child of project and optional phase.
- **Fields:** organization, project, nullable phase, choice-backed `category`,
  description, free-text `vendor_name`, Decimal amount, incurred date, status,
  void reason/time/actor, receipt reference, notes, creator/updater, deletion
  timestamp, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Constraints/indexes:** indexes on `(organization, project, incurred_on)`,
  `(organization, category)`, `(organization, deleted_at)`, and
  `(organization, phase, incurred_on)`; no business-key uniqueness constraint.
- **Lifecycle:** `recorded` or `void`; soft deletion is present but normal
  financial reporting excludes deleted records.
- **Mutation services:** atomic creation and row-locked void workflow. Voiding
  requires a reason, preserves the amount, records actor/time, and audits.
- **Invariants:** amount is Decimal and nonnegative; project and phase are checked
  against organization/project. Creation currently accepts any declared status,
  including `void`, without requiring void metadata, which is an integrity gap.
- **Authorization/isolation:** owner/admin/manager mutations; tenant-scoped reads.
  Django admin disables add/change/delete for this model.
- **Important tests:** tenant isolation, categories, Decimal values, phase
  validation, void preservation, idempotency rejection, and admin immutability.
- **Known free-text/business references:** `vendor_name`; `category` is a fixed
  string choice (`materials`, `labor`, `equipment`, `subcontractor`, `permit`,
  `other`) rather than an `ExpenseCategory` entity.

#### `Payment` — `apps.payments`

- **Business purpose:** posted cash receipt or disbursement associated with a
  project and optionally a contract/phase.
- **Aggregate relationship:** tenant-owned financial record; may be referenced by
  project documents.
- **Fields:** organization, project, nullable contract and phase, payment number,
  direction, Decimal amount, payment date, method, free-text
  `counterparty_name`, reference, notes, status, void reason/time/actor,
  creator/updater, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Constraints/indexes:** unique `(organization, payment_number)`; indexes on
  `(organization, paid_on, status)` and `(organization, project, paid_on)`.
- **Lifecycle:** created as `posted`; can transition to `void` through the void
  service. No edit/reversal/allocation aggregate exists.
- **Mutation services:** atomic create and row-locked void. Create validates
  tenant/project/contract/phase, role, positive Decimal amount, direction,
  payment method, and uniqueness. Void requires a reason and preserves amount.
- **Authorization/isolation:** owner/admin/manager mutate; list queries are tenant
  scoped. Django admin disables add/change/delete.
- **Important tests:** cross-tenant project/contract/phase checks, Decimal amount,
  scoped uniqueness, void preservation, and admin immutability.
- **Known free-text/business references:** `counterparty_name`; `direction`,
  `method`, and `status` are choice-backed strings. There is no
  `PaymentAllocation`.

### 4.6 Documents

#### `ProjectDocument` — `apps.documents`

- **Business purpose:** secure project file metadata and attachment storage.
- **Aggregate relationship:** child of project; optionally linked to one payment.
- **Fields:** organization, project, nullable payment, document type, title,
  uploaded file, original filename, MIME type, byte size, SHA-256 hash, creator,
  archive reason/time/actor, and created timestamp.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK and tenant/project-segmented
  random upload path.
- **Nullable relationships:** payment and archive actor/time are nullable.
- **Constraints/indexes:** indexes on `(organization, project, created_at)` and
  `(organization, payment)`; no content-hash uniqueness requirement.
- **Lifecycle:** available or archived; file content is retained on archive.
- **Mutation services:** upload validates role, project/payment relationships,
  size (10 MB limit), extension, MIME type, file signature, and calculates hash.
  Archive uses row locking and a required reason. Downloads are scoped, check
  availability, and emit audit events.
- **Authorization/isolation:** tenant checks are strong in normal services and
  views. Admin permits direct creation/editing and cross-tenant FK selection,
  bypassing service-level upload and relationship validation.
- **Important tests:** file size, MIME/signature/extension validation, cross-tenant
  payment linkage, scoped list/detail/download, archive, and download audit.
- **History limitation:** there is no stable `Document` identity with
  `DocumentVersion` history or generic `DocumentLink` relationships.

### 4.7 Daily reporting

#### `DailyReport` — `apps.daily_reports`

- **Business purpose:** one worksite report per site and reporting date.
- **Aggregate relationship:** root of labor, material, and equipment entries;
  child of project/site and optionally phase.
- **Fields:** organization, project, site, nullable phase, reporting date, status,
  weather, labor count, work performed, progress summary, issue/delay notes,
  safety notes, quality notes, submitted/approved timestamps, approver,
  creator/updater, and timestamps.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Nullable relationships:** phase and approval fields are nullable.
- **Constraints/indexes:** unique `(organization, site, reporting_date)`; indexes
  on `(organization, reporting_date)`, `(organization, status)`, and
  `(organization, phase, reporting_date)`.
- **Lifecycle:** `draft` -> `submitted` -> `approved`; service transitions are
  one-way and use transactions plus row locking.
- **Mutation services:** atomic report creation, child-entry creation, submission,
  and approval. Creator or manager-level roles may mutate a draft; approval is
  owner/admin/manager only.
- **Invariants:** project, site, and phase organization/hierarchy are explicitly
  checked in the services. Site must be active; phase must be active when used.
- **History behavior:** services do not provide edits after finalization, but
  admin and direct ORM can change approved reports and child entries.
- **Authorization/isolation:** active tenant and membership are checked for all
  workflows; viewer is read-only. Normal lookups use organization scope.
- **Important tests:** duplicate site/date, project/site/phase cross-tenant and
  hierarchy checks, role behavior, entry validation, and submit/approve sequence.
- **Known free-text business concepts:** `issues_and_delays`, `safety_notes`, and
  `quality_notes`; there are no `DailyActivity`, `DelayEvent`, `SafetyIncident`,
  or `QualityIssue` records.

#### `DailyReportLaborEntry` — `apps.daily_reports`

- **Business purpose:** labor summary line for a daily report.
- **Aggregate relationship:** child of `DailyReport`.
- **Fields:** organization, daily report, free-text `team_name`, worker count,
  Decimal hours worked, notes, creator, and created timestamp.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Constraints/indexes:** index on `(organization, daily_report)`.
- **Lifecycle:** append-like draft child; no edit/void model workflow.
- **Mutation services:** draft-only addition under row lock; positive worker count
  and hours validation; audited.
- **Authorization/isolation:** report is fetched by organization. No database rule
  ensures child and report organizations match.
- **Important tests:** draft lock, role/creator behavior, positive values, and
  tenant isolation.
- **Known free-text business references:** `team_name`; no `WorkTeam` FK.

#### `DailyReportMaterialEntry` — `apps.daily_reports`

- **Business purpose:** material usage summary line for a daily report.
- **Aggregate relationship:** child of `DailyReport`.
- **Fields:** organization, daily report, free-text `material_name`, Decimal
  quantity, free-text `unit`, notes, creator, and created timestamp.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Constraints/indexes:** index on `(organization, daily_report)`.
- **Lifecycle/mutations:** draft-only addition through a row-locked, audited
  service; quantity must be positive.
- **Authorization/isolation:** report is organization scoped; database does not
  enforce matching organizations.
- **Important tests:** lifecycle, quantities, roles, and tenant isolation.
- **Known free-text business references:** `material_name` and `unit`; there are
  no `Material` or `UnitOfMeasure` FKs.

#### `DailyReportEquipmentEntry` — `apps.daily_reports`

- **Business purpose:** equipment usage summary line for a daily report.
- **Aggregate relationship:** child of `DailyReport`.
- **Fields:** organization, daily report, free-text `equipment_name`, Decimal
  hours used, notes, creator, and created timestamp.
- **Primary key:** UUID.
- **Tenant ownership:** explicit organization FK.
- **Constraints/indexes:** index on `(organization, daily_report)`.
- **Lifecycle/mutations:** draft-only addition through a row-locked, audited
  service; hours must be positive.
- **Authorization/isolation:** report is organization scoped; database does not
  enforce matching organizations.
- **Important tests:** lifecycle, positive hours, roles, and tenant isolation.
- **Known free-text business references:** `equipment_name`; no `Equipment` FK.

## 5. Current free-text and choice-backed business references

| Field | Current meaning | Target-model concern |
|---|---|---|
| `Contract.counterparty_name` | Contract party label | No `BusinessParty` identity or role integrity. |
| `Payment.counterparty_name` | Payer/payee label | Cannot reliably join payments to a party. |
| `Expense.vendor_name` | Vendor label | Cannot reliably join expenses to supplier/vendor records. |
| `DailyReportMaterialEntry.material_name` | Material label | No material master, category, or canonical unit. |
| `DailyReportEquipmentEntry.equipment_name` | Equipment label | No equipment identity, assignment, or maintenance link. |
| `DailyReportLaborEntry.team_name` | Work-team label | No workforce/team identity. |
| `EstimateItem.unit` | Estimate line unit | Free text; no canonical unit conversion or identity. |
| `DailyReportMaterialEntry.unit` | Usage unit | Free text and can disagree with estimate/material terminology. |
| `Expense.category` | Fixed expense classification | Choice string, not tenant-configurable `ExpenseCategory`. |
| `*.status` | Lifecycle state | Choice-backed strings exist on Organization, Membership, Invitation, Project, Phase, Contract, Estimate, Expense, Payment, and DailyReport. Enforcement strength varies by workflow. |
| `*.role` | Authorization role | Choice-backed strings exist on Membership and Invitation. |
| `Payment.direction` | Receipt/disbursement | Explicit choice is present and should be preserved. Contract direction is absent. |
| `Payment.method` | Payment method | Choice-backed string; adequate for the current scope. |
| `ProjectDocument.document_type` | Attachment category | Choice-backed string; future document links/versions are absent. |

No current `supplier_name` field was found. Supplier meaning is represented
indirectly by `vendor_name` or `counterparty_name`.

## 6. Tenant-safety audit

### 6.1 Tenant-owned models

Every current business model other than global `User` has an organization FK.
`AuditEvent.organization` is deliberately nullable; all other tenant-owned model
organization FKs are required.

### 6.2 Tenant-owned foreign-key matrix

| Source -> target | Nullable | Normal service validation | Database cross-tenant guarantee | Current concern |
|---|---:|---|---|---|
| Membership -> Organization | No | Access source of truth | FK only | Admin can mutate roles/status without service/audit. |
| Invitation -> Organization | No | Explicit | FK only | Admin bypass remains possible. |
| Project -> Organization | No | Explicit | FK only | Stable. |
| Site -> Project | No | Explicit project tenant check | None for organization equality | Admin/direct ORM can create a cross-tenant link. |
| Phase -> Site | No | Direct site tenant check; parent project availability checked | None | Service does not independently re-check site project's organization if database is already inconsistent. |
| Contract -> Project | No | Explicit | None | Admin/direct ORM bypass. |
| Estimate -> Project | No | Explicit | None | Admin/direct ORM bypass. |
| Estimate -> Phase | Yes | Organization and project hierarchy explicit | None | Admin/direct ORM bypass. |
| Estimate -> Contract | Yes | Organization and project explicit | None | Admin/direct ORM bypass. |
| EstimateItem -> Estimate | No | Scoped parent lookup | None | Admin inline/direct ORM bypass. |
| Expense -> Project | No | Explicit | None | Direct ORM can bypass. |
| Expense -> Phase | Yes | Organization and project hierarchy explicit | None | Direct ORM can bypass. |
| Payment -> Project | No | Explicit | None | Direct ORM can bypass. |
| Payment -> Contract | Yes | Organization and project explicit | None | Direct ORM can bypass. |
| Payment -> Phase | Yes | Organization and project explicit | None | Direct ORM can bypass. |
| ProjectDocument -> Project | No | Explicit | None | Admin bypasses upload service. |
| ProjectDocument -> Payment | Yes | Organization and project explicit | None | Admin/direct ORM can cross-link. |
| DailyReport -> Project | No | Explicit | None | Admin/direct ORM bypass. |
| DailyReport -> Site | No | Organization and project explicit | None | Admin/direct ORM bypass. |
| DailyReport -> Phase | Yes | Organization/site hierarchy explicit | None | Admin/direct ORM bypass. |
| Each daily entry -> DailyReport | No | Scoped parent lookup | None | Admin/direct ORM bypass. |
| AuditEvent -> Organization | Yes | Caller supplied | FK only | Recording helper does not prove actor membership. |

### 6.3 Querysets, forms, views, middleware, and workflows

- Normal application list/detail services filter by active organization and, for
  archivable records, by non-deleted state.
- Forms receive the active organization and scope project/site/phase/contract/
  payment choices accordingly. Dependent relationships are rechecked by services.
- Active-organization middleware resolves session state only through an active
  membership in an active, non-deleted organization. Invalid session tenant IDs
  are cleared. A sole valid membership can be auto-selected.
- Business views use the active-organization decorator and delegate mutations to
  services. Object lookup is normally performed inside tenant-scoped services.
- No current HTMX endpoint was found, so there is no separate HTMX isolation path
  to audit.
- Approval/void/submission services re-fetch their root under organization scope
  and, where state races matter, use `select_for_update` inside a transaction.
- Document list/detail/download services explicitly scope organization and reject
  archived/unavailable files. Download is audited.

### 6.4 Tenant-safety findings

1. **Admin is the largest bypass surface.** Most registered tenant models expose
   global staff querysets, unscoped related-field choices, and direct save paths.
   This can create cross-tenant relationships or mutate protected states without
   service validation or audit. Expense and Payment are read-only in admin, and
   AuditEvent is append-only there, but their lists remain global by design for
   staff/superusers.
2. **Cross-table organization equality is not database-enforced.** Composite
   uniqueness protects tenant-local business keys but not the equality of two
   organization columns across a foreign key. Correctness currently relies on
   services/forms.
3. **Model-level validation is not a sufficient guard.** Cross-tenant relationship
   invariants are primarily service checks; direct `.save()`, fixtures, custom
   scripts, or admin paths can bypass them.
4. **Phase creation has an inferred parent invariant.** It checks the site's
   organization and parent project availability but assumes the stored site ->
   project relationship is already tenant-consistent.
5. **The audit creation helper trusts its caller.** It can record an actor under
   an organization without checking that actor's membership. Existing call sites
   generally pass already-authorized actors, but the helper boundary is not
   self-defending.
6. **No tenant leak was found in normal user-facing queryset paths inspected.**
   The identified risks concern bypass paths, stored-data integrity, and future
   callers rather than a demonstrated public cross-tenant read endpoint.

## 7. Financial and history-safety audit

### 7.1 Decimal handling

- Project budgets, contract values, estimate quantities/prices/totals, expense
  amounts, payment amounts, and daily usage quantities/hours use `DecimalField`.
- Services convert external values to `Decimal`; financial totals quantize to two
  decimal places. Estimate calculations explicitly use `ROUND_HALF_UP`.
- No use of Python `float` for authoritative financial values was found.

### 7.2 Finalization and immutability

| Area | Current strength | Current risk |
|---|---|---|
| Contracts | Creation validates value and tenant. | Status/value can be changed directly; no controlled activate/complete/terminate or amendment history. |
| Estimates | Atomic approval, role check, row lock, approver/time, audit; service blocks item addition to approved estimates. | Approved header/items remain editable via admin/direct ORM; revised/archived estimates are not blocked by item service; no `EstimateRevision`. |
| Expenses | Explicit atomic void workflow preserves original amount and records reason/actor/time; admin is read-only. | Direct ORM can change historical fields; creation can accept `void` without matching void metadata; no adjustment/reversal entity. |
| Payments | Created posted; explicit atomic void workflow preserves amount and records reason/actor/time; admin is read-only. | Direct ORM can mutate posted/void records; no allocations or reversal/adjustment record. |
| Daily reports | Atomic one-way submit/approve with row locks and audit. | Approved reports and entries can be changed in admin/direct ORM; no explicit correction/revision workflow. |
| Documents | Archive preserves file and metadata; download is audited. | Admin can replace/edit metadata outside validation; no immutable version history. |
| Financial reports | Read-only services use tenant-scoped ORM aggregation and Decimal. | Reports depend on mutable source rows; contract value is not included as a committed-cost total, and there is no claim/allocation history. |

### 7.3 Financial read model

The current financial dashboard/report aggregates:

- approved, non-deleted estimates;
- recorded, non-deleted expenses;
- posted payments split by receipt/disbursement; and
- counts of non-deleted contracts and approved estimates.

All sources are filtered to the active organization and available projects.
Variance is currently approved-estimate total minus recorded expenses. Contract
values are counted but not summed into the main totals, so the read model is not
yet a complete budget/commitment/actual/forecast model.

### 7.4 Audit append-only behavior

Application-level protections are strong: ordinary update/delete, bulk update,
bulk delete, and bulk create are rejected. Admin mutation is disabled. This is
not a database-level append-only guarantee, so privileged SQL or migration code
can still alter history. That is acceptable for the current stage but must be
recognized in operational controls.

## 8. Authorization summary

- Broad tenant roles currently are owner, admin, manager, member, and viewer.
- Most financial/project creation services admit owner/admin/manager.
- Estimate approval is owner/admin only.
- Daily report creation and draft entry addition admit members; creator ownership
  or manager-level authority controls draft mutation; approval is
  owner/admin/manager.
- Invitation creation is owner/admin.
- Authorization is rechecked in normal mutation services. There is no project- or
  site-specific role model yet.
- Admin permissions are based on Django staff/superuser configuration rather than
  the tenant membership model and therefore need hardening before relying on
  admin for tenant operations.

## 9. Important current test coverage

The repository contains targeted tests for:

- custom-user authentication and optional email;
- atomic organization/owner creation, memberships, invitations, session tenant
  resolution, and organization lifecycle;
- project/site/phase tenant checks, permissions, archive, and transitions;
- contract project isolation and Decimal validation;
- estimate hierarchy checks, Decimal totals, approval roles, and service locking;
- expense and payment tenant checks, void workflows, value preservation, and
  read-only administration;
- document type/size/signature validation, relationship isolation, archive,
  download authorization, and audit;
- daily report hierarchy, role, line-entry, submission, and approval behavior;
- financial report tenant scoping and Decimal aggregates; and
- audit append-only and sensitive-metadata safeguards.

Important missing coverage includes admin tenant scoping, direct-ORM cross-tenant
relationship rejection, immutable-state enforcement outside services, database
constraint behavior for lifecycle metadata, and future data-backfill tests.

At this inspection checkpoint, `manage.py check` passes. A full database-backed
test run was not used as evidence for this document; existing source and test
definitions were inspected directly.

## 10. Models explicitly not implemented

The following Domain Model v1.0 concepts are not current models:

- Organization settings: `OrganizationSettings`.
- Party master: `BusinessParty`, `PartyRole`, `PartyContact`.
- Workforce: `Employee`, `Department`, `Position`, `WorkTeam`,
  `EmployeeProjectAssignment`.
- Project controls: `CostCenter`, `WBSNode`, `Activity`, `ProjectBaseline`,
  `ProgressRecord`.
- Contract/estimate history: `ContractItem`, `ContractAmendment`,
  `EstimateRevision`.
- Daily details: `DailyActivity`, `DelayEvent`.
- Material master: `UnitOfMeasure`, `MaterialCategory`, `Material`.
- Procurement: purchase requests/items, purchase orders/items, and goods
  receipts/items.
- Inventory: `Warehouse`, `StockTransaction`.
- Equipment: `Equipment`, `EquipmentAssignment`, `MaintenanceRecord`.
- Finance: `ExpenseCategory`, `PaymentAllocation`.
- Billing: progress claims/items and claim adjustments.
- Documents v2: `DocumentVersion`, `DocumentLink` and a separate stable
  `Document` root (the current model is `ProjectDocument`).
- Optional/future: `SafetyIncident`, `QualityIssue`, `Notification`.

These are listed only to mark absence. Their target responsibilities and the
incremental path to them are covered in the companion gap analysis and refactor
sequence.
