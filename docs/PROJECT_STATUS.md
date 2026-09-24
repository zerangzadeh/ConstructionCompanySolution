# Project Status Reference

This file holds dated, volatile project snapshots that should not be loaded for
ordinary implementation tasks. `ROADMAP.md` is authoritative for current delivery
status; Django models and migrations are authoritative for the schema; current test
runs are authoritative for validation.

## Documentation audit snapshot — 2026-09-24

The repository-first product/domain/architecture audit reconciled active
documentation with the implemented workflow runtime/workbench and receivable
Billing domain, produced the dependency-based roadmap, and completed the
enterprise UI interaction standard. No application behavior, package, or
migration was changed by that audit.

Validation observed for that working tree:

- `python manage.py check`: passed.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `python -m pytest --collect-only -q`: 563 tests collected.
- The initial full `pytest -q` run progressed beyond 85% without a failure but
  was interrupted after the large demo-seed test produced no output for an
  extended period. The tail was then rerun verbosely from Workforce panels
  through the end: 45 tests and 39 subtests passed in 36m32s, including the
  previously slow `seed_demo_data` idempotency test. Combined execution covered
  the collected suite without a reported failure; there is no single uninterrupted
  full-suite completion line for this working tree.
- Environment-level `pip check`: failed because the local virtual environment
  contained undeclared `nltk` with missing optional/runtime dependencies. The
  project does not declare `nltk`; this is recorded as reproducibility evidence,
  not treated as an application dependency failure.

These are dated observations rather than production certification. The full test
and Ruff results for the completed documentation-only change should be taken from
the corresponding work session/release evidence.

## Process retrospective — 2026-09-24

The repository-wide product audit consumed substantially more time and model
context than necessary. Some cost was inherent in the unusually broad request:
the source prompt covered the complete repository, product/domain architecture,
Iranian regulation, competitors, libraries, UI standards, production readiness,
and a dependency roadmap. Avoidable cost came from large file/output reads,
duplicated detail across documents, an application-wide test run for a
documentation-only change, and repeated polling while the demo-data idempotency
test ran for an extended period.

The durable corrective rules are in `Agents.md` under **Token, time, and execution
efficiency**. Future sessions must use progressive inspection, one authoritative
location per conclusion, proportionate validation, output limits, explicit stop
conditions, and concise progress reporting. For documentation-only changes, the
default is targeted document/reference/format validation; a full application suite
requires an explicit request or a documented executable/configuration risk.

When an adequate lower-token approach exists, the agent must inform the user of
the saving and any material coverage tradeoff. If quality and safety are unchanged,
the efficient approach should be taken without unnecessary confirmation.

## Historical snapshot — 2026-09-15

At this date the platform was recorded as an active full-product initiative rather
than an MVP. The ERP core and multiple operational domains were implemented and
validated on PostgreSQL 18.6 with Psycopg 3. The ERP and Django Admin interfaces
shared the approved Persian-first RTL design system.

The implemented core covered tenant identity/settings, parties, material masters,
projects and project controls, workforce, procurement, inventory, equipment,
contracts, estimates, daily reporting, safety and quality issue workflows,
expenses, payments and allocations, versioned private documents, audit, and
financial read models. The current entity map, relationships, invariants, and
lifecycle states belong in `docs/architecture/DOMAIN_AND_DATA_MODEL.md`.

The server-rendered UI used Django templates and Tailwind CSS, with HTMX where
useful. It included a responsive RTL application shell, shared page/form/table and
feedback patterns, and Django Admin overrides that preserved native behavior.

The development-only, idempotent `seed_demo_data` command populated first-party
business models through the Django ORM and application services. Its recorded
deterministic dataset contained 10 organizations, 40 projects, 200 contracts, 80
estimates, 200 payments, 200 expenses, 320 daily reports, their supported related
records, and generated audit history. Django internal/system tables were excluded.

The delivery note at that time identified Tenant Workflow & Work Management as the
next cross-domain foundation and Billing & Progress Claims as dependent on it. This
is historical context only; consult `ROADMAP.md` for the current state.

## Historical validation baseline — 2026-09-15

- Full PostgreSQL suite: 167 passed.
- Subtests: 26 passed.
- Django check: passed.
- Ruff check and format: passed.

PostgreSQL 18.6 with Psycopg 3 was the authoritative database baseline. These
counts are not a current release claim; rerun relevant checks for the current
checkout and consult newer dated validation records in the roadmap and architecture
documents.
