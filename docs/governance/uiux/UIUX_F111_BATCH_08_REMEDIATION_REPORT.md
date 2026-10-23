# BATCH-08 — Project-owned selectors

Date: 2026-10-22, Asia/Tehran. **UIUX-F-113, F-116, F-117 and F-125 =
RUNTIME_VERIFIED_RESOLVED / RESOLVED.** Decision:
**BATCH_08_RUNTIME_VERIFIED_RESOLVED**.
Authority: the Human's attached end-to-end request, including minimum synthetic
Development fixtures and existing canonical authority if needed, and the
[BATCH-08 contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-08).

## Baseline and Actual Execution Touch Set

`main`; HEAD and local `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`; upstream `origin/main`;
local-reference divergence 0/0; no fetch. Fourteen dirty product files and existing
untracked tests, UIUX evidence, Graphify and protected documents are the effective
entry baseline. All four findings entered OPEN / STATIC_CONFIRMED / NOT_EXECUTED.
BATCH-01..07 source/evidence remains preserved.
[Entry state, 5,484 hashes and exact intended touch set](f111_batch_08_evidence/ENTRY_BASELINE.json).

Actual product changes, with necessary local imports only:

| Finding | Form constructor | View form construction |
| --- | --- | --- |
| F-113 | `apps/procurement/forms.py:PurchaseRequestForm` | `apps/procurement/views.py:purchase_request_create` |
| F-116 | `apps/contracts/forms.py:ContractForm` | `apps/contracts/views.py:contract_create` |
| F-117 | `apps/inventory/forms.py:WarehouseForm` | `apps/inventory/views.py:warehouse_create` |
| F-125 | `apps/workforce/forms.py:TrainingRequirementForm` | `apps/workforce/views.py:workforce_training_requirement_create` |

Added `tests/test_uiux_f111_pattern_project_scope.py`, this report and
`f111_batch_08_evidence/`; changed only the four named findings in the register.
No model, migration, schema, service, shared helper, template, setting, catalog,
generic Workforce form, `_foundation_form`, Registry or Roadmap change.
Migration: **NO**. [Final preservation/boundary checks](f111_batch_08_evidence/VERIFICATION.json)
compare all entry hashes, every other finding block byte-for-byte, and source AST
outside the four constructors, four form assignments and necessary imports.
This includes accepted prior Procurement, Inventory and Workforce changes in
the same files. Graph navigation was read-only; current source governed the patch.

## Implementation and preserved domain behavior

Each view resolves the active membership server-side with `get_active_membership`.
Each local constructor retains its initially empty Project queryset unless a valid
same-tenant membership is supplied, then intersects the original tenant/non-deleted
query with existing `scope_queryset(project_lookup="pk")`. Its existing
`include_site_parent=False` default is preserved. No global authorization semantics
changed. Existing ordering, master-data predicates, form fields and service rules
remain unchanged. The constructor handles GET, validation and error redisplay.

- **F-113:** required Project choices reflect effective Project grants. Existing
  Purchase Request create permission, service authorization and validation remain.
- **F-116:** required Project choices are scoped; tenant BusinessParty choices,
  number normalization, Jalali dates, status/date checks and service rules remain.
  Negative Contract value remains a service validation, verified through real
  HTTP-form handling in disposable tests.
- **F-117:** optional Project and the central-warehouse blank option remain.
  A limited actor's blank submission still fails the existing service gate;
  organization authority can still create a no-project warehouse.
- **F-125:** optional Project is scoped before downstream validation. Competency
  and Position remain tenant masters. The stricter organization-level Training
  service gate and related-record tenant checks are unchanged. A limited A/B actor
  may select B but still receives the canonical service denial. No requirement
  was created in persistent Development; SP-031 remains untouched.

## Automated validation and regression attribution

[Focused](f111_batch_08_evidence/focused.txt): **86 tests + 106 subtests PASS**,
with independent concrete suites for all four constructors/routes. Coverage:
authorized A/B; C/D/X UUIDs and distinctive labels excluded from full responses;
bound B retention; site-only exclusion; missing/invalid/wrong-tenant membership;
absent/revoked/expired/future grants; inactive member/user/tenant; missing
role/capability entry denial; required-field and malformed/forced Project POSTs;
safe service-error redisplay; no denied business mutation or success audit;
direct service denials; actual authorized creation; organization-scope success;
optional blank-domain behavior; unchanged lifecycle/order/master predicates;
Contract validation and Training downstream tenant checks.

[Regression](f111_batch_08_evidence/regression.txt): **83 tests + 129 subtests
PASS; 22 baseline failures**. Ran complete `apps/procurement/tests.py`,
`apps/contracts/tests.py`, `apps/inventory/tests.py`, Workforce foundation controls,
original F-111 suite and BATCH-04 receipt/BATCH-05 stock suites. The
[exact dirty-entry replay](f111_batch_08_evidence/baseline_regression.txt) executes
the captured eight form/view files through an import loader without replacing
working files. [Per-test attribution](f111_batch_08_evidence/REGRESSION_ATTRIBUTION.json)
proves identical outcomes and failure messages: nine legacy Procurement controls
fail `create_purchase_request` authorization in fixture preparation; thirteen
ContractServiceTests fail `setUp -> create_project` authorization. These occur
before the affected forms/views. **Zero new regression failures.** No full-suite
PASS or repair of unrelated debt is claimed.

[Django](f111_batch_08_evidence/django_check.txt),
[Ruff lint](f111_batch_08_evidence/ruff.txt),
[new-test formatting](f111_batch_08_evidence/ruff_format.txt),
[migration drift](f111_batch_08_evidence/migration_check.txt), YAML, links,
whitespace and boundary checks: PASS. Development has zero pending migrations.
Tests ran serially against migrated disposable PostgreSQL
`test_bonira_uiux_batch01`, temporary document storage and test-only password
hashing. No whole-file formatting of existing product files occurred.
[Commands and harness corrections](f111_batch_08_evidence/VALIDATION_COMMANDS.json).

## Runtime preparation and authority

[Read-only preflight](f111_batch_08_evidence/PREFLIGHT.json) found qualifying
non-deleted A/B/C/D in `demo-construction-01`, X in `demo-construction-02`, and
all required existing capabilities on three nonstaff/nonsuperuser actors:

- `uiux.persona.project-manager`: explicit A/B Project grants only.
- `uiux.persona.tenant-admin`: organization scope.
- `uiux.reference.batch03.site-only`: existing operations-manager role and A Site
  grant only; no parent Project grant.

[Reused fixtures](f111_batch_08_evidence/FIXTURES.json): **no actor, fixture, role,
permission, assignment or scope grant created or changed**. Existing authorized B
Purchase Request number and Warehouse code supplied non-mutating duplicate browser
controls. Temporary authority: **NONE**; revocation unnecessary. No canonical flow
or security/business control was bypassed.

## Independent HTTP and browser runtime evidence

Fresh Development processes on `localhost:8011`, PostgreSQL `construction_erp`,
zero pending migrations. [Initial browser-process identity](f111_batch_08_evidence/initial_SERVER_IDENTITY.json)
and [fresh HTTP-process identity](f111_batch_08_evidence/SERVER_IDENTITY.json)
prove the same checkout, HEAD and product hashes. The user continuation interrupted
the original process and unfinished validation commands; the complete HTTP and
baseline suites were rerun. Partial runs remain labeled as such. Browser evidence
comes from the initial fresh process with identical product bytes. Authentication
used existing credentials and actual forms/CSRF. No password, cookie, CSRF token
or raw token-bearing HTML is retained.

[HTTP](f111_batch_08_evidence/RUNTIME_HTTP.json): **88 observations PASS**, **22
per finding**. Every route has limited, organization and site-only GETs and invalid
required-field redisplays. Each limited route rejects complete forced C/D/X POSTs;
each site-only route rejects complete A/B/C/D/X POSTs. Forced query parameters also
leave choices unchanged. All return 200 with safe form errors, no unauthorized
business write and no success audit. Required Project omissions remain invalid;
blank optional Warehouse and Training submissions retain existing service denial.
Authorized B Training denial is independently observed.
[Direct services](f111_batch_08_evidence/DIRECT_SERVICE.json): **32 denials PASS**,
eight per finding, with unchanged business/audit fingerprints.

| Finding | Own HTTP | Own browser observations | Final status |
| --- | --- | --- | --- |
| F-113 | 22 PASS | GET, duplicate server POST, C query, organization/site-only GET; extra client-only date rejection | RUNTIME_VERIFIED_RESOLVED |
| F-116 | 22 PASS | Independent limited Contract GET | RUNTIME_VERIFIED_RESOLVED |
| F-117 | 22 PASS | GET, duplicate and blank-central denial server POSTs, organization/site-only GET | RUNTIME_VERIFIED_RESOLVED |
| F-125 | 22 PASS | Independent GET and B stricter-service denial POST | RUNTIME_VERIFIED_RESOLVED |

[Browser ledger](f111_batch_08_evidence/RUNTIME_BROWSER.json): **14 observations**
with DOM option values/labels/required flags and screenshots compared independently
to each finding's HTTP GET. Four are real server POST rejections. One additional
invalid Jalali date was blocked client-side and is explicitly not counted as a
server POST. The contract requires Purchase Request/Warehouse as representative
browser variants; the additional Contract/Training observations do not substitute
for their complete own HTTP matrices.
[Required GET](f111_batch_08_evidence/browser_request_get.png),
[required server rejection](f111_batch_08_evidence/browser_request_duplicate_post.png),
[optional GET](f111_batch_08_evidence/browser_warehouse_get.png),
[blank central denial](f111_batch_08_evidence/browser_warehouse_blank_post.png),
[site-only](f111_batch_08_evidence/browser_warehouse_site_only.png),
[Contract](f111_batch_08_evidence/browser_contract_get.png),
[Training denial](f111_batch_08_evidence/browser_training_denied_post.png).

All protected selectors show A/B for the limited actor, A–D for organization
authority, and no nonblank Projects for site-only authority. C/D same-tenant and X
cross-tenant negatives pass independently for every finding. Full-response scans
exclude protected IDs and distinguishable labels. X and A share a demo display
name, so X UUID establishes the runtime tenant negative; disposable tests use
distinctive labels. Existing site navigation may show A parent context, while the
project-owned field stays empty. Caller-supplied query echoes in navigation/hidden
`next` are distinguished from fetched protected metadata.

## Integrity, cleanup and safety

[Before](f111_batch_08_evidence/RUNTIME_BEFORE.json),
[after](f111_batch_08_evidence/RUNTIME_AFTER.json) and
[integrity](f111_batch_08_evidence/RUNTIME_INTEGRITY.json): **519 model tables**;
all pre-existing business rows preserved; runtime changes only sessions, with
authentication `User.last_login` excluded explicitly. **Zero unauthorized business
mutations, zero success-audit changes, zero financial changes.** Full authority
fingerprints match. Zero TrainingRequirements remain. Audit/history is preserved.
[Cleanup](f111_batch_08_evidence/SERVER_CLEANUP.json) records verified own server
termination and no remaining port listener; browser actors were logged out.
No temporary authority exists or requires revocation.

Only the four finding entries advance to resolved. **BATCH-01..07 preserved;
BATCH-09 NOT_EXECUTED and unchanged; Wave C NOT_STARTED.** SP-031 untouched.
No unrelated remediation, shared authorization change, new permission/role,
schema/domain redesign, production action, CEP-078/079 execution, posting,
payment, Human Sign-off or Production Certification. No Git add/commit/push,
branch or worktree creation. BATCH-08 complete; STOP.
