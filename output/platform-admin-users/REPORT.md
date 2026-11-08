# BONIRA System Users management

Implemented on 2026-11-08. Baseline `main` and local upstream `1d3593a91536477fcfd146a522701980b9ebf205`. The changes build on the existing uncommitted Platform Admin work and preserve unrelated changes.

## Delivered

- **کاربران سامانه** is the third destination in the shared eight-section Platform Admin menu. The dashboard links to it from Quick Actions and the registered-accounts KPI.
- The directory has one row per account and uses server-side search, company and status filters, membership counts and pagination. The account file shows profile information, company memberships, effective Platform Admin status and the ten latest relevant global account events.
- Platform Admins with the corresponding catalog permissions can create independent accounts, edit names and phone numbers, change status with a recorded reason, and request email recovery. Usernames and existing recovery addresses are read-only in this workspace because they are authentication and recovery identifiers.
- Membership organization and status are visible as account-administration data. Role names require the actor's existing membership and role-view permissions in the target company. Account creation and status changes do not grant a tenant membership or role.
- Deactivation protects the last effective Platform Admin, the last active owner of an active or suspended company, technical recovery duties, staff, Superusers, blocked accounts and the initiating administrator. Account deactivation changes the authentication revision, invalidating prior Django sessions and recovery links, including after reactivation. Pending tenant membership activation cannot undo a platform deactivation.
- New accounts require a distinct registered recovery email. Django stores the hash of an undisclosed random initial credential. The account holder chooses a password through the existing recovery flow. Recovery requests target only the stored address, require an active eligible account, apply a per-account cooldown, and log the requester without saving the link or recipient address in event metadata. The UI distinguishes SMTP acceptance, transport failure and unavailable configuration.

## Reuse and files

- `apps/accounts/platform_user_services.py` and `apps/accounts/platform_user_views.py` add bounded account operations and screens. They reuse `User`, `OrganizationMembership`, `PlatformRoleAssignment`, the existing authorization and audit services, and shared pagination.
- `apps/accounts/{models,recovery,views,admin}.py` integrates authentication revision handling with Django session and token primitives and the existing password recovery forms and email templates. `apps/organizations/{access_services,services}.py` applies the corresponding ownership and reactivation checks at the existing authorization seams. [Django authentication and session handling](https://docs.djangoproject.com/en/5.2/topics/auth/default/#session-invalidation-on-password-change) · [Django email API](https://docs.djangoproject.com/en/5.2/topics/email/)
- `apps/organizations/{models,permission_registry,role_reconciliation,urls,context_processors,platform_console}.py` and `core/product_surface.py` register the access, route exposure, navigation and account audit projection. `apps/audit/models.py` adds creation and update action labels.
- `templates/accounts/platform_user_{list,detail,form,status_badge}.html`, `templates/components/page_header.html`, `templates/organizations/platform_dashboard.html`, `templates/base.html` and `apps/accounts/static/css/{erp_platform,tailwind}.css` compose the RTL screens with shared headers, forms, buttons, confirmation behavior and pagination.
- `apps/accounts/test_platform_users.py` covers the new journeys. `apps/organizations/test_platform_console.py` extends the existing console navigation regression.

## Permissions and migrations

| Migration | Purpose |
| --- | --- |
| [accounts 0010](../../apps/accounts/migrations/0010_platform_user_management.py) | Adds a nullable account authentication revision. Accounts without a revision retain their existing session and recovery hash behavior. |
| [audit 0059](../../apps/audit/migrations/0059_platform_user_management.py) | Registers account creation and update audit actions. |
| [organizations 0129](../../apps/organizations/migrations/0129_platform_user_permissions.py) | Registers `platform_admin.users_view`, `platform_admin.users_manage` and `platform_admin.users_recover`. They require an effective platform duty and are excluded from tenant role grants. |

All three migrations were rehearsed on newly created test databases. The configured development database was checked with a migration plan only. It still needs these three migrations and the preceding platform migrations `audit.0058` and `organizations.0128`. The separate pending Payroll migration is outside this implementation. The updated user model needs `accounts.0010` before the existing development server can read user rows. No production operation, Git commit or push was performed.

## Verification

- The final clean isolated PostgreSQL selection passed **114 tests and 83 subtests**. It covered the platform user directory, profile mutations, deactivation and reactivation, old sessions and links, last-admin and last-owner safeguards, pending tenant activation, missing permissions, tenant isolation, public and administrative recovery, cooldown, SMTP unavailable/failure handling and MVP Product Surface exposure.
- The separate FULL_ERP technical Admin regression passed **15 tests**. Django system and migration-drift checks, focused Ruff lint and format checks, CSS build and whitespace checks passed. The CSS build reported a non-blocking outdated Browserslist metadata notice.
- The initial isolated clone contained prior synthetic browser fixtures, which affected global-count assertions. The final automated run used a newly created clean isolated database. The browser used a separate isolated clone with synthetic fixtures.

Browser validation used an isolated localhost server and synthetic fixtures. Desktop verification at 1440 px covered the dashboard shortcut, account KPI link, eight destinations, search returning a single account and the membership boundary in the detail page. Mobile verification at 390 px covered the keyboard-opened drawer, eight destinations, RTL card layout and horizontal fit. The SMTP-disabled browser displayed the unavailable recovery state. Account mutations and signed recovery were exercised through integration tests.

- [Desktop directory](desktop-directory.jpg)
- [Mobile directory](mobile-directory.jpg)

## Remaining limits

- Account recovery delivery requires the existing SMTP settings. Tests verify transport acceptance and failure behavior with synthetic messages. Receipt by a real mailbox requires an enabled environment.
- The directory intentionally keeps role assignment and protected technical account changes in their existing governed workflows.
