# Safety detail header context — 2026-11-05

Scope: top context control on the requested Safety Incident detail page, matching Work Team Create. Branch: main; HEAD/origin/main: 59f2fde64fc3684f09871b82a2b1945905c28aab. Existing unrelated work preserved. No commit/push.

Changed only templates/safety/detail.html: reuse components/list_working_context.html in header_working_context, header_layout=True and fit_tablet_panel=True; load the same existing tokens/reference-list/create-form styles as the reference page, preserving related_documents.css. Suppress the standalone context strip. The record's own project/site display, document evidence and workflow controls remain unchanged. No view, model, permission, data, schema or domain changes.

Verification: Django system check PASS; template compilation PASS; scoped git diff --check PASS. Actual Chrome at 1440, 1024 and 390px: one header context control, zero standalone strips, no page overflow, open panel within viewport. Enter opens/closes the native disclosure. Existing CSRF and /organizations/context/ destination retained. No context update or incident action submitted.

Evidence: checks.json, open-1440.jpg, open-1024.jpg, open-390.jpg, after-1440.jpg and header-1440.jpg. Human visual acceptance not inferred.
