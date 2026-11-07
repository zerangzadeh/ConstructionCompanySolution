# Parties list visual alignment — 2026-11-05

Authorization: explicit user request to align /parties/ with /equipment/; local, presentation-only scope.
Branch: main. Start HEAD and origin/main: 59f2fde64fc3684f09871b82a2b1945905c28aab.
Existing dirty working tree preserved. No Git write or branch/worktree operation.

Changed product files:
- templates/parties/list.html: reuse operational_list, header, navigation, filter bar, responsive rows, detail menu and pagination.
- apps/accounts/templatetags/reference_lists.py: additive parties presentation profile; existing profile edits preserved.
- apps/parties/views.py: presentation profile context only.

Existing query, sorting, pagination, tenant, role, governance and authorization semantics preserved. No schema, service, permission or database write.

Validation:
- python -m pytest tests/test_operational_list_adapter.py -q: 3 passed.
- python manage.py check: no issues.
- python -m ruff check apps/accounts/templatetags/reference_lists.py apps/parties/views.py: passed.
- git diff --check on the three changed files: passed.
- Authenticated localhost browser: nine existing records; name search reduces to one; tax-ID sorting preserves name filter; row detail popup opens; unmatched search shows filtered empty state; clear restores nine records.
- Mobile 390x844: responsive cards, no document horizontal overflow (scroll width 375); viewport override reset.
- Desktop/mobile screenshots: desktop.png, mobile.png. Screenshots contain existing demo records.

Coverage limits: pagination footer verified with one page only; no broad business or cross-tenant suite run for this presentation-only change. No Human UAT/sign-off or production action claimed.
