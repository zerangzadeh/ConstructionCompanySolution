# B04 technical checks

12 November 2026 · isolated PostgreSQL 18.6 · MVP

| Check | Actual result |
|---|---|
| Pre-fix bounded regressions | `12 failed, 4 passed` including parametrized/subtest results; original log retained. No current PASS inferred from this output. |
| Final bounded regressions | **8 passed, 9 subtests passed**. Current source, migrated snapshot, ordinary transaction-isolated test cases. |
| Affected boundary selection | **32 passed, 21 subtests passed**; three existing live-browser tests failed before page access on a hard-coded `sessionid` lookup. |
| Corrected browser fixture | **3 passed** after using the expected cookie name only in the disposable technical settings and redirecting its output to a private folder. No product or historical test was edited. |
| Original legacy selection | 35 failed, 35 passed, 1 teardown error, 15 subtests passed before product mutation. Equipment/legacy Expense bases create legacy memberships without migrated grants; the teardown hits an unregistered retained Payments FK table in the reused snapshot. These are separately evidenced baseline fixture/flush debt. |
| From-zero technical schema | Stopped at 387/457 applied migrations after prolonged historical workflow catalog migration CPU cost. TEST INFRASTRUCTURE LIMIT; no tests/PASS claimed from that attempt. |
| Runtime migration check | Original/retest each have 457 applied, zero pending; `migrate --noinput`: no migrations to apply. |
| Django system check | PASS, no issues. |
| Schema drift | PASS, no changes detected; no migration files created. |
| Ruff / format | PASS; all 10 changed Python files pass lint and format checks. |
| Scoped `git diff --check` | PASS. |

The affected selection was:

```text
pytest tests/test_b04_remediation.py
       tests/test_equipment_operations_workspace.py
       tests/test_equipment_selector_remediation.py
       apps/safety/test_cep079_hse_scope.py
       apps/expenses/test_p4_s26_s30.py --reuse-db -q
```

The existing selector driver assumes `sessionid`; B04 runtime Chrome sessions deliberately use per-database cookie names. Its corrected three-case rerun sets `SESSION_COOKIE_NAME='sessionid'` only in the isolated technical process. Its screenshot directory is overridden before collection so prior artifacts are preserved. The 32 passing cases were not repeated after a cookie-only fixture correction. The final eight B04 tests are a subset of those 32, not eight additional unique cases.

The equivalent affected suite uses this task's isolated migrated snapshot. A retained historical table is outside the managed Django flush list; the existing browser base's own cascade-safe teardown handles that fixture. No extra table was removed and no product schema was changed. No full-repository, durability, production or Human-UAT PASS is claimed.

Logs: [pre-fix regressions](b04-regression-original.log), [final focused](b04-regression-final.log), [boundary selection](boundary-final.log), [corrected browser fixture](selectors-retest.log), [legacy attribution](legacy-suite-original.txt), [original migrations](runtime-original-migrations.log), [retest migrations](runtime-retest-migrations.log), [system check](system-check.log), [schema drift](schema-drift.log), [lint](lint.log).
