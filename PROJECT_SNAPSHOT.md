# Construction ERP — Project Snapshot

**Snapshot date:** 2026-09-03  
**Status:** Active MVP development  
**Architecture:** Multi-tenant Django modular monolith with SQL Server

## Implemented capabilities

The application currently provides the following tenant-scoped modules:

- **Accounts:** custom user model and username/password authentication.
- **Organizations:** organization lifecycle, active membership selection,
  invitations, role checks, and active-tenant session handling.
- **Projects:** projects, worksites, phases, soft archival, and role-limited
  project administration.
- **Daily reports:** daily worksite reporting with labor, equipment, material,
  progress, safety, and quality information.
- **Contracts:** organization-scoped project contracts and contract values.
- **Estimates:** estimate line items, Decimal totals, approvals, and locking of
  approved estimates.
- **Expenses:** recorded expenses, project/phase association, and an audited
  void workflow that preserves original financial values.
- **Payments:** posted receipts/disbursements, project/contract/phase links,
  void workflow, and financial reporting integration.
- **Documents:** validated private PDF/JPEG/PNG uploads, secure downloads,
  SHA-256 file metadata, archival, and receipt/payment association.
- **Financials:** organization and project financial reporting using approved
  estimates, recorded expenses, and posted payments.
- **Audit:** append-only audit events for important security and business
  actions.

## Current architecture safeguards

- Business workflows are implemented in per-app `services.py` modules; views
  remain thin.
- Every business query and mutation is scoped to the authenticated user's active
  organization and active membership.
- Financial amounts use `Decimal`; business records use UUID identifiers.
- Finalized financial records are corrected through audited void workflows,
  rather than deletion or silent modification.
- Audit events reject application-layer changes, deletes, bulk inserts, and
  sensitive metadata keys.
- Suspended, archived, deleted, and cancelled organizations are denied at
  service boundaries.
- Payment and expense add/change/delete operations are unavailable in Django
  admin, preventing an administrative bypass of the audited workflows.

## UI status

- Django Templates and Tailwind CSS provide the initial interface.
- Shared navigation is responsive for desktop and mobile layouts.
- Reusable components now include form fields/errors, messages, navigation, and
  a `page_header` component used by the core list pages.
- The expense void control includes a screen-reader label and server-side input
  validation.

## Pending database migrations

Run the following in a normal local terminal connected to SQL Server:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

The current unapplied migration set includes:

- `payments.0001_initial`
- `documents.0001_initial`
- `documents.0002_projectdocument_archive_reason`
- `expenses.0003_expense_void_fields`
- `audit.0003_alter_auditevent_action`
- `audit.0004_alter_auditevent_action`
- `organizations.0004_alter_organization_status`

No secrets or database credentials are stored in this repository. Local database
settings are read from `.env`; use `.env.example` as the safe template.

## Validation status

The latest validation in this workspace passed:

- `python manage.py check`
- `python -m ruff check .`
- `python -m ruff format --check .`
- Django compilation of the updated shared templates
- Lightweight Django-admin immutability tests for payments and expenses

Full database-backed tests cannot run from the Codex process because its SQL
Server TLS credential provider cannot authenticate. They should be run from the
developer's normal terminal after migrations:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Current local URL

The development login screen is available at:

`http://127.0.0.1:8011/accounts/login/`

Business pages require a logged-in user with an active organization. For example,
`/payments/` redirects to login until that context exists.

## Remaining MVP work

- Run full database-backed test coverage after SQL Server migrations.
- Create a real user and organization for browser-based workflow verification.
- Continue tenant-isolation and authorization tests for each new endpoint.
- Complete production deployment configuration and verification.
- Add future approved domains only after their workflows and ownership are
  defined: procurement, inventory, equipment, workforce, billing, and safety.

## Domain diagram

The diagram below represents the broader product-domain plan. Some entities in
it are future modules and are not part of the current Django schema yet.

![Construction ERP domain ERD](ERD_Diagram.png)
