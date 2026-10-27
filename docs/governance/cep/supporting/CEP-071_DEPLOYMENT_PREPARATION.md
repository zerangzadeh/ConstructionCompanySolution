# CEP-071 deployment preparation

2026-10-27. Development preparation under PD-004 / SPEC-006; production target
and topology remain UNSPECIFIED. Canonical source identities and current dirty
baseline: [ENTRY](../evidence/CEP-071_072_DEVELOPMENT_20261027/ENTRY.json).
This is the repository process contract prepared for approval, not a deployment
approval or CEP-075 execution result.

## Established source facts

The application is a synchronous Django modular monolith with PostgreSQL/Psycopg
3, Django templates and compiled static assets. Both `config.wsgi:application`
and `config.asgi:application` exist; neither selects an approved process server.
No background worker is required by this preparation. Requirements/lock files
and existing supply-chain tooling remain the dependency/artifact authorities.
No new process server, provider, container platform or infrastructure dependency
has been installed.

The [completed CEP-013 Development build](../reports/CEP-013_COMPLETION_REPORT.md)
already establishes CPython 3.11.17 / Debian 12 / linux-amd64, a pinned image,
Linux runtime/development hash locks and pure Psycopg with system libpq. The
historical Windows lock is separate. Signed wheelhouse attestation and actual
production installation remain UTV in that existing release contract; this work
does not repeat supply-chain qualification or select a container topology.
The approved EXT-0020 Windows/PostgreSQL synthetic recovery target and its owners
apply only to that bounded recovery qualification, not EXT-0021 deployment.

`config.settings.development` alone loads checkout `.env`; production consumes
process environment exclusively, sets DEBUG=False and disables reference personas.
WSGI/ASGI retain their Development default for local tooling: a deployed process
MUST explicitly set `DJANGO_SETTINGS_MODULE=config.settings.production` before
importing either entrypoint. An omitted setting is not a production deployment.

## Environment contract

| Variables | Enforced contract |
| --- | --- |
| DJANGO_SETTINGS_MODULE | Explicit production module in the selected process launcher; Development default is unsuitable for deployment |
| DJANGO_SECRET_KEY | Dedicated secret, at least 50 characters; no development/insecure/replace-with prefix; Django deployment checks also assess strength |
| DJANGO_ALLOWED_HOSTS | Explicit comma-separated hosts; empty/wildcard configuration rejected |
| DB_NAME / DB_USER / DB_PASSWORD / DB_HOST | Required non-placeholder process values; never captured in evidence |
| DB_SSLMODE / DB_SSLROOTCERT | verify-full mandatory; CA path optional when the trusted default store suffices |
| DB_PORT / DB_CONNECT_TIMEOUT | Existing port default 5432; positive timeout default 10; exact target supplied by its owner |
| DJANGO_EMAIL_BACKEND / HOST / HOST_USER / HOST_PASSWORD / DEFAULT_FROM_EMAIL / USE_TLS | SMTP, required credentials/from address and TLS; variables after the backend retain the DJANGO_EMAIL_ prefix except DJANGO_DEFAULT_FROM_EMAIL |
| DJANGO_EMAIL_PORT / TIMEOUT | Positive values; existing defaults 587 / 10 |
| DJANGO_CACHE_BACKEND / DJANGO_CACHE_LOCATION | Explicit configured backend/location; LocMem and DummyCache rejected; actual cross-process/host behavior requires target qualification |
| DJANGO_STATIC_ROOT / DJANGO_MEDIA_ROOT / DOCUMENT_PROTECTED_ROOT | Explicit absolute dedicated paths, mutually disjoint; parent/child overlaps and repository/filesystem roots rejected |
| DJANGO_SECURE_SSL_REDIRECT / SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE | True mandatory; all retain DJANGO_ prefix; insecure/invalid overrides rejected |
| DJANGO_USE_X_FORWARDED_PROTO | False default; true only when the approved proxy strips client forwarding claims and supplies trusted HTTPS evidence |
| DJANGO_CSRF_TRUSTED_ORIGINS | Exact approved HTTPS origins when needed; no wildcard/origin inferred |
| DJANGO_HSTS_SECONDS / INCLUDE_SUBDOMAINS / PRELOAD | Nonnegative seconds; existing 31536000 / true / true defaults; all retain DJANGO_HSTS_ prefix; target/domain ownership must qualify these before activation |
| DJANGO_PASSWORD_RESET_TIMEOUT / DJANGO_PASSWORD_RESET_THROTTLE_SECONDS | Existing positive defaults 3600 / 900; no password-recovery semantics changed |

Do not print environment dumps or credentials. Select the environment's approved
injection/custody/rotation mechanism before activation; no `.env` fallback, secret
file generation, or secret-manager/provider choice is implied here.

## Static and media boundary

`collectstatic` assembles versioned static assets into STATIC_ROOT. Production
Django does not serve MEDIA_ROOT through the Development URL helper. Private DMS
bytes remain under DOCUMENT_PROTECTED_ROOT and existing authorized document
views; a proxy/CDN must never expose that root. Legacy MEDIA_ROOT contents are
not approved for blanket public serving. The actual serving method, durable
mounts, ownership and backup coverage require target input. Deployment tooling
must provision paths and test access without relocating/deleting existing bytes.

## Release, validation and rollback procedure prepared for approval

1. Retain candidate/previous artifact and lock/config hashes, configured settings
   identity, change/migration list, target identity, release/activation owners,
   approved recovery reference and exception/evidence location. No secret values.
2. Review config differences and verify TLS trust, explicit hosts, SMTP/cache,
   directory separation/permissions, protected-byte denial and the approved
   proxy contract. Use `python manage.py check --deploy --fail-level WARNING
   --settings=config.settings.production` against that configured environment.
3. Before any authorized migration, inspect its versioned plan and compatibility
   with both candidate and previous artifact. Record approved backup checkpoint
   and rollback-versus-roll-forward decision. This CEP introduces no migrations;
   no migration has been run for this preparation.
4. On an approved disposable target, collect static assets into its own release
   directory with `collectstatic --noinput`. Never use `--clear` against a shared
   or previous release. Start only the selected launcher with explicit settings.
5. Capture process/config identity, authorized login/tenant/CSRF behavior, HTTPS
   and protected-file denial, and dependency reachability via `operational_health`.
   A 200/302 or successful probe alone never establishes application readiness.
6. If validation fails, retain sanitized logs/correlation IDs and halt activation.
   For an artifact/config-only rollback, stop the candidate and reactivate the
   retained previous artifact/config/static release only after the recorded
   database compatibility decision. Never blindly reverse migrations or restore
   finalized business history. Database recovery/roll-forward follows the approved
   recovery policy with explicit owner/authority; Production action is separate.
7. Revalidate after recovery, retain failed and recovered evidence and obtain the
   designated acceptance decision. Rollback failure is a failure, never readiness
   PASS. The running artifact, schema version and retained media must agree.

Synthetic local validation proves settings loading, Django deployment checks,
WSGI/ASGI import and static collection without network/database access. It cannot
qualify an unspecified target, process manager, proxy, durable storage or rollback
execution there. See [EXT-0021 unresolved decisions](EXT-0021_DECISION_MATRIX_20261027.md).
