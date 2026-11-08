# Timekeeping navigation cleanup

2026-11-07 · Local `main` · HEAD `1d3593a9`

The Timekeeping landing page now leads with Attendance, Leave/Mission, Overtime and Work Log actions. The Workforce sidebar entry opens the existing Workers, Assignments and Work Teams tabs. The record toolbar groups the filtered Excel export with the result count. Filters, attendance list and monthly view use the existing workspace components.

An empty required worker selector offers worker creation or assignment in the selected project and site when the user can perform that action. Calendar and shift setup links appear with the missing configuration. The selector only offers setup on an empty unfiltered lookup. The changes use the existing routes, permissions and workflows.

## Chrome verification

| Journey | 1440 px | 1024 px | 390 px |
| --- | --- | --- | --- |
| Create Worker | PASS | PASS | PASS |
| Assign Worker | PASS | PASS | PASS |
| Create Work Team | PASS | PASS | PASS |
| Register Attendance | PASS | PASS | PASS |
| Create Leave/Mission draft | PASS | PASS | PASS |
| Create Overtime draft | PASS | PASS | PASS |
| Register Work Log | PASS | PASS | PASS |
| Review monthly attendance | PASS | PASS | PASS |

The final Chrome run verified saved records, sidebar access, contextual assignment and shift links, tenant denials, and filter state through Back and Forward. It also checked for document overflow and JavaScript errors. The focused suite passed 34 tests, and the separate Workforce browser navigation test passed. The first Chrome run reached an assignment lookup before it finished. The final run passed after the assertion waited for the visible hint. [Final Chrome log](journeys-final.log) · [Focused and navigation test log](test-results.log)

Django system checks, Ruff, JavaScript syntax and Git whitespace checks passed. Changes are local and uncommitted.

## Screenshots

| View | Chrome capture |
| --- | --- |
| Timekeeping landing page | [1440 px](screenshots/timekeeping-1440.png) · [1024 px](screenshots/timekeeping-1024.png) · [390 px](screenshots/timekeeping-390.png) |
| Missing assignment in Attendance | [1024 px](screenshots/missing-assignment-1024.png) |
| Monthly attendance | [390 px](screenshots/monthly-attendance-390.png) |
| Workforce reached through the sidebar | [390 px](screenshots/workforce-from-sidebar-390.png) |
