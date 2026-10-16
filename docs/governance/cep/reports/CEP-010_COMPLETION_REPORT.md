# CEP-010 Completion Report

**Execution verdict: CLOSED — VERIFIED** for bounded Development implementation of
`IMB-0069` only. **CEP-010 execution status: EXECUTION COMPLETE.**
`AUTH-BATCH-001` and the Product Owner's 2026-10-14 bounded schema-migration
resolution govern this work. Human Sign-off and global `GATE-01` passage are not
claimed.

## Baseline and finding

- Branch: `cep/CEP-010-person-workrelationship`; HEAD:
  `0b0cfcdabb93e4e6215d6f2805e763dd82f99cf4` (local `main`). The clean
  worktree had empty `git status --short`, `git diff --name-status`, and
  `git diff --stat` before its execution manifest and product changes.
- `CEP-010-FINDING-001 / BLOCKER-MIGRATION`: **RESOLVED** by explicit Human
  authorization for the minimum schema migration. No bulk Employee migration,
  historical reconstruction, cutover, or production operation occurred.
- Actual touch set and change details: [execution manifest](../manifests/CEP-010_EXECUTION_MANIFEST.md)
  and [change manifest](../manifests/CEP-010_CHANGE_MANIFEST.csv).

## Implemented boundary

`Person` has a stable UUID, tenant ownership, name and optional active-member
`User`. `WorkRelationship` has a separate UUID, tenant/Person references,
employment number, effective start/end, and optional explicit legacy `Employee`
link. A relationship is one episode. The create service rejects overlapping
episodes for the same tenant Person or employee number and serializes number
allocation under the tenant lock. Ending an episode appends an immutable
`WorkRelationshipRevision`; it preserves the original revision and earlier
episodes. Tenant and legacy identity validation rejects incompatible links.
Existing `Employee` remains addressable through an explicit resolver, which
returns the legacy source without creating target rows and fails closed on
multiple linked episodes. The service reuses existing Workforce permissions;
there is no endpoint, UI, new role, or Job Family/Grade architecture.

## Migration verification

- Migration: `apps/workforce/migrations/0009_cep010_person_workrelationship.py`.
  Dependency chain: `workforce.0008`, `organizations.0107`, swappable User.
  Operations: three `CreateModel`, six `AddConstraint`, one `AddIndex`.
  Schema impact: three tenant-owned tables, UUID keys, foreign keys, uniqueness,
  date checks and Person/date index. Data impact: **none**; no `RunPython` or
  bulk operation. Reverse drops only these new tables/constraints/index; existing
  Employee and assignment tables are untouched.
- `manage.py migrate workforce 0009 --plan`: schema-only plan.
- `manage.py migrate workforce 0009 --noinput`: **PASS**.
- `manage.py migrate workforce 0008 --noinput` then reapply `0009`: **PASS**.
- Configured Development database before and after: `Employee=10`,
  `EmployeePositionAssignment=12`, `EmployeeProjectAssignment=8`;
  `Person=0`, `WorkRelationship=0`, `WorkRelationshipRevision=0` after migration.
  Existing Employee records and assignment history were preserved; no Person or
  episode rows were fabricated.

## Verification and evidence

| Check | Result |
| --- | --- |
| `python -m pytest apps/workforce/test_cep010_person_workrelationship.py --nomigrations --reuse-db -q` | **12 passed** |
| `python -m pytest apps/workforce/tests.py::WorkforceModelTests --nomigrations --reuse-db -q -k employee` | **4 passed, 6 deselected** |
| `ruff check apps/workforce/models.py apps/workforce/person_services.py apps/workforce/test_cep010_person_workrelationship.py` | **PASS** |
| `ruff format --check apps/workforce/person_services.py apps/workforce/test_cep010_person_workrelationship.py` | **PASS** |
| `manage.py makemigrations --check --dry-run` | **PASS**, no changes |
| `manage.py check` | **PASS**, zero issues |
| `git diff --check` | **PASS** |

The initial ordinary pytest run was stopped during the repository's lengthy
test-database migration setup. The subsequent `--nomigrations` run provided
focused executable model/service evidence; the actual migration was verified
separately in the configured Development database. A supplemental full
`WorkforceModelTests` run under `--nomigrations` gave 9 passed and one
permission-catalog fixture failure. The identical test and failure were
reproduced on the untouched baseline branch with the same test mode. The
four Employee-specific regression tests passed; this baseline fixture issue
is not attributed to CEP-010.

Evidence IDs: `CEP-010-EV-001` through `CEP-010-EV-006` in the
[evidence manifest](../evidence/CEP-010_EVIDENCE_MANIFEST.csv). The
[acceptance mapping](../evidence/CEP-010_ACCEPTANCE_MAPPING.csv) records **AC-1 through
AC-6 PASS**. Scoped DoD: **PASS**. Model/schema constraints, effective dating,
tenant/object integrity, compatibility path, focused regression, lint and
Django checks: **PASS**.

## Remaining boundaries

- No unresolved in-scope blocker or package-introduced required-test failure.
- Performance/concurrency under production load and browser/accessibility are
  **UTV**, not claimed PASS. No UI was added.
- `CEP-029 / IMB-0070` retains Employee backfill, historical reconstruction
  and cutover; it is **not executed** or made ready by this CEP alone.
- `GATE-01`: **NOT GLOBALLY EVALUATED / NOT CLAIMED**. Human Sign-off:
  **NOT EXECUTED**. Production migration/cutover: **NOT EXECUTED**.
- `git add`, `git commit`, `git push`, and `git merge`: **NOT EXECUTED**.

The affected active roadmap and domain/data-model entries were reconciled in
this change. Other roadmap packages and historical snapshots were not changed.
