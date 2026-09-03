# PostgreSQL Migration Assessment

## Recommendation — MIGRATE NOW

Migrate the current application to PostgreSQL **before** beginning Domain Model
v1.0 refactoring. This is the lowest-cost point in the project lifecycle: the
application is still in active development, there is no production data to
preserve, the current database can be discarded, and the inspected domain code
uses portable Django ORM features rather than SQL Server-specific SQL.

The migration should be a dedicated infrastructure/schema-baseline change with
no intentional domain behavior changes. It must pass the validation gate in
this document before Domain Model work resumes.

| Decision item | Assessment |
|---|---|
| Recommendation | **MIGRATE NOW** |
| Overall migration risk | **MEDIUM** |
| Estimated implementation files affected | **Approximately 43 version-controlled paths** with the recommended rebaseline: 8 maintained dependency/configuration/documentation files, 25 old first-party migration files replaced by approximately 10 clean initial migrations. Add 1–3 test-file changes only if compatibility tests are placed in existing test modules. |
| First-party migrations reviewed | **25** |
| SQL Server-specific issues found | **14 repository coupling locations/groups:** 8 active dependency/configuration couplings and 6 documentation/tooling references |
| Recommended migration-history strategy | **REBASELINE** |
| Major blockers | No technical blocker. Execution gates are an explicit string/case-sensitivity policy, an available PostgreSQL instance, coordinated recreation of every development/test database, and a passing full PostgreSQL test/browser baseline. |
| Recommended first implementation step | **P0.1 — Establish and record a clean current baseline**, including the 130 discovered tests, migration state, case-variant behavior decisions, and PostgreSQL version/environment choice. |

Why the risk is MEDIUM rather than LOW:

- driver and settings replacement is straightforward;
- no current data migration is required;
- all current first-party migrations are written with standard Django operations;
- however, SQL Server collation is not declared in the repository, while
  PostgreSQL string equality and uniqueness are normally case-sensitive;
- the current full suite has not been demonstrated against PostgreSQL and has no
  real concurrency tests; and
- a migration rebaseline changes active migration identifiers and therefore
  requires every developer/test database to be recreated together.

## 1. Inspection scope and current baseline

This assessment is based on the actual repository inspected on 2026-09-03. The
inspection covered:

- the complete current `AGENTS.md` and its Target Domain Model;
- `PROJECT_SNAPSHOT.md`, while treating code and migrations as authoritative;
- all requirements and tooling configuration;
- `.env.example` and all split Django settings;
- all current applications, 18 registered business/application models, managers,
  querysets, services, forms, views, admin registrations, and tests;
- all 25 first-party migration files;
- raw SQL, database-vendor imports, custom fields, PostgreSQL-specific imports,
  indexes, constraints, transactions, row locks, JSON, UUID, Decimal, datetime,
  and document metadata behavior; and
- available local package metadata without installing or removing anything.

Current verified facts:

- Django in the virtual environment is 5.2.17.
- `mssql-django` 1.8.0 and `pyodbc` 5.3.0 are installed.
- Neither `psycopg` nor `psycopg2` is installed.
- `manage.py check` passes.
- `manage.py makemigrations --check --dry-run` reports no model changes, but its
  migration-history consistency probe cannot connect to the configured SQL
  Server because of the existing ODBC/TLS credential-provider error.
- The repository contains 130 test methods across the current apps. This is more
  than the historical 75-test checkpoint in project documentation.
- No `TransactionTestCase` or explicit concurrent-locking test was found.
- No raw SQL, `RunSQL`, `RunPython`, database-vendor branch, custom database field,
  stored procedure, trigger, view, sequence SQL, T-SQL function, or PostgreSQL
  extension usage was found.
- No Dockerfile, Compose configuration, or CI workflow is currently present.
- All financial values use Django `DecimalField`/Python `Decimal`; all current
  important domain records use UUID primary keys.
- Audit metadata is the only `JSONField`.
- ProjectDocument is the only `FileField`; file bytes remain in file storage and
  only the path/metadata are stored in the database.

The current architecture remains a shared-database, shared-schema modular Django
monolith with `Organization` as the tenant boundary. Changing the database engine
does not require changing that model.

## 2. SQL Server dependency inventory

The 14 groups below define the reported issue count. Repeated lines inside one
file/configuration concern are treated as one group unless they require distinct
replacements.

| # | File/location | Current usage | PostgreSQL replacement required? | Replacement approach | Risk |
|---:|---|---|---|---|---|
| 1 | `requirements-db.txt` — `mssql-django` | Third-party Django SQL Server backend. | Yes | Replace with Psycopg 3 package after PostgreSQL is approved and available. Django's built-in PostgreSQL backend needs no separate Django backend package. | LOW |
| 2 | `requirements-db.txt` — `pyodbc` | ODBC DB-API driver required indirectly by `mssql-django`. | Yes | Remove after PostgreSQL validation; Psycopg replaces the ODBC transport. | LOW |
| 3 | `config/settings/base.py` — `ENGINE` | Uses `"mssql"`. | Yes | Use `"django.db.backends.postgresql"`. | LOW |
| 4 | `config/settings/base.py` — port | Defaults `DB_PORT` to SQL Server port 1433. | Yes | Default to PostgreSQL port 5432 while retaining an environment override. | LOW |
| 5 | `config/settings/base.py` — ODBC driver option | Builds `OPTIONS["driver"]` from `DB_DRIVER`, defaulting to ODBC Driver 17 for SQL Server. | Yes | Remove the driver option; Psycopg/libpq does not use ODBC driver names. | LOW |
| 6 | `config/settings/base.py` — ODBC extra parameters | Passes semicolon-delimited `DB_EXTRA_PARAMS` as `OPTIONS["extra_params"]`. | Yes | Replace with explicit libpq/Django PostgreSQL options such as `sslmode`, optional `sslrootcert`, and `connect_timeout`. Do not translate the string mechanically. | MEDIUM |
| 7 | `config/settings/production.py` | Requires and parses `DB_EXTRA_PARAMS`, enforcing `Encrypt=yes` and rejecting `TrustServerCertificate=yes`. | Yes | Enforce PostgreSQL `DB_SSLMODE=verify-full` and, where needed, a CA path. Retain strong production validation but rewrite it for libpq semantics. | MEDIUM |
| 8 | `.env.example` | Documents SQL Server, port 1433, `DB_DRIVER`, and `DB_EXTRA_PARAMS`. | Yes | Keep generic DB name/user/password/host variables; use port 5432 and PostgreSQL SSL variables. | LOW |
| 9 | `README.md` | Names SQL Server in current stack/onboarding. | Yes for maintained documentation | Update only after PostgreSQL validation so onboarding commands describe the real baseline. | LOW |
| 10 | `AGENTS.md` | Declares SQL Server as the architecture, validation history, operational gap, and prioritized deployment work. | Yes for architectural truth | Update the database-stack, status, migration, validation, and priority sections after the switch; do not change Domain Model v1.0. | LOW |
| 11 | `PROJECT_SNAPSHOT.md` | Describes SQL Server architecture, pending migrations, TLS limitation, and validation steps. | Yes | Regenerate/update after the final PostgreSQL validation checkpoint. | LOW |
| 12 | `docs/architecture/PROPOSED_REFACTOR_SEQUENCE.md` | R0/R1 explicitly refer to SQL Server baseline behavior. | Yes | Update the baseline wording after PostgreSQL is frozen; do not reorder Domain Model phases as part of database migration. | LOW |
| 13 | `AGENTSـold.md` | Historical copy contains SQL Server statements. | No runtime replacement | Treat as archival/stale documentation. Do not silently rewrite or delete it; decide separately whether archival files remain in the repository. | LOW |
| 14 | `project_tree.txt` and current virtual environment snapshot | The generated tree records installed `mssql`, `mssql-django`, and `pyodbc` artifacts. | Not required for runtime; required if the artifact is maintained | Regenerate or retire the tree only under a separate documentation/tooling decision. The ignored `.venv` itself should be rebuilt/cleaned only after validation. | LOW |

The developer's ignored `.env` will also need new values, but it was deliberately
not read because it may contain credentials and is not counted as a repository
issue. No SQL Server-specific CI or Docker configuration exists.

### SQL Server-specific items not found

- raw T-SQL or cursor execution;
- stored procedures, triggers, database views, functions, or schemas;
- bracket quoting or manually quoted identifiers;
- `IDENTITY`, `TOP`, `GETDATE`, `NEWID`, `nvarchar`, `datetime2`, or `bit` SQL;
- database-specific `RunSQL`, `SeparateDatabaseAndState`, or vendor conditionals;
- SQL Server-specific indexes, included columns, filtered indexes, collations,
  tablespaces, or deferrable constraints;
- custom model fields or `django.contrib.postgres` fields;
- database-generated (`db_default`) values or generated columns; and
- database routers or multiple database aliases.

## 3. Django model compatibility audit

### 3.1 Cross-model field and ORM behavior

| Concern | Current behavior | PostgreSQL behavior | Required change | Risk |
|---|---|---|---|---|
| UUID primary keys | All 18 current application models have UUID PKs generated in Python (`uuid.uuid4`), either directly or through `core.UUIDModel`. SQL Server stores its backend representation. | Django maps `UUIDField` to native PostgreSQL `uuid`. Values remain Python `UUID` instances. | None in models or services. Replay/rebaseline migrations and verify UUID URL/object lookup. | LOW |
| Decimal money/quantities | Nine declared Decimal fields use precisions of `(18,2)`, `(18,4)`, or `(8,2)`; services use Python Decimal and estimate totals use `ROUND_HALF_UP`. | Maps to PostgreSQL `numeric(p,s)` and returns Decimal. | No model change. Retain application rounding and assert exact totals in PostgreSQL tests. | LOW |
| DateTime/time zones | `USE_TZ=True`, project timezone is UTC, and services use `timezone.now()`/auto timestamps. | Django uses PostgreSQL `timestamp with time zone`; PostgreSQL stores instants internally in UTC and converts for the session timezone. | No model change. Verify aware values, invitation expiry, submit/approve/void timestamps, and microsecond comparisons. | LOW |
| DateField | Project, contract, expense, payment, and daily report dates are date-only. | Native `date`; portable. | None. | LOW |
| JSONField | `AuditEvent.metadata` uses `models.JSONField(default=dict)`. Current code creates and reads JSON but performs no JSON containment/path query. | Django maps JSONField to PostgreSQL `jsonb`. Object key order is not a semantic guarantee. | No schema/model change. Test representative nested metadata and avoid depending on textual key order. | LOW |
| TextField/CharField | Standard Unicode strings with declared CharField lengths up to 255. | `varchar(n)` and `text`, Unicode via database encoding (create database as UTF-8). PostgreSQL enforces `varchar(n)` lengths. | No field change. Create the database with UTF-8 and validate long/boundary inputs. | LOW |
| FileField | Database stores a path up to 100 characters; bytes are in configured storage. Metadata contains MIME, size, SHA-256, uploader, and archive fields. | Same ORM behavior; database engine does not move file bytes. | No model change. Preserve media root and execute upload/download/hash tests. | LOW |
| BooleanField | Standard Boolean flags such as `ProjectSite.is_active`. | Native PostgreSQL boolean; ORM conversion is portable. | None. | LOW |
| Positive integer fields | Daily counts, sort order, and file size use positive integer field types. | Django creates appropriate integer types and backend-generated nonnegative checks where supported. | No intentional model change. Confirm generated constraints and boundary behavior after rebaseline. | LOW |
| ForeignKey/on-delete | Standard CASCADE, SET_NULL, and PROTECT relations. FK columns are indexed by Django unless disabled. | Fully supported. PostgreSQL FK constraints may be created with backend-specific deferrability semantics, but Django ORM behavior remains portable. | No model change. Validate cascade/protect/set-null cases and all tenant relationship tests. | LOW |
| OneToOneField | None currently exists. | Supported. | No change. | LOW |
| Unique fields/constraints | Unique username, organization slug, invitation token hash, and eight `UniqueConstraint`s. All fields participating in current composite unique constraints are non-null. | Portable B-tree uniqueness. PostgreSQL normally treats string equality as case-sensitive and treats multiple NULLs as distinct by default. | Decide case policy before cutover. No NULL-policy change is needed for current non-null composite keys. | **MEDIUM** |
| CheckConstraint | No explicit model CheckConstraint exists. | Supported. | None for migration. Do not add domain constraints during this database-only phase. | LOW |
| Explicit indexes | 26 model Index declarations; longest explicitly named database object found is 39 characters. | PostgreSQL identifier limit is 63 bytes; current explicit names fit. Django may create an additional pattern-operator index for indexed varchar/text fields used by LIKE lookups. | No model change. Compare expected indexes after migration and account for legitimate PostgreSQL pattern indexes. | LOW |
| Descending index fields | Audit indexes include descending `created_at`. | PostgreSQL B-tree supports descending columns. | None. | LOW |
| Ordering | Current orderings use names, non-null dates/timestamps, status, and sort order. No material default ordering by a nullable field was found. | PostgreSQL's default NULL sort position differs from some databases, but it should not affect current declared orderings. Ties remain unspecified unless a tie-breaker is given. | No current change required; tests must not assume order among equal keys. | LOW |
| Null/blank | Django `blank` is form validation; `null` is database state. Existing code follows normal Django semantics. | Same ORM contract. Empty string and NULL remain distinct. | None. | LOW |
| Database defaults | Defaults are Python/Django defaults (`uuid4`, Decimal constants, choices, auto timestamps); no `db_default` or generated fields. | Portable. | None. | LOW |
| `transaction.atomic()` | 24 transaction references protect multi-step services. | PostgreSQL defaults to READ COMMITTED through Django and supports savepoints. | Keep default isolation initially; do not change transaction design during migration. Run workflow and error/savepoint tests. | LOW |
| `select_for_update()` | 11 row-lock references protect invitations, phase transitions, archive, approval, submit, and void workflows; calls are inside atomic workflows. | PostgreSQL provides well-defined row locks; conflicting operations block until release and can deadlock if lock order differs. | No service change required for parity. Add PostgreSQL `TransactionTestCase` concurrency coverage before relying on concurrency guarantees. | MEDIUM |
| `select_related()` / `prefetch_related()` | Used throughout scoped query/read services and financial reporting. | ORM-generated joins and prefetch queries are supported. Query plans will differ. | No code change expected; run functional tests and profile only after correctness passes. | LOW |

Django 5.2 supports PostgreSQL 14+ and recommends Psycopg 3.1.8 or newer over
Psycopg 2. The built-in engine is `django.db.backends.postgresql`.
[Django database documentation](https://docs.djangoproject.com/en/5.2/ref/databases/)

### 3.2 Case sensitivity is the principal compatibility condition

The repository does not specify a SQL Server database/column collation and does
not normalize or case-fold current business keys. There are no `iexact`, `Lower`,
or `casefold` lookups. Services strip surrounding whitespace but use exact
lookups. Therefore actual SQL Server behavior depends on the developer database's
collation, while normal PostgreSQL equality and unique constraints distinguish
case.

Potentially affected identifiers are:

- `User.username` and exact invitation username lookup;
- `Organization.slug`;
- `Project.code`;
- `ProjectSite.code`;
- `ProjectPhase.code`;
- `Contract.contract_number`;
- `Estimate.estimate_number`; and
- `Payment.payment_number`.

Example: a commonly case-insensitive SQL Server collation may reject `P-001` and
`p-001` under one tenant, while a normal PostgreSQL unique constraint permits
both. This is not a PostgreSQL incompatibility in the models; it is an undeclared
product rule exposed by the switch.

**Required before cutover:** approve one policy per identity class and add tests.
For codes/numbers, the lowest-complexity option is application normalization
(for example uppercase canonical storage) if that matches business intent. If
case-insensitive uniqueness is required without canonical storage, use a
deliberately approved Django functional constraint/collation solution in a
separate, minimal compatibility change. Do not introduce `citext` or broad
collation changes automatically.

### 3.3 Per-model PostgreSQL verdict

| Model | Relevant database features | PostgreSQL verdict and required change | Risk |
|---|---|---|---|
| `accounts.User` | UUID PK; unique username; char/email/boolean/datetime; auth M2M tables | Types and Django auth migrations are portable. No model change. Confirm username case policy and authentication/invitation behavior. | MEDIUM |
| `organizations.Organization` | UUID; unique slug; indexed status; timezone/currency strings; nullable actor FKs/timestamp | Portable. No type change. Confirm slug case policy. | MEDIUM |
| `organizations.OrganizationMembership` | UUID; FK pair unique; nullable inviter/joined time; ordered through related names | Portable; unique columns are non-null, so NULL uniqueness is irrelevant. No change. | LOW |
| `organizations.OrganizationInvitation` | UUID; unique SHA-like token string; indexed status; expiry/acceptance times; FKs | Portable. Token generation is application-side. Re-run expiry and locked acceptance tests. | LOW |
| `audit.AuditEvent` | UUID; nullable tenant/actor FKs; JSONField; descending indexes; immutable manager/queryset | PostgreSQL `jsonb` and descending indexes are supported. No model change. Application-level immutability remains application-level, not a database trigger. | LOW |
| `projects.Project` | UUID; Decimal budget; scoped unique code; dates; soft-delete timestamp; compound indexes | Portable. Confirm code case policy and exact Decimal/date behavior. | MEDIUM |
| `projects.ProjectSite` | UUID; Boolean; scoped unique code; compound index; project/tenant FKs | Portable. Confirm code case policy. PostgreSQL does not automatically strengthen cross-tenant FK equality; existing service checks remain required. | MEDIUM |
| `projects.ProjectPhase` | UUID; scoped unique code; status/date/indexes; site/tenant FKs | Portable. Confirm code case policy and lifecycle row locking. | MEDIUM |
| `contracts.Contract` | UUID; scoped unique number; Decimal; dates/text; project/tenant/actor FKs; indexes | Portable. Confirm contract-number case policy. No migration-specific domain refactor. | MEDIUM |
| `estimates.Estimate` | UUID; scoped unique number; nullable contract/phase/actors; status indexes | Portable. Confirm estimate-number case policy and approval lock behavior. | MEDIUM |
| `estimates.EstimateItem` | UUID; Decimal quantity/price; free-text unit; sort ordering; FK/index | Portable. Decimal round-trip and `ROUND_HALF_UP` stay application-side. | LOW |
| `expenses.Expense` | UUID; Decimal; nullable phase/void actor/time/deletion; indexed strings and compound indexes | Portable. Re-run recorded/void reporting and immutability tests. No schema change. | LOW |
| `payments.Payment` | UUID; scoped unique number; Decimal; nullable contract/phase/void data; compound indexes | Portable. Confirm payment-number case policy and row-locked void behavior. | MEDIUM |
| `documents.ProjectDocument` | UUID; FileField path; positive big integer; SHA-256/MIME strings; nullable payment/archive actor/time; indexes | Portable. No file migration because current database data/storage need not be preserved; validate new uploads/downloads and 100-character path constraint. | LOW |
| `daily_reports.DailyReport` | UUID; date-based scoped unique; nullable phase/approval data; text/status/indexes | Portable. Date uniqueness has no collation risk; validate submit/approve locks and timestamps. | LOW |
| `daily_reports.DailyReportLaborEntry` | UUID; Decimal hours; positive count; text; report/tenant FKs | Portable. No change. | LOW |
| `daily_reports.DailyReportEquipmentEntry` | UUID; Decimal hours; text; report/tenant FKs | Portable. No change. | LOW |
| `daily_reports.DailyReportMaterialEntry` | UUID; Decimal quantity; text material/unit; report/tenant FKs | Portable. No change; material/UOM refactor remains later Domain Model work. | LOW |

PostgreSQL unique constraints treat NULL values as distinct unless explicitly
configured otherwise. None of the current eight composite `UniqueConstraint`s
contains a nullable field, so no current behavior change is required.
[PostgreSQL constraint documentation](https://www.postgresql.org/docs/current/ddl-constraints.html)

## 4. Migration history audit

### 4.1 File-by-file classification

Classification result:

- **A — Portable and safe to replay:** 21
- **B — Portable with minor changes:** 0
- **C — SQL Server-specific or risky:** 0
- **D — Development-history noise reasonably rebaselined:** 4

Class D files still use portable Django operations; D means their historical
steps add little value when there is no deployed data/history to preserve.

| Migration | Operations | Class | Assessment |
|---|---|---:|---|
| `accounts.0001_initial` | CreateModel | A | Standard custom-user schema; dependency on Django auth migration is portable. |
| `audit.0001_initial` | CreateModel, AddIndex x2 | A | Standard UUID/FKs/JSON/indexes. PostgreSQL creates JSON as jsonb. |
| `audit.0002_alter_auditevent_action` | AlterField | D | Choice/state evolution on CharField; no SQL Server construct. Superseded by later choice migrations. |
| `audit.0003_alter_auditevent_action` | AlterField | D | Repeated choice/state evolution; rebaseline can capture final state once. |
| `audit.0004_alter_auditevent_action` | AlterField | D | Repeated choice/state evolution; rebaseline can capture final state once. |
| `contracts.0001_initial` | CreateModel, AddConstraint, AddIndex x2 | A | Standard fields and constraints. Contains an unnecessary historical dependency on an audit choice migration, but remains replayable. |
| `daily_reports.0001_initial` | CreateModel, AddConstraint, AddIndex x2 | A | Standard FK/date/text/status schema. |
| `daily_reports.0002_daily_report_entries` | CreateModel x3, AddIndex x3 | A | Standard child tables, Decimal fields, and indexes. |
| `daily_reports.0003_dailyreport_phase` | AddField, AddIndex | A | Nullable FK expansion is portable. |
| `documents.0001_initial` | CreateModel, AddIndex x2 | A | Standard FileField metadata schema; file bytes are not database data. |
| `documents.0002_projectdocument_archive_reason` | AddField | A | Standard TextField addition. |
| `estimates.0001_initial` | CreateModel x2, AddConstraint, AddIndex x3 | A | Standard UUID/FK/Decimal schema. Historical audit dependency is unnecessary but replayable. |
| `estimates.0002_estimate_approval` | AddField x2 | A | Nullable actor/time additions. |
| `estimates.0003_estimate_phase` | AddField, AddIndex | A | Nullable FK/index expansion. |
| `expenses.0001_initial` | CreateModel, AddIndex x3 | A | Standard UUID/FK/Decimal/date schema. Historical audit dependency is unnecessary but replayable. |
| `expenses.0002_expense_phase` | AddField, AddIndex | A | Nullable phase FK/index expansion. |
| `expenses.0003_expense_void_fields` | AddField x3 | A | Nullable void metadata additions. |
| `organizations.0001_initial` | CreateModel | A | Standard tenant root. |
| `organizations.0002_organizationmembership` | CreateModel | A | Standard join table and unique constraint. |
| `organizations.0003_organizationinvitation` | CreateModel | A | Standard workflow table. |
| `organizations.0004_alter_organization_status` | AlterField | D | Choice/state update only; clean initial migration can contain final choices. |
| `payments.0001_initial` | CreateModel, AddConstraint, AddIndex x2 | A | Standard UUID/FK/Decimal/date schema. |
| `projects.0001_initial` | CreateModel, AddConstraint, AddIndex x2 | A | Standard project schema. |
| `projects.0002_projectsite` | CreateModel, AddConstraint, AddIndex | A | Standard site schema. |
| `projects.0003_projectphase` | CreateModel, AddConstraint, AddIndex | A | Standard phase schema. |

No migration contains raw SQL, data migration code, backend conditionals, custom
operations, expression/partial indexes, custom collations, generated fields, or
database defaults.

### 4.2 Strategy A — preserve migration history

Keep all 25 first-party migrations and apply them to an empty PostgreSQL database.

| Dimension | Assessment |
|---|---|
| Safety | HIGH confidence technically: all operations are portable and there is no data. It preserves the exact active migration graph. |
| Complexity | LOW. Change the backend/dependency, create an empty database, run migrate. |
| Rollback difficulty | LOW before SQL Server removal: switch environment/settings back and use the untouched SQL Server development database. PostgreSQL schema can be discarded. |
| Future maintainability | Acceptable, but carries three superseded audit-choice migrations, an organization-choice migration, and unnecessary cross-app dependencies on audit migrations into the long Domain Model refactor. |
| Git/history implications | Minimal churn; old migration identifiers remain valid. |
| Test implications | Full suite still required; replay itself tests portability. |
| Effect on Domain Model v1.0 | Works, but future migration graph starts from noisier history and audit dependencies unrelated to schema ownership. |
| Hidden SQL Server assumptions | Replay on PostgreSQL exposes most DDL assumptions. Case/collation behavior still requires explicit tests. |
| Overall strategy risk | LOW. |

### 4.3 Strategy B — rebaseline development migrations

After current models and behavior are frozen, remove only approved first-party
development migration files (preserving migration package `__init__.py` files),
generate clean initial migrations, and apply them to an empty PostgreSQL database.
Django built-in migrations remain untouched.

| Dimension | Assessment |
|---|---|
| Safety | MEDIUM during the coordinated change, then HIGH for the new baseline. There is no data/deployed migration state to preserve, but generated migrations must be reviewed against all 18 models and dependencies. |
| Complexity | MEDIUM. Approximately 25 old files become about 10 app initial migrations, and all local/test databases must be recreated. |
| Rollback difficulty | LOW while the old Git revision and SQL Server configuration remain available. Do not support mixed old/new migration histories against one database. |
| Future maintainability | Best option: final current schema is captured once, repeated choice changes disappear, and unnecessary audit dependencies can be eliminated before many Domain Model migrations arrive. |
| Git/history implications | High one-time diff, but Git retains historical files in prior commits. Every active developer must reset by recreating the development database rather than faking migrations. |
| Test implications | Requires schema review, empty-database migrate, no-change detection, full tests, and browser validation. Migration tests must verify dependencies and all constraints/indexes. |
| Effect on Domain Model v1.0 | Positive. It creates a small, understandable PostgreSQL baseline before incremental expand/backfill/switch/validate/contract migrations begin. |
| Hidden SQL Server assumptions | Rebaseline avoids replaying old DDL, but it can hide historical behavior; explicit type, collation, constraint, locking, and workflow tests compensate. |
| Overall strategy risk | MEDIUM. |

### 4.4 Recommendation — REBASELINE

Choose Strategy B for this repository, subject to explicit approval at
implementation time.

The choice is not required by PostgreSQL—the existing 25 migrations are portable.
It is recommended because:

1. there is no production or development data that must survive;
2. every environment may be recreated;
3. the implementation is only approximately 30–35% complete;
4. Domain Model v1.0 will add many carefully staged migrations next;
5. four current files are state-history noise; and
6. several domain initial migrations have historical dependencies on audit choice
   migrations even though their tables have no audit foreign key.

Do not combine rebaselining with any Domain Model change. Generate the clean
initial migrations from the exact current models and prove behavior on an empty
PostgreSQL database first.

## 5. Recommended PostgreSQL target stack

### 5.1 Driver/package choice

Use **Psycopg 3**, not Psycopg 2. For this final application and its Windows
development environment, the pragmatic initial requirement is:

```text
psycopg[binary]>=3.1.8,<4.0
```

Reasons:

- Django 5.2 recommends Psycopg 3.1.8+;
- the binary distribution supports Windows and packages the required client
  libraries, avoiding a new local compiler/libpq onboarding burden; and
- it removes the current ODBC driver/TLS provider dependency.

For a controlled Linux production image with build tools and system libpq, the
team may later choose `psycopg[c]` so libpq/OpenSSL follow system updates. That is
an operational packaging decision, not a reason to split application behavior.
Do not add pooling during this migration; Django's Psycopg pooling requires an
additional pool dependency and there is no measured need yet.

Psycopg documents `psycopg[binary]` as the recommended option for most users and
describes `psycopg[c]` as the locally linked production option when build
prerequisites are controlled.
[Psycopg installation documentation](https://www.psycopg.org/psycopg3/docs/basic/install.html)

### 5.2 Planned Django configuration

The eventual configuration should remain explicit rather than accepting a
database URL parser package:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", ""),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": {
            "sslmode": os.getenv("DB_SSLMODE", "prefer"),
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        },
    }
}
```

This is an assessment example, not an implemented change. Add `sslrootcert` only
when the deployment supplies an explicit CA path. Avoid empty option values.
Keep `CONN_MAX_AGE` at Django's current/default behavior for the first switch;
tune connections only after observing the deployment platform.

### 5.3 Environment variables

Retain:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`

Change/add:

- `DB_PORT=5432`
- `DB_SSLMODE` (`disable` only for trusted local-only development if desired;
  production should be `verify-full`)
- optional `DB_SSLROOTCERT` when the CA is not available through the system trust
  store
- `DB_CONNECT_TIMEOUT`, with a small finite value such as 10 seconds

Retire after PostgreSQL validation:

- `DB_DRIVER`
- `DB_EXTRA_PARAMS`

Do not log these settings or include credentials in source control.

### 5.4 Development and production behavior

**Development:** default port 5432; local UTF-8 database; a dedicated application
role; local TLS may be disabled only for a loopback/local service or set according
to the developer's PostgreSQL installation. The database role used by tests must
either be allowed to create a test database or a separately configured test
database must be prepared.

**Production:** require non-placeholder database credentials and explicitly
validate `DB_SSLMODE`. Use `verify-full` with a hostname matching the certificate
and a trusted CA. `sslmode=require` encrypts but is not the same as full server
identity verification. PostgreSQL/libpq recommends `verify-full` for
security-sensitive environments.
[PostgreSQL SSL documentation](https://www.postgresql.org/docs/current/libpq-ssl.html)

Use the default READ COMMITTED isolation level initially. Do not introduce a
pooler, higher isolation level, read replicas, or statement-level tuning until a
deployment need is measured.

### 5.5 Eventually removable SQL Server components

After the PostgreSQL acceptance gate and rollback window:

- remove `mssql-django` from database requirements;
- remove `pyodbc` from database requirements;
- remove ODBC driver prerequisites from onboarding;
- remove `DB_DRIVER`/`DB_EXTRA_PARAMS` processing;
- rebuild or clean developer virtual environments so unused packages disappear;
  and
- update active architecture/status documentation.

Do not uninstall/remove them before the PostgreSQL baseline is proven.

## 6. Multi-tenancy impact

### Required for migration

The tenancy model remains unchanged:

```text
One PostgreSQL database
└── one shared application schema
    └── Organization is the tenant boundary
        └── tenant-owned rows carry organization_id
```

No current code requires schema-per-tenant or database-per-tenant. PostgreSQL does
not require `django-tenants`, database routers, or changes to active-organization
middleware/services. All existing queryset, form, view, service, and authorization
checks must continue to scope by the active Organization.

The engine change also does not solve the existing cross-tenant relationship
integrity concern: a conventional FK proves that a referenced row exists, not
that `child.organization_id == parent.organization_id`. Existing service/form
checks and tenant-isolation tests remain mandatory. Hardening those rules belongs
to Domain refactor R1, after the database migration baseline is frozen, unless a
demonstrated migration blocker is found.

### Optional future PostgreSQL hardening

These are **not required for migration**:

- functional unique constraints (for example on `Lower(code)`) if business rules
  require case-insensitive identifiers;
- `UniqueConstraint(nulls_distinct=False)` for future nullable business keys where
  NULL must count as one value;
- partial/covering indexes after query evidence exists;
- PostgreSQL Row Level Security; and
- advanced exclusion constraints for future assignment/date-overlap models.

RLS should not be introduced in this migration. The application currently uses a
shared database role and request/session-derived tenant state. Safe RLS would
require a separately designed connection-session tenant context, reliable reset
semantics with pooling, migration/admin policy, background-task policy, and tests.
Adding it now would mix a security architecture change with an engine change.

## 7. Testing impact

### 7.1 Current tests most likely to expose differences

| Test area | PostgreSQL concern | Required validation |
|---|---|---|
| Tenant isolation | ORM behavior should match; test database must contain both tenants and every cross-tenant UUID path. | All existing isolation tests pass unchanged. Add no RLS assumptions. |
| Uniqueness | String case/collation differs; PostgreSQL raises IntegrityError and marks the current transaction/savepoint for rollback. | Test exact duplicates and approved case variants for username, slug, codes, and numbers. Keep expected IntegrityError inside atomic/savepoint boundaries. |
| Organization invitation | Exact username lookup and unique token hash. | Test case policy, expiry, concurrent acceptance, and membership uniqueness. |
| Transactions/approvals | PostgreSQL row locks are strong; current TestCase tests do not simulate two connections. | Existing workflow tests plus targeted TransactionTestCase concurrency for invitation acceptance, phase transition, estimate approval, daily submit/approve, archive, and void. |
| Expense/payment void | Posted/recorded state, actor/time, audit, preserved amount. | Full Decimal and immutability assertions; repeated void remains rejected. |
| Audit immutability/JSON | JSON stored as jsonb; application manager blocks update/delete but direct SQL is still outside the guarantee. | Nested metadata round-trip, sensitive-key rejection, update/delete/bulk-create rejection, scoped ordering. |
| Decimal calculations | numeric adaptation and aggregation plans differ. | Exact values for estimate line totals, dashboard totals, variance, receipt/disbursement, and net cash flow. |
| Datetime/time zones | `timestamptz`, session timezone, microseconds, expiry boundaries. | Aware UTC round-trip and comparison tests for all lifecycle timestamps. |
| Query ordering | Ties and NULL placement may differ. | Ensure tests assert explicit ordering and do not rely on unspecified tie order. Current declared orderings mostly use non-null fields. |
| NULL uniqueness | Current composite unique fields are non-null, so no expected difference. | Schema inspection confirms this; add tests when future nullable unique keys appear. |
| File/document flows | Database only stores path/metadata, while test storage uses override settings. | Upload, signature/MIME/size, hash, tenant-scoped download, archive, and file cleanup behavior. |
| Financial prefetch/reporting | Query plans and aggregation execution differ but ORM semantics should not. | All financial report/dashboard tests and query-result parity. |

The current suite contains 130 test methods but no `TransactionTestCase`. The
database migration can be accepted with all current tests passing, but the
row-locking workflows should receive a small, targeted PostgreSQL concurrency
test set before the new database is frozen as the foundation for Domain Model
refactoring.

### 7.2 Test database requirements

- Run pytest against PostgreSQL, not SQLite.
- Ensure `DJANGO_SETTINGS_MODULE=config.settings.development` resolves PostgreSQL.
- Grant the test role `CREATEDB`, or configure a dedicated disposable test
  database and documented permissions.
- Start from an empty database and let Django create/apply the recommended
  rebaselined migrations.
- Do not use `--keepdb` for the first acceptance run.
- Run a second clean-database test/migrate cycle to prove reproducibility.

## 8. Development and deployment impact

### Local Windows development

- Install/run PostgreSQL locally or use an approved remote development instance.
- Psycopg binary wheels remove the ODBC Driver 17 prerequisite.
- Create a UTF-8 database and least-privilege application role; grant test database
  creation only where needed.
- Update the ignored `.env` from the future PostgreSQL `.env.example`.
- Recreate the virtual environment after the rollback window if a clean package
  inventory is desired; do not manually edit site-packages.
- Document service startup and a simple connection/migration diagnostic.

### Developer onboarding

Onboarding must state the supported PostgreSQL major version, host/port, role and
database creation steps, SSL mode, migration strategy, test database permission,
and the fact that old SQL Server development databases are not reusable after a
rebaseline.

### CI/testing

No CI configuration exists today. A future CI job should provision a disposable
PostgreSQL service at the same supported major version and run the exact validation
gate. This does not require Docker to be introduced into the application
repository; use the CI provider's native PostgreSQL service where available.

### Docker readiness

There is no Docker/Compose baseline, so adding Docker solely for this migration
would expand scope. The Django configuration will be container-compatible because
all connection values remain environment-driven. Docker can be evaluated later as
deployment infrastructure, not as a migration prerequisite.

### Production hosting

- Prefer a managed PostgreSQL service with automated backups, point-in-time
  recovery, encryption at rest, TLS, and monitoring.
- Use a dedicated application role without database-owner/superuser privileges.
- Run migrations as a controlled release step using a role with only the required
  DDL permissions.
- Size connection limits before enabling persistent connections or a pooler.
- Validate hostname/certificate behavior with `verify-full`.

### Backup, restore, and monitoring

There is no current data to transfer, but operational readiness should include:

- a documented `pg_dump`/`pg_restore` or provider-native backup/restore test after
  PostgreSQL becomes authoritative;
- automated backup retention and point-in-time recovery appropriate to production;
- monitoring for connection saturation, long transactions, blocked locks,
  deadlocks, slow queries, database/disk growth, WAL growth, replication/backup
  health, and failed migrations; and
- application logs that do not expose connection strings or credentials.

## 9. Proposed implementation sequence

Each phase below is database-migration-only. Business/domain behavior must remain
unchanged.

### P0.1 — Establish clean current baseline

- **Files likely affected:** none initially; record results in the approved task
  report. If stale active docs are corrected later, that belongs to P0.7.
- **Objective:** freeze current models, migration graph, 130-test inventory,
  browser behavior, constraints/indexes, and case-sensitivity decisions.
- **Prerequisites:** working repository; access to a disposable test environment;
  explicit acknowledgement that no data must be preserved.
- **Risks:** an already-failing test or unapplied SQL Server migration could be
  misattributed to PostgreSQL.
- **Tests/checks:** `check`, `makemigrations --check --dry-run`, Ruff, migration
  inventory, current suite wherever SQL Server can run, and case-policy decisions.
- **Rollback:** not applicable; read-only baseline.
- **Acceptance criteria:** exact baseline results and exceptions are documented;
  current model state is stable; no Domain Model work is mixed in.

### P0.2 — Add PostgreSQL dependency and configuration

- **Files likely affected:** `requirements-db.txt`, `config/settings/base.py`,
  `config/settings/production.py`, `.env.example`; local ignored `.env` outside
  source control.
- **Objective:** make Django connect through Psycopg using environment variables
  and preserve production certificate validation.
- **Prerequisites:** P0.1; selected PostgreSQL major/version and SSL policy.
- **Risks:** invalid option names, weak production TLS default, credentials in
  source, or premature removal of SQL Server rollback dependencies.
- **Tests/checks:** settings import, `check`, production negative/positive settings
  validation, and a direct Django connection diagnostic against PostgreSQL.
- **Rollback:** revert configuration/dependency commit/change set and point the
  ignored environment back to SQL Server; retain old packages temporarily.
- **Acceptance criteria:** development connects to PostgreSQL; production settings
  reject missing credentials and insecure SSL mode; no secret is committed.

### P0.3 — Create empty PostgreSQL development/test databases

- **Files likely affected:** none in application source; environment/onboarding
  instructions later in P0.7.
- **Objective:** provision UTF-8 databases and least-privilege roles with test
  database capability.
- **Prerequisites:** P0.2; PostgreSQL service available.
- **Risks:** wrong collation/locale, excessive role privileges, hostname/TLS
  mismatch, or tests targeting the wrong database.
- **Tests/checks:** Django reports `connection.vendor == "postgresql"`; server
  version/encoding/timezone/SSL and role permissions are recorded without secrets.
- **Rollback:** drop only the explicitly named disposable PostgreSQL databases and
  restore SQL Server environment values.
- **Acceptance criteria:** empty dev/test databases are reachable, UTF-8, correctly
  secured, and clearly distinguishable from any future production database.

### P0.4 — Rebaseline first-party development migrations

- **Files likely affected:** 25 current first-party migration files replaced by
  approximately 10 clean app initial migrations; keep every migrations
  `__init__.py`. No model file changes.
- **Objective:** generate a clean PostgreSQL-era initial schema from the exact
  current models and a clean dependency graph.
- **Prerequisites:** explicit approval of REBASELINE, P0.1 model freeze, P0.3 empty
  database, all developers informed that databases must be recreated.
- **Risks:** missing field/index/constraint, incorrect dependency ordering,
  accidental model drift, or a developer faking new initial migrations onto an
  old database.
- **Tests/checks:** review generated migrations model-by-model; verify 18 models,
  UUID PKs, 8 composite UniqueConstraints, 26 explicit model indexes, JSON/File/
  Decimal fields, FK delete behavior, and apply from empty database.
- **Rollback:** restore the 25 migration files from the prior Git revision/change
  set, restore SQL Server settings, and discard the PostgreSQL database. Never mix
  histories in one database.
- **Acceptance criteria:** clean `migrate` succeeds from zero; all first-party
  migrations show applied; `makemigrations --check --dry-run` reports no changes;
  schema matches current models.

### P0.5 — Run automated and manual validation

- **Files likely affected:** ideally none; up to 1–3 existing test files if approved
  compatibility/concurrency coverage is added without changing business behavior.
- **Objective:** prove current application behavior on PostgreSQL.
- **Prerequisites:** P0.4.
- **Risks:** accepting only unit checks while missing collation, locking, file, or
  browser regressions.
- **Tests/checks:** the complete validation gate in section 10, including a clean
  database run and every listed browser workflow.
- **Rollback:** keep SQL Server configuration/dependencies available and discard
  the PostgreSQL database if parity fails.
- **Acceptance criteria:** every automated gate passes; approved case semantics are
  proven; all browser flows work with two tenants; no unexplained schema warning.

### P0.6 — Remove SQL Server-specific dependencies/configuration

- **Files likely affected:** `requirements-db.txt`, settings and `.env.example` if
  a temporary dual-backend window was used; developer environment separately.
- **Objective:** make PostgreSQL the only supported runtime database.
- **Prerequisites:** P0.5 accepted and rollback window explicitly closed.
- **Risks:** removing rollback capability too early or leaving stale ODBC variables
  that mislead deployment.
- **Tests/checks:** rebuild a clean virtual environment from requirements; verify no
  `mssql-django`/`pyodbc` dependency; repeat checks/tests.
- **Rollback:** reintroduce the prior pinned SQL Server requirements/configuration
  from version control and recreate its database; there is no data rollback need.
- **Acceptance criteria:** clean install uses Psycopg only; no active settings or
  environment template references ODBC/SQL Server.

### P0.7 — Update active documentation

- **Files likely affected:** `AGENTS.md`, `README.md`, `PROJECT_SNAPSHOT.md`, and
  `docs/architecture/PROPOSED_REFACTOR_SEQUENCE.md`; decide separately whether
  `project_tree.txt` is maintained. Do not silently rewrite the archival old
  AGENTS copy.
- **Objective:** make PostgreSQL and the rebaselined migration state the documented
  source of truth.
- **Prerequisites:** P0.6 and recorded validation results.
- **Risks:** documentation claiming validation that was not actually performed or
  accidentally changing Domain Model v1.0 priorities.
- **Tests/checks:** search active files for stale SQL Server/ODBC references and
  verify commands/environment names.
- **Rollback:** restore prior documentation if the technical switch is rolled back.
- **Acceptance criteria:** onboarding, architecture, snapshot, migration count,
  and validation checkpoint accurately describe PostgreSQL.

### P0.8 — Freeze PostgreSQL as the project database baseline

- **Files likely affected:** no new application files; status documentation may
  record the final checkpoint.
- **Objective:** declare the database-only migration complete and open the gate for
  Domain Model v1.0 R0/R1 work.
- **Prerequisites:** P0.1–P0.7 complete.
- **Risks:** beginning domain changes with unresolved flaky tests, case policy, or
  environment differences.
- **Tests/checks:** repeat clean migrate, no-change check, full tests, Ruff,
  production settings/deploy check, browser smoke suite, and backup/restore smoke.
- **Rollback:** before Domain Model migrations begin, revert the isolated database
  change set and recreate the old environment. After Domain Model migrations begin,
  PostgreSQL is the authoritative forward baseline.
- **Acceptance criteria:** section 10 is fully green and recorded; PostgreSQL is the
  only active documented backend; Domain Model refactoring has not started yet.

## 10. Required validation gate before Domain Model refactoring

All gates must run with Django connected to the approved PostgreSQL database.

### 10.1 Automated commands

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Production configuration must also pass with safe non-secret validation values and
a reachable appropriately secured PostgreSQL environment:

```powershell
.\.venv\Scripts\python.exe manage.py check --deploy --settings=config.settings.production
```

Required outcomes:

- `connection.vendor` is `postgresql` and the selected server major version is
  recorded;
- migration from an empty database succeeds;
- a second `migrate` reports no work;
- every first-party and Django migration is applied;
- no model changes are detected;
- all 130 currently discovered test methods pass, plus any approved compatibility/
  concurrency additions;
- Ruff passes;
- schema inspection confirms all UUID PKs, FK actions, unique constraints, and
  expected indexes;
- approved case-variant behavior passes for username, slug, codes, and numbers;
- timezone/JSON/Decimal/FileField round trips pass; and
- production settings require verified TLS rather than merely encrypted but
  unauthenticated transport.

### 10.2 Manual browser workflows

Use at least two users and two organizations so isolation is observed, not merely
assumed:

1. Login and logout.
2. Organization creation/selection and active-tenant switching.
3. Member invitation and acceptance.
4. Project creation, listing/detail, and archive.
5. Site creation and phase creation/status transition.
6. Contract creation and tenant-scoped listing.
7. Estimate creation, Decimal line totals, approval, and approved-item lock.
8. Expense creation, void, preserved amount, and financial exclusion.
9. Payment creation, detail, void, preserved amount, and financial exclusion.
10. Daily report creation, labor/material/equipment entries, submit, approve, and
    final-state lock.
11. Document PDF/JPEG/PNG upload, metadata/hash verification, authorized download,
    archive, and cross-tenant UUID rejection.
12. Audit-log visibility and event creation for the workflows above.
13. Project and organization financial reports/dashboard totals.
14. Tenant switch followed by attempts to open the prior tenant's object URLs.

Acceptance requires no cross-tenant read/write, correct authorization, exact
financial values, and no silent finalized-history mutation.

## 11. Separation from Domain Model v1.0

The PostgreSQL change must result in exactly:

```text
CURRENT APPLICATION BEHAVIOR
+ CURRENT MODELS
+ POSTGRESQL / PSYCOPG
```

It must not add or refactor BusinessParty, material/UOM masters, WBS, Activity,
workforce, procurement, inventory, equipment, billing, ProgressClaim, document
versions/links, safety, or quality. It must not alter tenant architecture,
approval/void semantics, routes, templates, or financial calculations.

After P0.8, the previously proposed Domain Model sequence resumes with its own R0
baseline against PostgreSQL, followed by R1 tenant/history hardening. Database
migration findings may inform those phases, but their code must not be bundled
into this migration.

## 12. Final assessment

PostgreSQL is a strong fit for the inspected repository. The project already uses
the portable parts of Django correctly: UUIDs, Decimal fields, standard FKs,
standard indexes/constraints, JSONField, atomic services, and row locks. The
existing ODBC/TLS problem is environmental coupling that Psycopg will remove, not
a reason to retain SQL Server.

The best decision is to migrate now, rebaseline the 25 first-party development
migrations into a clean set for the unchanged current models, prove behavior on an
empty PostgreSQL database, remove SQL Server support only after acceptance, and
freeze that state before any Domain Model v1.0 work begins.

The single highest-risk issue is not data transfer or DDL portability; it is
silently changing identifier uniqueness/authentication behavior through an
undeclared case/collation difference. Resolve and test that policy in P0.1, then
proceed with the isolated PostgreSQL migration.
