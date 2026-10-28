# Production-scoped dispositions — executed GATE-11 closeout

2026-10-28. **GATE-11 PASS, C1–C5 satisfied, 5/5.**
main@c9fe1d7e7ed586ef96a2ee453a3490369d25e6a3 plus the bounded uncommitted
changes identified below. [Entry](ENTRY.json), [direct Human authority](../../PRODUCTION_SCOPED_DISPOSITIONS_20261028.md),
[approved runtime contract](../../PRODUCTION_RUNTIME_CONTRACT.json).

## Authority and exact result

The Human supplied Production-scoped EXT-0018/0020/0021/0022 selections and
explicitly authorized the necessary implementation and isolated qualification.
No completed CEP was reopened. Canonical Gate/source identities and five exact
Pass Condition conjuncts remain unchanged. C1 retains GATE10 PASS; C2 retains the
nine completed required IMB contributions; C3 has executed current runtime evidence;
C4 now has approved Production policy and all required reproducible qualification;
C5 has no unresolved in-scope blocker. The Registry and machine-readable
[Gate evaluation](../../GATE11_EVALUATION.json) are synchronized.

The canonical row says UTV lasts until production-equivalent evidence exists and
unlocks a future production release decision. Its statutory activation evidence
was executed with the approved Production envelope through real services on
synthetic non-production data. It does not expressly require a customer Production
event before PASS. Actual activation/cutover and GATE12/EXT0026 remain separate.

## Actual mutation surface

- apps/payroll/statutory_governance.py: separate PRODUCTION_REVIEWED scope,
  secure settings, exact Human authorization and frozen parameter-digest boundary.
  Existing NON_PRODUCTION_QUALIFICATION still rejects Production settings.
- apps/payroll/test_production_governance.py: four-envelope validation, unsupported
  scope/value/source/population/settings negatives, synthetic tax/insurance source
  import/activation/calculation and traceability using existing tenant/actor fixtures.
- core/production_operations.py and config/gunicorn_production.py: explicit private
  durable technical sink/HTTP binding, sanitized failed-login observation, registered
  technical failure classes, correlation, 30-day diagnostics, fsync and fail-closed
  startup. No business authority, financial alerts, thresholds or audit disposal.
- scripts/production_recovery.py: small native OpenSSL CMS AES-256-GCM adapter;
  private disjoint paths, no overwrite, authenticated recovery publication. No new
  Python dependency or custom security primitive.
- tests/test_production_operations.py: private receipt/restart/retention, security
  correlation/sanitization, insecure-sink refusal and no credential retention.
- Production policy/envelope/environment/reference/readiness/evidence documents;
  Registry GATE11 and repository checkpoint metadata only. No schema migration.

ENTRY.json is the initial planned touch set; the proposed tests/test_production_recovery.py
was unnecessary because native recovery/negative controls were exercised directly.
The Gunicorn binding and diagnostic/access tests are the discovered actual seams.
All prior Legacy Payment changes/evidence are preserved without re-execution or
additional population conditions. Treasury/GL/AP/AR calculations, tenant/domain
authority, permissions and schemas remain unchanged.

## Executed qualification

**Final affected Linux run: 52/52 PASS**, [commands/output](runtime/FINAL_APP_TESTS.txt).
It covers the unchanged adopted calculation/tenant/authorization boundaries,
new Production envelopes, diagnostic semantics and existing support authority,
independent approval, scope, expiry/revocation and audit. Secure deploy/drift checks
pass. The test client alone disables HTTPS redirect after actual secure deploy
checks; test password hashing is simplified. No broad/full-suite PASS is claimed.
An earlier affected run was repaired from 47/48 to 48/48; the final expanded run
supersedes it. The separate [six diagnostic/access checks](runtime/OPS_ACCESS_TESTS.txt)
also pass. Ruff checks/format pass on all six product/test files.

[Native PITR](runtime/PITR_RESULT.json) passes pg_basebackup, pg_verifybackup,
continuous WAL and named-point replay with the source stopped. The result includes
a commit after the base backup and excludes a later committed row. Exact full
database fingerprints match across **534 tables / 7,854 rows**, constraints and
sequences; all **15 files** across the other three classes match. Recovery took
**326.981 seconds**, below 3,600 seconds. Missing WAL never reaches the requested
point; corruption and a wrong private key fail without published plaintext.

[Actual capture cadence/custody](runtime/CADENCE_CUSTODY_RESULT.json): two real
OS-timer captures **65.271 seconds apart**, protection lags **32.548/33.453 seconds**,
within the 900-second contract. The timer is stopped after the bounded drill.
Captures carry minimum 30-day holds and 30-day restore due dates; no purge or
future elapsed-operation evidence is fabricated. A third protected capture
[independently restores current audit coverage](runtime/CURRENT_AUDIT_RECOVERY.json):
**70 files**, including **51 actual alert/HTTP receipts** and release/recovery records.
The private backup filesystem differs from active storage; application access to
backup/key payload and backup-writer access to the private key are denied.
Actual provider/path remains a cutover binding, not an off-host guarantee claimed here.

[Selected deployment/operations](runtime/WEB_OPERATIONS_RESULT.json): 28 real
HTTPS cases across worker restart, authentication/private delivery, CSRF/tenant
denials, TLS/Host/proxy/static and health. Real failed login, sink outage,
failed worker bootstrap, unreachable migration/readiness and backup/recovery controls
produce durable correlated receipts; response behavior is preserved on sink failure.
Health remains NOT_VALIDATED rather than claiming certification.

[Final release identity](runtime/FINAL_RELEASE_IDENTITY.json) verifies the actual
mounted release against **1,611 source files** and repeats **14 HTTPS cases**.
The reused driver erroneously read its head from /srv/bonira/source/BUILD.json;
the first web result retains that stale field as failed provenance, not as the
current source identity. Final metadata identifies c9fe1d7 plus the exact source
manifest. The intervening release delta is only the repaired recovery adapter,
qualified by the native PITR run; HTTP/domain/configuration source is unchanged.

## Retained failures, reuse and provenance

The four failed PITR setup attempts are preserved by public traces/private
diagnostics: initial database readiness, missing replication HBA rule, CMS
recipient argument ordering, and the system Python tar API. A script-only
directory execute permission was corrected while diagnosing the archive process.
Extraction now explicitly accepts only bounded regular files/directories; links,
devices and escaping paths are rejected. The wrapper defect is fixed with the
explicit recipient option. Native recovery, negative controls and final source
verification pass after these repairs. No security/business invariant was weakened.

[Frozen source](SOURCE_FREEZE.json) and [target check](runtime/FINAL_TARGET_CHECK.json)
identify source bytes and executed helpers. The initial application-test manifest
is retained separately. The source and the final mounted release both verify;
the unchanged runtime image supplies dependencies while source is mounted read-only.
[Native identities](runtime/TOOLCHAIN.json) record OpenSSL3.0.22/Debian package and
binary integrity, PostgreSQL18.6 and Nginx. The host qualification Python3.11.2 is
distinct from the approved application CPython3.11.17; no interpreter identity is conflated.

Earlier 070/074 recovery, 075 compatible rollback/HTTPS, 069 adopted review,
072/076 operations, 077 supply-chain and 079 representative UAT are reused with
their source/environment limits. Their original scoped reports are not rewritten.
Dependency locks and canonical prompts are unchanged; no fresh advisory scan,
cold rebuild, performance target or universal security claim is invented.
The prior artifact manifests remain historical checkpoints. This checkpoint has
its own final hashes and before copies of changed readiness/Registry records.

[Collection](COLLECTION.json) screens generated private secrets/key blocks before
public extraction. [Shutdown](SHUTDOWN.json) confirms Nginx, both PITR services,
database, timer and guest stopped, vault unmounted and both loopback listeners
closed. Private source/backup/failed data and credentials remain outside Git.
No historical/source records or retained failed evidence were destroyed.

## Remaining actual actions

Separately authorized deployment must bind the real hostname/IP/provider/DNS,
certificate/renewal ownership, paths, distinct private secrets and enterprise
destination; verify the complete recovery set and current applicability; coordinate
writes; execute the reviewed migration/release and customer bootstrap; reconcile;
receive real receipts and an explicit go/no-go. Continue the approved capture,
retention/restore acceptance, access and certificate duties after activation.

GATE12 Human Business Sign-off/EXT0026 is NOT EXECUTED; final Human certification
is NOT EXECUTED. No actual Production deployment, database/customer cutover,
Payroll activation, DNS/firewall/provider change or Git write occurred.
All 86 CEP records, including the 79 completed CEPs, and other existing Gate
records are unchanged. No further EXT0018/0020/0021/0022 disposition or executable
GATE11 prerequisite remains.
