# BONIRA Stage 6 — System states and feedback

Implemented on local `main` (`59f2fde6`, matching local `origin/main`) alongside the existing uncommitted UI work. This is technical evidence; no commit, push, production operation or Product Owner acceptance was issued.

| Area | Files and scope |
| --- | --- |
| Shared feedback | `templates/base.html`, `templates/components/{interaction_styles,interaction_scripts,messages}.html`, `apps/accounts/static/{js/erp_interactions.js,css/erp_interactions.css}`. All pages using the ERP shell, including MVP-visible entry, organization, project, field operations, procurement, contracts/billing and shared workspaces. Reused the existing local SweetAlert2 11.26.25 assets and provenance. |
| Confirmation migration | `templates/procurement/request_detail.html` (submit, approve, reject, cancel) and `apps/billing/templates/billing/progress_detail.html` (submit, verify, reject). Existing confirmation wording, endpoints, validation and CSRF stay in place. |
| HTMX adapter | `templates/workflows/_work_item_row.html` delivers the existing Django message in an OOB fragment on HTMX response. Existing redirects, headers and 409 responses retain their contracts. Current MVP workbench controls still use native posts. |
| Inline states | `templates/components/form_errors.html` adds a focused summary with field links; `templates/{403,404,500}.html` use `templates/components/system_state.html`. Existing empty, loading, badge, and persistent guidance components remain in place. |
| Documentation and tests | `docs/ui-guidelines.md` §55; `tests/test_stage6_system_states.py`, `tests/test_f2_shared_interactions.py`, `scripts/verification/stage6_browser.mjs`, `scripts/verification/stage6_baseline_probe.py`. |

Django Admin, standalone print output and hidden `FULL_ERP` pages were outside the page-level rollout. Shared ERP shell changes apply wherever the shell is reused. No page layout, business action, exposure rule or backend architecture was added or redesigned.

| Chrome 156 screenshot | 1440px | 1024px | 390px |
| --- | --- | --- | --- |
| Live purchase request confirmation | [PNG](live-pages/mvp04-pr-1440-confirmation.png) | [PNG](live-pages/mvp04-pr-1024-confirmation.png) | [PNG](live-pages/mvp04-pr-390-confirmation.png) |
| Live Django success toast | [PNG](live-pages/mvp04-pr-1440-success.png) | [PNG](live-pages/mvp04-pr-1024-success.png) | [PNG](live-pages/mvp04-pr-390-success.png) |
| Inline validation | [PNG](validation-1440.png) | [PNG](validation-1024.png) | [PNG](validation-390.png) |
| HTMX conflict feedback | [PNG](htmx-conflict-1440.png) | [PNG](htmx-conflict-1024.png) | [PNG](htmx-conflict-390.png) |
| 500 page | [PNG](500-1440.png) | [PNG](500-1024.png) | [PNG](500-390.png) |

Also captured: [interactive alert](interactive-alert-390.png), [asset failure fallback](vendor-failure-390.png) and the three other toast levels at every width.

- [Live PostgreSQL browser run](live-pages/results.json): nine pages (field worker, contract create, purchase request at each width); external browser requests blocked. Purchase request cancel and Escape sent zero POSTs; confirm sent one POST and showed success after the server response. Approve/reject cancellation and submitter/validation behavior also exercised.
- [Shared shell browser run](results.json): three widths, all four toast levels, focus and keyboard behavior, one POST per operation, OOB message delivery, 409 feedback, inline states and asset failure fallback. HTMX 2.0.11 was used on an isolated fixture with official asset integrity verification; it was not added to product dependencies. 403/404/500 status and safe rendering verified through Django default handlers. Progress detail confirmation wiring was inspected; it was not a separate browser journey.
- Django system check, JavaScript syntax, focused Ruff and the existing shared loading browser test passed. Six workflow tests passed, including HTMX status, CSRF and transition coverage. Two query-count tests remain red at 86 vs a limit of 45; the [baseline comparison](baseline-query-comparison.txt) reproduced both counts with the Stage 6 template additions removed via an in-memory template loader.
