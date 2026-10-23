# BATCH-06 — Expense allocation selector authority

Date: 2026-10-22, Asia/Tehran. **UIUX-F-119 = RUNTIME_VERIFIED_RESOLVED / RESOLVED.**
Decision: **BATCH_06_RUNTIME_VERIFIED_RESOLVED**.
Authority: the Human's attached BATCH-06 end-to-end execution request, including
minimum synthetic Development fixtures and existing authority, and the
[canonical contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-06).

## Baseline and Actual Execution Touch Set

`main`; HEAD and local `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`; upstream `origin/main`; divergence
0/0 against local reference; no fetch. Twelve dirty product files, previous
F-111/BATCH-01..05 tests/reports/evidence, Graphify and protected documents form
the effective entry baseline. F-119 entered OPEN / STATIC_CONFIRMED /
NOT_EXECUTED. [Entry state and hashes](f111_batch_06_evidence/ENTRY_BASELINE.json).

Actual product touch set: `apps/expenses/forms.py:ExpenseAllocationForm` and its
necessary imports; `apps/expenses/views.py:expense_detail,expense_allocate`.
Added `tests/test_uiux_f111_pattern_allocation_scope.py`, this report and
`f111_batch_06_evidence/`; changed only F-119 in the findings register.
No service, model, schema, migration, template, setting, role/permission catalog,
shared helper, Registry, Roadmap or other product module changes. Migration: **NO**.
The final [boundary verification](f111_batch_06_evidence/VERIFICATION.json)
checks entry hashes, non-target source, and all other finding entries.

## Implementation and existing form context

Both callers resolve membership from authenticated user and active organization.
Project/WBS/Activity choices begin empty; missing/invalid/wrong-tenant membership
has no tenant-wide fallback. Canonical `scope_queryset` intersects original
tenant/lifecycle querysets using Project `pk`, WBS `project_id`, Activity
`project_id`, without site-parent promotion. Unbound forms retain all authorized
children. Bound children narrow to the selected authorized Project/WBS; malformed,
unauthorized and incompatible combinations fail field validation. Parent Expense
visibility never supplies allocation-source authority. Locked tenant CBS and
CostCenter masters retain their original predicates.

An independently reproduced entry defect made all bound forms crash:
`ExpenseAllocation.clean()` dereferenced the absent Expense, and valid coding
also needed its non-editable governing budget. The authorized form/view seam now
supplies the scoped Expense and reads the existing accepted governing-budget
pointer for the selected authorized Project. Incomplete field validation returns
errors before model relation dereferences; complete inputs still run the original
model validation. The canonical transactional service independently locks,
rechecks authority/state/budget/amount and saves through the original model rules.
No financial, budget, multi-project allocation or authorization policy is changed.
[Exact baseline replay and resolution](f111_batch_06_evidence/BASELINE_FORM_CONTEXT.json).

## Automated validation and regression attribution

- [Focused](f111_batch_06_evidence/focused.txt): **12 tests + 42 subtests PASS**.
  All three choice families; qualifying A/B/C/D/X; full-response metadata;
  organization scope; site-only denial; missing/wrong membership; absent,
  revoked, expired and future scope; inactive user/member/tenant; role/capability
  denial; draft/returned rendering and submitted hiding; manipulated and malformed
  IDs; required fields; mixed Projects and same-Project wrong WBS; safe bare 400
  and refreshed GET; tenant masters; lifecycle filters; accepted-budget, structure,
  cost-center, amount and state guards; existing direct-service denials; valid
  A-parent/B-allocation, governing budget and matching audit.
- [Regression](f111_batch_06_evidence/regression.txt): **47 tests + 64 subtests
  PASS; 15 baseline failures**. Runs complete `apps/expenses/tests.py`,
  `apps/expenses/test_p4_s26_s30.py` and prior `tests/test_uiux_f111_scope.py`.
  [Exact dirty-entry replay](f111_batch_06_evidence/baseline_regression.txt)
  has the same test outcomes. All 15 failures occur in legacy
  `ExpenseServiceTests.setUp -> create_project -> _has_project_permission`:
  role-only membership lacks canonical authorization bootstrap, before the
  changed forms/views are reached. [Attribution](f111_batch_06_evidence/REGRESSION_ATTRIBUTION.json).
  **Zero new regression failures.** No repository-wide PASS claim or debt repair.
- [Django](f111_batch_06_evidence/django_check.txt),
  [Ruff](f111_batch_06_evidence/ruff.txt),
  [format](f111_batch_06_evidence/ruff_format.txt),
  [migration drift](f111_batch_06_evidence/migration_check.txt), YAML, report links,
  whitespace, source boundaries and prior-work preservation: PASS.

Initial harness corrections concerned disposable fixture currency/expense-group
prerequisites, grant start timestamps, organization-control assertions, and one
overlapping disposable-database initialization. The overlapping initialization
was stopped; final suites ran serially against the existing migrated disposable
`test_bonira_uiux_batch01` database, never the Development business database.
[Initial infrastructure collision](f111_batch_06_evidence/initial_infrastructure_collision.txt).
No failed draft/preparation attempt left business rows: canonical preparation ran
atomically. Evidence readers' inherited read-only session was explicitly changed
to writable only after Development/database guards, for authorized fixture work.

## Development fixtures and authority

[Preflight](f111_batch_06_evidence/PREFLIGHT.json) found existing draft Expenses,
WBS/Activity rows and eligible personas but **zero governing budgets**. Existing
A/B/C/D/X Projects and existing owner/approver authorities were reused. Five
explicitly synthetic qualifying coding contexts were prepared through canonical
WBS/Activity, cost-structure/CBS/CostCenter/lock, estimate/item/approve, budget
draft/classify/submit/independent-accept workflows. One dedicated synthetic
Expense A draft (`B06-RUNTIME-PARENT`, amount 60) supports isolated runtime checks.
[Exact actors, IDs and retained fixtures](f111_batch_06_evidence/FIXTURES.json).

Limited persona `uiux.persona.project-manager` has A/B Project grants;
`uiux.persona.tenant-admin` has Organization scope;
`uiux.reference.batch03.site-only` has only its existing SITE grant and
`operations_manager` role. All are nonstaff/nonsuperuser and possess the existing
view/allocate capabilities. Preparation uses existing tenant owners and independent
existing approvers; Tenant X budget acceptance uses the existing authorized admin.
No new user, role, permission, scope grant or authorization semantics.
Preparation retains 66 synthetic business/planning rows and 46 canonical audits.
Accepted budgets are synthetic non-production planning fixtures; no Expense
approval, GL posting, payment or project-cost transaction was performed.

## HTTP and browser runtime

Fresh current-checkout Development process on loopback port 8009; PostgreSQL
`construction_erp`; zero pending migrations. Real authenticated users, login,
form handling and CSRF. [Server identity and source timestamps/hashes](f111_batch_06_evidence/SERVER_IDENTITY.json),
[runtime baseline](f111_batch_06_evidence/RUNTIME_BEFORE.json).

**25 HTTP security observations PASS** across detail and allocate routes:
limited/organization GETs; C/D/X forced Project, WBS and Activity (nine otherwise
complete submissions); authorized mixed Project/WBS and Project/Activity;
four required-field controls; over-amount and wrong locked CBS-structure controls;
site-only GET and five forced A/B/C/D/X allocations. Limited invalid coding returns
bare **400 with zero body**, then a safe refreshed **200** detail with identical
authorized options. Full responses exclude forbidden UUIDs, distinct WBS/Activity
labels and distinguishable Project names. Organization scope exposes A–D and
excludes X. [HTTP observations](f111_batch_06_evidence/RUNTIME_HTTP.json),
[summary](f111_batch_06_evidence/HTTP_SUMMARY.json).

Site-only authority cannot read this project-owned Expense: detail and allocate
return **404**, before rendering any allocation selector. Live construction also
proves all three protected querysets empty for that membership. This is the
existing fail-closed parent/source contract; no artificial parent-read grant was
added. **Eight existing direct-service Project/tenant/site denials PASS** with
no mutation. [Service controls](f111_batch_06_evidence/DIRECT_SERVICE.json).

**Seven browser observations PASS**, through Chrome using Computer Use:
limited GET; actual Project/WBS mismatch and browser HTTP-400 page; refreshed
GET; actual Project/Activity mismatch and HTTP-400 screenshot; refreshed GET;
organization GET; site-only 404. Project/WBS/Activity option counts including blank
are **3/9/11** for limited and refreshed GETs and **5/17/21** for organization
scope. Exact options match authenticated HTTP observations; all existing eligible
children plus synthetic controls are retained. No site-only allocation selectors.
[Browser records](f111_batch_06_evidence/RUNTIME_BROWSER.json),
[limited](f111_batch_06_evidence/browser_limited_get.png),
[WBS rejection](f111_batch_06_evidence/browser_mixed_wbs_400.png),
[Activity rejection](f111_batch_06_evidence/browser_mixed_activity_400.png),
[refresh](f111_batch_06_evidence/browser_activity_refreshed.png),
[organization](f111_batch_06_evidence/browser_organization.png),
[site-only](f111_batch_06_evidence/browser_site_only.png).
Full-page screenshot capture timed out; viewport screenshots succeeded. Chrome
also transiently delayed navigation/frame observations on bare-400 pages; URL,
visible HTTP-400 screenshot, server response and refreshed detail establish the
result. No browser workaround changed application state or security.

One authorized real-CSRF positive submission created a **10-unit draft allocation
to B on Expense A**, exactly one corresponding success audit and no approval or
posting. [Positive control](f111_batch_06_evidence/RUNTIME_POSITIVE.json).
Demo tenant Project names can coincide; identical authorized text is not treated
as a forbidden label. Actual UUIDs, exact option sets and distinct synthetic
source labels establish cross-tenant exclusion.

## Integrity, cleanup and stop

All **519 model tables** compared before/after. Every pre-existing non-session
row is unchanged, excluding authentication `User.last_login`. Beyond separately
accounted canonical preparation, runtime adds only the one authorized Allocation,
one matching audit and session bookkeeping. **Zero unauthorized allocation,
business or success-audit mutation.** Financial/posting/payroll/stock/project-cost
tables unchanged. [Integrity](f111_batch_06_evidence/RUNTIME_INTEGRITY.json),
[before preparation](f111_batch_06_evidence/PREPARATION_BEFORE.json).
Authority fingerprint before/after:
`11d2793d4f063b9cff9fe754e53e46cd9c03d3de0ee3ab2e347920b882b86825`.
**Temporary authority: NONE; revocation not required.** Existing reference authority
and all other actors remain unchanged. An initial integrity comparison compared
serialized UUID strings to UUID objects; canonical fingerprints corrected that
harness-only comparison without changing data or expected authority.

Browser persona logged out; temporary tab closed; fresh server stopped.
[Cleanup](f111_batch_06_evidence/SERVER_CLEANUP.json).
[Final verification](f111_batch_06_evidence/VERIFICATION.json),
[evidence hashes](f111_batch_06_evidence/INDEX.json).

**BATCH-01..05 preserved; BATCH-07..09 NOT_EXECUTED; Wave C NOT_STARTED.**
No Production action, CEP-078/079 execution, Git add/commit/push/merge, new branch
or worktree, Human Sign-off, Production Certification, schema change or financial
posting. BATCH-06 closed; STOP.
