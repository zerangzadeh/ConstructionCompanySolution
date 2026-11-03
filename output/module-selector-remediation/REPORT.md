# Module Selector UI remediation

Scope: explicit user-requested presentation remediation, on local main at b97fcc45. Unrelated working-tree changes preserved. No commits or pushes. No schema, migration, domain, permission, route, sidebar or Product Surface rule changes.

## Changed files
- core/templatetags/product_surface.py: presentation families derived exclusively from the existing filtered selector links; active existing destination preferred, otherwise an existing authorized family destination. Unknown destinations keep their own card.
- templates/components/module_selector.html: shared native modal, header, semantic cards, carousel controls and position indicator.
- templates/components/module_selector_icon.html: local stroke SVG partial following existing icon conventions; no dependency.
- apps/accounts/static/css/erp_module_selector.css: card hierarchy, blue active state, focus outlines, compact overlay, RTL and mobile layouts.
- apps/accounts/static/js/erp_module_selector.js: RTL scrolling, arrow/Home/End navigation, position indicator and stable modal focus. Existing trigger, modal opening/closing and page-state behavior retained.
- tests/test_f3_module_selector.py: authorized grouping, denied/hidden destinations, active descendants and owner/restricted browser fixtures.
- scripts/verification/f3_browser.mjs: card assertions, keyboard/scroll controls and navigation from all owner-visible cards.
- scripts/verification/module_selector_validate.py: isolated migrated PostgreSQL test database and guarded fixture restoration.

## Validation
Final command: `.venv/Scripts/python.exe scripts/verification/module_selector_validate.py tests/test_f3_module_selector.py core/test_product_surface.py core/test_cep017_navigation.py -q --reuse-db --junitxml=output/module-selector-remediation/tests.xml`
Result: 27 passed, 21 subtests passed; 10 real installed-Chrome browser scenarios (1440 and 390 px, four owner routes and restricted project reader). Each owner-visible card navigated successfully. Existing context selectors/sidebar remained unchanged. Close button, Escape, backdrop, focus restoration/trapping, RTL arrow keys, mobile wheel, desktop previous/next, reduced motion, no page overflow and no hidden destination exposure verified.
Ruff check/format, Django system check, both JavaScript syntax checks and scoped git diff --check: PASS.
Evidence: tests.xml, browser/results.json, browser/command.txt and browser/*-open.png / *-closed.png.

The initial browser assertion assumed all mobile lists overflowed; corrected for a restricted account whose two cards fit. A real boundary-arrow focus loss was corrected before the final passing run. A concurrent shared test-database seed restore collision was isolated by using a dedicated test clone of an inactive fully migrated test database. Only this clone was used for the final run; no development/production database changes.

Visual QA: desktop and mobile Contracts and Projects screenshots inspected against supplied target/current images. Header, icon/title/description hierarchy, compact top panel, dimmed backdrop and active card match the target direction. Cards remain 168–172 px wide and scroll inside the panel. The exact eight-card list is not forced: authorized workbench, business-party and settings families are retained after the eight primary families. Secondary destinations remain accessible in the unchanged sidebar. Existing source route aliases and longest authorized path identify the active card; page text is never inspected.
