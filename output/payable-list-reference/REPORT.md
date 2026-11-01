# Payable Certificates List visual alignment

Authorization: user UI request, 2026-11-01. References: supplied image and current Contracts List.
Branch main; start HEAD/origin/main 5b760e853b329e2b03415da7b046641359db6a62. Existing dirty changes preserved. No Git writes or production action.

## Implementation

- Reuse Contracts header, filter bar, chips, result summary, sorting helper, status badges, responsive table/cards and pagination.
- Exact requested title, subtitle and primary CTA; CTA follows existing create permission.
- Existing authorized selector unchanged. Filters and options only narrow it; invalid choices fail closed.
- Display actual snapshot counterparty, certificate/revision, contract/project, period, gross, signed adjustment, net, currency, status and creation date. No financial calculation or aggregation added.
- Vertical row menu matches Contracts: existing secondary Detail navigation in a new tab. Certificate number is primary Detail link. No unsupported edit/delete/revision/print/export controls.
- Models, migrations, domain rules, calculations, permission definitions, workflow, tenant/project selector and Product Surface unchanged.

## Chrome verification with existing development records

Chrome extension session, local port 8000. No development business records created or mutated.

- Desktop 1536px: three existing certificates, ten columns, no document overflow. Long status badge wraps within its cell.
- Approved filter reduces three rows to two and displays active chip.
- Advanced filters open the number field.
- Missing search produces zero results; clear restores three rows.
- Net sort produces sort=net and aria-sort=ascending.
- Row menu exposes existing secondary Detail navigation.
- Mobile 390x844: document width 375, grid cards, LTR identifiers, menu bounds 30.8..198.24 within viewport. Temporary viewport reset.
- Desktop/mobile/filter/advanced/empty/menu screenshots saved here. Existing shell and navigation retained under Product Surface constraint.

## Validation

Django check, focused Ruff and whitespace checks: PASS.
Focused functional tests: 5 PASS (calculations, workflow/candidacy/immutability/audit, denied reader and tenant isolation/create visibility, valid/invalid filters/chips/sorting, pagination). See final-tests.log: its one browser failure was a driver-step configuration error, corrected without a product change.

Final Chrome automation: 1 test PASS, six scenarios PASS, all HTTP 200 and zero JavaScript errors. See browser-tests.log and browser/pay-cert-owner-results.json. Scenarios: desktop, desktop menu, filters/chip removal/sorting, mobile cards, mobile menu bounds, filtered empty state. Functional assertions were not rerun after the browser-only test-step correction.

Dedicated test environment: test_bonira_payable_list_ready_20261101, copied from an inactive, fully migrated test database (446 recorded migrations, zero user records). The source database was not changed. Normal pytest migration preparation remains enabled; canonical authorization/workflow bootstrap helpers restore test catalogues. The initial partial migration database is not used by the completed validation. Browser teardown restores its original seed snapshot after the existing safe test flush, permitting reuse.
Initial run failed before the changed list: legacy fixture roles lacked explicit project-create authority; workflow serialization rejected restoration of published history. Local test fixture uses existing explicit_fixture_roles helper; product authorization unchanged. Dedicated test database runs configured migrations.

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

FUNCTIONAL VALIDATION: PASS

BROWSER VALIDATION: PASS

REFERENCE VISUAL CONFORMANCE: PASS

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
