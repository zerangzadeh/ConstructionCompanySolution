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
- Database: PostgreSQL 18.6 through Django's PostgreSQL backend and Psycopg 3
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

> Last Updated: 2026-09-04
>
> Status: **Active Product Development.** The current ERP core is implemented
> and validated on PostgreSQL 18.6 with Psycopg 3. Workforce is the next planned
> product domain; other future product domains are not yet implemented.

The implemented core covers tenant identity/settings, parties, material masters,
projects and project controls, contracts, estimates, daily reporting, expenses,
payments and allocations, private project documents, audit, and financial read
models. The current entity map, relationships, invariants, and lifecycle states
are maintained in `docs/architecture/DOMAIN_AND_DATA_MODEL.md`; Django models and
migrations remain the schema source of truth.

The current server-rendered UI uses Django templates and Tailwind CSS, with HTMX
only where useful. Configuration remains split by environment, production
settings reject insecure database/TLS configuration, and shared model/template
conventions live under `core/` and `templates/components/`.

## 12. Database and Migration Status

Checked-in migrations cover every persisted first-party app. Exact schema,
migration order, and dependencies are defined by those files. The application
uses PostgreSQL 18.6 through Django's ORM and Psycopg 3. Every environment must
run `python manage.py migrate` against its configured database; the repository
must not assume that a local or deployed database is current.

Do not place database credentials or connection strings in source control.

## 13. Current Validation Baseline

- Full PostgreSQL suite: **167 passed**.
- **26 subtests passed**.
- Django check: **PASS**.
- Ruff check/format: **PASS**.

PostgreSQL 18.6 with Psycopg 3 is the authoritative database baseline. Rerun the
relevant checks after any code, migration, or configuration change.

## 14. Product Roadmap

`ROADMAP.md` is the source of truth for future delivery order and the parallel
UI/UX workstream. Workforce is the only **NEXT** product domain. **PLANNED**
phases record direction but do not authorize implementation; decompose and
implement only the current/next phase after explicit approval.

`docs/architecture/DOMAIN_AND_DATA_MODEL.md` is the concise reference for current
entities, relationships, invariants, lifecycle states, and approved future domain
concepts. Do not duplicate those catalogs here.

## 15. Product Modeling and Schema Evolution Guardrails

- The approved Domain Model v1.0 and Target ERD v1.0 guide evolution but do not
  authorize broad rewrites or future modules.
- Support small and large contractors with one core model; enterprise structures
  must remain optional.
- `User` is authentication identity and `Employee` is workforce data;
  `Employee.user` may be nullable.
- Reuse shared masters such as `BusinessParty`, materials, units, equipment, and
  expense categories instead of creating uncontrolled duplicates.
- Keep cross-domain dependencies explicit, avoid circular imports, and introduce
  a new app only with approved ownership, scope, lifecycle, and permissions.
- Full general-ledger accounting, payroll, CRM, generic workflow engines,
  microservices, and event sourcing remain out of scope unless explicitly
  approved.

For schema evolution:

1. Preserve working behavior unless an approved product change replaces it.
2. Use **expand → migrate/backfill → switch → validate → contract** where
   practical; add nullable shared-master references before switching consumers.
3. Preserve legacy compatibility fields until the replacement is deployed,
   historical data is migrated or retained, application dependencies are
   removed, invariants and tenant isolation are revalidated, tests/migrations
   pass, and removal is explicitly approved.
4. Preserve approved, posted, and other finalized history through revision,
   reversal, adjustment, void, or supersession workflows rather than overwrite.


## 16. SaaS Tenant Lifecycle

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

## 17. Authorization and RBAC

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

## 18. Workflow and Approval Rules

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

## 19. Operational Reliability

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

## 20. Construction-Specific Data Rules

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

## 21. Data Governance and Compliance

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
