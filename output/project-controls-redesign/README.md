# Project controls UI refresh — 2026-11-12

Authorized by the direct user request for the outdated /projects/<id>/controls/ page. Ordinary bounded UI task; no CEP execution/lifecycle change.

Grounding: local main at 865fa3f3; origin/main equal (0 ahead/behind). The working tree already contained extensive unrelated changes. Only the previously clean controls template and a new page-scoped stylesheet were changed; unrelated files preserved.

Product touch set:
- apps/projects/templates/projects/controls.html
- apps/projects/static/projects/controls.css

Reuses the Operational Workspace, Page Header, Form Field, Status Badge, Empty State and canonical color tokens. Independent WBS/activity tables, native no-JavaScript form disclosures, parent context, permission-conditioned operations and report links. The repeated id_code label association was removed by assigning the WBS code input a unique ID. No models, migrations, services, permissions, query scope, state transitions or financial behavior changed.

Validation:
- manage.py check: PASS, no issues.
- manage.py test apps.projects.tests.ProjectControlsServiceTests --keepdb --noinput: 2/2 PASS; hierarchy/lifecycle and tenant scope. Configured Django PostgreSQL test database, preserved by --keepdb.
- Ad hoc Django template rendering: empty state with read-only, creator and report permissions PASS; conditional forms and report links, unique IDs, CSRF and UTF-8 text verified. Initial check could not import optional bs4; rerun used standard-library re without installing a dependency.
- Installed Chrome, authorized existing local session: populated page inspected at widths 1440, 1024 and 390; no document-wide horizontal overflow. Mobile tables have independently scrollable, named keyboard-focusable regions and a visible scrolling hint.
- Both form disclosures opened on mobile; all 4 WBS and 10 activity inputs/selects retained and labels resolved. No business forms were submitted against the user's database.
- git diff --check for the changed tracked template: PASS.
- Full regression and manual Human UAT: not performed. Template-only permission rendering is not a full authorization test suite.

Evidence: preview.png is the viewport screenshot. The full-page desktop/tablet/mobile PNGs exhibit the browser capture's sticky-shell stitching artifact; do not interpret that artifact as page layout. The empty and permission variants were rendered, not browser-tested.

Git add/commit/push/branch/worktree: not executed. Production action and Human sign-off: not executed.

## Context-bar follow-up — 2026-11-12

Direct user request: correct this page's context bar. Reused the existing shared list_working_context disclosure in header_working_context and suppressed the obsolete standalone working_context strip. The existing scoped POST selector, CSRF, safe next path, session semantics and project-owned page content remain unchanged. Added an explicit note separating the global working context from the project belonging to this page.

Touch set remains controls.html and controls.css. A page-loaded, 768–1279px override for the shared fit-tablet class centers the panel within the viewport; the initial 1024px check detected a left-edge overflow, and the post-fix check passed. Cache version incremented.

Validation: Django check PASS; diff whitespace PASS; two existing CEP016 context persistence/project-change-reset tests PASS on the preserved configured PostgreSQL test database. Real Chrome disclosure opened and inspected at 1440, 1024 and 390; post-fix panel bounds and no document overflow PASS. Exactly one existing context form, existing CSRF and return target verified. No global context form was submitted in the user's live browser. Desktop/mobile screenshots: context-desktop-1440.png and context-mobile-390.png; tablet: context-tablet-1024.png. A browser selector targeting the tablet-hidden text timed out; verification continued using the existing summary element. A later transient dispatch timeout affected only the attempted closing click; the final screenshot confirmed the completed panel. Temporary viewport override reset.

Final tablet visual review also identified sidebar occlusion even though the panel was inside viewport bounds. The 1024–1279px override now reserves the existing 260px sidebar plus 24px clearance. Final Chrome check at 1024: panel fully left of sidebar, disclosure open, document overflow false; verified visually and replaced context-tablet-1024.png. CSS cache version 3. Desktop and mobile rules unchanged by this narrower correction. Browser viewport restored.
