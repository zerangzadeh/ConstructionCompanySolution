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

> Last Updated: 2026-08-30
>
> Status: Active Development — MVP foundation and core financial workflows are
> implemented; the feature layer is still in progress.

### 11.1 Completed Project Foundation

- `config/` contains split settings (`base.py`, `development.py`,
  `production.py`), URL configuration, WSGI/ASGI entry points, and project
  configuration.
- Tooling configuration exists in `pytest.ini` and `pyproject.toml`.
- Dependency files include the base, database, and development requirement
  groups.
- SQL Server connectivity has been verified from Django using the configured
  development settings.

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
  - Create, list, detail, and soft-archive flows.
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
  - Category, Decimal amount, role validation, create, and list flows.
- `apps/audit/`
  - `AuditEvent` model and audit service.
  - Audit log view and events for important organization and business actions.
- `apps/financials/`
  - Reporting/service-only layer with no own business models.
  - Financial report and dashboard views/templates.
  - Aggregates approved estimates, contracts, and recorded expenses within the
    active organization.

### 11.3 Main Current Routes

The implemented UI currently covers organization management and selection,
projects, contracts, estimates, expenses, audit logs, and financial reporting.
Financial pages include `/financials/` and `/financials/dashboard/`.

## 12. Database and Migration Status

Migration files are present for:

- `accounts`
- `organizations` (including membership and invitation migrations)
- `audit`
- `projects`
- `contracts`
- `estimates` (including the approval workflow migration)
- `expenses`

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
- The full recorded test checkpoint was `75 passed`.
- The financial dashboard targeted test checkpoint was `7 passed`.

These checkpoints describe the state at the last validation run; rerun the
relevant checks after any code or configuration change.

## 14. Known Gaps and Technical Debt

- `core/` shared base models and mixins for UUID, timestamps, soft delete, and
  audit fields have not yet been extracted; some behavior remains app-local.
- A shared `templates/components/` directory and component conventions are not
  yet established.
- Tailwind utility patterns are repeated in some templates and need gradual
  consolidation.
- More cross-tenant integration coverage is needed as new endpoints are added.
- Production environment configuration and deployment verification remain
  incomplete.
- File/document upload validation and document management are not yet a complete
  feature.
- DRF and Celery/Redis are intentionally deferred.

## 15. Prioritized Next Work

1. Daily worksite reporting as the next MVP feature for contractors.
2. Reusable template components and documented component conventions.
3. Additional tenant-isolation and permission integration tests for every new
   endpoint.
4. Payment and cash-flow workflows built on the existing financial reporting
   foundation.
5. Document and receipt management with secure upload validation.
6. Extract shared `core/` mixins only after the recurring model patterns are
   stable and the extraction has a clear benefit.
7. Reassess DRF and Celery/Redis when API or background-processing requirements
   are approved.
