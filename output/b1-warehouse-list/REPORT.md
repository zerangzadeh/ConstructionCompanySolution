# B1 — Warehouse List Reference Migration

Date: 2026-11-04 (Asia/Tehran). Direct bounded Human implementation request.
Branch: main; entry HEAD/origin/main: 06bcee2ffd31302091388b3738eca38f840500a6.

## Scope and implementation

Product changes are limited to:
- templates/inventory/warehouse_list.html
- apps/accounts/templatetags/reference_lists.py (one additive warehouses presentation profile)

Verification additions:
- tests/test_warehouse_reference_list.py
- scripts/verification/warehouse_list_validate.py
- output/b1-warehouse-list/ (before/after evidence and this report)

Reuses the accepted Contracts Reference List, existing reference/operational CSS,
page_header (including breadcrumbs), list_working_context, filter_bar and chips,
reference_list_toolbar/result summary, table_sort_header, status_badge,
list_detail_action, empty_state/filtered_empty_state and list_pagination.
No new shared component, stylesheet, JavaScript, dependency or build output.

Warehouse search remains the existing warehouse parameter (code/name), with the
existing project-text and location-text quick filters. Sort keys remain warehouse,
project, location and status. Status is sorting only, never a new filter.
Default ordering, pagination and authorized query/count remain view-owned.
Global Working Context uses the existing compact reference control and remains
independent of list filters; filter application does not alter session scope.
Existing custody/valuation links and Create eligibility are preserved.
Code, name and the row menu navigate only to the existing Detail endpoint.
Status display retains the original archived_at predicate and original labels.

The legacy Base filter/pagination blocks are overridden only in this template;
base.html, Contracts, other list templates and all existing shared assets remain
unchanged. No view/service/model/migration/permission/workflow/Product Surface
or tenant/project isolation change. No Development business data mutation.

## Verification environment

A dedicated test_bonira_b1_warehouse_20261104 PostgreSQL database was cloned from
an inactive, empty migrated test fixture (447 recorded migrations). Normal Django
migration checking remains enabled. Synthetic users/tenants/projects/warehouses
exist only in that test database. The runner restores its migration seed after
browser fixture cleanup. See database-preparation.json.

Real installed headless Chrome uses the repository's existing MVP-02/CDP driver
against Django StaticLiveServerTestCase. Browser requests are restricted to the
loopback test origin. Before: six scenarios, Warehouses and Contracts at
1440/1024/390. Desktop, tablet and mobile captures were visually inspected.
Contracts before/after viewport PNGs are byte-identical at all three widths:
contracts-comparison.json. Tablet horizontal scrolling is contained in the table,
matching the reference; mobile uses the existing reference row cards.

## Verification results

The before run passed six Chrome scenarios. The final suite passed all 20 tests
and all 20 Chrome scenarios, with no page-level horizontal overflow. The final
run covered Apply, Clear, chip removal, result counts, sorting, pagination,
Back/Forward, refresh, native GET with JavaScript disabled, Create/Detail links,
and reader, denied, empty scope and cross-tenant cases. See after-tests.txt,
after-tests.xml and browser-summary.json. Ruff, Django and scoped whitespace
checks passed.

The Warehouse List uses its three existing search fields, so it needs no
advanced filter disclosure. Its custody and valuation links retain their
permission checks and sit between the header and filter bar. The existing
test-server favicon request returned 404 outside the page under review.

Initial fixture/driver failures remain retained in before-attempt01.txt and
after-attempt01.txt/.xml. They include a missing explicit denied-member role,
an unavailable optional HTML parser (replaced with stdlib HTMLParser), incorrect
assumptions about revoked scope (403, not empty data), Persian font glyphs versus
canonical number strings, an invalid archived-active fixture and separate fill
steps unsupported by the existing browser driver. Product authorization and
business rules were not weakened to accommodate tests.

## Preservation and acceptance

Entry SHA-256 inventory: entry-hashes.json; preservation.json compares files.
A concurrent edit to docs/validation/related-documents-phase3.md was observed;
B1 never edits or overwrites that file. No overlapping B1 user change was found.

VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW.
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING.
No Git staging, commit, push, branch/worktree creation or production action.
No next batch execution is authorized or performed.
