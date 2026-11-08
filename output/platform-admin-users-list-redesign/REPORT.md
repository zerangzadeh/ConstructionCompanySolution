# BONIRA — Platform Users List redesign

Implemented locally on 2026-11-08 for `/organizations/platform/users/`. The existing Platform Admin sidebar, MVP exposure, account routes, and authorization remain in use.

The directory now has four real platform-wide counts, a single search and filter panel, a compact table on larger screens, and cards on mobile. The administrator count uses effective Platform Admin assignments. The result count reflects the current filters. The default is 20 accounts per page; 10 and 50 are also available. Pagination preserves search, filters, and page size. Long usernames are isolated left-to-right and clipped with an ellipsis; the complete value is available in the title and account detail. Each row has a keyboard-accessible actions menu, with shortcuts to the existing authorized account flows.

## Files and reuse

- `templates/accounts/platform_user_list.html` composes the existing page header, breadcrumbs, dashboard metric, form field, icon, and account-status components. `templates/accounts/platform_user_initials.html` is shared with account detail.
- `apps/accounts/platform_user_views.py` uses the existing platform directory query, effective duty annotation, permission gates, and pagination helper. It supplies aggregate counts and contextual action visibility. Mutation endpoints and services remain unchanged.
- `apps/accounts/static/css/erp_platform.css` scopes responsive presentation to the user pages. `apps/accounts/static/css/tailwind.css` was rebuilt and `templates/base.html` refreshes the platform stylesheet cache key.
- `apps/accounts/test_platform_users.py` extends coverage for platform counts, row permissions, long identifiers, and pagination.

## Verification

- PostgreSQL regression suite: **86 tests and 47 subtests passed** across accounts, Platform Admin console and roles, administration, and Product Surface. The tests cover Persian and case-insensitive English search, email, search combined with company membership, account status combined with platform duty, supported page sizes and filter preservation, missing profile fields, and action visibility for authorized, restricted, and protected accounts.
- Django system check, Ruff, Tailwind build, and `git diff --check` passed. The CSS build reported an advisory about the existing Browserslist data.
- In the MVP browser session with synthetic records, Persian full-name and full-length English username searches each returned the expected account. The row menu opened with Enter and navigated to the existing detail page. A no-match query displayed the empty state, and reset restored the unfiltered list. At all four requested viewport widths the long identifier rendered as one LTR line with ellipsis, without horizontal page overflow. The desktop table switches to fewer columns at tablet widths and to cards at 390 px.

| Viewport width | Before | After |
| --- | --- | --- |
| 1440 px | [Desktop](before-1440.jpg) | [Desktop](after-1440.jpg) |
| 1024 px | | [Compact table](after-1024.jpg) |
| 768 px | | [Tablet table](after-768.jpg) |
| 390 px | [Mobile](before-390.jpg) | [Mobile toolbar](after-390.jpg) · [Mobile cards](after-390-rows.jpg) |

The table lists measured browser viewport widths; the capture tool may omit the scrollbar gutter from the image dimensions.

Initials are used for listed identities. Status and recovery shortcuts lead to the existing controls in the account detail page; they do not execute from the menu. Live SMTP and production data were outside this verification. No migrations were applied, no commits or pushes were made, and no production operation was performed.
