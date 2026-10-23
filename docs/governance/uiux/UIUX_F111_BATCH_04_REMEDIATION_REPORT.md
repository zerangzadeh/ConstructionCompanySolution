# BATCH-04 — Goods Receipt source authorization

Date: 2026-10-22, Asia/Tehran. **UIUX-F-114 = RUNTIME_VERIFIED_RESOLVED / RESOLVED.**
Decision: **BATCH_04_RUNTIME_VERIFIED_RESOLVED**.
Authority: the Human's explicit attached BATCH-04 execution request, including
minimum synthetic Development fixture preparation, and the
[canonical BATCH-04 contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-04).

## Baseline and actual execution touch set

`main`; HEAD and local `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`; divergence 0/0; no network fetch.
The effective baseline includes ten dirty product files, prior F-111 and
BATCH-01..03 implementations, untracked tests/evidence, Graphify and protected
documents. F-114 entered OPEN/STATIC_CONFIRMED. No prior finding was reopened.
[Entry grounding, pre-mutation touch set and 5,090 source/evidence hashes](f111_batch_04_evidence/ENTRY_BASELINE.json).

Product touch set: only `GoodsReceiptForm.__init__` in Procurement `forms.py`
and `goods_receipt_create` in Procurement `views.py`. Added one focused test file,
this report and `f111_batch_04_evidence/`; updated only F-114's register entry.
Runtime touch set: five new synthetic PurchaseOrders, five items, five governing
versions, five version lines, 15 canonical audit events, and authentication/session
bookkeeping. No model, schema, migration, template, service, setting, role,
permission catalogue or shared authorization helper changed.

## Implementation and automated validation

The view obtains authenticated membership server-side. The form fails closed
without a valid same-tenant membership and intersects its existing issued-order
queryset with `scope_queryset(..., project_lookup="project_id")`. No SITE-parent
promotion or new Purchase Order view permission is introduced. Existing tenant,
issued-status, non-deleted Project, related loading and order-date ordering remain.
Receipt service locking, permission, status, governing-version and audit rules
are unchanged. Prior PurchaseOrderForm/view changes are preserved.

- [Focused validation](f111_batch_04_evidence/focused.txt): **10 tests and 13 subtests PASS**.
  Covers qualifying A/B/C/D/X, all protected labels/IDs, fail-closed membership,
  inactive actors/tenant, revoked/expired/future/absent grants, capability and role
  entry gates, site-only denial, manipulated POSTs, invalid/service redisplay,
  existing direct-service denials, valid limited/organization creation and
  pinned governing version, lifecycle and success-audit controls.
- [Regression](f111_batch_04_evidence/regression.txt): **94 tests and 214 subtests PASS**;
  **15 legacy failures**, reproduced with identical failure attributes and
  tracebacks by loading the captured dirty-entry Procurement forms **and** views
  in memory. No checkout replacement occurred.
  [Exact replay](f111_batch_04_evidence/baseline_regression.txt),
  [attribution](f111_batch_04_evidence/REGRESSION_ATTRIBUTION.json).
  These fail in legacy Purchase Request authorization/setup or panel entry;
  zero attributable regression. Their blocked downstream behavior is not claimed
  verified. Coverage includes Procurement model/service/panel, source-to-pay,
  CEP-034 receipt-contract controls and prior F-111/BATCH-01..03 focused suites.
- Django system check, Ruff lint/format, migration drift and currency,
  whitespace, YAML, links and bounded-source preservation: **PASS**.
  Migration impact: **NO**; Development pending migrations: **0**.

Final tests used `test_bonira_uiux_batch01` and temporary protected-file storage
outside the checkout. Initial fresh `test_bonira_uiux_batch04` schema preparation
was stopped before a test result because it remained CPU-bound; the partial
disposable database was retained. No Development or Production migration ran.
The verifier uses existing system Python/PyYAML; no dependency was installed.

## Canonical Development preparation

The existing demo A/B/C/D/X orders were completed and did not qualify. Five
synthetic `B04-RUNTIME-PO-A/B/C/D/X` orders were created through
`create_purchase_order` → `add_purchase_order_item` → `issue_purchase_order`,
using each tenant's existing owner, Project, supplier and Material. All are issued
with governing versions; no completed order was edited or reopened. The sources
remain as explicitly labeled Development fixtures with their audit/version history.
[Exact IDs, actors, sources and before/after authority](f111_batch_04_evidence/FIXTURES.json).

The existing limited `uiux.persona.project-manager` has exactly A/B Project grants;
`uiux.persona.tenant-admin` has Organization scope. Existing persistent reference
`uiux.reference.batch03.site-only` already has `goods_receipts.create` through
`operations_manager` and exactly one SITE grant, with no Project/Organization
grant. All runtime actors are nonstaff/nonsuperuser. No new actor, role, permission
or authority assignment was needed. Authority fingerprints are identical before
and after; **temporary authorization cleanup: not required**.

## HTTP and browser retest

Fresh current-checkout Development process, `--noreload`, loopback port 8007,
PostgreSQL `construction_erp`; actual authenticated login, CSRF and form handling.
[Server identity](f111_batch_04_evidence/SERVER.json).

**13/13 HTTP observations PASS**: limited GET exposes A/B; forced issued C/D/X
IDs are rejected with only the source field invalid; authorized B with a missing
required field redisplays safely. Organization GET exposes A–D and excludes X.
SITE-only GET exposes only the blank option; forced A/B/C/D/X and missing-field
redisplay remain empty. Complete responses exclude forbidden UUIDs, order numbers
and actual model labels. Eight corresponding direct service calls deny scope,
tenant or SITE-only authority. Existing Purchase Order create remains scoped as
a narrow known-good control. No persistent successful receipt was needed.
[HTTP details](f111_batch_04_evidence/RUNTIME_HTTP.json).

**Four browser observations PASS**, through the available Chrome extension:
limited GET, actual server-side duplicate-receipt service-error redisplay,
SITE-only GET and Organization GET. Source option counts including blank are
3, 3, 1 and 5. Native missing-required-field validation was also observed before
the server-error control. No forbidden source can be selected in the browser.
[Browser records](f111_batch_04_evidence/RUNTIME_BROWSER.json),
[limited GET](f111_batch_04_evidence/browser_limited_get.png),
[safe redisplay](f111_batch_04_evidence/browser_limited_redisplay.png),
[SITE-only](f111_batch_04_evidence/browser_site_only.png),
[Organization control](f111_batch_04_evidence/browser_organization.png).

## Integrity, evidence and safety

All **519 model tables** compared. Every pre-existing non-session row remains
identical, excluding User `last_login` from its digest. The only preparation
additions are the exact fixture/version rows and 15 canonical audits above.
After preparation, only session bookkeeping changes. **Zero Goods Receipts,
unauthorized business mutations or success audits; authority unchanged**.
[Before](f111_batch_04_evidence/PREPARATION_BEFORE.json),
[runtime integrity and fingerprints](f111_batch_04_evidence/RUNTIME_INTEGRITY.json).

Harness corrections covered a non-`id` model primary key before fixture writes,
the existing Procurement error CSS selector, session bookkeeping during concurrent
browser authentication, read-write transactions for locked direct-service denial
checks, and UUID JSON normalization. No product workaround or weakened assertion
was introduced; final full HTTP evidence passed after these corrections.

The fresh server was stopped and the temporary browser tab closed.
[Server cleanup](f111_batch_04_evidence/SERVER_CLEANUP.json).
All prior BATCH-01..03 product code, finding entries and evidence are preserved;
AST comparison proves only the two authorized product functions changed.
[Final verification](f111_batch_04_evidence/VERIFICATION.json),
[artifact hashes](f111_batch_04_evidence/INDEX.json).

**BATCH-05..09 NOT_EXECUTED; Wave C NOT_STARTED.** No Production action,
CEP-078/079 execution, Git add/commit/push, financial posting, Human Sign-off,
Production Certification or cutover. BATCH-04 is closed; STOP.
