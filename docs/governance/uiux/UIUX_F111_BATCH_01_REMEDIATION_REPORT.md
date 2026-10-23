# F-111 BATCH-01 — commercial create choices

Execution date: 2026-10-22, Asia/Tehran. Finding: **UIUX-F-121 only**.
Authority: explicit Human BATCH-01 execution request and the BATCH-01 contract in
[the approved plan](UIUX_F111_PATTERN_REMEDIATION_PLAN.md).

## Baseline and Actual Execution Touch Set

Branch `main`; HEAD and local `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`. No fetch or Git write occurred.
The eight pre-existing Daily Reports, Equipment, Procurement and Workforce
forms/views changes, prior F-111 tests, UIUX evidence, Graphify output and three
untracked protected-document directories are preserved. F-111 remains resolved.

The session re-grounded current source and dirty contents before its bounded
implementation. [ENTRY.json](f111_batch_01_evidence/ENTRY.json) is the subsequent
execution capture: its Git status already includes the initial BATCH-01 Billing
edits, alongside the eight prior F-111 files. It must not be misread as a pristine
pre-mutation snapshot. Original Billing code for regression attribution and source
boundary comparison comes from the unchanged HEAD, with no checkout replacement.

Actual Execution Touch Set:

| Area | Actual files and declarations |
| --- | --- |
| Product | `apps/billing/forms.py`: create-only `_CommercialEvidenceForm._configure_create`, the three create constructors, required imports. The inherited Compliance revision constructor retains its original configuration through the create/revision distinction. |
| Product | `apps/billing/views.py`: `guarantee_create`, `compliance_evidence_create`, `retention_release_create`, required import. |
| Tests | New `tests/test_uiux_f111_pattern_commercial_scope.py`. |
| Governance | This report; `UIUX_FINDINGS_REGISTER.yaml`, F-121 entry only. |
| Evidence | New `f111_batch_01_evidence/`: source preservation capture, isolated validation runner, runtime observer, boundary verifier, sanitized results and logs. |

No product file outside the authorized set was needed. Documents, authorization
helpers, commercial mutation services, models, migrations, templates, detail
functions and revision declarations are unchanged. Retention clearance choices
(F-122 / BATCH-02) remain outside this work.

## Implementation

The create-only configuration empties protected querysets before checking trusted
actor/membership context. It preserves the existing tenant, lifecycle, ordering
and subcontract filters. Contract choices intersect canonical `scope_queryset`
with `project_lookup="project_id"`; a site grant does not promote Project authority.

Document choices use `get_organization_documents` followed by
`get_organization_document` for each candidate. This preserves every linked-context
rule and the detail reader's legacy/typed-link consistency checks. Versions are
restricted by authorized document IDs, retaining eligible historical versions.
Missing DMS permission leaves version fields empty. All three views resolve
membership from authenticated request context; GET, bound validation and redisplay
share the same constructor. Existing services remain the mutation authority.

## Automated validation

Disposable automated records are confined to `test_bonira_uiux_batch01`;
test-generated files use temporary storage. Development fixtures, grants, roles
and permission catalogues are unchanged. All 434 migrations were applied only
to the disposable test database during its initial provisioning.

| Validation | Result and evidence |
| --- | --- |
| BATCH-01 focused suite | **18/18 tests and 67 subtests PASS**; [final log](f111_batch_01_evidence/focused_final.txt), [JUnit](f111_batch_01_evidence/focused_final.xml). |
| Prior F-111 selector/HTTP/service controls | **35/35 PASS**, including Expense/Estimate and shared context controls; [regression run](f111_batch_01_evidence/validation.xml). |
| `DocumentServiceTests` | **10/10 PASS**; same regression run. |
| Required `CommercialControlTests` | **8 baseline failures** during existing fixture Project creation. |
| Additional DMS governance/processing controls | **5 baseline failures** at the same existing fixture setup boundary. |
| Current-task baseline attribution | **13/13 failure tracebacks byte-identical** with entry Billing forms/views replayed in memory from HEAD; [baseline log](f111_batch_01_evidence/baseline.txt), [comparison](f111_batch_01_evidence/REGRESSION_ATTRIBUTION.json). No attributable regression observed. |
| Django system check | PASS, zero issues; [log](f111_batch_01_evidence/django_check.txt). |
| Ruff lint / formatting | PASS for both product files, new tests and evidence scripts; [lint](f111_batch_01_evidence/ruff.txt), [format](f111_batch_01_evidence/ruff_format.txt). |
| Migration drift / configured Development currency | PASS: `makemigrations --check --dry-run` reports no changes; `migrate --check` succeeds. [Drift](f111_batch_01_evidence/migration_drift.txt), [currency](f111_batch_01_evidence/migration_currency.txt). Migration expected/created: **NO**. |
| Source boundary / preservation / whitespace | PASS; [verification](f111_batch_01_evidence/VERIFICATION.json), [whitespace](f111_batch_01_evidence/whitespace.txt). |

Focused coverage includes all three constructors and HTTP paths, both version
field names, full-response forbidden labels/IDs, authorized B and organization
choices, missing/wrong-tenant/mismatched context, absent/revoked/expired/future
grants, inactive membership/user/tenant, missing roles/DMS permission, site-only
Contract denial, mixed-link/sealed/expired/unlinked/broken-link DMS negatives,
historical versions, C/D/X manipulated POSTs, service-error and invalid redisplay,
existing direct-service Contract denials, authorized Guarantee/Compliance creation,
and unchanged revision form/detail gates.

Preliminary runs exposed two new-test issues (a nonexistent membership enum and
an assertion that called the intentionally denying active-membership resolver).
Both were corrected within the new test file; final focused evidence supersedes
those failures. The original run logs remain available. Existing regression
fixtures were not changed. The 13 baseline failures prevent those legacy tests
from exercising downstream lifecycle behavior; this report does not claim a
completely green legacy suite or independently verified Retention lifecycle
success. The old audit's 199-failure debt was not used as a waiver.

## Runtime security retest

A newly launched Development process served the current checkout on
`127.0.0.1:8003`, with `--noreload`. Settings:
`config.settings.development`; PostgreSQL database `construction_erp`; zero pending
migrations. [Process record](f111_batch_01_evidence/server_process.json) and
[cleanup](f111_batch_01_evidence/SERVER_CLEANUP.json) identify the newly created
processes; only these processes were stopped after testing.

Existing ordinary P17 Project Manager was preflighted: active membership, explicit
A/B Project grants and all four existing commercial/DMS capabilities. It was
neither staff nor superuser. No authority or persistent fixture was prepared.
Authentication and CSRF passed actual middleware. Credentials and transient
authentication material stayed in memory; no raw token-bearing HTML was saved.

[HTTP observations](f111_batch_01_evidence/RUNTIME_HTTP.json) contain **24 passing
observations**: GET, C/D/X Contract rejections, C/D/X version rejections with an
authorized Contract, and ordinary missing-required-field redisplay on **each**
route. Each negative payload was first validated with authorized selections
without saving, isolating the manipulated field.

| Route | Authorized Contract options | DMS version options | GET / negative / invalid |
| --- | --- | --- | --- |
| `/billing/guarantees/new/` | 6, A/B only | 4, A/B only | PASS |
| `/billing/compliance-evidence/new/` | 6, A/B only | 4 via `document_version` | PASS |
| `/billing/retention-releases/new/` | 2, A/B payable subcontracts | 4 via `evidence_document_version` | PASS |

Same-tenant C/D and cross-tenant X Contract/version UUIDs and distinctive Contract
numbers were absent from full responses, including invalid redisplay. Generic
document titles recur across demo Projects; they are not distinctive runtime
leak indicators. Automated fixtures use distinct titles for complete title/label
controls. The complete option sets matched the canonical DMS readers.

All manipulated POSTs returned HTTP 200 with field validation errors; none entered
a successful commercial mutation. Per-observation commercial and audit digests
are unchanged. [Before](f111_batch_01_evidence/RUNTIME_BEFORE.json) and
[after](f111_batch_01_evidence/RUNTIME_AFTER.json) compare all 519 model tables:
only `sessions.Session` changed. User `last_login` is excluded from its digest;
all business, audit, authorization, membership and source-object evidence remains
unchanged. No session contents, cookies or tokens appear in these snapshots.

Required runtime evidence is **incomplete** for two concrete reasons:

1. Existing eligible tenant documents have no mixed authorized/forbidden linked
   contexts. The canonical context preflight records this in `RUNTIME_BEFORE.json`.
   The plan forbids inventing persistent fixtures without separate bounded
   authority. Mixed-link automated tests do not substitute for the required live
   mixed-link negative.
2. The initial Guarantee browser GET showed six A/B Contract options and four DMS
   versions. Subsequent browser control returned **“Local browser use is disabled
   in Work settings”**. The required representative Guarantee interaction and
   Retention browser observation could not be completed. No setting was changed
   and no screenshot evidence is claimed. See
   [browser record](f111_batch_01_evidence/BROWSER.json).

## Finding state and safety boundary

F-121 remains **OPEN**. Its original static confirmation and evidence are retained.
It is not `RUNTIME_VERIFIED_RESOLVED`; full runtime acceptance is pending the
mixed-link negative and representative browser checks. No other finding changes.

No BATCH-02..09, Wave C, broad UI remediation, Production action, CEP-078 or
CEP-079 execution, persistent business fixture/role/permission/grant creation,
Product Decision, authorization redesign, schema change, migration application to
Development, or Git add/commit/push occurred. Disposable automated test setup uses
only existing permission/role definitions and never changes Development authority.

Implementation is recorded as `REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST`.
Required runtime coverage remains incomplete; no resolved status is issued.

**BATCH_01_IMPLEMENTED_RUNTIME_RETEST_PENDING**
