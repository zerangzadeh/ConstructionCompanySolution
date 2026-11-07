# Inbox project-context alignment

2026-11-06. The Inbox now reuses the same header `list_working_context.html` component and tablet positioning stylesheet as Compact/Sectioned Forms. The old standalone context strip is suppressed only on the Inbox. Existing global-context POST, scoped choices, CSRF, return URL and queue/filter independence are unchanged.

Changed: `templates/workflows/workbench.html`, plus focused coverage in `tests/test_operational_workspace.py`.

[Test result](tests.txt): **1 passed**, covering seven Chrome scenarios at 1440px, 1024px and 390px: closed/open header panel, viewport fit, project selection, clearing, retained filter URL and unchanged authorized queue. A foreign-tenant project selection is rejected with 403. Django system check, Ruff and scoped whitespace check passed.

Screenshots: [desktop](procurement-owner-context-closed-1440-viewport.png), [tablet panel](procurement-owner-context-open-1024-viewport.png), [mobile panel](procurement-owner-context-open-390-viewport.png).

No shared shell/component, backend, migration or permission changes. No commit or push.
