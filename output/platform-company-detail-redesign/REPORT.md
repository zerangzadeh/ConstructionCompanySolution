# Platform Admin Company Detail redesign

The [reference refinement report](reference-refinement/REPORT.md) contains the current layout, 30 passing focused tests and the latest before/after screenshots. The captures and results below document the initial redesign.

2026-11-10, Asia/Tehran. Implemented on local main at 865fa3f3, matching origin/main at entry. Changes are uncommitted.

The page uses the shared Record Detail header, breadcrumbs, summary, section cards, semantic status badge and List Page filter, results, table, empty state and pagination components. Native section links lead to management, activity and sensitive operations. The full company code is available through a collapsed disclosure.

Suspension is separately framed and collapsed by default. Its required reason, hidden concurrency/state fields and existing POST route are retained. The shared SweetAlert2 hooks provide confirmation, cancellation, Escape and focus restoration. Existing reactivation for suspended companies and conditional onboarding retry remain available.

Activity retains its existing username/event-type search, localized event descriptions, actor identities, shared Jalali formatting, stable newest-first ordering and 25-record pagination. Only the existing supported search is exposed.

## Files changed by this task

- apps/organizations/templates/organizations/platform_company_detail.html
- apps/organizations/static/css/erp_platform_company_detail.css
- apps/organizations/platform_forms.py, ActivitySearchForm widget presentation
- apps/organizations/platform_views.py, Company Detail presentation context
- apps/organizations/test_platform_companies.py, activity search/pagination regression
- This evidence directory

The pre-existing Company List changes and shared component edits were preserved. Additional unrelated working-tree changes observed during execution were also preserved.

## Verification

The browser used installed Google Chrome through Playwright against the actual loopback Django server and a disposable PostgreSQL 18 database. All records and identities in captures are synthetic. The test database was isolated from the application's configured development database.

| Check | Result |
| --- | --- |
| Focused company and platform-console tests | 29/29 PASS |
| Django system checks | PASS, zero issues |
| Ruff check and format check for the three touched Python files | PASS |
| git diff --check | PASS |
| Browser at 1440 × 900, 1024 × 768 and 390 × 844 | PASS |
| Company identity, active status and exact code disclosure | PASS |
| Edit/list/breadcrumb navigation and section links | PASS |
| Required reason and server rejection of a whitespace-only reason | PASS |
| Suspension Cancel, Escape, default Cancel focus and focus return | PASS, cancellation sends no POST |
| Existing suspension and reactivation through the browser | PASS in disposable fixtures |
| Username and Persian event-label search, clear, previous/next pages | PASS |
| Filtered and genuinely empty history | PASS |
| Tenant owner and unassigned superuser access | 403 |
| Anonymous access | Login redirect |
| RTL, loaded Vazirmatn and document/body horizontal overflow | PASS at all three widths |
| Browser JavaScript errors | None observed |

The focused tests also cover cross-company audit isolation, CSRF, revoked authority, stale versions, blank reasons, immutable audit transitions, finalized company states and transactional rollback.

[Focused test log](focused-tests.log) · [Django checks](django-check.log) · [Ruff and whitespace checks](static-checks.log) · [Browser results](browser.log)

## Screenshots

| Width | Before | After |
| --- | --- | --- |
| 1440 | [Original page](before-1440.png) | [Full page](after-1440.png) · [Viewport](after-viewport-1440.png) |
| 1024 | [Original page](before-1024.png) | [Full page](after-1024.png) · [Viewport](after-viewport-1024.png) |
| 390 | [Original page](before-390.png) | [Full page](after-390.png) · [Viewport](after-viewport-390.png) |

[Mobile suspension confirmation](suspension-confirmation-390.png) · [Mobile filtered empty state](activity-empty-filter-390.png)

Visual review corrected an uneven summary wrap at tablet width. An initial browser date assertion was corrected to account for the shared formatter's ASCII DOM digits and Vazirmatn's Persian numeral glyphs.

## Remaining issues and acceptance

No remaining in-scope issue was observed in the verified journeys. The shared date formatter and existing search semantics are retained. Human visual acceptance is pending.

```text
VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```
