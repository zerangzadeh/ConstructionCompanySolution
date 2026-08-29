# Construction ERP

Construction ERP is planned as a multi-tenant SaaS platform for construction
contractor companies. Each company is represented by an `Organization`
(tenant), and business data must remain isolated between organizations.

## Current status

The repository currently contains the first SaaS foundation:

- Custom username-based authentication (`email` is optional).
- Organization and membership models with active-organization session
  resolution and tenant-isolated views.
- Organization creation with an atomic owner membership.
- Existing-user invitations with expiring, hashed tokens.
- Organization-scoped audit events and an audit log view.
- Tenant-scoped projects with role-based creation, detail, and soft-archive
  workflows.
- Development, production, and SQL Server settings split by environment.

The invitation, audit, and projects migrations are present in the repository
but must be applied to each configured database before using those workflows.

## Planned technology stack

- Python and Django
- Microsoft SQL Server
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
