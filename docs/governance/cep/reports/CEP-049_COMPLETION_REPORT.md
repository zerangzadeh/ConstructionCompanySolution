# CEP-049 Completion Report

**Execution verdict: EXECUTION COMPLETE. Lifecycle: CLOSED_VERIFIED.**

| Checkpoint | Result |
| --- | --- |
| CEP / IMB | CEP-049 / IMB-0043 — Project Controls governed metric layer |
| Baseline | `main` and `origin/main` at `21476e7b583e87bb22775c8cbca33f61702a926c`; initial worktree clean |
| Identity / authority | Repository-local canonical prompt SHA-256 `6d6658933f4dfeba9c8ebbf48226ee80ab31d8a07876d2fb0537f3815c963805` matches manifest; CEP-020 and CEP-040 COMPLETE; prior-wave foundations present; standing bounded non-production authority applies |
| Product changes | Project Controls reporting adapters now select only governing accepted budget allocations and dated classified cost facts, subtract positive commitment relief, fail closed on mixed currencies or incomplete coverage, and retain budget/fact/source/contract version identity. Existing permission-checked Persian RTL drill-through displays lineage and coverage. |
| Migration / data change | NONE; `makemigrations --check --dry-run` reports no change; no non-test source data mutated |
| AC / DoD | 6/6 PASS in [acceptance mapping](../evidence/CEP-049_ACCEPTANCE_MAPPING.csv); scoped DoD PASS |
| Validation | Baseline P10 reporting 21 passed. Final focused suite 48 passed on PostgreSQL, including inherited reporting regression and new CEP-049 unit/service/permission/tenant/UI checks. Adjacent Project Cost supersession/release regression 1 passed. Ruff, Django check, migration drift, and diff whitespace passed. [Evidence manifest](../evidence/CEP-049_EVIDENCE_MANIFEST.csv). |
| Screenshot | [Permission-authorized test-fixture drill-through](../evidence/CEP-049_Drillthrough.png), rendered through Django and captured with headless Chrome at 1280×900; no real tenant data |
| Pre-existing / validation interference | An optional first broad run overlapped another process on the shared `--keepdb` database, causing setup deadlock and flush errors; serial focused and affected regression reruns passed. A second optional fresh full-schema run was stopped during migrations after sufficient focused evidence was obtained; its uniquely named disposable test database was removed. Neither run supplies a PASS claim. |
| Package-introduced failure / blocker | NONE |
| Remaining UTV | Performance/concurrency runtime and browser/accessibility runtime beyond the bounded fixture screenshot. Project Cost producer coverage remains explicitly incomplete by its owning domain; reporting does not certify it. |
| Downstream readiness | Exact source/version and incomplete-coverage evidence is available to authorized reporting readers. No new source producer, financial posting, Project Cost coverage certification, metric code, or formula was activated. |
| Registry / Git / production / Human Sign-off | Registry synchronized; Git branch/worktree created NO; git add, commit, push, merge, rebase, reset NOT EXECUTED; production and Human Sign-off NOT EXECUTED |
| Next CEP | CEP-052 is the smallest blast-radius dependency-ready candidate after CEP-049; not started at a clean operational boundary for reviewability and a practical Human-controlled Git checkpoint. |

The [execution manifest](../manifests/CEP-049_EXECUTION_MANIFEST.md) records the actual touch set before product mutation; the [change manifest](../manifests/CEP-049_CHANGE_MANIFEST.csv) records the final files. The P10 six-metric catalogue remains closed, and reporting remains a read/projection authority. The baseline `apps.financials` compatibility projection was not promoted or modified.
