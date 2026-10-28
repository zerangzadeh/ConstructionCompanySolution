# Current-release qualification attempts

The bounded readiness run reuses the retained BONIRA-PE-NP-01 runtime and existing
qualified mechanisms. It addresses code/schema changes since `de6e208` and creates
new isolated databases and release/static directories. No completed CEP is reopened.

- Attempt 1 failed because the host driver probed PostgreSQL immediately after
  starting its stopped container. Retained `ATTEMPT_01_FAILED.json`; added an
  actual bounded readiness wait. No product change or service readiness inferred.
- Attempt 2 applied all six migrations and passed deploy/drift checks, but its
  overstrict row comparison failed on the canonical post-migrate catalog bootstrap.
  Retained `ATTEMPT_02_FAILED.json`. Compared original and migrated catalogs by
  primary key: 663 permission and 28 role records differ only in `updated_at`;
  five new authorized permissions are additive. All old business row bytes and
  catalog semantic fields remain preserved. The checker now proves that precise
  invariant instead of excluding unexplained catalog changes.
- Before HTTP execution, the previous release was rebound to a new old-schema
  clone, `pe_readiness_previous_20261028`, preserving the original reference
  database from synthetic login/session writes. `PREVIOUS_DB_BINDING.json`
  records it. Candidate code uses its separately migrated clone. This is a
  compatible release/schema-binding rollback, not a live schema downgrade.
- Attempt 3 failed during genuinely empty test-database creation under production
  settings at documents migration 0012: `Legacy Payment disposition is authorized
  for Development only`. This is a retained Production bootstrap authority blocker,
  not a waived or repaired migration. Billing 0018 carries an additional explicit
  local-Development guard. The subsequent migrated-clone/flush fixture supports
  only isolated current-boundary tests; it does not satisfy empty Production
  bootstrap, change settings to evade the guard or fake migration history.
- Final host evidence tools received formatting and unused-import cleanup; these
  do not change product source. Guest-executed tool copies are retained separately
  with hashes so the actual execution is reviewable. Failed private command
  diagnostics stay in the owned guest; public failures omit credentials/data.
- Attempt 4 reached HTTP after 21/21 Linux tests passed, then failed public-static
  byte delivery because the new public release roots inherited umask 077. Retain
  `ATTEMPT_04_FAILED.json`. Corrected only the two verified dedicated public-static
  directory modes to 0755; protected data/secrets roots remain 0700. Repeated only
  the HTTP release transitions, not the passing financial/migration tests. Final
  previous/current/rollback/return evidence has 56/56 actual HTTPS cases PASS.

The earlier host command `supply_chain.py check-config` was rejected by argparse
before executing any check. The supported `check-locks` command and the existing
lock/secret guards then passed; no false check result is retained.

Configuration guards executed once: `.venv-2/Scripts/python.exe -m unittest
tests.test_production_configuration -v`, 6 tests in 21.958 seconds, OK. Tests cover
positive defaults/explicit secure cookies and negative secret, required input,
SMTP/cache/TLS/host/redirect/cookie/storage cases without network/DB/dotenv.
The terminal output is summarized in `REUSE_AND_BUILD_CHECKS.json`.

Existing migration authority guards were additionally executed with database and
dotenv access forbidden: 2/2 PASS, `BOOTSTRAP_GUARD_TESTS.txt`. This confirms the
Production/remote rejection; it does not satisfy empty Production bootstrap.
Final Linux boundary run: 21/21 PASS in 174.643 seconds. Source and protected modes
were reverified before public evidence collection and graceful owned-guest shutdown.
