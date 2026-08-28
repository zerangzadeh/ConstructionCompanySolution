# Construction ERP – Development Rules

## Product
This is a multi-tenant SaaS platform for construction contractor companies.
Each company is an Organization (Tenant). Data isolation between organizations
is mandatory.

## Technology Stack
- Backend: Python + Django
- Database: Microsoft SQL Server
- Current frontend: Django Templates + Tailwind CSS + HTMX when needed
- Future API: Django REST Framework
- Future background jobs: Celery + Redis
- Architecture: Modular Monolith with lightweight Clean Architecture

## Project Structure
- Django apps are under `apps/`
- Shared business and technical code is under `core/`
- Settings are split into base, development, and production.
- Tests are under `tests/` and/or each app's tests directory.

## Architecture Rules
1. Keep Django Views thin.
2. Put business workflows in application services/use cases.
3. Do not put complex business logic or calculations in Django templates.
4. Domain rules should not depend on HTTP, templates, or external services.
5. Avoid unnecessary abstractions and over-engineering.
6. Prefer Django ORM unless a repository abstraction has a clear benefit.
7. Use service/use-case classes for multi-step business operations.
8. Do not hide critical business logic in Django signals.

## Multi-Tenancy Rules
1. Almost every business entity must belong to an Organization.
2. Never trust `organization_id` from user input.
3. Determine current organization from authenticated user's active membership/session.
4. Every queryset, form, view, service, and API endpoint must be scoped to
   the active organization.
5. Prevent cross-tenant access and add tests for tenant isolation.

## Data Rules
Important entities must support:
- UUID public identifier
- created_at, updated_at
- created_by, updated_by where applicable
- soft delete for important business records
- audit logging for important actions

Use Decimal for money. Never use float for financial values.
Use timezone-aware datetime values.

## Security Rules
- Never hardcode secrets, credentials, tokens, or database connection strings.
- Use environment variables.
- Enforce authentication, authorization, and organization scope in every endpoint.
- Keep CSRF protection enabled.
- Validate all user input.
- Check uploaded file type and size.

## Frontend Rules
- Use Tailwind CSS classes; avoid scattered custom CSS and inline styles.
- Build responsive, mobile-first pages suitable for site engineers.
- Use HTMX only for small dynamic interactions without page refresh.
- HTMX endpoints must have the same authorization and tenant isolation as regular views.
- Reuse template components where possible.

## Code Quality
- Use English naming for code, files, classes, variables, and database fields.
- Use Python type hints.
- Write small, focused functions and classes.
- Add unit tests for business rules.
- Add integration tests for permissions and tenant isolation.
- Use select_related/prefetch_related where needed to prevent N+1 queries.

## Working Process
Before implementing a feature:
1. Inspect the existing project structure and relevant code.
2. Explain the proposed implementation plan briefly.
3. List files to create or modify.
4. Implement only the requested scope.
5. Run relevant tests, formatting, and checks.
6. Report changed files, test results, assumptions, and any follow-up work.

Do not rewrite unrelated files.
Do not introduce a package unless it has a clear purpose and is approved.

