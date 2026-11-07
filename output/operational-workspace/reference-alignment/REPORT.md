# Workflow Inbox — visual reference alignment

2026-11-06, Asia/Tehran. This revision responds to the comparison of `current (3).png` and `target (2).png`. It supersedes the earlier Inbox appearance; the existing domain workspace rollout is retained.

The earlier Inbox had stretched summary tiles, tall rows, an oversized filter area and large repeated action buttons. The revision uses one framed operational panel, the shared icon-led Page Header, bounded summary tiles, one compact primary filter row, a subtle blue table header, alternating rows and the existing native List row-action menu. Mobile retains wrapped record cards and the same actions. Summary values remain the actual existing routing counts; no sample statuses, KPIs, search, checkboxes or bulk actions were added.

Full subject text remains in the accessible DOM; row-menu names refer to that subject with `aria-labelledby`. All existing POST forms, CSRF/idempotency fields, permission/lifecycle conditions, source handoffs and assignment history remain intact. The accepted application shell and other page patterns are unchanged.

Changed in this revision:

- `templates/workflows/workbench.html`
- `templates/workflows/_work_item_row.html`
- `templates/components/operational_workspace.html` — stylesheet cache version only.
- `apps/accounts/static/css/erp_operational_workspace.css` — Inbox-scoped alignment.
- `apps/accounts/templatetags/operational_workspaces.py` — explicit existing filter labels.
- `tests/test_operational_workspace.py` — native-menu journeys and a 21-record queue.
- `scripts/verification/mvp02_browser.mjs` — graceful CDP shutdown of the private test Chrome before guarded profile cleanup. This fixes the observed Windows Crashpad profile-lock cleanup failure without weakening UI assertions.
- `docs/ui-guidelines.md` — appended Inbox visual alignment guidance.

Validation: [8 passed, 2 deselected](recheck.txt). The two deselected query-budget checks are the previously reproduced 86-versus-45 baseline failures, recorded in [original-template comparison](../query-baseline.txt). Six existing queue regressions and both real-browser tests passed. All **15 current Inbox browser scenarios** passed, including filtering/clear/Back/reload, source navigation, no-JavaScript GET filtering, claim/release/approval, read-only access, denial, and a 21-item queue at **1440, 1024 and 390px**. Desktop/tablet rows are verified at no more than 60px and the primary filter row at no more than 48px. The open menu is verified within the viewport. [Structured browser results](browser-scenarios.json).

| Actual browser screenshots | View |
| --- | --- |
| 21-item Inbox, 1440px | [Viewport](procurement-owner-reference-density-1440-viewport.png), [full page](procurement-owner-reference-density-1440-full.png) |
| 21-item Inbox, 1024px | [Viewport](procurement-owner-reference-density-1024-viewport.png), [full page](procurement-owner-reference-density-1024-full.png) |
| 21-item Inbox, 390px | [Viewport](procurement-owner-reference-density-390-viewport.png), [full page](procurement-owner-reference-density-390-full.png) |
| Open row-action menu | [1024px](procurement-owner-reference-action-menu-viewport.png) |

`manage.py check`, scoped Ruff, JavaScript syntax and whitespace checks passed. Existing POST form markup matches the starting copy. Protected components/Lists retain their earlier hashes. `templates/base.html` differs from the older rollout snapshot; this revision did not edit it and preserves that unrelated work. No model, migration, service, permission, workflow or Product Surface change. No commit or push. Product Owner acceptance remains pending.
