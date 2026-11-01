# Contracts List — final micro-polish

Date: 2026-11-01, Asia/Tehran. Explicit bounded Product Owner request.

```text
REFERENCE VISUAL CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

The existing approved-reference composition was retained. Changes are limited to:

- Clear result count plus an exact Decimal/SQL `Sum(contract_value)` over the
  existing authorized Queryset after all filters and before pagination. The sum
  covers all current results, uses the organization currency, and returns zero
  for empty or invalid-filter results. It is a read-only projection.
- Contract numbers and titles remain the primary Detail links. The `⋮` disclosure
  contains only the real secondary action “open details in a new tab”; no edit,
  delete, export or other unsupported domain operation was invented.
- Clearer chip-label/value hierarchy, individually named removal links and Clear
  All. Existing context-preserving URLs and history behavior remain unchanged.
- Only the five existing sortable columns have sort controls. The currently
  ordered header exposes `aria-sort`, including the existing default title order.
- Small header alignment, numeric-summary separation and responsive spacing refinements.

Real connected-Chrome evidence:

- [Filtered desktop](desktop-filtered.jpg), [general desktop](desktop-general.jpg).
- [Filtered mobile](mobile-filtered.jpg).
- [Desktop secondary menu](desktop-menu.jpg), [mobile secondary menu](mobile-menu.jpg).
- [Desktop checks](desktop-checks.json), [mobile checks](mobile-checks.json).

Reviewed directly against the earlier supplied reference and the immediately
preceding Contracts output. The same real five-contract project was used for the
filtered capture, with a real business search plus project filter. Count and sum
changed correctly between five filtered results and twenty general results.
No screenshot content or application data was fabricated.

Manual checks exercised chip removal, Clear All, Back, the actual new Detail tab,
single-item secondary menus, Escape/focus return and menu bounds. Mobile at 390px
and small mobile at 320px had no page overflow. The same existing card adaptation
and LTR contract identifiers were retained. No application JavaScript errors were
observed; logged connection errors originated from a browser extension.

Focused validation:

```text
.venv/Scripts/python.exe scripts/verification/mvp03_validate.py apps/contracts/test_filter_bar.py apps/contracts/test_reference_list_browser.py --reuse-db -q
10 passed, 8 subtests passed in 59.45s
```

[Full result](test-results.txt), [Chrome test artifacts](browser/).
The tests prove exact fractional totals across pages, invalid/empty results,
foreign-tenant exclusion and project-scope restrictions, as well as existing
filter/navigation behavior, sorting and the new real secondary-menu link/bounds.
Tests use only the dedicated `test_bonira_mvp03_20261029` PostgreSQL database.
Django system checks, Ruff checks, changed-test formatting, JavaScript syntax and
`git diff --check` passed.

An initial test run exposed an invalid attempt to change a finalized fixture's
value and a shared money formatter reformatting the new summary. The fixture now
uses its existing value; the server-formatted summary uses the existing formatter's
already-formatted marker, preserving the organization currency exactly once.
The final run above passed without weakening any domain invariant.

Branch `main`; HEAD and grounded `origin/main`:
`5b760e853b329e2b03415da7b046641359db6a62`. The tree was already dirty. Initial
versions of the ten touched source/test files are retained in [baseline](baseline/).
Unrelated existing work was preserved. This request changed the Contract List view
only for the read summary/sort presentation, five list/component templates,
Contracts-scoped CSS, the existing small JavaScript module and two focused test files.

No Domain, Model, Migration, Permission, tenant/project Scope, Workflow, Sidebar,
dependency or live application data change. No rollout to other pages. No staging,
commit, push, branch/worktree creation or production action. Product Owner visual
acceptance remains pending.
