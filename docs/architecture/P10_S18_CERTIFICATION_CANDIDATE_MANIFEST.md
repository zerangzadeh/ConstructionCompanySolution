# P10-S18 Certification Candidate Manifest

**Candidate ID:** `P10-RC1-20261007-E0E078C9`

**Status:** **CANDIDATE FROZEN — P10-S18 CERTIFICATION PREREQUISITES
SATISFIED.**

**Recorded:** 2026-10-07.

**Final candidate commit:**
`0db3ac9a9fa70e8a857ef0867d532be5206a14c4`.

**Intended scope:** the complete implemented repository runtime through
Product Owner-accepted `P10-S02–S17`, including governed metrics, reconciliation/
exceptions and project-closeout coordination, plus all previously accepted
runtime on which those controls depend. `P10-S18–S21` adds certification evidence
only. The candidate excludes `P10-S22+`, AI/RAG/vector, providers, queues/
schedulers, integrations, automatic downstream/financial effects and production
activation.

## 1. Freeze result

Commit `0db3ac9a9fa70e8a857ef0867d532be5206a14c4` contains the accepted
P10-S02–S17 runtime, migrations, tests and templates, the certification documents
required at freeze, and `requirements-lock.txt`. The certification-scope worktree
was clean immediately after the commit. The unrelated local scratch directories
`.codex_tmp_p10_lock_20261007/`, `.codex_tmp_p10_lock_verify_20261007/` and
`.codex_tmp_p10_lock_verify_b_20261007/` are explicitly ignored and are not part
of the candidate.

The final runtime/dependency fingerprint is:

`76cdbbddea7a03c0463fee4a1827c70f6fadf40dfd5c340cfc9bb4d3794d6b05`

It is SHA-256 over the ordered tracked candidate paths and Git blob identities for
`apps/`, `config/`, `core/`, `templates/`, `manage.py` and
`requirements*.txt`: 1,134 paths at the final candidate commit. A clean checkout
of the commit therefore reproduces the frozen runtime/dependency state.

Disposition: the candidate freeze itself is **PASS**. The candidate remains
frozen even though the later migration preflight failed its accepted time gate.

## 2. Documentation-only attestation boundary

The final candidate commit includes the accepted implementation and the
certification documentation available at freeze. The subsequent S18 evidence
attestation updates only `ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAYBOOK.md`, this
manifest, the release-certification decision packet and
`PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`. Those status/evidence updates are
explicitly excluded from the runtime fingerprint; they do not change the frozen
candidate runtime or dependencies.

## 3. Dependency lock

`requirements-lock.txt` is the candidate lock for CPython 3.11 on Windows x86-64.
It pins 16 direct/transitive runtime and certification packages and includes one
SHA-256 artifact hash per selected wheel. File SHA-256:

`ec2f92a67b0f64ab2045364b6ed9fcef9a17aab5f74d18f8080ee74388525e12`

Installation with `pip install --require-hashes` completed successfully in a new
temporary virtual environment and imported Django 5.2.17/Psycopg 3.3.5. The base
Python installation exposes an unrelated incomplete global NLTK installation;
that pollution is not in the project lock and must be absent from or isolated in
the final certification environment.

## 4. Configuration and migration references

- Python: 3.11.1; Django: 5.2.17; Psycopg: 3.3.5.
- Database: PostgreSQL 18.6 through Django's PostgreSQL backend.
- Production settings reference: `config.settings.production`; its required
  secret/host/database values and `DB_SSLMODE=verify-full` remain environment
  inputs and are not stored here.
- Dependency declarations: `requirements.txt`, `requirements-db.txt`,
  `requirements-dev.txt`; immutable resolution: `requirements-lock.txt`.
- Migration heads:
  `accounting.0011`, `accounts.0009`, `admin.0003`, `audit.0052`, `auth.0012`,
  `billing.0015`, `compliance.0001`, `contenttypes.0002`, `contracts.0009`,
  `daily_reports.0006`, `documents.0009`, `equipment.0006`, `estimates.0005`,
  `expenses.0008`, `fixed_assets.0006`, `inventory.0006`, `knowledge.0002`,
  `materials.0010`, `organizations.0107`, `parties.0004`,
  `partner_qualification.0001`, `payments.0006`, `payroll.0005`,
  `procurement.0015`, `projects.0008`, `quality.0001`, `reporting.0006`,
  `safety.0001`, `sessions.0001`, `subledgers.0003`, `support.0002`,
  `timekeeping.0002`, `treasury.0007`, `workflows.0027`, `workforce.0008`.

## 5. Accepted certification parameters

- Recovery: RPO 15 minutes; RTO 60 minutes. Certification targets only, not a
  production SLA.
- Migration/downtime window: maximum 30 minutes. Rollback decision occurs before
  irreversible production activation; exceeding 30 minutes fails certification
  unless separately re-approved.
- Workload: 50 baseline concurrent users; 100 peak; 130 surge; 10 Tenants; 25
  active users per Tenant; 10 representative projects per Tenant; realistic data
  across governed reporting, reconciliation and closeout source domains.
- Duration: 30 minutes at peak, 15 minutes at 130-user surge, and two hours at
  peak for endurance. The previously accepted latency/error/resource thresholds
  remain unchanged.

## 6. Environment and recovery-tooling inventory

Current available host evidence is **environment-qualified only**:

- Windows 11 Home 10.0.26200; Intel i7-1165G7; 8 logical processors; 31.77 GiB
  physical memory;
- no explicit application process topology, proxy, container, CPU/memory cap or
  production-equivalence record;
- PostgreSQL 18.6 is reachable and the configured role has `CREATEDB`;
  `max_connections=100`, `shared_buffers=128MB`, `work_mem=4MB`;
- the development database remains non-authoritative and is not certification
  evidence;
- PostgreSQL 18.6 tools are available and verified at
  `D:\Program Files\PostgreSQL\18\bin\pg_dump.exe` and
  `D:\Program Files\PostgreSQL\18\bin\pg_restore.exe`; and
- the disposable preflight created separate source and restore databases plus
  isolated source, backup and restore DMS paths under the local temporary root.

Therefore performance must later be classified
`environment-qualified / production capacity certification still gated` unless a
production-equivalent isolated environment is supplied.

## 7. Migration diagnosis and backup/restore preflight result

The initial stopped preflight used only uniquely named disposable non-production
resources:

- source database:
  `p10_s18_pf_src_20261007_082054_e0e078c9`;
- separate restore database:
  `p10_s18_pf_restore_20261007_082054_e0e078c9`; and
- isolated DMS source, coherent-backup and restore locations below
  `C:\Users\azera\AppData\Local\Temp\p10_s18_recovery_20261007_082054_06em_w8v`.

The configured role proved database create/migrate/drop authority and the local
temporary root provided isolated DMS write/cleanup authority. The clean migration
crossed the accepted 30-minute maximum after approximately 30 minutes 8 seconds.
Execution was stopped at the gate before creating a database dump or DMS backup,
so database restore, DMS restore and restored DB/DMS coherence are **not passed**.
No RPO/RTO certification is claimed. `test_construction_erp` and production data
were not used or mutated. Both disposable databases were dropped and the isolated
DMS root was removed after the failed attempt.

That result remained an explicit `FC-3` failure until a candidate-preserving
diagnosis and fresh gate rerun succeeded. No missing result was treated as pass.

The instrumented diagnosis then used a fresh clean database, one migration runner
and 0.25-second PostgreSQL activity sampling. Actual Django migration execution
completed in `1,032.661` seconds (`17m 12.661s`) across 376 migrations. Database
creation took `0.495s`, Django/process preparation took `3.704s`, post-migration
process overhead took `0.959s`, and migration-framework overhead within the timed
window was `6.107s`. No blocking PID was observed in 4,127 samples. The longest
individual migrations were `procurement.0002` (`46.861s`), `workforce.0002`
(`44.968s`), `equipment.0002` (`29.485s`), `inventory.0002` (`28.621s`) and
`workforce.0008` (`28.232s`).

The diagnosis classifies the earlier overrun as avoidable certification
harness/environment timing and transient contention, not a genuine migration
graph workload, redundant migration, lock wait or migration defect. Evidence is
two unchanged-candidate clean runs below 18 minutes, no observed blockers, and no
individual migration approaching the prior excess. The candidate-preserving
procedure correction uses one isolated database and runner, directly measures
only Django migration execution, separately records setup/cleanup, samples locks/
waits, and invokes the verified PostgreSQL 18.6 binaries directly. No migration
was skipped, faked, pre-applied or edited.

The fresh gate rerun used source database
`p10_s18_diag_20261007_101534_e0e078c9`, separate restore database
`p10_s18_restore_20261007_101534_e0e078c9`, and isolated source/backup/restore DMS
paths below
`C:\Users\azera\AppData\Local\Temp\p10_s18_diag_20261007_101534_bw86oqas`.
Actual Django migration execution completed in `969.888` seconds (`16m 09.888s`),
passing the 30-minute gate with no blocking PID observed in 3,869 samples.

Post-migration preflight then passed:

- PostgreSQL custom-format backup: 3,461,995 bytes, SHA-256
  `7057d479d7668d15886d8eb4ae360021ea02a917877f2a63d0b7aed74728ceee`;
- database restore into the separate disposable restore database: **PASS**;
- DMS source-to-backup-to-separate-restore copy: **PASS**;
- restored DB/DMS evidence identity, relative path, 49-byte size, storage
  visibility and SHA-256
  `7b0bdcddc9a9f89cf9de8a57195ef412840d06eaacdf5318d26f207e43f30779`:
  **PASS**; and
- both databases and all isolated file resources removed: **PASS**.

This is S18 preflight only. It is not S19 migration/rollback/reapply or final
RPO/RTO certification.

## 8. Named owners and preserved gates

| Responsibility | Owner |
| --- | --- |
| Certification Acceptance Owner | Product Owner |
| Certification Owner / Coordinator | Authorized Technical Maintainer |
| Evidence Custodian | Authorized Technical Maintainer |
| Migration/Restore Executor | Authorized Technical Maintainer |
| Database/Recovery Executor | Authorized Technical Maintainer with database authority |
| Security/Tenant Reviewer | Independent authorized Security Reviewer |
| Performance Executor | Authorized Technical Maintainer |

The accepted non-waivable controls and the six unrelated permission-registry
failures retain their recorded treatment. `P10-S22+`, AI/RAG/vector, providers,
queues/schedulers, integrations, automatic downstream/financial effects and
production activation remain gated.

## 9. S18 conclusion

`P10-S18 = certification prerequisites satisfied`.

The frozen candidate, verified hashed dependency lock, PostgreSQL 18.6 tools,
isolated recovery topology, 30-minute migration gate and coherent database/DMS
backup/restore preflight all pass. The prior FC-3 blocker is resolved by the
candidate-preserving certification-procedure correction; the threshold was not
changed and the frozen candidate runtime/schema semantics were not modified.

`P10-S19–S21 = may start under existing bounded certification authorization`.
They were not executed in this pass. All production, P10-S22+ and preserved
capability gates remain unchanged.
