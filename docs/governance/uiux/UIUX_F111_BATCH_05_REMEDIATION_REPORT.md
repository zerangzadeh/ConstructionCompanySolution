# BATCH-05 — Inventory movement source authorization

Date: 2026-10-22, Asia/Tehran. **UIUX-F-118 = RUNTIME_VERIFIED_RESOLVED / RESOLVED.**
Decision: **BATCH_05_RUNTIME_VERIFIED_RESOLVED**.
Authority: the Human's attached BATCH-05 execution request, including minimum
synthetic Development fixtures and existing canonical authority, and the
[canonical contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-05).

## Baseline and Actual Execution Touch Set

`main`; HEAD and local `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`; upstream `origin/main`; divergence
0/0; no fetch. Existing ten dirty product files, prior F-111/BATCH-01..04 tests,
reports, evidence, Graphify and protected documents form the effective baseline.
F-118 entered OPEN / STATIC_CONFIRMED / NOT_EXECUTED. BATCH-01..04 accepted
changes and finding entries remain intact; no prior finding is reopened.
[Entry status, canonical hashes and 5,141 source/evidence hashes](f111_batch_05_evidence/ENTRY_BASELINE.json).

Product mutations: `apps/inventory/forms.py:StockTransactionForm.__init__` plus
its two authorization imports; `apps/inventory/views.py:transaction_create` plus
its membership import. Added `tests/test_uiux_f111_pattern_stock_scope.py`, this
report and `f111_batch_05_evidence/`; updated only F-118 in the findings register.
No models, migrations, services, templates, settings, role/permission definitions,
shared helpers, Registry or Roadmap changes. Migration: **NO**.

Runtime mutations are the documented synthetic source rows, two warehouses,
two authorized drafts, append-only audits and authentication/session bookkeeping
below. No temporary role/scope assignment was needed.

## Implementation and automated evidence

The view resolves membership from authenticated user and active organization.
All protected choices begin empty and remain empty for missing, invalid or
wrong-tenant membership. Existing Project, shared source/destination Warehouse
and posted/unconsumed receipt-item querysets intersect canonical `scope_queryset`
with `pk`, `project_id` and `goods_receipt__project_id` respectively. No site-parent
promotion. Organization scope retains central warehouses; limited Project scope
excludes them. Material/UOM remain tenant masters with their original predicates.

The shared constructor governs GET, bound validation and all redisplays.
Unauthorized receipt IDs fail field validation before receipt-derived Project
assignment. Existing movement shape, distinct warehouses, material/receipt match,
Project consistency, service locking, draft creation, receipt contract and posting
boundaries remain unchanged. Authorized cross-Project combinations still fail
existing domain validation; no new cross-Project business policy is introduced.

- [Focused tests](f111_batch_05_evidence/focused.txt): **12 tests + 43 subtests PASS**.
  Covers qualifying A/B/C/D/X; all four selectors and full-response metadata;
  membership/user/tenant and absent/revoked/expired/future grant negatives;
  capability/role entry denial; central and site-only denial; manipulated source
  IDs; incompatible relationships; required receipt/issue/transfer/adjustment
  variants; safe invalid/service redisplay; direct service denial; authorized
  limited and organization draft success, audit and unchanged balances; original
  archival, status, consumption, material and UOM predicates.
- [Regression](f111_batch_05_evidence/regression.txt): **76 tests + 77 subtests PASS**.
  Full `apps/inventory/tests.py`, `apps/inventory/test_cep034_receipt_contract.py`,
  prior `tests/test_uiux_f111_scope.py` and BATCH-04 receipt scope controls.
  **No failures, no baseline-debt waiver and no attributable regression.** No
  broader repository-wide regression claim is made.
- [Django check](f111_batch_05_evidence/django_check.txt),
  [Ruff](f111_batch_05_evidence/ruff.txt),
  [format](f111_batch_05_evidence/ruff_format.txt),
  [migration drift](f111_batch_05_evidence/migration_check.txt), YAML, links,
  whitespace and exact source/other-finding preservation: PASS.

## Canonical Development preparation and authority

[Preflight](f111_batch_05_evidence/INVENTORY_PREFLIGHT.json) found zero posted,
unconsumed receipt items. Existing A/B/C/D/X Projects, suppliers, materials,
warehouse sources, tenant owners and test personas were reused. Five new
`B05-RUNTIME-PO-A/B/C/D/X` orders and their posted `B05-RUNTIME-GR-A/B/C/D/X`
receipts were created through `create_purchase_order` → `add_purchase_order_item`
→ `issue_purchase_order` → `create_goods_receipt` → `add_goods_receipt_item` →
`post_goods_receipt`. Each order has one governing version/line. Quantity two
ordered and one received leaves these new orders issued; no BATCH-04 order or
other existing source was edited. This posts Procurement receipt status only.

`create_warehouse` created `B05-CENTRAL` and `B05-SECOND-B` for the central control
and valid same-Project transfer. Preparation added 30 Procurement rows, two
warehouses and 32 canonical audits. [Exact fixture IDs and actors](f111_batch_05_evidence/FIXTURES.json).
These explicitly synthetic Development fixtures retain their audit/history.

Existing nonstaff/nonsuperuser personas: `uiux.persona.project-manager` has A/B
Project grants, `uiux.persona.tenant-admin` has Organization scope, and
`uiux.reference.batch03.site-only` has one SITE grant and the existing
`operations_manager` role. All have the existing create capability. No new actor,
role, permission, grant or authority semantic. Before/after authority fingerprints
match. **Temporary authority cleanup: NONE REQUIRED.**

## HTTP and browser runtime

Fresh current-checkout Development process, loopback port 8008, PostgreSQL
`construction_erp`, zero pending migrations, real authenticated login and CSRF.
[Server identity](f111_batch_05_evidence/SERVER.json),
[configured environment and integrity baseline](f111_batch_05_evidence/RUNTIME_BEFORE.json).

**41/41 HTTP security observations PASS:** three actor GETs, 32 otherwise valid
forced Project/source Warehouse/destination Warehouse/receipt-item submissions
(C/D/X for limited actor and A/B/C/D/X for site-only), four required-field
redisplays, and receipt/transfer incompatible authorized-Project service
rejections. All options exactly match canonical scoped querysets. Same-tenant
unauthorized and cross-tenant identifiers and distinguishable labels remain
absent from complete responses. Organization scope exposes A–D and central
warehouses, excludes X. Site-only protected selectors contain only blank options.
[HTTP records](f111_batch_05_evidence/RUNTIME_HTTP.json),
[summary](f111_batch_05_evidence/HTTP_SUMMARY.json).
**Eight existing direct service scope/tenant/site denials PASS**, with zero
mutation. [Service controls](f111_batch_05_evidence/DIRECT_SERVICE.json).

**Five browser observations PASS**, using the available Chrome extension:
limited GET; actual receipt and transfer service rejection/redisplay; site-only
GET; organization GET with central warehouse control. Option counts including
blank, in Project/source/destination/receipt order, are 3/4/4/3 for limited and
redisplays, 1/1/1/1 for site-only, and 5/7/7/5 for organization scope.
[Browser records](f111_batch_05_evidence/RUNTIME_BROWSER.json),
[limited GET](f111_batch_05_evidence/browser_limited_get.png),
[receipt redisplay](f111_batch_05_evidence/browser_receipt_redisplay.png),
[transfer redisplay](f111_batch_05_evidence/browser_transfer_redisplay.png),
[site-only](f111_batch_05_evidence/browser_site_only.png),
[organization](f111_batch_05_evidence/browser_organization.png).

The global navigation legitimately retains the parent Project A as site context;
this supplies no movement-source authority. Demo tenants reuse some human labels:
identical authorized master/context text is not classified as forbidden metadata.
UUIDs, actual option sets and distinguishable source labels establish exclusion.
Receipt-item labels retain the existing model string; no label/UI redesign was
introduced. Shared context and labels were not changed by this batch.

After all negative/browser checks, two real-CSRF positive submissions created
`B05-RUNTIME-TRANSFER` and `B05-RUNTIME-RECEIPT` as authorized B Project **drafts**,
with exactly two corresponding success audits. The receipt source is then
consumed by that draft, preserving the existing selector/contract predicate.
[Positive controls and exact retained IDs](f111_batch_05_evidence/RUNTIME_POSITIVE.json).
Neither draft was posted; no stock balance or value changed.

## Integrity, harness corrections and closeout

All **519 model tables** compared before/after. Every pre-existing non-session row
is identical, excluding User `last_login`. Runtime adds only the two documented
authorized drafts, their two success audits, three legitimate receipt-failure
audits from authorized mixed-Project rejection/retest, and session bookkeeping.
No unauthorized StockTransaction or success audit; authority unchanged; all stock
posting/value tables unchanged. Preparation rows and 32 audits are separately
accounted. [Integrity](f111_batch_05_evidence/RUNTIME_INTEGRITY.json),
[before preparation](f111_batch_05_evidence/PREPARATION_BEFORE.json).

Harness corrections included the balance-reader user argument, legitimate global
site context, duplicate demo labels, summary-error HTML parsing, preservation of
canonical failure audits, browser navigation/date normalization and screenshot
viewport fallback. One preparation attempt selected a multi-item source with
`get()`; the canonical transaction rolled back before writes, then used the first
existing source material. Final focused, HTTP, positive and integrity runs pass.

A reused preflight initially overwrote BATCH-04 `RUNTIME_ENTRY.json`. Its exact
original bytes were reconstructed from retained preflight/preparation evidence
and verified against the captured entry SHA-256; final preservation verifies it
and every other prior artifact unchanged.
[Byte-for-byte recovery evidence](f111_batch_05_evidence/PREFLIGHT_RECOVERY.json).
No product workaround or weakened authorization was introduced.

The temporary browser tab is closed and the verified fresh server stopped.
[Cleanup](f111_batch_05_evidence/SERVER_CLEANUP.json).
[Final boundary verification](f111_batch_05_evidence/VERIFICATION.json),
[artifact hashes](f111_batch_05_evidence/INDEX.json).

**BATCH-06..09 NOT_EXECUTED; Wave C NOT_STARTED.** No Production action,
CEP-078/079 execution, Git add/commit/push/merge, Human Sign-off, Production
Certification, schema change, Inventory posting or cutover. BATCH-05 closed; STOP.
