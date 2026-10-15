# CEP-009 execution manifest

## Grounding and authorization

- Branch: local `main`; start and end HEAD: `533fbd52e38dd448973ba4cc618e5faa44b01fec`.
- Before mutation, `git status --short`, `git diff --name-status`, and `git diff --stat` showed the uncommitted CEP-006 changes and unrelated `Agents.md` / `BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md`. Those changes were preserved.
- The Human Decision Maker explicitly authorized CEP-009 in this chat, after CEP-006 `EXECUTION COMPLETE`. `AUTH-BATCH-002` records the serial queue and `GATE-01 = PASS` approval basis.
- Canonical sources: `packages/CEP-009.md` and `BONIRA_CEP_ACCEPTANCE_COVERAGE_REGISTER.csv` in `BONIRA_CODEX_EXECUTION_PACKAGE_DESIGN_CONSOLIDATED_LATEST.zip`, plus `prompts/CEP-009_EXECUTION_PROMPT.md` in the approved consolidated prompt materials. The package-design draft authorization label is superseded for this execution by the Human authorization; its scope, ten AC, and no-migration boundary remain in force.

## Actual execution touch set

- Services: `apps/inventory/services.py`, `apps/inventory/p8_services.py`.
- Tests: `apps/inventory/test_cep009.py`, `apps/inventory/tests.py`, `apps/inventory/test_p8_s05_s11.py`.
- Evidence runners/results: `output/cep-009/`.
- Documentation: `ROADMAP.md` and this CEP-009 manifest set.
- Models, schema, migrations, permissions, views, templates, settings, and valuation policy: **NONE**.

## Implementation and validation

- A single filtered SQL aggregate now computes posted/reversed incoming minus outgoing quantity for the authorized tenant, warehouse, and material. It returns a `Decimal` and loads no movement history into Python.
- Both stock-movement paths and transfer preparation acquire warehouse row locks by sorted UUID. Warehouse locks precede material locks on stock create/post/reverse; transfer line material locks are also sorted by UUID. Existing transaction boundaries, business validation, status transitions, audit calls, and source ledger remain authoritative.
- The selected isolated PostgreSQL validation used `test_cep009_validation_20261015_71e4`. The initial broad selection failed 13/13 in shared Inventory fixture setup because legacy tests lacked explicit organization scope grants. Scoped fixture correction resolved that test debt.
- Final selected run: five passed and two test-only failures (SQL UUID rendering assertion and custody-controller fixture scope). Focused recheck: both passed. Combined final evidence: **7/7 selected tests pass**. See `output/cep-009/validation-results.xml` and `validation-recheck-results.xml`; no claim of a single all-green full-suite run is made.
- Ruff, formatting, `manage.py check`, `makemigrations --check --dry-run`, and `git diff --check`: pass. No migration was created. Operational-load concurrency and production performance remain UTV.

No Git write, production action, Human Sign-off, CEP-011 implementation, or CEP-013 implementation was performed.
