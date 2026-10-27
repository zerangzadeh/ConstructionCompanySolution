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

## Checkpoint re-entry and executable acceptance preparation

At `de6e20863896e7587e58bf917f807cea75f95b7a`, local `main` and local
`origin/main` agree; the entry working tree was clean. No remote refresh or Git
write was performed. Canonical prompts 071/075 and recovered deployment/profile/
dependency sources were hash-verified again. PD-004 remains explicit about
selection; the configuration profile matrix contains no deployment default.

[Current synthetic execution](../evidence/CEP-071_EXT0021_REENTRY_20261027/REQUEST_EXECUTION.json)
uses Windows CPython 3.11.1 / Django 5.2.17 and production settings. The installed
local runtime is distinct from the approved Linux artifact; no production
equivalence is inferred. Both actual Django WSGI and ASGI handlers execute seven
requests each: HTTP-to-HTTPS 301, anonymous business-root login redirect 302,
missing-CSRF login POST 403, media/private/collected-static paths 404 and invalid
Host 400. HTTPS responses retain HSTS. No authentication/tenant fixture or
application permission behavior is changed. A 404 proves only the Django serving
boundary, not a future proxy's storage access policy.

`check --deploy --fail-level WARNING` passes. Two actual `collectstatic` runs
produce matching hashes for 153 files in separate disposable release directories;
the previous release stays unchanged through both request executions. This proves
static preparation/preservation, not a deployed release switch or rollback.
Dotenv, application network connects and database connects are forbidden. Windows
event-loop initialization precedes the network guard because asyncio internally
creates a local socket pair; no app request uses a socket or selected server.
The failed initial harness attempt is retained, then corrected and rerun.

Repeat this preparation from the repository root:

```powershell
.venv-2/Scripts/python.exe docs/governance/cep/evidence/CEP-071_EXT0021_REENTRY_20261027/preflight.py
```

After target selection, Development completes its launcher/path/configuration
commands and executes the existing procedure above. Acceptance must retain:

| Check | Required target result / failure handling |
| --- | --- |
| Identity and authority | Target, exact candidate/previous artifact and config hashes, runtime/settings, owners and approved scenario/equivalence reference. Missing references stop activation. |
| Preflight | Explicit production settings; deploy checks with WARNING fatal; actual DB TLS identity, proxy/header trust, SMTP/cache contract and path permissions. Static synthetic fixtures are not credentials or dependency evidence. |
| Process | Start selected launcher under selected runtime identity; inspect actual bind/settings/termination behavior and capture sanitized exit/failure logs. Import or in-memory execution is insufficient. |
| Assets and media | Collect candidate static without clearing previous; verify target HTTP delivery and protected/legacy-media denial using disposable bytes and actual serving configuration. Preserve durable bytes and record ownership/backup references. |
| Health and application acceptance | Execute `python manage.py operational_health --settings=config.settings.production` on the approved target, retain its signals and exit code, then run the approved application scenario. The command probes DB read-only and cache GET; its own `production_readiness` remains `NOT_VALIDATED`, including on success. |
| Failed activation and recovery | Retain failed attempt; halt candidate; use recorded compatibility decision before switching previous artifact/config/static. Recheck process/assets/health and retained-media identity after actual recovery. A failed recovery remains open, never PASS. |
| Release evidence | Timestamped command/result/exception record, artifact/config identities and designated acceptance result. No environment dump, secrets, invented business success, inferred Human review or migration reversal. |

Existing approved EXT-0022 operating/acceptance owner and procedures are available
as references, including OP-01..04, restricted diagnostics and read-only health
qualification. Their approved Development target does not select EXT-0021's
deployment design. The matrix proposes extending those existing responsibilities;
it does not ask to invent new people or redo completed operating drills.

The remaining blocker is the selected deployment contract and target evidence,
not a generic requirement to deploy Production. `EXT-0021` blocks Production for
071 and Verification for 075; missing Production-only clauses do not block valid
non-production preparation. See the single [EXT-0021 request](EXT-0021_DECISION_MATRIX_20261027.md).

## Approved profile qualification

The subsequent [Human decision](EXT-0021_HUMAN_APPROVAL_20261027.md) selects the
existing minimum Windows/loopback/isolated-test-PostgreSQL Development profile.
The [matrix](EXT-0021_DECISION_MATRIX_20261027.md) now records approved selections;
there is no outstanding request to select Linux or a new provider.
[Selected runbook](EXT-0021_DEVELOPMENT_RUNBOOK_20261027.md) and
[actual seven-step qualification](../evidence/CEP-071_EXT0021_APPROVED_20261027/SCENARIO.json)
prove copied current-source releases, static delivery, real dependency probes,
failed-candidate rejection and actual previous-build/config/process rollback
without database mutation. CEP-071 is COMPLETE for this approved Development
scope; Production configuration/runtime properties remain unqualified.

CEP-075 uses fresh unchanged-source component execution. Its canonical
production-equivalent target property remains unestablished, consistent with the
Human instruction to make no such claim. Executable Development components and
that final target-property limitation are recorded separately; no Production
deployment or completed-CEP re-execution is required for these component checks.
