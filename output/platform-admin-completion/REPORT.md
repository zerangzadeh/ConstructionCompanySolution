# BONIRA Platform Admin completion

Date 2026-11-07, Asia/Tehran. Baseline `main` at `1d3593a91536477fcfd146a522701980b9ebf205`, matching the local `origin/main` reference at inspection. This implementation follows the seven-section request. Concurrent changes outside this scope were left in the shared working tree.

## Delivered

| Section | Behavior |
| --- | --- |
| Dashboard | Default login landing for active Platform Admins when there is no explicit safe return URL. Real company-state, registered-account and membership counts, recent administrative events, missing starter-workflow warnings for the five newest active companies and database/cache reachability. |
| Companies | Existing searchable directory, company settings and suspend/reactivate controls. Detail identifies the company, recorded creator, current owners and local administrators. Creation records the initiating admin and initial owner separately and redirects to detail. Company, owner, audit and both starter workflows commit together. Existing partial onboarding can be retried through the same workflow services when one effective owner is identifiable. |
| Platform administrators | Current and historical Platform Admin assignments with reasoned grant/revoke actions. Ordinary operations require an active Platform Admin and an eligible account. Self-grant, self-revocation, changes to other platform duties and removal of the last effective admin are guarded. The existing technical Superuser bootstrap/recovery services remain available. |
| Roles and permissions | Separate system/global definitions, tenant-specific definitions and member assignments. Role definitions remain on the existing services. Global changes show an impact warning and check the submitted version. Owner and protected tenant governance permissions are preserved. Member-role assignment and revocation require explicit authority in the selected tenant, including independent approval. |
| Platform settings | Existing protected-operation and versioned policy catalogs are grouped in one destination. Product Surface availability is shown as read-only information. Currency, fiscal-year start and numbering prefixes on existing companies are read-only in the platform editor. |
| Activity and audit | Read-only platform events with date, actor, action and company filters. The projection includes global privilege events and safe status results. It omits raw metadata and unrelated tenant events. Metadata and change validation inspect nested lists and dictionaries before writing. |
| System status | Existing database/cache probes and, where installed, recent allowlisted signals from the existing operations sink. Unverified sources have an explicit state. The page reports dependency reachability separately from production readiness. |

The shared Persian RTL shell exposes the same seven destinations on desktop and mobile. Platform screens identify the target company independently of tenant session context. The existing confirmation component is used for company status changes and operator revocation.

## Reuse and changes

- **Existing services extended.** `apps/organizations/{access_services,services,policy_services,platform_companies,platform_views,platform_forms,forms,views,urls,context_processors}.py` and `apps/accounts/{views,admin}.py`. The company workflow starters, tenant delegation services, role catalog and platform policy services remain the sources for their own mutations.
- **New console views and templates.** `apps/organizations/platform_console.py` and `templates/organizations/platform_{administrators,audit,dashboard,health_signals,member_roles,navigation,roles_navigation,settings,status}.html`. Existing company detail/edit, role and member-authorization templates and `templates/base.html` were adapted.
- **Existing product, audit and operations boundaries extended.** `core/{product_surface,operations}.py`, `apps/audit/{models,services}.py`, `apps/organizations/{models,permission_registry,role_reconciliation}.py` and `apps/support/management/commands/operational_health.py`. The decision is recorded in `docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md`.
- **Tests.** `apps/organizations/{test_platform_console,test_p1_1_authorization,tests}.py` and `core/test_cep014_administration.py` cover the changed platform contracts and retain existing tenant safeguards.
- **Styles.** `apps/accounts/static/css/tailwind.css` was rebuilt through the existing `npm run build:css` command.
- **Migrations.** [0058_platform_onboarding_audit.py](../../apps/audit/migrations/0058_platform_onboarding_audit.py) records the onboarding-retry action choice. [0128_platform_console_permissions.py](../../apps/organizations/migrations/0128_platform_console_permissions.py) registers three platform-only capability codes without granting them to tenant roles.

## Verification

All database-backed verification uses the newly created isolated PostgreSQL database `test_bonira_platform_completion_01a1b05d`. Its 454 repository migrations were applied by the test runner. No migration was applied to a pre-existing environment database.

The runner set `DATABASES['default']['TEST']['NAME']` before Django setup and used `--reuse-db -p no:cacheprovider -q --tb=short --show-capture=no`.

| Final selection | Result |
| --- | --- |
| MVP/default. Platform console, platform companies, organization creation services/views and settings services, P1.1 authorization, CEP-014 administration, Product Surface and Accounts journeys. | 111 tests and 73 subtests PASS. |
| FULL_ERP process. Existing Accounts technical Admin and policy-localization tests, plus all 12 new console tests, which explicitly override their own profile to MVP. | 35 tests and 12 subtests PASS. |

The two selections cover 137 distinct passing tests. The second selection repeats nine console tests and adds three checks for protected financial settings, sanitized health failures and exclusion of platform privileges from business roles. Explicit-target role delegation also verifies that an existing different active-tenant session survives assignment and revocation.

Eleven legacy assertions expect technical Admin or tenant-policy routes to be available under the default MVP profile. They return 403 under MVP and pass under FULL_ERP. The dedicated MVP tests verify the intended exposure restrictions.

The independent registry/reconciliation selection reproduces the assessment baseline of 5 passing tests, 3 failures and 28 passing subtests. The failures concern four duplicate Payroll model registrations, 77 existing permission namespace mismatches and existing missing enforcement references. The three new `platform_admin.*` codes are registered and referenced by their declared enforcement modules.

Django system checks, migration-drift checks for Audit/Organizations, focused Ruff lint/format checks and whitespace checks PASS. The CSS build PASS includes a non-blocking outdated Browserslist metadata notice.

Actual browser verification is unverified. The browser tool's `local-web-development` capability reports that local browser use is disabled in Work settings. Desktop and mobile share the same seven-destination navigation template and have HTTP/template coverage. Pixel layout, keyboard behavior and SweetAlert interactions require a subsequent enabled local-browser session.

## Boundaries and outstanding items

- A Platform Admin without target-tenant business authority can manage tenant metadata and role definitions. Member-role inspection and delegation require separate tenant authorization. Existing financial and statutory activation paths remain under their domain controls.
- Existing incomplete onboarding with no unambiguous effective owner requires the governed owner recovery process. Existing audit events retain their historical actor attribution.
- Platform tenant creation requires an active initial owner account separate from the initiating admin. Currency, fiscal-year start and numbering prefixes are conservatively read-only in the platform editor for every existing company, including companies with no business records, because this task defines no domain change policy for those settings.
- The operations page depends on an authenticated application request. Database-wide outage monitoring, alerts with no installed sink, production readiness and restore qualification remain external to this workspace.
- The existing development database was inspected for migration plans only. The two new migrations require authorized application to an existing environment. The previously pending Payroll migration is separate.
- The isolated test database is retained for repeatable verification. Implementation and test evidence remain in the working tree for review. No commit, push or production action was performed.
