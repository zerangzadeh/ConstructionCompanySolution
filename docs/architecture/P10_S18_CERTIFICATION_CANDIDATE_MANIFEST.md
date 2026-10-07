# P10-S18 Certification Candidate Manifest

**Candidate ID:** `P10-RC1-20261007-E0E078C9`

**Status:** **PREPARED BUT NOT CERTIFICATION-FROZEN — BLOCKED.**

**Recorded:** 2026-10-07.

**Base commit:** `3dd1b4ef8234f3071bf6ba186772861db99a01c0`.

**Intended scope:** the complete implemented repository runtime through
Product Owner-accepted `P10-S02–S17`, including governed metrics, reconciliation/
exceptions and project-closeout coordination, plus all previously accepted
runtime on which those controls depend. `P10-S18–S21` adds certification evidence
only. The candidate excludes `P10-S22+`, AI/RAG/vector, providers, queues/
schedulers, integrations, automatic downstream/financial effects and production
activation.

## 1. Freeze result

The base commit is identifiable, but it is **not** the certifiable candidate
commit. Accepted P10-S07–S17 runtime, migrations, tests and templates exist only
as modified/untracked worktree content relative to that commit. The runtime state
contains 36 modified/untracked runtime/dependency files and has fingerprint:

`e0e078c9519db964c63e0d211ad4c1078945e08abd2c64d3e9d2397c427e04ee`

The fingerprint is SHA-256 over the ordered `<path><TAB><Git blob hash>` entries
in section 2. It identifies the observed state but does not replace the accepted
requirement for a clean immutable Git commit. No commit was created because this
tranche did not authorize committing the user's existing runtime changes.

Disposition: `FC-0 Evidence invalid`. Candidate freeze remains blocked until the
accepted runtime and dependency lock are reviewed and committed, a clean checkout
of that exact commit reproduces this intended scope, and the manifest is refreshed
with the final commit SHA.

## 2. Observed runtime/dependency state

| Path | Git blob hash |
| --- | --- |
| `apps/audit/models.py` | `68c142f74d2322fe0f557e4b356df25196b49bdc` |
| `apps/organizations/migrations/0106_p10_s07_s13_reconciliation_permissions.py` | `668479861f01d586a68890ccfe1f28e1e54866f4` |
| `apps/organizations/migrations/0107_p10_s14_s17_project_closeout_permissions.py` | `d37ce3d8e49318c375a4291aeb3e5602bf4d43ce` |
| `apps/organizations/models.py` | `1808c726f477bf63e551e8e60cc0b540e3fe5a97` |
| `apps/organizations/permission_registry.py` | `d98c34edde442a3c148f4abc3e12b32c512451c6` |
| `apps/organizations/role_defaults.py` | `d37e3e8bfd1795cb7c1011f650d1fe34c0b0faa2` |
| `apps/reporting/apps.py` | `4d0b746ccaa2af7d43d950bb094cb1c11ba20e90` |
| `apps/reporting/catalog_bootstrap.py` | `7f7b2dc943ce09924866a41a83ac27e9193d93a3` |
| `apps/reporting/catalog.py` | `fbe470987d89bf0cc3520a43ad1c1b3bc9a8495e` |
| `apps/reporting/migrations/__init__.py` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |
| `apps/reporting/migrations/0001_initial.py` | `0cba223bdd6fbf063c1c9fd0a2950895692e29b4` |
| `apps/reporting/migrations/0002_seed_approved_metric_catalogue.py` | `6c10f347347a672160af3d95468281d7b34c3e33` |
| `apps/reporting/migrations/0003_p10_s07_s13_reconciliation_controls.py` | `bf5f72d9e4fc5318d331be129fe2b0575f925ed5` |
| `apps/reporting/migrations/0004_seed_p10_s07_s13_reconciliation_pairs.py` | `79939b4ee691939948492a41495174f7261e3ccd` |
| `apps/reporting/migrations/0005_projectcloseoutprofiledefinition_and_more.py` | `ea1ea0899ac3ff31d11ae6dd2f2294a9cd8f2d56` |
| `apps/reporting/migrations/0006_seed_p10_s14_s17_project_closeout_profile.py` | `51004d2ce3080fc29cba6a8ac4cc254c1ba8f54f` |
| `apps/reporting/models.py` | `a25ae0918172f2aea4dad23909242745f384e366` |
| `apps/reporting/project_closeout_catalog.py` | `c54609d177a196245841889038205f79f8a7002a` |
| `apps/reporting/project_closeout.py` | `f241de05192510011e5d202d295e7a0ccb14fb68` |
| `apps/reporting/reconciliation_catalog.py` | `3393dbbb8da1a3c992a3e1b3436a69f6b1b14dd0` |
| `apps/reporting/reconciliation.py` | `1b91d86b53dabddea42a7db3285f2fe5af95f85a` |
| `apps/reporting/services.py` | `cba543ab1c7a34e8d885674da17ea16f62e383ad` |
| `apps/reporting/test_p10_s02_s06.py` | `63acca3192de603dd83d50d692b53ea0e22af6e6` |
| `apps/reporting/test_p10_s07_s13.py` | `87ea9f1386c3c90aecdb1f5c46f90e3228fc53f0` |
| `apps/reporting/test_p10_s14_s17.py` | `34061daef0beba3b2239cc51a637c6375d116564` |
| `apps/reporting/urls.py` | `1a0448c0947f32d9fea7dc463b5b21b6eff5bbde` |
| `apps/reporting/views.py` | `f779b63c78d5cfcff0b2ad59eca67e9ad544b79e` |
| `requirements-lock.txt` | `327ad889513632ff9e68e616897a6d88e1aec1c9` |
| `templates/components/navigation_links.html` | `513bfa7d1251841e7cf32e55cccb5c3fba7b103d` |
| `templates/financials/dashboard.html` | `f8da677a3c6cc7487efcfeccbeb792d5f815d357` |
| `templates/financials/report.html` | `5b428e99a1551fb0881e6be55786905c9f1fd2b1` |
| `templates/reporting/dashboard.html` | `626577021f098cffd98d9eaee17922c15b73749d` |
| `templates/reporting/project_closeout_detail.html` | `e1a9e590935df915e39d7da32cf3ac0a822ec85b` |
| `templates/reporting/project_closeout_workbench.html` | `4384f5e6d3262cd8a6f614c810600a07d7fc832f` |
| `templates/reporting/reconciliation_detail.html` | `0c3eb0ca18eaf461ad789f26d3faaae06a5ab1dd` |
| `templates/reporting/reconciliation_workbench.html` | `e8e0288007c0e63b15700cc86c7fc5bde4b42a09` |

## 3. Documentation-only differences excluded from runtime fingerprint

The observed worktree also contains documentation-only changes in `ROADMAP.md`,
`docs/ROADMAP_EXECUTION_PLAYBOOK.md`, `docs/architecture/DATA_MODEL.md`,
`docs/architecture/DOMAIN_AND_DATA_MODEL.md`, `docs/architecture/DOMAIN_MODEL.md`,
the four P10 decision/certification records, `PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`,
`USER_CAPABILITY_MAP.md` and `WORKFLOW_AND_PERMISSION_MATRIX.md`. They are excluded
from the runtime fingerprint only; final candidate documentation must still be
committed or explicitly excluded with exact hashes before certification evidence.

## 4. Dependency lock

`requirements-lock.txt` is the candidate lock for CPython 3.11 on Windows x86-64.
It pins 16 direct/transitive runtime and certification packages and includes one
SHA-256 artifact hash per selected wheel. File SHA-256:

`ec2f92a67b0f64ab2045364b6ed9fcef9a17aab5f74d18f8080ee74388525e12`

Installation with `pip install --require-hashes` completed successfully in a new
temporary virtual environment and imported Django 5.2.17/Psycopg 3.3.5. The base
Python installation exposes an unrelated incomplete global NLTK installation;
that pollution is not in the project lock and must be absent from or isolated in
the final certification environment.

## 5. Configuration and migration references

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

## 6. Accepted certification parameters

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

## 7. Environment and recovery-tooling inventory

Current available host evidence is **environment-qualified only**:

- Windows 11 Home 10.0.26200; Intel i7-1165G7; 8 logical processors; 31.77 GiB
  physical memory;
- no explicit application process topology, proxy, container, CPU/memory cap or
  production-equivalence record;
- PostgreSQL 18.6 is reachable and the configured role has `CREATEDB`;
  `max_connections=100`, `shared_buffers=128MB`, `work_mem=4MB`;
- the development database is not current at all migration heads and is not
  certification evidence; and
- `pg_dump`/`pg_restore` were not available on PATH or under the standard local
  PostgreSQL installation directories, and no coherent database/DMS backup/
  restore target was provisioned.

Therefore performance must later be classified
`environment-qualified / production capacity certification still gated` unless a
production-equivalent isolated environment is supplied. Recovery rehearsal cannot
start until PostgreSQL backup/restore tooling and an isolated coherent database/
DMS restore environment are available.

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

`P10-S18 = BLOCKED` because:

1. no clean committed candidate contains the accepted P10-S02–S17 runtime and the
   new dependency lock; and
2. PostgreSQL backup/restore tooling plus an isolated coherent database/DMS
   recovery environment are not available.

`P10-S19–S21` must not start until both blockers are resolved and this manifest is
reissued with the final clean candidate commit and environment fingerprints.
