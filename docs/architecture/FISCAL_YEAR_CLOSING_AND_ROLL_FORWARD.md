# Fiscal-year closing and opening roll-forward

Authority: explicit Human Product/Accounting instruction dated 2026-10-27, new
bounded Development / Non-Production capability; no completed CEP is reopened.

## Grounding and touch set

Start: `main`, HEAD and local `origin/main`
`a1322c38e5c89d399c6ba54c239444a2b61c119a`. Existing payroll, policy-specification,
CEP-069 evidence and Registry edits are unrelated and must be preserved.

| Classification | Repository evidence / disposition |
| --- | --- |
| EXISTING_AND_REUSABLE | `accounting.models`: tenant-local AccountType asset/liability/equity/income/expense; active leaf accounts; IRR journal/line Decimal amounts, project/site/WBS/party references and posted snapshots. Organization is the book/company authority; no separate company ledger exists. |
| EXISTING_AND_REUSABLE | `services`: atomic posting, organization serialization, period locking, numbering, payload hashing, monetary policies, independent maker/checker, reversal/replacement and audited period close/reopen. |
| EXISTING_AND_REUSABLE | Opening Import forms/views/services: supplied initial/migration balances, draft/proposed/accepted, independent acceptance. Retained reconciliation and statements support period close. |
| PARTIAL | FiscalYear draft/active/closed exists, but no year transition service; period close does not close a fiscal year. Ledger reports accumulate posted history. |
| MISSING | Annual-close configuration, execution/linkage, nominal closing, retained earnings transfer, derived opening, pair uniqueness, year reopen, annual reconciliation and UI. No dormant implementation found. |
| POLICY_CONFLICT | Ordinary OPENING appended to cumulative reports would duplicate balances. Resolve with governed opening boundaries in financial reporting; keep historical source facts and reports intact. |
| ACCOUNTING_POLICY_REQUIRED / RESOLVED | Human instruction supplies permanent/temporary treatment, configured summary/equity references, no distributions, maker/checker, exceptional reopen and downstream-posting stop. No external statutory claim is made. |

Planned mutation surface: new accounting closing models/services/forms/views,
templates/tests and additive migrations; bounded extensions of accounting models,
posting registry, services, reporting and navigation; permission codes/registry/
default catalog migration; audit action/catalog migration; this design/evidence.
No dependency, production action, CEP state change or Git checkpoint is authorized.

## Implemented contract

The existing five stored account types are authoritative. Assets, liabilities and
equity are permanent; income and expense are temporary. Unsupported types fail
closed. There is no memorandum/statistical classification or eligibility catalog;
no such automatic carry-forward is introduced. Preserve every existing ledger
dimension (project, site, WBS, party); there is no account-specific dimension policy
that permits safely discarding any recorded dimension. No new dimension is added.

The latest immutable configuration version for a source year identifies distinct
active posting equity accounts for Year-End Result and Retained Earnings. Summary
must initially be zero per dimension. No configuration version changes in place.
A new version may be selected before preparation or after withdrawal/reopen;
existing executions retain their original configuration. Preparation may be
withdrawn before any closing entry is posted, preserving the request history.

The close execution uses versioned source/target linkage and an append-only event
history. Active source and target uniqueness prevents conflicting pairs. Fiscal
year status reuses active/closed and adds closing/rolled_forward. Preparation pins
the posted balance snapshot; close approval revalidates it under the organization
lock, posts a CLOSING journal through the existing kernel, zeros nominal accounts
through the configured summary account and transfers the signed result to equity.
Opening acceptance is a separate atomic, independently approved step. It derives
one OPENING journal from final permanent balances and records exact reconciliation.
When no nominal balance needs closing, the execution itself is the governed
closing reference and no journal is fabricated. When all final balances are zero,
the independently accepted, versioned execution is the zero-balance opening
artifact. Its evidence explicitly records that no financial entry was required.
Database constraints and frozen snapshots distinguish these cases from missing
journals. Every posted journal still requires nonempty balanced lines.

Year-end-generated opening boundaries seed subsequent ledger statements without
double counting earlier history. Profit/loss statements exclude annual closing
and its reversal so closing does not erase annual performance. Historical source
journals remain available in journal history. Retained reports keep their original
cutoffs/evidence and are not rewritten. Boundary selection and journal-line reads
share one SQL snapshot, preventing a concurrent roll-forward commit between two
reads from duplicating an opening. Treasury and subledger reconciliation queries
were inspected: they tie out explicit producer journal IDs, rather than summing
all history; their domain authority is unchanged.

Reopen reverses opening (if present), then closing (if required), atomically, records inverse
reconciliation, restores source-year access and reopens the last source period
through existing protected period rules. Downstream posted transactions or an
active subsequent close block automatic reopen. Existing period reopen separation
rules continue to apply. Correct, re-close periods, prepare a new version and
reconcile again; old executions/journals/events remain immutable evidence.

Failures roll back the complete business transition. Denied/failed HTTP actions
return user-facing validation; successful transitions retain audit and execution
events. No failure creates a partial execution or posted journal.

## Actual implementation surface

- `apps/accounting/closing_models.py`, `closing_services.py`, `closing_guards.py`,
  `closing_forms.py`, `closing_views.py`: tenant-owned configuration versions,
  execution/linkage, evidence, controls and application workflow.
- `apps/accounting/models.py`, `services.py`, `posting_registry.py`: fiscal status
  controls, explicit CLOSING semantics, posting registration and protected seams.
- `apps/accounting/reporting.py`, `reconciliation.py`, `views.py`, `urls.py`,
  `admin.py`: coherent opening boundaries, exact annual-source tie-out, source
  navigation and read-only administration.
- Accounting `year_end_list.html`, `year_end_detail.html`, `_tabs.html`,
  `journal_detail.html`: Persian RTL workflow and guarded journal actions.
- `apps/organizations/models.py`, `permission_registry.py`, `role_defaults.py`,
  migration `0124_fiscal_year_closing_permissions`: five explicit capabilities;
  existing accounting roles retain independent-actor requirements; platform
  administration grants no tenant accounting authority.
- `apps/audit/models.py`, migration `0055_fiscal_year_closing_actions`: audited
  configuration and lifecycle transitions. Existing append-only history survives.
- Accounting migrations `0014_fiscal_year_closing`,
  `0015_fiscal_year_closing_controls`, `0016_fiscal_year_zero_entry_references`:
  additive configuration/linkage/history and extended constraints. No journal
  history is backfilled, rewritten or deleted.
- `test_fiscal_year_closing.py`, `test_fiscal_year_closing_runtime.py`,
  `scripts/qualify_fiscal_year_closing.cjs`: focused PostgreSQL, concurrency,
  rollback, migration preservation and real-browser qualification.

## Validation and execution evidence

Final qualification: **COMPLETE — Development / Non-Production, 2026-10-27**.
52/52 final qualification cases PASS, including populated migration preservation,
concurrency and a real browser workflow; 3/3 subsequent narrow retry/guard checks
PASS. Five feature migrations are applied to configured local Development
PostgreSQL; Django checks, migration drift and bounded Ruff checks pass.
Runtime synthetic annual profit = 50 IRR; derived opening debit = credit = 150 IRR;
closing/opening and inverse reconciliation PASS with zero discrepancies. Separate
loss, zero-result, zero-entry, dimensional and repeated-year cases also PASS.
Evidence is in
[`docs/validation/fiscal-year-closing`](../validation/fiscal-year-closing/).

- `final-qualification.txt`: 52 exact final feature, reporting, populated migration
  rollback/reapply and browser cases. Test authentication uses a fast hasher only
  in the disposable test process; product settings are unchanged.
- `idempotent-retry-check.txt`: three narrow checks after preserving historical
  posted-journal read-only retries while keeping annual journals protected.
- `final-regression-tests.txt`: 62 affected accounting/catalog cases: 59 PASS and
  three explicitly expected global permission-registry baseline failures.
- `baseline-attribution.json`: HEAD and current duplicate-model, namespace and
  enforcement-reference defects compared independently; zero new faults.
- `focused-tests.txt`: original mixed-run failure evidence. The two legacy
  serialized-restoration classes fail before reaching business assertions with a
  duplicate Django content-type row. The isolated regression runner disables
  `serialized_rollback` only for `AccountingPostingConcurrencyTests` and
  `AccountingFinancialHardeningTests`; canonical post-migrate catalog bootstrap
  still runs, all nine business/concurrency cases execute unchanged, and no
  product or historical test file is modified for that adaptation.
- `browser-qualification.json`, twelve PNG captures: six actual browser states at
  1440 and 390 pixels, RTL with no horizontal document overflow. Representative
  desktop/mobile images were visually inspected.
- `accounting-qualification.json`: actual synthetic closing/opening and inverse
  reconciliation, annual result, references and frozen snapshot hashes.

No global full-suite PASS is claimed. The three pre-existing global registry
assertions are unrelated baseline debt; they are neither fixed nor concealed.
No Product/Accounting decision remains unresolved. Implementation defects resolved
include report duplicate balances and boundary-read races, nominal/result/equity
transfer and correction lineage, zero-entry handling without empty journals,
prepared-state approval rendering, duplicate form-control identifiers, source
navigation and ordinary historical idempotent retries. Browser test labels were
adapted to the existing required-field accessibility suffix. Production qualification,
production migration/cutover and Human sign-off are outside this Development
qualification. Real tenant closing accounts are not inferred or seeded.

Git: local `main`; no branch/worktree created; no add, commit, push, merge or other
Git write. Unrelated payroll, policy-specification, CEP-069 and Registry changes
remain outside this task. No CEP is reopened or re-executed.

