# Construction ERP

Construction ERP is a multi-tenant SaaS platform for construction
contractor companies. Each company is represented by an `Organization`
(tenant), and business data must remain isolated between organizations.

## Current status

The repository currently implements the accepted R1-R8 foundation and domain
refactors on PostgreSQL 18.6:

- Custom username-based authentication (`email` is optional).
- Tenant lifecycle, settings, memberships, invitations, active-organization
  resolution, and append-only auditing.
- Tenant-scoped party, unit-of-measure, material, project, site, phase, WBS, and
  activity masters and workflows.
- Versioned estimates, contracts/amendments, expenses, payments/allocations,
  daily reports, private documents, and financial read models.
- Service-layer tenant validation, Decimal financial handling, row-locked
  transitions, and immutable finalized financial history.

Migrations for the implemented apps are present and must be applied to each
configured database. The current logical model is summarized in
`docs/architecture/DOMAIN_AND_DATA_MODEL.md`; models and migrations remain the
schema source of truth.

R9 workforce is the next product-development phase. R9+ phases are not yet
implemented and require separate approval.

## Planned technology stack

- Python and Django
- PostgreSQL 18.6 with Psycopg 3
- Django Templates with Tailwind CSS
- HTMX for small dynamic interactions when needed
- Django REST Framework (future API)
- Celery and Redis (future background jobs)

## Repository conventions

- Django applications will be placed under `apps/`.
- Shared technical and business support code will be placed under `core/`.
- Settings will be split into base, development, and production modules.
- Tests will be placed under `tests/` and/or application test directories.
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

## Development principles

- Keep views thin and place multi-step workflows in services or use cases.
- Scope every business query and operation to the authenticated user's active
  organization.
- Use `Decimal` for financial values and timezone-aware datetimes.
- Add tests for business rules, permissions, and tenant isolation.

## License

License information has not been defined yet.
