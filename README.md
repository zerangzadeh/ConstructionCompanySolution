# Construction ERP

Construction ERP is a multi-tenant SaaS platform for construction
contractor companies. Each company is represented by an `Organization`
(tenant), and business data must remain isolated between organizations.

This repository is developed as a complete, production-oriented construction
ERP product. It is no longer scoped or managed as a minimum viable product.
Delivery remains incremental: implemented capabilities are usable product
domains, while incomplete domains and operational-readiness work stay visible
in `ROADMAP.md` until they meet their acceptance criteria.

## Current status

**Product maturity:** Active full-product development. This describes the
approved product direction and does not claim that every roadmap phase is
already complete or that production readiness has been certified.

The repository currently implements the ERP foundation and the following
domain capabilities on PostgreSQL 18.6:

- Custom username-based authentication (`email` is optional).
- Tenant lifecycle, settings, memberships, invitations, active-organization
  resolution, and append-only auditing.
- Tenant-scoped party, unit-of-measure, material, project, site, phase, WBS, and
  activity masters and workflows.
- Workforce, procurement, inventory, equipment, safety-incident, and
  quality-issue workflows with explicit tenant ownership and permissions.
- Versioned estimates, contracts/amendments, expenses, payments/allocations,
  daily reports, versioned private documents, and financial read models.
- Tenant-configurable bounded workflow definitions and runtime, persistent work
  items/candidates/delegation history, position-aware routing, and a centralized
  workbench adopted by the approved domain lifecycles.
- Project baselines and progress records, receivable progress claims and
  adjustments, immutable submission evidence, workflow decisions, and
  payment-backed claim settlement allocations.
- Service-layer tenant validation, Decimal financial handling, row-locked
  transitions, and immutable finalized financial history.

Migrations for the implemented apps are present and must be applied to each
configured database. The current logical model is summarized in
`docs/architecture/DOMAIN_AND_DATA_MODEL.md`; models and migrations remain the
schema source of truth.

Tenant Workflow & Work Management and the receivable Billing & Progress Claims
baseline are implemented; their architecture records are in
`docs/architecture/TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md` and
`docs/architecture/BILLING_AND_PROGRESS_CLAIMS.md`. The repository-wide
current/target assessment, pre-production correction register, regulatory and
competitor research, and release gates are in
`docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`. Remaining product
capabilities and production-readiness work are dependency-ordered in
`ROADMAP.md`; a planned item records direction and still requires explicit
implementation approval.

## Technology stack

- Python and Django
- PostgreSQL 18.6 with Psycopg 3
- Django Templates with Tailwind CSS
- HTMX for small dynamic interactions when needed
- Django REST Framework (deferred API capability)
- Celery and Redis (deferred background-processing capability)

## Repository conventions

- Django applications are placed under `apps/`.
- Shared technical and business support code is placed under `core/`.
- Settings are split into base, development, and production modules.
- Tests are placed under `tests/` and/or application test directories.
- Environment-specific values must be provided through environment variables.

## Environment configuration

Copy `.env.example` to `.env` and replace all placeholder values with local
development values. Load those variables in the shell or through your chosen
process manager before running Django.

Never commit `.env`, passwords, tokens, or other credentials.

## Common commands

Run these commands from an activated virtual environment:

```powershell
python manage.py check
python manage.py migrate
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

For a production configuration review:

```powershell
python manage.py check --deploy --settings=config.settings.production
```

The deployment check expects a strong `DJANGO_SECRET_KEY` and non-empty
`DJANGO_ALLOWED_HOSTS` supplied through environment variables.
Production imports never load `.env`. They also require distinct absolute
`DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`, and `DOCUMENT_PROTECTED_ROOT` paths.
See the [deployment preparation contract](docs/governance/cep/supporting/CEP-071_DEPLOYMENT_PREPARATION.md)
for the full environment and release-validation boundary.

## Development principles

- Keep views thin and place multi-step workflows in services or use cases.
- Scope every business query and operation to the authenticated user's active
  organization.
- Use `Decimal` for financial values and timezone-aware datetimes.
- Add tests for business rules, permissions, and tenant isolation.

## License

License information has not been defined yet.
