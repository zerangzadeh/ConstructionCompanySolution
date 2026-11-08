# BONIRA — Platform User Detail redesign

Implemented locally on 2026-11-08 for `/organizations/platform/users/<user-id>/`. The account detail page remains in the existing Platform Admin workspace and is available under MVP.

The header now shows the person's full name, readable username, account status, effective platform role, membership count, and dates. Contact information, security actions, company memberships, and recent account events have separate panels. Desktop uses two columns and mobile stacks the sections and adapts membership rows into cards. The page uses the existing edit, change-status, password recovery, and company authorization routes. Roles and their links appear only where the operator has the existing company permissions. A known email-delivery outage is clearly distinguished from a recorded recovery request. Account deletion is not offered by the existing account services.

## Files and reuse

- `templates/accounts/platform_user_detail.html` composes shared breadcrumbs, account and membership status badges, icons, form fields, and membership pagination. It shares `templates/accounts/platform_user_initials.html` with the directory. The existing confirmation dialog continues to guard change-status and recovery submissions.
- `apps/accounts/platform_user_views.py` supplies contextual action visibility, existing company role-view authorization, and an allowlisted recovery status from audit data. It does not pass raw audit metadata to the template. Account workflows, effective roles, and tenant boundaries remain governed by the existing services.
- `apps/accounts/static/css/erp_platform.css` adds scoped responsive styles. `apps/accounts/static/css/tailwind.css` was rebuilt and `templates/base.html` refreshes the platform stylesheet cache key.
- `apps/accounts/test_platform_users.py` verifies protected controls, company role visibility and links, and the unavailable-email presentation alongside the existing account lifecycle coverage.

## Verification

- PostgreSQL regression suite: **86 tests and 47 subtests passed** across accounts, Platform Admin console and roles, administration, and Product Surface. Tests cover permitted edits, deactivate/reactivate, revocation of prior sessions and recovery tokens, protected accounts and last-admin/owner safeguards, denied access, CSRF, and recovery behavior with a test mail backend.
- Django system check, Ruff, Tailwind build, and `git diff --check` passed. The CSS build reported an advisory about the existing Browserslist data.
- The MVP browser run used a synthetic account with a long username and three company memberships. The username remained readable without horizontal page overflow in all four viewports. Only the authorized company showed a role and a role-inspection link. The existing edit form loaded, the status confirmation opened and was cancelled, and the recovery button was disabled with an explanation and matching audit outcome. No state-changing account operation was submitted in the browser.

| Viewport width | Before | After |
| --- | --- | --- |
| 1440 px | [Desktop](before-1440.jpg) | [Desktop](after-1440.jpg) |
| 1024 px | | [Two columns](after-1024.jpg) |
| 768 px | | [Stacked panels](after-768.jpg) |
| 390 px | [Mobile](before-390.jpg) | [Mobile summary](after-390.jpg) · [Mobile memberships and events](after-390-memberships.jpg) |

The table lists measured browser viewport widths; the capture tool may omit the scrollbar gutter from the image dimensions.

This page uses initials and displays up to ten recent account audit events from the existing audit stream. Production SMTP delivery was outside this verification. No migrations were applied, no commits or pushes were made, and no production operation was performed.
