# F-111 BATCH-03 — payable Contract and ContractItem source choices

Execution date: 2026-10-22, Asia/Tehran. Findings: **UIUX-F-123 and UIUX-F-124 only**.
Decision: **BATCH_03_IMPLEMENTED_RUNTIME_RETEST_PENDING**. Both findings remain
**OPEN** / **REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST**. Neither receives
runtime-resolved status: the required live site-only actor control cannot be run
with existing authority fixtures.

Authority: the Human's explicit BATCH-03-only request and
[canonical BATCH-03 contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-03),
including its common automated/runtime acceptance and fixture-preparation boundary.

## Grounding and bounded implementation

Branch `main`; HEAD and local upstream `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`; divergence 0/0, no fetch or Git write.
The ten existing dirty product files, BATCH-01/02 implementations and evidence,
prior F-111 tests/evidence, Graphify artifacts and protected documents were
captured before product mutation. [Entry and 8,902 file hashes](f111_batch_03_evidence/ENTRY.json).
The initial entry capture's intended report path retained a copied `BATCH_02`
filename; the actual report is this new BATCH-03 file. No existing report changed.
The entry capture remains intact; its generator now refuses to overwrite it.

Actual execution touch set:

| Area | Bounded changes |
| --- | --- |
| Product forms | `apps/billing/forms.py`: `PayableMeasurementForm` and `PayableCertificateForm` only. |
| Product views | `apps/billing/views.py`: `payable_measurement_create` and `payable_certificate_create` only. |
| Tests | New `tests/test_uiux_f111_pattern_payable_scope.py`. |
| Governance | F-123/F-124 entries only in `UIUX_FINDINGS_REGISTER.yaml`; this new report. |
| Evidence | New `f111_batch_03_evidence/`, including [index](f111_batch_03_evidence/INDEX.json). |

Each form empties its protected queryset before validating trusted membership and
tenant context. Existing canonical `scope_queryset` applies Project authority to
`ContractItem.contract__project_id` or `Contract.project_id`, with no site-parent
promotion. Existing tenant, payable, subcontract, active, non-deleted-parent and
ordering predicates remain intact. Both views resolve membership from the
authenticated user and active organization, sharing the constructor across GET,
bound validation, invalid redisplay and existing service-error redisplay.

No shared helper, reader gate, payable service, model, template, permission,
business rule, term/calculation/approval policy or schema change was required.
Migration expected/created/executed against Development: **NO**.

## Automated checks and regression attribution

Runtime: Python 3.11 at the established host installation, repository `.venv`
packages via `PYTHONPATH`, `config.settings.development`. Automated fixtures use
the existing disposable `test_bonira_uiux_batch01` PostgreSQL database and temporary
document storage outside the checkout. No persistent Development fixture or
authority preparation occurred.

| Required check | Result |
| --- | --- |
| BATCH-03 focused suite | **13 tests and 42 subtests PASS**; [log](f111_batch_03_evidence/focused.txt), [JUnit](f111_batch_03_evidence/focused.xml). |
| BATCH-01, BATCH-02 and prior F-111 regression | **65 tests and 163 subtests PASS**; includes Expense/Estimate/shared-scope controls. [Regression log](f111_batch_03_evidence/regression.txt), [JUnit](f111_batch_03_evidence/regression.xml). |
| Entire `apps/billing/test_payable_certificates.py` | **11 baseline failures** at legacy Project creation in setup, before changed forms/views. |
| Current-task entry-source replay | **11/11 failure attributes and tracebacks identical**, with captured dirty-entry Billing forms loaded in memory. [Replay log](f111_batch_03_evidence/baseline.txt), [JUnit](f111_batch_03_evidence/baseline.xml), [attribution](f111_batch_03_evidence/REGRESSION_ATTRIBUTION.json). Zero attributable regression observed. |
| Django system check | PASS, zero issues; [log](f111_batch_03_evidence/django_check.txt). |
| Ruff lint and format | PASS, both touched product files, new tests and all new Python evidence scripts; [lint](f111_batch_03_evidence/ruff.txt), [format](f111_batch_03_evidence/ruff_format.txt). |
| Migration drift / Development currency | PASS, no model changes and no pending migrations; [drift](f111_batch_03_evidence/migration_drift.txt), [currency](f111_batch_03_evidence/migration_currency.txt), [exit codes](f111_batch_03_evidence/checks.json). |
| Source bounds, preservation, YAML, report links and whitespace | PASS; [verification](f111_batch_03_evidence/VERIFICATION.json), [Git whitespace](f111_batch_03_evidence/whitespace.txt). |

The focused matrix covers both constructors/routes independently: qualifying A/B
visibility and authorized B submission; C/D/X UUID/label/number/title exclusion in
complete responses; same/cross-tenant manipulated POSTs with only the source field
invalid and unchanged record/audit counts; missing/invalid/wrong-tenant membership;
absent/revoked/expired/future scope; inactive user/member/tenant; role/capability
entry denials; site-only source exclusion and POST/service denial; missing-field
and service-error redisplay; organization-scope visibility/success; existing direct
service tenant/object/capability denials; limited-actor measurement/certificate
success; preserved organization-gated list reader; existing quantity, term,
cutoff, period-overlap and currency behavior. Successful business writes occur
only in disposable tests. No approval, posting or certification expansion occurs.

The first focused attempt had two cross-tenant service-test harness failures:
the foreign disposable member had no qualifying scope. An explicit foreign
test-database organization grant corrected that fixture; the final suite passes.
Historical [failed attempt](f111_batch_03_evidence/focused_harness_failure.txt)
is retained. Ruff initially identified loop-closure bindings in the new runtime
harness; explicit argument binding corrected them without changing its synchronous
observations. Existing product/tests were not changed to accommodate legacy debt.
The blocked legacy payable tests do not independently verify downstream lifecycle
or concurrency behavior; their failures are not represented as a green suite.
Field Observation paths have no dependency on these two Billing constructors and
are not a newly exercised regression surface.

## Runtime security retest

A fresh checkout process served `127.0.0.1:8005`, `--noreload`,
`config.settings.development`, loopback PostgreSQL `construction_erp`, zero pending
migrations. [Process](f111_batch_03_evidence/SERVER.json),
[read-only preflight](f111_batch_03_evidence/RUNTIME_BEFORE.json).

Existing ordinary P-17 (`uiux.persona.project-manager`) has active membership,
both required capabilities, explicit Project A/B grants and no C/D or organization
grant. It is neither staff nor superuser. The existing ordinary organization-scope
tenant-admin is a positive control. All A/B/C/D/X Contract and ContractItem sources
are real existing eligible active payable subcontracts, with non-deleted parents
and matching tenant relationships. No grants, roles, permissions or fixtures were
created to manufacture a runtime result.

| Finding / route | Available live results |
| --- | --- |
| F-123 `/billing/payable-measurements/new/` | P-17 GET shows four A/B items; C/D/X items absent. Each forced C/D/X POST fails only source selection; missing-date redisplay stays scoped. Organization actor sees eligible tenant items and excludes X. Browser popup opened and all five options including blank inspected. |
| F-124 `/billing/payable-certificates/new/` | P-17 GET shows the two A/B payable Contracts; C/D/X absent. Each forced C/D/X POST fails only source selection; missing-period-start redisplay stays scoped. Organization actor sees eligible tenant Contracts and excludes X. Browser popup opened and all three options including blank inspected. |

All **12 available HTTP observations PASS** using actual login and CSRF middleware.
Each negative starts from a form-valid authorized B payload, then changes only
the protected source. These checks validate the source boundary, without creating
a certificate or measurement or claiming a full payable approval workflow.
[HTTP evidence](f111_batch_03_evidence/RUNTIME_HTTP.json),
[runtime harness](f111_batch_03_evidence/runtime_retest.py).

Complete responses were scanned for forbidden source UUIDs, actual model labels
and Contract numbers. Repeated demo titles/descriptions are identified as generic
and are not misrepresented as project-distinctive negatives; exhaustive automated
controls use distinctive labels, titles and descriptions. No rate/amount
disclosure is claimed for the default ContractItem model label.

The retained in-app browser identity was checked through its visible account
summary. An initial unscoped text locator also matched a hidden responsive header;
the account-summary-scoped locator confirmed P-17. Both popup option sets match
their live HTTP GET sets. A first Chrome tab had a different retained account and
no active membership; it was not used as payable-visibility evidence and its
session was not altered. All created tabs were closed.
[Browser observations](f111_batch_03_evidence/BROWSER.json),
[measurement screenshot](f111_batch_03_evidence/browser_measurement.png),
[certificate screenshot](f111_batch_03_evidence/browser_certificate.png).

**Required live site-only negative: PENDING independently for F-123 and F-124.**
Read-only enumeration of active memberships with active users across Development
tenants found **zero currently effective site-only memberships**. The target
tenant likewise has no qualifying existing site-only actor. The plan's common
runtime contract forbids inventing a persistent grant/role/fixture without its
own bounded authority. This task grants no such preparation authority. Automated
site-only negatives pass, but do not substitute for this requested runtime control.
Neither finding can receive `RUNTIME_VERIFIED_RESOLVED` in this execution.

Across all 519 model tables, only session bookkeeping changed; User `last_login`
is excluded from the identity digest. Every business, payable source, audit,
membership and authority digest is unchanged, including all previously retained
BATCH-01/02 fixtures. Per-request comparisons also have zero model deltas.
**No unauthorized or authorized runtime payable business mutation occurred.**
[After snapshot](f111_batch_03_evidence/RUNTIME_AFTER.json),
[integrity](f111_batch_03_evidence/RUNTIME_INTEGRITY.json).

## Governance, cleanup and stop

F-123 and F-124 alone receive implementation/pending-runtime metadata; their
original static confirmation, problem, source trace and historical recommendation
remain. All other finding entries, including resolved F-121/F-122, are preserved.
Byte-level comparison outside the four allowed product declarations preserves
all earlier Billing changes; file hashes preserve all other pre-existing code,
tests, evidence, protected documents and Graphify artifacts.

Only the newly launched server was stopped; no port 8005 listener remains.
[Cleanup](f111_batch_03_evidence/SERVER_CLEANUP.json).
No Git add/commit/push, Production, CEP-078/079, BATCH-04..09, Wave C, schema change,
permission catalogue change, financial posting or business-rule change occurred.
BATCH-04..09 = **NOT_EXECUTED**; Wave C = **NOT_STARTED**.
Human Sign-off, Production Certification and Production Cutover = **NOT EXECUTED**.

**BATCH_03_IMPLEMENTED_RUNTIME_RETEST_PENDING — STOP.**
