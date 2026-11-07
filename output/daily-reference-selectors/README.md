# Daily Report reference selector presentation — 2026-11-05

Explicit user scope: make Safety, Quality and existing-document references appear
as selectors on `/daily-reports/create/`.

Grounding: local `main`, HEAD `59f2fde6`, `origin/main` ahead/behind 0/0; substantial
existing changes, including the related-record feature, were preserved.

Touch set: `ReferenceMultipleSelect` in `apps/daily_reports/reference_forms.py`,
its dedicated wrapper template and `daily_reports/reference_choices.css`.
The existing shared Tom Select search, multi-selection, dependent resets,
authorized lookups, native fallback, validation and submission remain in use.
Scoped styles add an RTL-positioned dropdown chevron, open-state indicator and
pointer cursor without changing other selectors. The enhanced hidden native
select no longer inherits the create form's large minimum height.

Validation:

- `pytest tests/test_daily_report_references.py::DailyReportReferenceTests --reuse-db -q`:
  8 passed, 4 subtests passed (239.57s). Includes creation, preserved sources,
  forged/cross-tenant/scope choices, authorization, lookup pagination, bound
  selection retention, upload rollback and native refresh. See `tests.txt`.
- Ruff lint and format: PASS for `reference_forms.py`.
- Django system check: no issues.
- Before change, Chrome confirmed all three fields were existing searchable
  multi-selects whose controls had no dropdown chevron. Final live-browser
  verification was unavailable after the browser connection detached/timed out.

No schema, migration, endpoint, permission, business-rule or dependency changes.
No new tests were added for this bounded presentation change. No Git write,
production action or Human sign-off was performed.
