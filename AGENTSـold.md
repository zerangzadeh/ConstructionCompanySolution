# Construction ERP — Agent Instructions

## 1. Product and Scope

This repository contains a multi-tenant SaaS platform for construction contractor
companies. Each company is represented by an `Organization` (tenant), and strict
data isolation between organizations is mandatory.

The current product is a modular monolith. The initial user interface uses Django
templates with Tailwind CSS and HTMX where a small dynamic interaction is useful.
REST APIs and background jobs are future extensions, not current requirements.

## 2. Technology Stack

- Backend: Python and Django
- Database: Microsoft SQL Server through `mssql-django` and `pyodbc`
- Frontend: Django Templates, Tailwind CSS, and optional HTMX
- Future API layer: Django REST Framework
- Future background jobs: Celery and Redis
- Architecture: Modular Monolith with lightweight Clean Architecture
- Testing: `pytest`/`pytest-django`
- Quality tooling: Ruff

Do not add a new package unless it has a clear purpose and is explicitly approved.

## 3. Repository Structure

- Django applications are under `apps/`.
- Shared business and technical code belongs under `core/`.
- Settings are split into `config/settings/base.py`,
  `config/settings/development.py`, and `config/settings/production.py`.
- Project-level configuration is under `config/`.
- Tests may be under `tests/` and/or each app's test directory.
- Per-app templates are kept with their app; shared UI components belong under
  `templates/components/` when that directory is introduced.

Use English naming for code, files, classes, variables, URL names, and database
fields.

## 4. Architecture Rules

1. Keep Django views thin.
2. Put business workflows and multi-step operations in application services or
   use cases.
3. Do not put complex business logic or financial calculations in templates.
4. Domain rules must not depend on HTTP, templates, or external services.
5. Prefer the Django ORM. Introduce a repository abstraction only when it has a
   clear, demonstrated benefit.
6. Avoid unnecessary abstractions and over-engineering.
7. Keep services small, focused, and type-hinted.
8. Do not hide critical business logic in Django signals.
9. Validate authorization and tenant scope at the service boundary as well as at
   the view boundary where appropriate.

## 5. Multi-Tenancy Rules

1. Almost every business entity must belong to an `Organization`.
2. Never trust an `organization_id` supplied by a user, form, URL, or request
   body.
3. Resolve the current organization from the authenticated user's active
   membership and session state.
4. Every queryset, form, view, service, and future API endpoint must be scoped to
   the active organization.
5. Membership status and role must be checked before accessing or mutating tenant
   data.
6. Prevent cross-tenant reads and writes, and add integration tests for tenant
   isolation.
7. Organization creation must create the initial owner membership atomically.

## 6. Data and Financial Rules

Important business entities should support:

- UUID public identifiers
- `created_at` and `updated_at`
- `created_by` and `updated_by` where applicable
- Soft deletion or archival where business records must be retained
- Audit logging for important actions

Additional rules:

- Use `Decimal` for all money and never use `float` for financial values.
- Use timezone-aware datetimes.
- Enforce organization-scoped uniqueness in database constraints where needed.
- Prefer database constraints and transactions for invariants that must be
  atomic.
- Use `select_related` and `prefetch_related` when needed to prevent N+1 queries.

## 7. Security Rules

- Never hardcode secrets, credentials, tokens, or database connection strings.
- Read environment-specific values from environment variables.
- Keep authentication, authorization, and organization scope enabled for every
  endpoint.
- Keep CSRF protection enabled.
- Validate all user input server-side.
- Validate uploaded file type and size before accepting files.
- Do not expose internal identifiers or tenant data across organization
  boundaries.

## 8. Frontend Rules

- Use Tailwind utility classes and avoid scattered custom CSS or inline styles.
- Build responsive, mobile-first pages suitable for site engineers.
- Use HTMX only for small dynamic interactions that benefit from avoiding a full
  page refresh.
- HTMX endpoints must enforce the same authentication, authorization, CSRF, and
  tenant-isolation rules as regular views.
- Reuse template components and keep presentation logic out of Python services.

## 9. Code Quality and Testing

- Add unit tests for business rules and service behavior.
- Add integration tests for permissions, organization scope, and tenant
  isolation.
- Run `python manage.py check` after configuration or Django changes.
- Run `python -m pytest` for the relevant test scope.
- Run `python -m ruff check .` and `python -m ruff format --check .` before
  handoff when the tooling is available.
- Keep functions and classes small and focused.
- Preserve unrelated user changes in a dirty worktree.

## 10. Required Working Process

Before implementing a feature:

1. Inspect the existing project structure and relevant code.
2. Explain the proposed implementation plan briefly.
3. List the files to create or modify.
4. Implement only the requested scope.
5. Run relevant tests, formatting, and checks.
6. Report changed files, test results, assumptions, and follow-up work.

When the user requests a multi-step implementation, complete only the agreed
scope and report each completed step clearly. Do not combine unrelated feature
work into one step.

Do not rewrite unrelated files. Do not create branches, commits, pushes, pull
requests, or remote changes unless explicitly requested.

## 11. Project Snapshot and Implementation Status

> Last Updated: 2026-09-03
>
> Status: Active Development — the multi-tenant MVP foundation, daily reporting,
> payments, documents, and core financial workflows are implemented. Production
> deployment verification and several planned product domains remain in progress.

### 11.1 Completed Project Foundation

- `config/` contains split settings (`base.py`, `development.py`,
  `production.py`), URL configuration, WSGI/ASGI entry points, and project
  configuration.
- Tooling configuration exists in `pytest.ini` and `pyproject.toml`.
- Dependency files include the base, database, and development requirement
  groups.
- SQL Server connectivity has been verified from Django using the configured
  development settings.
- Local `.env` values are loaded through `python-dotenv`; `.env.example` is the
  safe configuration template and must not contain real credentials.
- Production settings reject missing, placeholder, or insecure database/TLS
  configuration.
- `core/models.py` provides stable UUID and timestamp mixins used by the
  business models where the schema pattern has stabilized.
- Shared template conventions are documented in `templates/components/`.

### 11.2 Implemented Django Apps

- `apps/accounts/`
  - Custom `User` model and manager.
  - Login uses required `username`; `email` is optional.
  - Authentication forms, views, admin integration, and tests.
- `apps/organizations/`
  - `Organization`, `OrganizationMembership`, and
    `OrganizationInvitation` models.
  - Organization-scoped middleware, decorators, and active-organization
    session handling.
  - Services for organization creation with an initial owner, membership
    lookup, active-organization selection, invitations, invitation acceptance,
    member listing, and organization switching.
  - Organization selection and switching views, URLs, and tenant-isolation
    tests.
- `apps/projects/`
  - Organization-scoped project model and services.
  - Project, worksite, and phase create/list/detail flows, lifecycle changes,
    and soft archival.
  - Role-based creation and Decimal project budget handling.
- `apps/contracts/`
  - Organization-scoped contract model and services.
  - Project validation, Decimal contract value, and organization-scoped unique
    contract number.
  - Create and list templates with tests.
- `apps/estimates/`
  - Organization-scoped estimate and estimate-item models.
  - Decimal line totals using `ROUND_HALF_UP`.
  - Approval workflow: only authorized `OWNER`/`ADMIN` members can approve, and
    approved estimates are locked.
  - Create, list, and detail templates with tests.
- `apps/expenses/`
  - Organization-scoped expense model and services.
  - Category, Decimal amount, project/phase validation, create, and list flows.
  - Audited void workflow that preserves the original amount; voided expenses
    are excluded from financial reporting.
- `apps/payments/`
  - Organization-scoped posted receipts and disbursements linked to projects,
    contracts, and phases where applicable.
  - Organization-scoped unique payment numbers, Decimal values, audited void
    workflow, and financial-reporting integration.
  - Admin does not allow direct add, edit, or delete operations for payments.
- `apps/documents/`
  - Private organization-scoped project and payment documents.
  - Validates PDF/JPEG/PNG extension, MIME type, signature, and a 10 MB size
    limit before storage.
  - Stores original filename, content type, size, SHA-256 hash, uploader, and
    archive metadata; authorized downloads are audited.
- `apps/daily_reports/`
  - Organization-scoped daily worksite reports with labor, equipment, material,
    progress, safety, quality, and approval-state information.
  - Project, worksite, and phase relationships are validated at the service
    boundary.
- `apps/audit/`
  - Append-only `AuditEvent` model and audit service; application-layer updates,
    deletes, and bulk creation are rejected.
  - Audit metadata rejects sensitive keys such as password, token, secret,
    credential, and authorization values.
  - Audit log view and events for important organization and business actions.
- `apps/financials/`
  - Reporting/service-only layer with no own business models.
  - Financial report and dashboard views/templates.
  - Aggregates approved estimates, contracts, recorded expenses, and posted
    payments within the active organization.

### 11.3 Main Current Routes

The implemented UI currently covers authentication, organization management and
selection, projects/sites/phases, daily reports, contracts, estimates, expenses,
payments, documents, audit logs, and financial reporting. Financial pages include
`/financials/` and `/financials/dashboard/`; payment and document pages begin at
`/payments/` and `/documents/`.

## 12. Database and Migration Status

Migration files are present for:

- `accounts`
- `organizations` (including membership and invitation migrations)
- `audit`
- `projects`
- `contracts`
- `estimates` (including the approval workflow migration)
- `expenses` (including project phase and financial void fields)
- `payments`
- `documents` (including document archival fields)
- `daily_reports`

Recent migrations that may need to be applied in a developer database are:

- `organizations.0004_alter_organization_status`
- `audit.0003_alter_auditevent_action`
- `audit.0004_alter_auditevent_action`
- `expenses.0003_expense_void_fields`
- `payments.0001_initial`
- `documents.0001_initial`
- `documents.0002_projectdocument_archive_reason`

The application uses Microsoft SQL Server through Django's ORM. Every environment
must run `python manage.py migrate` against its own configured database before
using new features. The repository must not assume that a developer's local
database has every migration applied.

Do not place database credentials or connection strings in source control.

## 13. Validation Status

The latest recorded validation checkpoints include:

- `python manage.py check` passed.
- `python -m ruff check .` passed.
- `python -m ruff format --check .` passed.
- Updated shared Django templates compile successfully.
- Lightweight Django-admin immutability tests for payments and expenses passed.
- The historical full test checkpoint was `75 passed`; it must be rerun after
  applying the current migrations.

These checkpoints describe the state at the last validation run; rerun the
relevant checks after any code or configuration change.

The current Codex process may be unable to run database-backed tests because its
SQL Server TLS credential provider cannot authenticate. This does not replace
validation from a developer terminal connected to the configured SQL Server.

## 14. Known Gaps and Technical Debt

- `core/` UUID and timestamp mixins are established, but soft-delete and audit
  actor fields remain app-local until their recurring patterns are fully stable.
- Shared components exist for navigation, page headers, form fields/errors, and
  framework messages; Tailwind utility patterns still need gradual
  consolidation.
- More cross-tenant integration coverage is needed as new endpoints are added.
- Production environment configuration and deployment verification remain
  incomplete.
- Full database-backed regression tests and browser workflow verification should
  be rerun after the current migrations are applied.
- Document versioning, retention policy enforcement, and organization data
  export remain future work.
- DRF and Celery/Redis are intentionally deferred.

## 15. Prioritized Next Work

1. Apply migrations and run the full database-backed test suite from a normal
   developer terminal.
2. Verify authenticated browser workflows with a real owner user and active
   organization.
3. Add tenant-isolation and permission integration tests for every new endpoint
   and lifecycle transition.
4. Complete production deployment configuration, secure SQL Server TLS
   verification, and operational monitoring.
5. Extend payments into approved billing, receivables, settlements, and
   cash-flow workflows only after their business rules are agreed.
6. Extend document retention, versioning, and export behavior when those
   governance requirements are approved.
7. Extract further `core/` mixins only after a repeated model pattern has a
   demonstrated benefit; reassess DRF and Celery/Redis when API or background
   processing is approved.

## 16. Product Domain Map

The planned Construction ERP domain is organized into bounded Django apps. Add a
new app only when the domain has clear ownership, data boundaries, and business
responsibilities:

- `organizations`: tenants, memberships, invitations, and tenant settings
- `accounts`: authentication and user identity
- `projects`: projects, sites, phases, and project-level access
- `contracts`: client and subcontractor contracts
- `estimates`: estimates, line items, revisions, and approvals
- `expenses`: operational expenses and expense categories
- `procurement`: purchase requests, purchase orders, and vendor workflows
- `inventory`: materials, warehouses, stock movements, and transfers
- `equipment`: equipment, assignments, usage, maintenance, and fuel
- `workforce`: workers, teams, time entries, and labor costs
- `daily_reports`: daily site progress, labor, equipment, materials, and events
- `safety`: incidents, inspections, risks, and corrective actions
- `quality`: inspections, non-conformities, and quality checklists
- `documents`: secure documents, attachments, metadata, and versions
- `billing`: invoices, progress claims, retention, and receivables
- `payments`: payments, settlements, and cash-flow transactions
- `audit`: immutable records of important business and security actions
- `financials`: cross-domain financial reporting and read-only aggregates

Cross-domain dependencies must be explicit. Avoid circular imports and avoid
duplicating the same business concept in multiple apps.

## 17. SaaS Tenant Lifecycle

The tenant model must support a controlled lifecycle, even if subscription
billing is introduced later:

- `active`: normal access is allowed
- `suspended`: sign-in may be allowed for administrators, but business
  mutations are blocked
- `cancelled`: normal access is blocked; retention and export policies still
  apply

Tenant status, plan limits, feature flags, and quotas must be checked on the
server. Never rely on frontend visibility to enforce subscription or quota
rules. Organization deletion, export, and suspension operations must be
audited and transactional.

Tenant configuration such as timezone, currency, fiscal settings, and numbering
schemes belongs to the organization and must not be inferred from global
defaults after the organization has configured it.

## 18. Authorization and RBAC

Authorization must be explicit and deny by default:

- Organization roles define broad capabilities such as `OWNER`, `ADMIN`,
  `MANAGER`, `ACCOUNTANT`, `SUPERVISOR`, and `VIEWER`.
- Project or site roles may further restrict access within an organization.
- Object-level permission checks are required for viewing, editing, approving,
  archiving, exporting, and deleting sensitive records.
- A role check must be performed server-side in services and views; hiding a
  button is not authorization.
- Privilege escalation, role changes, invitation acceptance, and membership
  removal must be audited.

Use the existing membership and active-organization services as the source of
truth. Do not introduce a second independent permission model without documenting
its relationship to organization membership.

## 19. Workflow and Approval Rules

Business records with lifecycle states must define:

- Allowed states and valid transitions
- The role allowed to perform each transition
- Required fields and validations for each transition
- Whether a transition is reversible
- Audit data for actor, timestamp, previous state, new state, and reason

Approved, posted, paid, or otherwise finalized financial records should be
immutable. Corrections must use a documented revision, reversal, or adjustment
workflow rather than silently changing historical values.

Approval services must use transactions and re-check authorization and current
state inside the transaction to avoid race conditions.

## 20. Operational Reliability

For multi-step or externally visible operations:

- Use `transaction.atomic()` for all-or-nothing business workflows.
- Make retryable operations idempotent where duplicate requests are possible.
- Define unique business keys for important external or user-facing actions.
- Handle concurrent updates explicitly and avoid lost updates.
- Keep structured logs free of passwords, tokens, and unnecessary personal data.
- Record correlation or request identifiers when introducing background jobs or
  integrations.
- External integrations must fail safely and must not bypass tenant checks.

Background processing, queues, and scheduled jobs remain deferred until approved,
but new services should not assume that every operation is synchronous forever.

## 21. Construction-Specific Data Rules

- Preserve the hierarchy between organization, project, site, phase, contract,
  and cost center where the business process requires it.
- Separate budget, committed cost, actual cost, forecast, and variance; do not
  overload one amount field with multiple meanings.
- Use explicit units of measure and quantities for materials, labor, and
  equipment usage.
- Store document and estimate revisions instead of overwriting approved history.
- Daily site reports should record their reporting date, site, author, approval
  state, and relevant labor, equipment, material, progress, safety, and quality
  data.
- Financial and operational aggregates must state their source records and
  organization scope.

## 22. Data Governance and Compliance

- Audit records for security and financial actions must be append-only from the
  application layer.
- Define retention and archival behavior before implementing hard deletion.
- Support organization-scoped data export when the product requires it.
- Treat uploaded documents as untrusted input and retain metadata about type,
  size, uploader, tenant, and version.
- Use the organization's configured timezone and currency in presentation and
  reporting, while storing canonical values consistently.
- Sensitive data must not appear in logs, test fixtures, screenshots, or error
  messages.
