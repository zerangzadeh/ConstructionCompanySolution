# F-111 BATCH-02 — Retention Release clearance source only

Date: 2026-10-22, Asia/Tehran. Decision:
**BATCH_02_IMPLEMENTED_RUNTIME_RETEST_PENDING**.

## Baseline and authority

The Human authorized BATCH-02 / UIUX-F-122 only under the
[canonical contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md). Branch `main`, HEAD
and local upstream `origin/main` are
`43ac319c6e73e48ca9626461b73987922c498ec3`, divergence 0/0; no fetch occurred.
Ten modified product files and existing untracked tests, UIUX evidence, Graphify
and generated-document artifacts were present at entry. The dirty Billing source
already contains accepted BATCH-01 work. Its exact contents, full dirty state,
contract/source hashes and 8,805 existing file hashes were captured before product
mutation in [ENTRY.json](f111_batch_02_evidence/ENTRY.json).

BATCH-01/F-121 remains `RUNTIME_VERIFIED_RESOLVED`. Its product behavior, finding
entry and all prior evidence are preserved. No other batch is authorized here.

## Actual Execution Touch Set

- `apps/billing/forms.py`: `RetentionReleaseForm.__init__` clearance queryset and
  one import of the existing canonical reader.
- `tests/test_uiux_f111_pattern_clearance_scope.py`: new disposable automated
  fixtures and 12 focused tests.
- This report; new `f111_batch_02_evidence/` scripts, observations, logs and index.
- `UIUX_FINDINGS_REGISTER.yaml`: UIUX-F-122 entry only.

The contract permits `retention_release_create` wiring if needed; accepted
BATCH-01 already supplies trusted actor/membership, so **views were not edited**.
Models, migrations, templates, settings, shared helpers, other forms, correction
paths and `commercial_services.py` are unchanged. Migration expected/actual: **NO**.

## Implementation

Clearance choices start empty. Missing, wrong-tenant or mismatched actor/membership
context returns empty. Valid context calls `get_compliance_evidence`, retaining
the existing `clearance` kind and `approved` status predicates; `PermissionDenied`
leaves the field empty. GET, bound validation and redisplay share this constructor.

The canonical reader still requires organization-scoped
`compliance_evidence.view`. Project A/B create/view grants do not permit clearance
enumeration. An organization actor lacking view permission receives no choices.
No Contract cascade or broader visibility was introduced. The existing writer
checks project create authority, terms and clearance validity; it does **not**
enforce this standalone enumeration gate. A disposable direct-service success
explicitly preserves that distinction. No new service protection is claimed.

## Automated validation and regression

| Check | Result |
| --- | --- |
| [Focused suite](f111_batch_02_evidence/focused_final.txt) | **12 tests + 32 subtests PASS** |
| Same-tenant / cross-tenant matrix | Limited A/B actor cannot select any A/B/C/D/X clearance; complete GET/POST responses exclude qualifying forbidden UUIDs, labels and references |
| Manipulated POST | Only `clearance_evidence` fails for otherwise-valid payloads; no release, evidence change or success audit |
| Positive control | Organization/view actor sees approved tenant clearances; draft, insurance and X excluded; authorized B HTTP creation succeeds with approved terms and actual retained capacity |
| Context controls | Missing/wrong/mismatched context, absent/revoked/expired/future/site-only scope, inactive user/membership/tenant, missing create/view authority fail closed as applicable |
| Redisplay | Missing amount and actual service rejection preserve empty limited clearance options; service rejection uses the view's existing message mechanism |
| Domain regression | Existing term approval/effectivity, explicit release authority/cap, amount capacity, matching Contract, clearance effective/expiry date, kind and approval checks retained |
| [Affected regression](f111_batch_02_evidence/regression.txt) | **53 tests + 131 subtests PASS; 8 existing Billing fixture failures** |
| [Baseline replay](f111_batch_02_evidence/REGRESSION_ATTRIBUTION.json) | All eight failure records byte-identical with exact dirty-entry forms replayed in memory; failure is `CommercialControlTests.setUp -> create_project` permission denial, before the changed form/service is reached; zero attributable regressions |
| Django check | PASS |
| Ruff lint / format | PASS for touched product/test and evidence scripts |
| Migration drift / runtime currency | PASS; no model changes detected; zero pending Development migrations |
| Whitespace / preservation | PASS; see [verification](f111_batch_02_evidence/VERIFICATION.json) |

Regression ran unchanged BATCH-01 commercial-create tests, original F-111 scope
controls and all eight required `CommercialControlTests`. This is affected-boundary
validation, not a full repository regression PASS. The eight legacy tests remain
baseline test debt; the new valid-fixture service tests supply direct term/date
and positive-release coverage without modifying legacy tests or authority.

Tests use PostgreSQL test databases and temporary document storage. The first
fresh-DB setup was stopped after successful acceptance on the existing disposable,
schema-current `test_bonira_uiux_batch01` database; its own partial test DB was
removed. See [initial-run disposition](f111_batch_02_evidence/INITIAL_RUN_DISPOSITION.json).
Earlier focused attempts exposed missing fixture revision evidence and test-harness
assumptions about draft approval metadata and message-based service errors. Those
logs/XML are retained; the final passing run governs acceptance. No product change
was made in response to those test-fixture errors.

## Runtime retest — partial; closure pending

A fresh process served the actual checkout at `127.0.0.1:8004`, `--noreload`,
`config.settings.development`, local PostgreSQL `construction_erp`, zero pending
migrations. [Server identity](f111_batch_02_evidence/SERVER.json) and
[read-only preflight](f111_batch_02_evidence/RUNTIME_BEFORE.json) are retained.

Existing P-17 `uiux.persona.project-manager` is active, nonstaff/nonsuperuser, with
explicit A/B Project grants, release-create and evidence-view capabilities, and
canonical reader denial. Existing `uiux.persona.tenant-admin` is likewise ordinary
and active, with organization scope, both capabilities and canonical reader access.
No role, permission, grant, identity or persistent fixture was changed.

**Development contains zero ContractComplianceEvidence records in all tenants.**
Thus there is no qualifying approved clearance for an organization/view positive
GET or source-backed same-/cross-tenant negative POST. Empty lists do not establish
those controls. They remain **PENDING_NO_QUALIFYING_SOURCES**; fixture preparation
was not authorized and was not performed.

[Four live HTTP observations](f111_batch_02_evidence/RUNTIME_HTTP.json) passed
actual authentication and CSRF: limited GET, missing-amount redisplay, supplemental
nonexistent UUID rejection, and organization/view GET. All returned HTTP 200 with
only the blank clearance option, and no business/audit/authority delta. The base
negative payload was validated without saving before manipulation. The nonexistent
UUID rejection is **not** a same-tenant or cross-tenant security proof; the empty
organization GET is **not** the required source-positive result.

The retained in-app browser session's
[account-summary identity](f111_batch_02_evidence/BROWSER_ACTOR.json) confirms P-17.
Its actual retention-create selector was opened and every option inspected:
[sanitized DOM options](f111_batch_02_evidence/BROWSER_OPTIONS.json),
[accessibility tree](f111_batch_02_evidence/browser_clearance_accessibility.txt),
[screenshot](f111_batch_02_evidence/browser_clearance.png). Only the blank option
exists. No browser business form was submitted; the temporary tab was closed.
This available observation does not substitute for missing qualifying sources.

[Runtime integrity](f111_batch_02_evidence/RUNTIME_INTEGRITY.json) compares all
519 model tables: only session bookkeeping changed, with User `last_login`
excluded from its digest. Business, audit, memberships, grants and catalogues are
unchanged. [Cleanup](f111_batch_02_evidence/SERVER_CLEANUP.json) stopped only the
newly created server; no listener remains on port 8004.

## Governance and safety boundary

UIUX-F-122 remains **OPEN**, implementation/runtime status
`REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST`. Its original `STATIC_CONFIRMED`
status and historical evidence are retained. Closure requires the canonical
runtime positive and same-/cross-tenant negatives using qualifying existing or
separately authorized sources; no runtime-resolved status is issued.

BATCH-03..09: **NOT_EXECUTED**. Wave C: **NOT_STARTED**. No Production,
CEP-078/079, persistent role/permission/grant or Product Decision creation,
persistent business fixture or financial action, schema/migration change, commercial authorization
change, unrelated product edit, Git add/commit/push or other Git write occurred.
The Registry, Roadmap, canonical plan and all other finding entries are unchanged.

[Evidence index](f111_batch_02_evidence/INDEX.json). STOP after this bounded closeout.
