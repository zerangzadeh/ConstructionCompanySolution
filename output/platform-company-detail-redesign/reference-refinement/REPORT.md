# Company Detail reference refinement

2026-11-10, Asia/Tehran. Local main at 865fa3f3. Changes are uncommitted.

The revised layout brings the page closer to the supplied visual reference with a six-field, two-row company summary, a blue company icon tile, a full-width section-navigation strip, white card headings, lighter borders, compact management actions and a denser activity table.

The edit link now sits in the management card. Active local administrators appear in the summary, while the owner and membership count remain in the management card. The company code is abbreviated in the summary and expands to its exact value. Native section links provide navigation among real sections.

Sensitive operations appear immediately before activity history in a separate collapsed disclosure. Existing reason validation, CSRF, concurrency/state fields and SweetAlert2 confirmation are retained. Activity uses its supported username/event search and existing localized event descriptions.

## Product files changed in this refinement

- apps/organizations/templates/organizations/platform_company_detail.html
- apps/organizations/static/css/erp_platform_company_detail.css

Other changes from the initial redesign and unrelated working-tree edits were preserved.

## Verification

| Check | Result |
| --- | --- |
| Company and Platform Console focused tests | 30/30 PASS |
| Django system checks | PASS, zero issues |
| Ruff check and format check | PASS |
| git diff --check | PASS |
| Real Chrome browser at 1440 × 900, 1024 × 768 and 390 × 844 | PASS |
| Status, identity, exact code disclosure and management navigation | PASS |
| Suspension required reason, whitespace rejection, Cancel and Escape | PASS |
| Confirmation default focus, focus return and zero cancellation POSTs | PASS |
| Existing suspension/reactivation in disposable records | PASS |
| Username/Persian event search, clear and previous/next pagination | PASS |
| Populated, empty and filtered empty activity | PASS |
| Tenant owner and unassigned superuser access | 403 |
| Anonymous access | Login redirect |
| RTL, Vazirmatn and no horizontal page/body overflow | PASS at all three widths |
| Browser JavaScript errors | None observed |

Actual Django requests used a disposable PostgreSQL 18 database and synthetic records. Browser review aligned the navigation icons consistently on mobile.

[Focused tests](focused-tests.log) · [Django checks](django-check.log) · [Static checks](static-checks.log) · [Browser results](browser.log)

## Captures

| Width | Before refinement | After refinement |
| --- | --- | --- |
| 1440 | [Viewport](before-viewport-1440.png) · [Full page](before-1440.png) | [Viewport](after-viewport-1440.png) · [Full page](after-1440.png) |
| 1024 | [Viewport](before-viewport-1024.png) · [Full page](before-1024.png) | [Viewport](after-viewport-1024.png) · [Full page](after-1024.png) |
| 390 | [Viewport](before-viewport-390.png) · [Full page](before-390.png) | [Viewport](after-viewport-390.png) · [Full page](after-390.png) |

[Suspension confirmation](suspension-confirmation-390.png) · [Filtered empty state](activity-empty-filter-390.png)

No remaining in-scope issue was observed in these verified journeys. Human visual acceptance is pending.

```text
VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```
