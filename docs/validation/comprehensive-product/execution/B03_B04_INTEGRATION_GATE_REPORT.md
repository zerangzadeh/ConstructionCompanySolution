# BONIRA B03/B04 Integration Gate

**PASS · 2026-11-12 · Non-production integration verification.** The full migration chain applied 462 migrations from zero on PostgreSQL 18.6, with zero pending. The same source export passed 68 focused tests, 31 subtests, and the four requested Chrome journeys.

## Migration failure and correction

The earlier `daily_reports.0009_revision_guards` attempt failed with `psycopg.ProgrammingError: only '%s', '%b', '%t' are allowed as placeholders, got '%R'`. Django's PostgreSQL schema editor defaults `params` to `()`, which sends the SQL through psycopg placeholder interpolation. Both `REPORT` and `ENTRIES` declare a PL/pgSQL record as `daily_reports_dailyreport%ROWTYPE`. psycopg read the `%R` prefix as a placeholder and failed before executing the SQL. The reproduction invoked the old default for each block through Django's SQL collector and got the same exception. [Original failure](evidence/b04-final-remediation-24ad220f/concurrent-migration-error.txt) · [Reproduction](evidence/b03-b04-integration-20261112/escaping-probe-frozen.log)

The concurrent B03 implementation already passed `params=None` to both calls when this gate started. That is the minimal correction. The gate added an explanatory comment and verified that both blocks reach the schema editor's collected SQL byte for byte, including the literal `%ROWTYPE`. SQL bodies, dependency order, trigger timing, and constraints retain their original definitions. [Migration](../../../../apps/daily_reports/migrations/0009_revision_guards.py)

The qualifying run started with a newly created `integration_frozen` database on the gate's own loopback PostgreSQL cluster. It ran `manage.py migrate --noinput --verbosity 2` once from the initial migration through all leaves, with no restore, fake migration, or reused schema. `0009_revision_guards` applied in 0.859 s. Django exited 0, migration history was consistent, and the database contained no tenants or users before fixtures. PostgreSQL showed three functions, eight enabled triggers, and the initially deferred decision guard. No independent migration failure surfaced. Django's system check and migration drift check passed. [Full migration log](evidence/b03-b04-integration-20261112/migrate-frozen-from-zero.log) · [Database catalogue witness](evidence/b03-b04-integration-20261112/migration-witness.json) · [System check](evidence/b03-b04-integration-20261112/system-check.log) · [Drift check](evidence/b03-b04-integration-20261112/drift-check.log)

## Focused integration results

| Check | Result | Evidence |
|---|---|---|
| B03 Return and compatibility | 31 tests passed in the main run. Coverage includes independent Return and approval, successor edits and resubmission, tenant and permission denial, pinned evidence, and SQL rejection of sealed content changes, reparenting, and unaudited decisions. | [Focused test log](evidence/b03-b04-integration-20261112/tests-focused.log) · [JUnit cases](evidence/b03-b04-integration-20261112/tests-focused.xml) |
| B03 concurrency | 3 tests passed on independent clones. Coverage includes Return versus approval, correction and resubmission races, labor replay, and legacy competing approvals. | [Return](evidence/b03-b04-integration-20261112/tests-return_race.log) · [Labor](evidence/b03-b04-integration-20261112/tests-labor_race.log) · [Approval](evidence/b03-b04-integration-20261112/tests-approval_race.log) |
| B04 regressions | 34 tests passed across remediation, Equipment Usage and operations, Safety and Quality reviews, and HSE scope. The combined main run passed 31 subtests. | [Focused test log](evidence/b03-b04-integration-20261112/tests-focused.log) · [Test selection](evidence/b03-b04-integration-20261112/replay/run_tests.py) |
| Daily Report Return in Chrome | Author Return denied. Reviewer reason required. Independent Return preserved the sealed original. Author corrected the header and labor count, resubmitted a new seal, and the reviewer approved the successor. | [Chrome assertions](evidence/b03-b04-integration-20261112/chrome/results.json) · [Return at 390 px](evidence/b03-b04-integration-20261112/chrome/daily-return-390.png) |
| Safety and Quality approval in Chrome | Creator and sibling-site decisions denied. Blank reasons rejected. Independent approval retained both formal review revisions and left the operational status at `reported`. | [Chrome assertions](evidence/b03-b04-integration-20261112/chrome/results.json) · [Safety approval](evidence/b03-b04-integration-20261112/chrome/safety-approved-390.png) · [Quality approval](evidence/b03-b04-integration-20261112/chrome/quality-approved-390.png) |
| Equipment Usage in Chrome | Rejected 20 hours for a two-hour interval. Valid retry persisted two hours with the selected active deployment, qualified operator, and Tehran-local 08:00–10:00 converted to 04:30–06:30 UTC. | [Chrome assertions](evidence/b03-b04-integration-20261112/chrome-equipment/results.json) · [Runtime feedback at 390 px](evidence/b03-b04-integration-20261112/chrome-equipment/equipment-usage-390.png) |

Chrome 156.0.8078.80 used separate authenticated headless contexts against the loopback server. All 32 assertions passed across the requested journeys. The 16 recorded layouts were RTL with one main region and no horizontal document overflow at 1440 and 390 px. No recorded journey request returned HTTP 5xx. A separate read-only PostgreSQL connection confirmed the persisted revisions, approvals, usage, and audit records after the browser sessions. [Persisted state](evidence/b03-b04-integration-20261112/persisted-witness.json)

## Baseline and scope

Local `main` and `origin/main` resolved to `24ad220f0376cb0b6232b745938b35433843a32d`. The qualifying baseline includes the concurrent B03 and B04 working files and two B03 service/view updates received before the export. An initial live-tree migration attempt was stopped when concurrent edits made that baseline unstable. The qualifying run began again on a second empty database using the file export. The export hashes matched at closeout, and B03/B04 source still matched the export in the working tree. Later Billing, Estimates, and B05 changes were preserved in the live tree and fall outside these results. [Entry state](evidence/b03-b04-integration-20261112/entry-baseline.json) · [Frozen source hashes](evidence/b03-b04-integration-20261112/frozen-source.json) · [Closeout](evidence/b03-b04-integration-20261112/closeout.json)

Two Equipment browser attempts stopped before submitting because the harness first selected the dependent field out of order and then used an incorrectly scoped selector for the optional source reference. The passing rerun selected Equipment first and used the normal generated source key. Its synthetic operator qualification was extended so it appeared in the browser's current-date choices. No product fix was needed. Ruff passed with `RUF012` excluded for the two pre-existing Django migration class lists. `git diff --check` passed. [First browser attempt](evidence/b03-b04-integration-20261112/chrome-equipment-selector-attempt.txt) · [Second browser attempt](evidence/b03-b04-integration-20261112/chrome-equipment-locator-attempt.log)

All database writes went to the gate's private PostgreSQL cluster. Existing Development and Production databases were untouched. The loopback PostgreSQL and Django listeners were stopped after evidence collection. No Git commit or push was performed. [Evidence checksums](evidence/b03-b04-integration-20261112/SHA256SUMS.txt)

## Replay

1. Copy the 2,027 files in `frozen-source.json` to a `source` subdirectory inside a new private scratch directory and verify their SHA-256 hashes. The original export is retained under `.scratch/b03-b04-integration-20261112/source`. Copy the [replay scripts](evidence/b03-b04-integration-20261112/replay/) into the scratch directory beside `source`.
2. Start a new PostgreSQL 18 cluster with its data directory at `<scratch>/pg`, role `gate_local`, and a free loopback port. Use a disposable cluster with loopback-only access. Write its port to `db-port.txt` and another free port to `web-port.txt`. Generate a fresh random Django key in `session-secret`. Create a new empty `integration_frozen` database. The replay settings and witnesses check the database, port, and cluster directory. The recorded run used Python 3.11.1, Django 5.2.17, and psycopg 3.3.5.
3. Set `DJANGO_SETTINGS_MODULE=gate_settings` and set `PYTHONPATH` to the scratch directory and `source`, plus the Playwright installation if it is outside the project virtual environment. From `source`, run the commands below with the project virtual environment. Create `gate_migrated_template` from `integration_frozen` immediately after the migration witness and before seeding. `run_tests.py` clones that template for the main run and each race test. It uses the Windows PostgreSQL 18 binary path recorded in the script.

   ```powershell
   python ../escaping_probe.py
   python manage.py migrate --noinput --verbosity 2
   python ../migration_witness.py
   python manage.py check
   python manage.py makemigrations --check --dry-run --noinput
   createdb -h 127.0.0.1 -p (Get-Content ../db-port.txt) -U gate_local -T integration_frozen gate_migrated_template
   python ../run_tests.py
   python ../seed_smoke.py
   ```

4. From the same `source` directory and environment, run `python ../serve.py` in a separate shell. Run `python ../chrome_smoke.py` against installed Chrome, then run `python ../persisted_witness.py`. Stop the replay server and private PostgreSQL cluster when done.
