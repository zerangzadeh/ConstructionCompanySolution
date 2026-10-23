# BATCH-07 — Recurring template collection and Project authority

Date: 2026-10-22, Asia/Tehran. **UIUX-F-120 = RUNTIME_VERIFIED_RESOLVED / RESOLVED.**
Decision: **BATCH_07_RUNTIME_VERIFIED_RESOLVED**.
Authority: the Human's attached end-to-end BATCH-07 request, including minimum
synthetic Development fixtures and existing canonical authority, and the
[canonical contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-07).

## Baseline and Actual Execution Touch Set

`main`; HEAD and local `origin/main`: `43ac319c6e73e48ca9626461b73987922c498ec3`;
upstream `origin/main`; local-reference divergence 0/0; no fetch. Fourteen dirty
product files and existing untracked prior tests, UIUX evidence, Graphify and
protected documents comprise the effective dirty-entry baseline. F-120 entered
OPEN / STATIC_CONFIRMED / NOT_EXECUTED. All BATCH-01..06 source and evidence are
preserved. [Entry state, 5,249 hashes and authorized touch set](f111_batch_07_evidence/ENTRY_BASELINE.json).

Actual product mutations: `apps/expenses/forms.py:RecurringExpenseTemplateForm`
and `apps/expenses/views.py:recurrence_list`, with the necessary local import.
Added `tests/test_uiux_f111_pattern_recurrence_scope.py`, this report and
`f111_batch_07_evidence/`; updated only F-120 in the findings register.
No service, model, schema, migration, template, setting, shared helper, catalog,
Registry, Roadmap or other product module changes. Migration: **NO**.
[Final preservation and boundary checks](f111_batch_07_evidence/VERIFICATION.json)
compare existing hashes and AST outside the named seams, including BATCH-06's
allocation implementation in these same files and every other finding entry.

## Implementation

The authenticated active membership is resolved server-side in `recurrence_list`.
The form starts with an empty Project queryset and rejects missing, invalid or
wrong-tenant membership. Existing `scope_queryset` intersects the original
tenant/non-deleted Project queryset using `project_lookup="pk"`; the collection
uses `project_lookup="project_id"`. Both use project-only authority, preserving
existing ordering and predicates. No active-template or Project-deletion filter
was added to the collection. Site-parent context never authorizes project-owned
templates. Both builders are reused on invalid create and service-error renders.

The [exact entry replay](f111_batch_07_evidence/baseline_form_context.txt) also
proved existing model-clean crashes on absent/malformed Project and absent start
date. Inside the authorized recurring form, incomplete field validation now stops
before model-clean dereferences those missing values. Complete inputs still run
the existing model validation; the unchanged canonical services recheck tenant,
capability and Project authority and validate saved records. Valid reversed-date
validation still executes and redisplays safely. No new financial or scheduling
behavior, global authorization semantics, permission or role was introduced.
The existing proposal view/service is exercised only as a control. There is no
recurring-template update endpoint in this surface; create and proposal are its
mutating actions.

## Automated validation and regression attribution

- [Focused](f111_batch_07_evidence/focused.txt): **13 tests + 44 subtests PASS**.
  Qualifying A/B/C/D/X; full-response Project UUIDs/labels, template descriptions
  and proposal-action IDs; form/collection consistency; organization scope;
  site-only exclusion; absent/invalid/wrong-tenant membership; absent/revoked/
  expired/future grants; inactive user/member/tenant; missing role/capability;
  manipulated/malformed Projects; all required-field redisplays; service-error
  redisplay; direct and mixed-query proposal denials; no template/Expense/success
  audit on denial; authorized B creation, draft-only proposal and idempotency;
  recurrence date/active-window controls and unchanged lifecycle predicates.
- [Regression](f111_batch_07_evidence/regression.txt): **59 tests + 106 subtests
  PASS; 15 baseline failures**. Complete `apps/expenses/tests.py`,
  `apps/expenses/test_p4_s26_s30.py`, prior `tests/test_uiux_f111_scope.py` and
  BATCH-06 allocation suite. [Exact dirty-entry replay](f111_batch_07_evidence/baseline_regression.txt)
  has identical test outcomes using captured forms/views through an import loader;
  no working file was replaced. All 15 legacy `ExpenseServiceTests` fail in
  `setUp -> create_project -> _has_project_permission`, before the recurring seam,
  because legacy role-only fixtures lack canonical authorization bootstrap.
  [Attribution](f111_batch_07_evidence/REGRESSION_ATTRIBUTION.json): **zero new
  regression failures**. No full-repository PASS or unrelated debt repair claimed.
- [Django](f111_batch_07_evidence/django_check.txt),
  [Ruff](f111_batch_07_evidence/ruff.txt),
  [format](f111_batch_07_evidence/ruff_format.txt),
  [migration drift](f111_batch_07_evidence/migration_check.txt), YAML, report links,
  whitespace and source boundaries: PASS. Zero pending Development migrations.

Suites ran serially against existing migrated disposable PostgreSQL
`test_bonira_uiux_batch01`, with temporary document storage and test-only password
hashing. Runtime uses the Development business database. Test harness corrections,
command/outcome records and transient browser recovery are recorded in
[validation commands](f111_batch_07_evidence/VALIDATION_COMMANDS.json).

## Fixture and authority preparation

[Read-only preflight](f111_batch_07_evidence/PREFLIGHT.json) found **zero templates**.
Existing Project A/B/C/D in `demo-construction-01` and X in `demo-construction-02`
and their existing owners were reused. Five synthetic active monthly templates,
one per Project, were created atomically through `create_recurring_expense_template`.
All have valid 2026-10-22 occurrences and distinct A/B/C/D/X descriptions, so the
negative sources qualify independently of lifecycle/date validation.
[Exact retained fixtures and actors](f111_batch_07_evidence/FIXTURES.json).

Existing personas, all nonstaff/nonsuperuser with `expenses.recurrences_manage`:
`uiux.persona.project-manager` has explicit A/B Project grants;
`uiux.persona.tenant-admin` has organization scope;
`uiux.reference.batch03.site-only` has its existing A Site grant and
`operations_manager` role. **No actor, role, permission, assignment or scope grant
was created or changed.** Temporary authority: **NONE**; revocation unnecessary.
The canonical template service emits no creation audit; no alternative audit path
was invented. Existing history remains preserved. No persistent recurring Expense
was proposed, approved or posted; the canonical plan requires no successful
persistent proposal. Authorized success is proven in disposable tests.

## HTTP and browser runtime

Fresh current-checkout Development process, `localhost:8010`, PostgreSQL
`construction_erp`, zero pending migrations. [Process/source identity](f111_batch_07_evidence/SERVER_IDENTITY.json).
Authentication used real existing credentials and forms/CSRF; passwords, cookies,
CSRF tokens and raw token-bearing HTML are not retained.

[HTTP](f111_batch_07_evidence/RUNTIME_HTTP.json): **33 observations PASS** across
limited, organization and site-only actors: all three GETs; six forced C/D/X
query/filter GETs; eight otherwise complete forced Project create submissions;
six required-field controls; eight forced C/D/X or site-only A/B template proposal
POSTs with a conflicting authorized Project query; authorized B invalid-occurrence
and GET-method controls. Forbidden same-tenant proposals return **403**, X returns
**404**; invalid create returns **200 with field errors and safe redisplay**.
Authorized invalid occurrence returns **400**, proposal GET **405**.
[16 direct create/propose service denials](f111_batch_07_evidence/DIRECT_SERVICE.json)
independently preserve existing object and tenant enforcement.

[Browser](f111_batch_07_evidence/RUNTIME_BROWSER.json): **five observations PASS**:
limited GET; real form POST with end date before start and selected B retained;
forced C Project/template query GET; organization GET; site-only GET. DOM options,
visible descriptions, proposal-action URLs and screenshots independently match
HTTP results. Limited sees A/B only; organization sees A–D and excludes X; site-only
sees no protected Project option, template row or proposal action. Invalid date
redisplay retains the same scoped choices and collection.
[Limited GET](f111_batch_07_evidence/browser_limited_get.png),
[invalid POST](f111_batch_07_evidence/browser_invalid_post.png),
[C query](f111_batch_07_evidence/browser_query_get.png),
[organization](f111_batch_07_evidence/browser_organization.png),
[site-only](f111_batch_07_evidence/browser_site_only.png).

Full HTTP responses were checked for protected IDs and distinctive labels; browser
DOM checks include actual option values and proposal actions. Caller-supplied
query values echoed in the shared hidden `next` field are excluded from metadata
claims. The shared site context selector may retain its authorized A parent; the
recurring Project selector remains empty. Demo Project display names repeat across
tenants, so cross-tenant assertions use X UUID, distinct template description/action
and distinguishable labels, never an ambiguous shared display name.

## Runtime integrity and cleanup

[Before](f111_batch_07_evidence/RUNTIME_BEFORE.json),
[after](f111_batch_07_evidence/RUNTIME_AFTER.json), and
[integrity](f111_batch_07_evidence/RUNTIME_INTEGRITY.json): **519 model tables**.
All pre-existing business rows are unchanged. Preparation adds exactly five
RecurringExpenseTemplates, no Expense or audit. Runtime changes only sessions;
`User.last_login` is intentionally excluded. **Zero unauthorized template/Expense
mutations; zero runtime success-audit changes; zero financial transaction changes.**
Authority fingerprints before/after are identical. Synthetic templates are retained
for reproducible Development evidence; history was not deleted or rewritten.
[Cleanup](f111_batch_07_evidence/SERVER_CLEANUP.json): browser persona logged out,
temporary tab closed, verified own fresh process stopped, port 8010 has no listener.

## Safety and disposition

**F-120 RUNTIME_VERIFIED_RESOLVED. BATCH-01..06 preserved. BATCH-08..09
NOT_EXECUTED; Wave C NOT_STARTED.** No F-113..119 or F-121..127 reopening, broad UI
work, Production action, CEP-078/079 execution, schema change, new authorization
semantics, posting or payment. No Git add/commit/push, branch or worktree creation.
Historical static and prior remediation evidence is preserved. BATCH-07 closed; STOP.
