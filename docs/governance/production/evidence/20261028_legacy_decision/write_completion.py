"""Produce closeout only from collected passing outputs; no database/Git writes."""

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent


def main():
    runtime = OUT / "runtime"
    load = lambda name: json.loads((runtime / name).read_text("utf-8"))
    empty = load("empty_RESULT.json")
    populated = load("populated_RESULT.json")
    recovery = load("RECOVERY_RESULT.json")
    assert all(v["result"] == "PASS" for v in (empty, populated, recovery))
    assert load("REGRESSION.json")["failed"] == 0
    assert json.loads((OUT / "SHUTDOWN.json").read_text())["result"] == "PASS"
    count = int(re.search(r"Ran (\d+) tests", (runtime / "REGRESSION.txt").read_text()).group(1))
    report = f"""# Legacy Payment Product Decision — executed closeout

2026-10-28. main@c9fe1d7e7ed586ef96a2ee453a3490369d25e6a3 plus bounded
uncommitted changes. [Direct Human decision](../../LEGACY_PAYMENT_RETIRED_DECISION_20261028.md).

## Implemented contract

Documents 0012 and billing 0018 no longer require Development, a loopback DB,
zero population or the earlier twelve-condition readiness file. Retired sources
are classified RETIRED_LEGACY_DATA. Existing tenant/reference/snapshot integrity
checks remain; neither source population nor financial interpretation is an
eligibility condition. Existing archival DMS/audit snapshots remain archival
evidence, with no new payment/accounting authority or financial mappings.

Billing 0018 and payments 0007 now remove Django model state while retaining the
four original raw tables, all original values, relationships and constraints.
No physical historical-record destruction is performed or authorized. New
snapshots use the new disposition; a valid prior accepted excluded_demo_test
snapshot is compared by all source fields without rewriting its bytes/hash.
Legacy runtime models and permissions remain absent. Active Treasury, GL and
AP/AR runtime services and ownership boundaries are unchanged.

Applied migrations are not replayed. Existing databases where earlier authorized
Development retirement already dropped tables remain supported; no deleted data
is reconstructed. Retained tables on newly migrated databases are private raw
historical storage, outside the active Django model/domain and customer bootstrap.
Any later physical disposal needs separate retention/audit authority.

## Executed qualification

- [Local contract tests](CONTRACT_TESTS.txt): 2/2 PASS, production settings and
  localhost/db/remote host cases, no readiness-file access; state-only no-drop
  operations. The local isolated test cache warning is retained; Linux deploy
  checks use the actual absolute cache root and report no issues.
- [Empty bootstrap](runtime/empty_RESULT.json): PASS, truly empty DB first
  migrated forward to the pre-retirement graph, then the full {empty['migration_nodes']}-node
  graph with config.settings.production, DEBUG false and PostgreSQL TLS verify-full.
- [Populated upgrade](runtime/populated_RESULT.json): PASS, same settings and
  graph; two tenants, posted/void nonzero legacy records, allocations, real
  historical claim-settlement records, typed/generic document links and audit IDs.
  All {populated['legacy_rows']} original rows across four raw tables match exact
  pre-migration row hashes. Two archival snapshots, four typed/generic references,
  unrelated draft GL/accounts/balanced lines and all existing active-financial
  rows remain unchanged. No financial targets are fabricated. One synthetic prior
  accepted snapshot is byte-for-byte unchanged. Repeated preservation is idempotent.
- Both paths: migrate/post-migrate catalog, no pending graph, makemigrations
  --check --dry-run and check --deploy --fail-level WARNING PASS. No fake migration
  history, DEBUG switch or Production database is used.
- [Affected Linux regressions](runtime/REGRESSION.txt): {count}/{count} PASS;
  runtime retirement, Treasury post/reverse/projection, CSRF/tenant denials,
  canonical AR settlement/caps/reversals, DMS and reporting no-double-counting.
  Password hashing and HTTPS redirect overrides are test-process-only; actual
  prior HTTPS qualification is retained. No broad suite or new concurrency claim.
- [Native TLS backup/restore](runtime/RECOVERY_RESULT.json): complete restored
  state equals source across {recovery['tables']} tables, {recovery['rows']} rows,
  {recovery['constraints']} constraints and {recovery['sequences']} sequences,
  including retained raw history. {recovery['seconds']:.3f} seconds for this
  changed-schema check; no new RPO/RTO, capacity or real Production guarantee.

## Provenance, attempts and cleanup

[Entry](ENTRY.json) preserves authority, baseline hashes and the initial planned
touch set. The planned additional test module was unnecessary: actual integration
scenarios are in bootstrap_probe.py; existing test_retirement_contract.py was
updated. Six tracked Python files changed, plus readiness/Registry evidence.
[Final source manifest](SOURCE_FREEZE_FINAL.json) identifies 1,604 exact staged
source files, including the decision. The earlier SOURCE_FREEZE.json is the
initial capture. [Target collection check](runtime/FINAL_TARGET_CHECK.json)
verifies deployed source bytes and executed helper hashes; executed helpers are
retained alongside output. Host orchestration records explicit commands and owned
resources. No dependency/configuration/active-financial runtime change is hidden.

Three failed populated-fixture attempts remain in runtime/populated_ATTEMPT_*:
optional Party merge text, draft journal numbering and UUID generation were
corrected in synthetic fixture construction. The first failed database is retained;
later attempts use atomic fixture transactions. No application migration or
financial rule was weakened to repair these fixture failures.

The earlier readiness evidence remains historical with its original source and
scope, including prior rejected bootstrap and superseded rejection tests. Existing
070/074 recovery, 075 HTTPS/rollback, 069 statutory, 072/076 operational and 077
supply-chain qualification are reused, without replaying completed CEPs. Prior
21 Linux boundary tests, six secure-configuration tests and 56 HTTPS cases retain
their coverage. Current checks close only the authorized migration/retention delta.
The old artifact manifest describes the earlier checkpoint; this checkpoint has
its own manifest and before copies of revised readiness documents.

[Collection](COLLECTION.json) screens generated private secret values/key blocks
before public extraction. [Shutdown](SHUTDOWN.json) confirms owned DB/container/
guest shutdown and both loopback listeners closed. Private disk, synthetic raw
data, failed attempts, backup and secrets remain outside Git. No historical
record, private resource or failed evidence was deleted.

## GATE-11 determination

GATE-11 remains NOT_PASSED, now 3/5 exact canonical conjuncts satisfied: C1 retained
GATE10 PASS; C2 nine scoped required IMBs complete; C3 required approved runtime
qualification now includes complete bootstrap and changed-schema restore.
C4 required external Production evidence and C5 no unresolved blocker remain
unsatisfied. The remaining external records are Production statutory applicability/
activation policy (EXT-0018), recovery objectives/protection/key custody/acceptance
(EXT-0020), actual target/configuration selection (EXT-0021) and operating owners/
sink/escalation/retention/access acceptance (EXT-0022). Their approvals expressly
cover non-production only. The new decision supplies no such extension.

No Legacy Payment population, zero-history, old cash reconciliation or disposal
approval is required for bootstrap. No safe executable migration prerequisite
remains. The exact next input is the four release-linked Production-scoped external
dispositions in the revised reference contract. Actual deployment and GATE12 Human
Business Sign-off are separate later events, not invented pre-Gate prerequisites.
All 79 CEPs and all other Gate records are unchanged. No Production mutation,
statutory activation, final certification, Human Sign-off or Git write occurred.
"""
    (OUT / "COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
    print("Completion report generated from passing collected evidence")


if __name__ == "__main__":
    main()
