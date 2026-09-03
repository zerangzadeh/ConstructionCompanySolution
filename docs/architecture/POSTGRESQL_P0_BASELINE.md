# PostgreSQL Migration P0.1 — Clean Current Baseline

> Date: 2026-09-03  
> Scope: P0.1 only — establish and document the current application baseline  
> Decision context: **MIGRATE NOW**, PostgreSQL with Psycopg 3, development-migration **REBASELINE**  
> Domain Model v1.0 refactoring: explicitly out of scope

## 1. Outcome

P0.1 is complete at the source/model-state level. The current Django model state is internally consistent, the requested Django and Ruff checks pass, pytest discovers 130 tests, and no SQL Server-specific schema construct blocks recreating the current schema on PostgreSQL.

P0.2 is **safe to begin with change-control conditions**:

1. P0.2 must be limited to the approved PostgreSQL dependency and configuration work.
2. The existing dirty working tree must be treated as the current baseline and preserved. Several files that P0.2 is expected to touch already contain uncommitted changes.
3. The approved identifier canonicalization policy is not fully enforced today. Its small application-layer compatibility patch must be approved and completed before the PostgreSQL schema becomes the frozen baseline, but it does not block starting P0.2.
4. The existing SQL Server connection cannot currently complete a migration-history consistency query because of a local ODBC/TLS credential error. This does not invalidate the migration-file or model-state audit, but it means database-backed runtime validation remains outstanding.

No model, migration, database setting, dependency, or application behavior was changed during P0.1.

## 2. Scope and Sources Inspected

The assessment was based on the actual working tree, not only the project snapshot. The following were read or inspected:

- `AGENTS.md`, including the approved Target Domain Model and PostgreSQL migration guidance
- `docs/architecture/POSTGRESQL_MIGRATION_ASSESSMENT.md`
- split Django settings and environment examples
- dependency and tooling configuration
- all first-party Django models and migrations
- managers, services, forms, views, decorators, middleware, admin registrations, URLs, and tests
- tenant-scoping and authorization helpers
- audit, approval, posting/void, document, and financial-reporting paths
- raw-SQL, custom-field, constraint, index, transaction, locking, and vendor-specific-code searches

The counts and results in this document describe the repository working tree on 2026-09-03.

## 3. Requested Checks

| Check | Result | Evidence / qualification |
|---|---:|---|
| `python manage.py check` | PASS | `System check identified no issues (0 silenced).` |
| `python manage.py makemigrations --check --dry-run` | PASS WITH ENVIRONMENT WARNING | Exit code 0 and `No changes detected`. Django warned that it could not check migration-history consistency because the current SQL Server ODBC connection failed during TLS negotiation. |
| `python -m ruff check .` | PASS | `All checks passed!` |
| `python -m ruff format --check .` | PASS | `120 files already formatted` |
| `python -m pytest --collect-only -q -p no:cacheprovider` | PASS | `130 tests collected in 0.32s` |

The pytest command was collection-only and used no cache provider. A database-backed full test run was not part of the requested P0.1 command set and was not represented as passing in this checkpoint.

### SQL Server warning captured during model-state checking

The warning was raised while Django tried to query the existing database's applied-migration history:

```text
pyodbc ... Encryption not supported on client ...
SSL Provider: No credentials are available in the security package
```

This is a local SQL Server connection/TLS issue, not a detected model delta. The migration autodetector completed successfully and reported no model changes requiring a migration.

## 4. Baseline Inventory

### 4.1 Counts

| Item | Count | Counting rule |
|---|---:|---|
| First-party Django models | **18** | Registered models whose app configuration is under `apps.*` |
| All registered Django models | **23** | First-party models plus Django contrib models |
| First-party migration nodes/files | **25** | Migrations belonging to first-party apps; Django contrib migrations excluded |
| Explicit model indexes | **26** | Entries declared in model `Meta.indexes`; implicit FK, uniqueness, PK, and `db_index=True` indexes excluded |
| `UniqueConstraint` declarations | **8** | Explicit constraints in model `Meta.constraints` |
| `CheckConstraint` declarations | **0** | Explicit constraints in model `Meta.constraints` |
| Pytest-discovered tests | **130** | Actual pytest collection with cache disabled |

### 4.2 Current first-party models

1. `accounts.User`
2. `organizations.Organization`
3. `organizations.OrganizationMembership`
4. `organizations.OrganizationInvitation`
5. `audit.AuditEvent`
6. `projects.Project`
7. `projects.ProjectSite`
8. `projects.ProjectPhase`
9. `contracts.Contract`
10. `estimates.Estimate`
11. `estimates.EstimateItem`
12. `expenses.Expense`
13. `payments.Payment`
14. `documents.ProjectDocument`
15. `daily_reports.DailyReport`
16. `daily_reports.DailyReportLaborEntry`
17. `daily_reports.DailyReportEquipmentEntry`
18. `daily_reports.DailyReportMaterialEntry`

### 4.3 Explicit indexes and unique constraints by model

| Model | Explicit indexes | `UniqueConstraint` count |
|---|---:|---:|
| `accounts.User` | 0 | 0 |
| `organizations.Organization` | 0 | 0 |
| `organizations.OrganizationMembership` | 0 | 1 |
| `organizations.OrganizationInvitation` | 0 | 0 |
| `audit.AuditEvent` | 2 | 0 |
| `projects.Project` | 2 | 1 |
| `projects.ProjectSite` | 1 | 1 |
| `projects.ProjectPhase` | 1 | 1 |
| `contracts.Contract` | 2 | 1 |
| `estimates.Estimate` | 3 | 1 |
| `estimates.EstimateItem` | 1 | 0 |
| `expenses.Expense` | 4 | 0 |
| `payments.Payment` | 2 | 1 |
| `documents.ProjectDocument` | 2 | 0 |
| `daily_reports.DailyReport` | 3 | 1 |
| `daily_reports.DailyReportLaborEntry` | 1 | 0 |
| `daily_reports.DailyReportEquipmentEntry` | 1 | 0 |
| `daily_reports.DailyReportMaterialEntry` | 1 | 0 |
| **Total** | **26** | **8** |

The eight explicit unique constraints are:

| Model | Constraint | Fields |
|---|---|---|
| `OrganizationMembership` | `unique_user_organization_membership` | `user`, `organization` |
| `Project` | `unique_project_code_per_organization` | `organization`, `code` |
| `ProjectSite` | `unique_site_code_per_project` | `organization`, `project`, `code` |
| `ProjectPhase` | `unique_phase_code_per_site` | `organization`, `site`, `code` |
| `Contract` | `unique_contract_number_per_organization` | `organization`, `contract_number` |
| `Estimate` | `unique_estimate_number_per_organization` | `organization`, `estimate_number` |
| `Payment` | `unique_payment_number_per_organization` | `organization`, `payment_number` |
| `DailyReport` | `daily_report_org_site_date_uq` | `organization`, `site`, `reporting_date` |

All constraint fields are non-null in their current models. None uses a database-vendor-specific condition, expression, operator class, collation, include list, or deferrable option.

## 5. First-Party Migration Baseline

### 5.1 Count by app

| App | Migration count |
|---|---:|
| `accounts` | 1 |
| `organizations` | 4 |
| `audit` | 4 |
| `projects` | 3 |
| `contracts` | 1 |
| `estimates` | 3 |
| `expenses` | 3 |
| `payments` | 1 |
| `documents` | 2 |
| `daily_reports` | 3 |
| **Total** | **25** |

### 5.2 Actual dependency graph

`accounts.__first__` below is Django's swappable-user dependency and resolves to the custom user model's first migration.

```text
accounts.0001_initial
  <- auth.0012_alter_user_first_name_max_length

organizations.0001_initial
  <- accounts.__first__
organizations.0002_organizationmembership
  <- organizations.0001_initial, accounts.__first__
organizations.0003_organizationinvitation
  <- organizations.0002_organizationmembership, accounts.__first__
organizations.0004_alter_organization_status
  <- organizations.0003_organizationinvitation

audit.0001_initial
  <- organizations.0003_organizationinvitation, accounts.__first__
audit.0002_alter_auditevent_action
  <- audit.0001_initial
audit.0003_alter_auditevent_action
  <- audit.0002_alter_auditevent_action
audit.0004_alter_auditevent_action
  <- audit.0003_alter_auditevent_action

projects.0001_initial
  <- organizations.0003_organizationinvitation, accounts.__first__
projects.0002_projectsite
  <- accounts.__first__, projects.0001_initial
projects.0003_projectphase
  <- accounts.__first__, projects.0002_projectsite

contracts.0001_initial
  <- organizations.0003_organizationinvitation, projects.0001_initial,
     audit.0002_alter_auditevent_action, accounts.__first__

estimates.0001_initial
  <- organizations.0003_organizationinvitation, projects.0001_initial,
     contracts.0001_initial, audit.0002_alter_auditevent_action,
     accounts.__first__
estimates.0002_estimate_approval
  <- estimates.0001_initial, accounts.__first__
estimates.0003_estimate_phase
  <- estimates.0002_estimate_approval, projects.0003_projectphase

expenses.0001_initial
  <- organizations.0003_organizationinvitation, projects.0001_initial,
     audit.0002_alter_auditevent_action, accounts.__first__
expenses.0002_expense_phase
  <- expenses.0001_initial, projects.0003_projectphase
expenses.0003_expense_void_fields
  <- expenses.0002_expense_phase, accounts.__first__

payments.0001_initial
  <- accounts.__first__, contracts.0001_initial,
     organizations.0003_organizationinvitation, projects.0003_projectphase

documents.0001_initial
  <- accounts.__first__, organizations.0003_organizationinvitation,
     payments.0001_initial, projects.0003_projectphase
documents.0002_projectdocument_archive_reason
  <- documents.0001_initial

daily_reports.0001_initial
  <- accounts.__first__, organizations.0003_organizationinvitation,
     projects.0002_projectsite
daily_reports.0002_daily_report_entries
  <- accounts.__first__, daily_reports.0001_initial
daily_reports.0003_dailyreport_phase
  <- daily_reports.0002_daily_report_entries, projects.0003_projectphase
```

The graph is acyclic and loadable by Django. It contains development-history noise already identified in the approved migration assessment (the incremental audit action-field alterations and organization status alteration) and some historical cross-app dependencies that do not represent current schema ownership. Those are reasons to rebaseline; they are not blockers to P0.2.

No migration contains `RunSQL`, `RunPython`, raw T-SQL, vendor-specific DDL, stored procedures, database functions, triggers, or custom migration operations.

## 6. Identifier Policy Audit

### 6.1 Approved canonical forms

| Identifier | Canonical form |
|---|---|
| Username | `value.strip().lower()` |
| Organization slug | `value.strip().lower()` |
| Project, site, and phase code | `value.strip().upper()` |
| Contract, estimate, and payment number | `value.strip().upper()` |

The approved policy makes surrounding whitespace insignificant. PostgreSQL's normal text uniqueness is case-sensitive, so canonicalization must occur before persistence and before identifier-based lookup. No `CITEXT`, custom PostgreSQL collation, or Row Level Security is required or recommended for this policy.

### 6.2 Current path-by-path behavior

| Identifier | Creation path | Update path | Lookup path | Current normalization | Finding |
|---|---|---|---|---|---|
| Username | `UserManager.create_user()` / `create_superuser()`; account admin | account admin and direct ORM save | Django authentication; invitation target lookup | Login and invitation `CharField`s strip whitespace, but the manager does not strip/lower and lookups do not lower | Lowercase and whitespace policy is not guaranteed. Case variants can be stored and PostgreSQL exact lookups can fail for differently cased input. |
| Organization slug | `create_organization_with_owner()` through `OrganizationForm`; admin/direct ORM | organization admin/direct ORM | No core tenant-session resolution depends on slug; UUID is used for active organization | ModelForm strips whitespace; service passes the received slug unchanged; no lowercase safeguard | Lowercase is conventional in current tests but not an enforced invariant. |
| Project code | `create_project()` through `ProjectForm`; admin/direct ORM | project admin/direct ORM; no public update service found | Tenant-scoped model/service queries and uniqueness constraint | Service strips; ModelForm strips; neither uppercases | `P-001` and `p-001` can coexist under PostgreSQL despite representing the same approved identifier. |
| Site code | `create_project_site()` through `ProjectSiteForm`; admin/direct ORM | admin/direct ORM; no public update service found | Exact tenant/project duplicate lookup | Service and form strip; no uppercase conversion | Duplicate pre-check and database uniqueness are case-sensitive. |
| Phase code | `create_project_phase()` through `ProjectPhaseForm`; admin/direct ORM | status service does not change code; admin/direct ORM can | Exact tenant/site duplicate lookup | Service and form strip; no uppercase conversion | Canonical uppercase is not enforced. |
| Contract number | `create_contract()` through `ContractForm`; admin/direct ORM | admin/direct ORM; no public update service found | Exact organization-scoped duplicate lookup | Service and form strip; no uppercase conversion | Canonical uppercase and case-insensitive semantic uniqueness are not enforced. |
| Estimate number | `create_estimate()` through `EstimateForm`; admin/direct ORM | admin/direct ORM; approved estimates are otherwise locked by services | Exact organization-scoped duplicate lookup | Service and form strip; no uppercase conversion | Canonical uppercase is not enforced; approved-record immutability does not itself normalize the number. |
| Payment number | `create_payment()` through `PaymentForm`; direct ORM | financial mutations are disabled in admin; service has no number-update workflow | Exact organization-scoped duplicate lookup | Service and form strip; no uppercase conversion | Main UI/service path trims but does not uppercase; direct ORM remains an unguarded path. |

All inspected relevant Django form fields report `strip=True`, confirming that browser form submissions normally ignore surrounding whitespace. That protection is not universal because managers, services invoked directly, model/admin paths, and exact lookup inputs do not all share a canonicalizer.

Repository searches found no `.upper()`, `.casefold()`, relevant lowercase normalization, `iexact`, `Lower(...)`, database collation, or expression-based uniqueness implementation for these identifiers.

Current tests overwhelmingly use already-canonical lowercase usernames/slugs and uppercase codes/numbers. No test was found that proves mixed-case or surrounding-whitespace inputs converge to one canonical value.

### 6.3 Minimal compatibility change required after P0.1 approval

This is a documented follow-up only; it was not implemented in P0.1.

1. Introduce two small, database-agnostic identifier functions in shared application code:
   - lower canonicalization: `strip()` then `lower()`
   - upper canonicalization: `strip()` then `upper()`
2. Normalize before persistence in the authoritative creation services/managers so duplicate checks and saved values use the same representation.
3. Normalize form values before Django's model uniqueness validation so users receive form errors instead of late `IntegrityError`s.
4. Add a model-level persistence safeguard for these identity fields so current admin and direct `objects.create()` paths cannot bypass the invariant. The application currently has no bulk-update path for them; such a path must remain prohibited or explicitly canonicalize values.
5. Normalize username before authentication and invitation-user lookup.
6. Add focused tests for lowercase username/slug, uppercase codes/numbers, whitespace removal, semantic uniqueness, admin/direct-manager coverage, and lookups with non-canonical input.

No PostgreSQL extension or PostgreSQL-only constraint is needed. Existing uniqueness constraints become semantically correct once all stored identifiers are canonical. Because there is no data to preserve, no production data migration is required; the new empty PostgreSQL database should be populated only with canonical test/development data.

Likely application files for that separately approved patch are the identifier helper, the relevant account/organization/project/contract/estimate/payment managers or services, their forms/models where the persistence safeguard lives, and focused tests. It must not be mixed with Domain Model v1.0 changes.

## 7. PostgreSQL Schema Compatibility Confirmation

The current model schema does not contain SQL Server-specific behavior that blocks PostgreSQL rebaselining.

Confirmed portable characteristics:

- primary/business identifiers use Django `UUIDField` with Python-side UUID defaults;
- financial values use `DecimalField`, not floating-point fields;
- timestamps use ordinary Django `DateTimeField` behavior;
- JSON metadata uses Django `JSONField` and does not depend on T-SQL JSON functions;
- document storage uses `FileField` metadata/path semantics rather than SQL Server binary types;
- relationships use standard `ForeignKey` and `OneToOneField` behavior;
- constraints and indexes use standard Django declarations;
- transactional workflows use Django `transaction.atomic()` and normal ORM locking patterns;
- no custom database field, database-generated default, generated column, sequence customization, `db_collation`, custom schema, or vendor-specific identifier quoting was found;
- no application raw SQL or T-SQL was found;
- no migration embeds SQL Server DDL or a SQL Server-only operation;
- declared database object names remain below PostgreSQL's 63-byte identifier limit.

Expected backend differences that must be tested, but do not block rebaseline:

- ordinary PostgreSQL string equality and uniqueness are case-sensitive, which exposes the current identifier-normalization gap;
- PostgreSQL maps Django `JSONField` to native `jsonb`; current ORM use remains portable;
- timezone-aware datetime storage representation differs internally, while Django's public behavior remains compatible;
- transaction and row-lock behavior should be revalidated with workflow tests;
- deterministic ordering must continue to be explicit where UI/test behavior depends on it.

The shared-database/shared-schema multitenancy architecture is unaffected. Tenant scope remains `organization_id` plus active membership/service validation. RLS is not required for the database migration and remains out of scope.

## 8. P0.2 Preservation Baseline

P0.2 may change only approved dependency/configuration/documentation surfaces needed to make PostgreSQL selectable. It must preserve all of the following:

### 8.1 Source and schema invariants

- 18 first-party models and their current fields/relationships
- 26 explicit indexes
- 8 explicit `UniqueConstraint`s
- no new or changed business model
- no Domain Model v1.0 entity
- no tenant-architecture change
- no business workflow or authorization change
- no migration deletion, regeneration, or rebaseline yet
- no SQL Server configuration removal during the additive P0.2 step
- no `CITEXT`, custom collation, RLS, schema-per-tenant, or database-per-tenant feature

### 8.2 Required automated gate for P0.2

Against the current configuration and, once available, the empty PostgreSQL target configuration:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Acceptance expectations:

- `check`: zero issues;
- `makemigrations --check --dry-run`: exit 0 and `No changes detected`;
- pytest: all 130 currently discovered tests collected and passed, with no unexpected skips;
- Ruff lint: zero violations;
- Ruff format check: zero files requiring formatting;
- the inventory counts above remain unchanged;
- migration graph remains unchanged until the separately approved rebaseline phase;
- no tenant-scoping, approval, void, audit, or document-security regression.

### 8.3 Database and manual smoke gate before PostgreSQL is frozen

These are later migration validation requirements, not actions performed in P0.1:

- create an empty PostgreSQL database with least-privilege credentials;
- create/apply the approved clean migration baseline;
- rerun the full automated gate on PostgreSQL;
- exercise login, organization selection/switching, project/site/phase creation, contract creation, estimate creation/approval, expense create/void, payment create/void, daily report create/submit/approve, document upload/download/archive, and financial reporting;
- repeat tenant-switching and cross-tenant denial scenarios;
- verify Decimal totals, timezone-aware values, uniqueness failures, atomic workflows, and row-lock-sensitive transitions;
- verify the approved identifier canonicalization cases once their separate patch is approved.

## 9. Risks and Blockers

| Item | Severity | Blocks P0.2? | Treatment |
|---|---:|---:|---|
| Existing dirty working tree, including `.env.example`, `config/settings/base.py`, `config/settings/production.py`, and `requirements.txt` | MEDIUM | Conditional | Treat the exact working tree as user-owned baseline. Review diffs before editing and make only surgical P0.2 changes. Do not clean, reset, stash, or overwrite unrelated work. |
| SQL Server ODBC/TLS connection failure during migration-history check | MEDIUM | No | P0.2 introduces an additive PostgreSQL path. Database-backed validation must run once PostgreSQL is available. |
| Identifier policy not fully enforced | MEDIUM | No for additive P0.2; yes before final PostgreSQL baseline freeze | Implement the separately approved, database-agnostic canonicalization patch and tests before rebaseline acceptance. |
| Full pytest suite not executed in this P0.1 run | MEDIUM | No for starting P0.2; yes for accepting P0.2 | P0.2 acceptance requires all 130 discovered tests to pass on the configured target database. |
| SQL Server-specific schema behavior | NONE FOUND | No | No remediation required. |

There is no schema-level blocker to PostgreSQL rebaselining.

## 10. P0.1 Acceptance Statement

The repository has a reproducible current-source baseline:

- Django system check passes;
- the migration autodetector reports no changes;
- lint and formatting checks pass;
- 130 tests are discoverable;
- 18 first-party models, 25 first-party migrations, 26 explicit indexes, and 8 explicit unique constraints are accounted for;
- the current migration dependency graph is documented;
- identifier-policy gaps and their minimal database-agnostic remedy are documented;
- no SQL Server-specific schema construct blocks an empty PostgreSQL rebaseline.

**Decision: P0.2 may begin after explicit approval, subject to preserving the dirty working tree and treating the full 130-test run plus identifier canonicalization as required gates before the PostgreSQL baseline is finalized. Do not begin P0.2 as part of this task.**
