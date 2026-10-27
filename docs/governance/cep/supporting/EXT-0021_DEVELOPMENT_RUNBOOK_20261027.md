# EXT-0021 — selected Development deployment qualification

Authority: [Human approval](EXT-0021_HUMAN_APPROVAL_20261027.md).
Accountable deployment/acceptance owner: Human Decision Authority. Technical
executor: Codex for this session. No Human Sign-off or Production authority.

## Selected existing profile

Windows, repository `.venv-2`, existing private repository `.env` and/or injected
process environment, existing loopback PostgreSQL test database, configured
Development cache, ephemeral loopback WSGI using Python's existing stdlib server.
The actual Django WSGI application is wrapped by Django's existing Development
static-files handler, as with Development runserver. No new infrastructure,
server package, external storage, secret manager or network listener beyond
loopback is introduced. ASGI executes in memory under existing production guards;
there is no installed ASGI network server or implied Production TLS frontend.

The launcher explicitly uses `config.settings.development`, disables DEBUG and
reference personas for its bounded validation lifetime, and permits only its
loopback host. It preserves existing tenant/authentication/CSRF middleware.
Production settings are separately checked without dotenv/DB/network access;
their mandatory TLS, SMTP/shared-cache and storage guards are not weakened to
fit this Development target. Loopback HTTP/local cache does not establish those
Production properties or production equivalence.

## Build, configure, deploy and validate

1. Record branch/HEAD, source/config hashes, Python/Django/Psycopg versions,
   authority and exact scenario. Verify the existing private secret source ACL;
   read values only through normal Development settings and pass them directly
   in child process environment. Never copy `.env` into releases/evidence, emit
   an environment dump or print connection strings/credential values.
2. Resolve only the configured test-database name; require its `test_` prefix
   and loopback host before connecting. Require that it already exists. Read
   `django_migrations` and record its history hash; no migration, schema change,
   database creation, flush, data write or database rollback is performed.
3. Create a fresh restricted local child under the existing
   `E:/BONIRA_Operations` storage boundary using the existing Windows DACL helper.
   Snapshot current application/config/template/static source into separate
   previous/candidate releases. Verify hashes; preserve all existing releases.
   Collect separate static trees without `--clear`; media and protected DMS
   fixture bytes live in distinct retained private directories.
4. Start previous release under the loopback launcher, capture exact PID/bind/
   settings/release identity, run `operational_health`, then actual HTTP root
   login redirect, missing-CSRF rejection, static-byte match and media/private
   denial checks. Stop the process and retain the now-verified previous release.
5. Exercise an explicit candidate startup failure and retain sanitized nonzero
   exit evidence. Start the candidate on the same loopback bind and repeat
   validation. A deliberately unavailable DB port must produce nonzero health
   evidence while leaving the original test DB untouched. Never mark that
   candidate ready; stop it.
6. Confirm candidate/previous application-source and database-history hashes
   agree. Reactivate the retained previous build/config/static release, repeat
   HTTP/health checks, and verify retained media/private/source/static identity.
   This is an actual bounded artifact/config/process rollback with no database
   rollback or destructive migration. Any history mismatch halts it for the
   applicable governed recovery/roll-forward decision.
7. Stop all session processes, verify restricted storage again, retain separate
   failed/recovered evidence and explicit profile-qualified results. Readiness
   refers only to this approved Development scenario. Production readiness and
   equivalence remain unverified; `operational_health` continues to report
   `production_readiness=NOT_VALIDATED` even when dependency checks succeed.

Run from the repository root with a fresh existing evidence output directory:

```powershell
.venv-2/Scripts/python.exe scripts/cep071_deployment_runtime.py --output <absolute-package-evidence-directory>
```

CEP-071 qualifies this implemented, approved non-production deployment control.
After its closeout, an unchanged-source fresh run can support the executable
Development portions of CEP-075. The canonical CEP-075 **production-equivalent**
target property remains blocked: this approved profile explicitly claims no
equivalence. It is never relabelled as a full CEP-075 PASS. No completed CEP's
qualification scenario is rerun.
