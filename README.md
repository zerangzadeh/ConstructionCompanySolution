# Construction ERP

Construction ERP is planned as a multi-tenant SaaS platform for construction
contractor companies. Each company is represented by an `Organization`
(tenant), and business data must remain isolated between organizations.

## Current status

The repository is currently in the project-foundation stage. Django project
code, applications, database models, authentication, and tenant handling have
not been implemented yet.

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
development values when the Django project is available.

Never commit `.env`, passwords, tokens, or other credentials.

## Development principles

- Keep views thin and place multi-step workflows in services or use cases.
- Scope every business query and operation to the authenticated user's active
  organization.
- Use `Decimal` for financial values and timezone-aware datetimes.
- Add tests for business rules, permissions, and tenant isolation.

## License

License information has not been defined yet.
