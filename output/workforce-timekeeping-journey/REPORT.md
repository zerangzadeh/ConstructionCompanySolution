# Workforce and Timekeeping UX remediation

2026-11-06. Local main, HEAD 59f2fde6. Product Owner visual acceptance remains pending.

The bounded authorization is the supplied remediation request. Both supplied
23-page journey PDFs were reviewed before implementation. Their click captions
were treated as recorded observations. The working tree already contained 99
modified tracked files and numerous untracked files, including shared form,
navigation and Workforce changes. This report describes this remediation's
additions to that existing work.

The supplied sources are the
[Workforce journey](<E:/ERP_Construction_Documents/screenshot journey/workforce_journey- 06-11-2026.pdf>)
and [Timekeeping journey](<E:/ERP_Construction_Documents/screenshot journey/timekeeping-journey - 06-11-2026.pdf>).

## Findings and changes

| Classification | Confirmed cause | Implemented correction |
| --- | --- | --- |
| Defect | Workforce tabs linked to their current list and repeated navigation reloads | Current list tabs render as text. Parent links on create/detail pages remain usable and identify the current section. Workforce and Attendance sidebar entries avoid self-navigation on their own list. |
| Usability | Worker detail repeated assignment actions and lacked the leave/mission handoff | One assignment entry, a direct edit action, and a permission-aware leave/mission link with the existing worker context. |
| Defect | Assignment destinations discarded selected project/site or list filters | Validated assignment context and relevant filter/sort parameters continue into Create, Cancel, breadcrumbs and post-save destinations. |
| Defect | Save-only roles could be sent to a detail page they could not read | Saved records open their permitted detail. Save-only users receive a success message and an authorized return destination. |
| Usability | Work Log exposed minute totals without a clear duration control | Separate hours/minutes inputs for the total and allocation. Human-readable saved durations. Existing integer-minute payloads remain supported. Zero, negatives, malformed values, minutes above 59 and storage overflow are rejected. |
| Defect | Empty Shift lookups could close without explaining that no record exists | Visible status beside the selector, dependent reset after changing Work Calendar, and permission-aware setup links. Setup forms also use the shared searchable controls. |
| Defect | Chrome left enhanced Project/Site controls hidden inside an opened mobile filter disclosure | Workforce and Timekeeping progressively enhance the disclosure to an accessible button with explicit visibility, preserving the original live controls and Apply behavior. |
| Usability | Work Calendar selection, date picking and attendance history were conflated | Explicit Work Calendar labels, a scoped Jalali monthly attendance summary, day-to-list drill-through and a filtered empty state. The datetime picker exposes a clock control on Timekeeping forms. |
| Defect | Date picker triggers accumulated handlers during rendering. Partial client conversion could change valid fields before another invalid date blocked submission | Bind each trigger once, position the opened picker within the viewport, and convert dates only after all entered dates validate. |
| Usability | Duplicate error alerts, summary-first focus, browser autofill noise and technical copy obscured entry | Shared field errors, first-invalid-control focus, retained values, opt-in autocomplete settings, sectioned form styling and clearer draft/save labels. Source field errors attach to their controls where available. |
| Potential domain change | Policy reference and request category are text contracts. Leave submission requires an authoritative reservation | Preserve these contracts and show the leave submission prerequisite. Authorized policy readers receive existing category suggestions. A governed policy/category selector and a connected leave reservation journey require separate Product Owner scope. |

Draft creation already allowed an empty policy reference. Worker, category,
reason and time-range requirements remain required by the existing contract.
The form now explains the draft/approval distinction. This remediation does not
add partial drafts with missing domain-required fields.

## Journey verification

Real installed Chrome, Django live server, dedicated disposable PostgreSQL test
databases and synthetic organizations were used. The test inspects saved model
records after browser submission before reporting a journey as passed.

| Journey | 1440 px | 1024 px | 390 px | Persisted evidence |
| --- | --- | --- | --- | --- |
| Create Worker | PASS | PASS | PASS | Employee, explicit relationship and selected Work Team, without login identity |
| Assign Worker | PASS | PASS | PASS | EmployeeProjectAssignment with selected project/site and start date |
| Create Work Team | PASS | PASS | PASS | WorkTeam with submitted code and name |
| Register Attendance | PASS | PASS | PASS | AttendanceRecord with selected Work Calendar, Shift and work date |
| Create Leave/Mission draft | PASS | PASS | PASS | Leave at desktop/mobile and Mission at tablet, saved as draft with empty policy reference |
| Create Overtime draft | PASS | PASS | PASS | OvertimeRequest persisted as draft |
| Register Work Log | PASS | PASS | PASS | Timesheet and allocation both store 155 minutes from 2 hours and 35 minutes |
| Review monthly attendance | PASS | PASS | PASS | Saved attendance appears on its day, with preserved date filters through Back/Forward |

Assertions also verify required-field focus, duration-error value retention,
calendar-to-shift dependency, meaningful empty Shift state, current-tab behavior,
tenant isolation and the unchanged attendance-record count after Work Log.
The calendar summary reads the same authorized attendance queryset as the list.
It presents attendance counts and has no scheduling or financial authority.

### Regression evidence

- Focused Workforce, selector, Timekeeping and localization suite, 62 tests PASS.
- Saved-record destination and save-only role regressions, 2 tests PASS.
- Requested Chrome journeys, existing navigation and A–H regression PASS.
- Final screenshot refresh and calendar setup regression PASS. Calendar, shift,
  holiday and break forms were exercised through invalid and successful browser
  submissions, with denied-role checks.
- Django system checks, changed Python-file lint, JavaScript syntax and diff
  whitespace checks PASS.

These results comprise 64 focused tests and four Chrome test methods across the
recorded runs. The final journey/navigation run passed both methods after the
mobile disclosure correction. Its 30 journey scenarios cover all three widths,
the unconfigured calendar and cross-tenant denials. The separate navigation
method passed 22 desktop/mobile scenarios.
- The wider initial run found three older fragment tests that also fail using
  the HEAD navigation/ESS templates. They assume historical fragment context and
  entries. Reproduction is retained in [baseline-fragment-tests.log](baseline-fragment-tests.log).

The repeatable test entry point is
[workforce_timekeeping_validate.py](../../scripts/verification/workforce_timekeeping_validate.py).
It sets a dedicated test database name and supports individual Django test labels.
The initial complete Chrome journey run is recorded in
[initial-complete-browser.log](initial-complete-browser.log), and the focused
suite in [focused-regression.log](focused-regression.log).
Supplementary results are in [saved-context-regression.log](saved-context-regression.log),
[save-only-role-regression.log](save-only-role-regression.log) and
[calendar-setup-final.log](calendar-setup-final.log). The combined Chrome run
in [final-browser.log](final-browser.log) also retains the old navigation-test
failure and the mobile filter issue subsequently corrected.
The final PASS is recorded in
[verified-journeys-and-navigation.log](verified-journeys-and-navigation.log).
Duration compatibility was rechecked in
[duration-compatibility.log](duration-compatibility.log).
Structured scenario results and screenshots are under [after](after/) and
[navigation](navigation/).

## Screenshots

Before images are rendered pages of the supplied journey PDFs. After images
are actual Chrome captures of synthetic test data. They show different data and
viewport sizes, so they are behavioral comparisons.

| Area | Before | After |
| --- | --- | --- |
| Work Log entry | [Minute-only control](before/timekeeping-23.png) | [Hours and minutes](after/390/timekeeping/journey-owner-work-log-form-390.png) |
| Work Calendar and Shift | [Empty references](before/timekeeping-05.png) | [Unconfigured calendar guidance](after/journey-owner-calendar-unconfigured.png) |
| Leave/Mission | [Draft form](before/timekeeping-10.png) | [Saved draft](after/390/timekeeping/journey-owner-leave-mission-390.png) |
| Workforce navigation | [Repeated navigation after validation](before/workforce-06.png) | [Saved worker and assignment](after/390/workforce/journey-owner-worker-and-assignment-390.png) |
| Work Team | [Registration](before/workforce-21.png) | [Saved team](after/1024/workforce/journey-owner-work-team-1024-viewport.png) |
| Attendance calendar | Recorded history appears only as lists in the supplied journey | [Monthly summary](after/390/timekeeping/journey-owner-attendance-month-390-viewport.png) |
| Saved Work Log | Minute-oriented entry above | [155 minutes displayed as hours and minutes](after/1440/timekeeping/journey-owner-work-log-1440.png) |

## Remaining limitations and Product Owner decisions

- Leave draft creation is verified. Final leave submission requires the existing
  authoritative reservation, and approval requires its governed policy evidence.
  Connecting policy choice, allocation and reservation into this back-office
  journey needs separately approved domain scope. Final leave approval is not
  counted as a passed journey here.
- Request category and policy reference remain existing text contracts.
  Assignment responsibility is also descriptive text rather than a Position
  relationship. Replacing these with governed masters needs explicit domain
  authorization.
- Empty selectors reflect actual authorized records. Synthetic calendar/shift
  records were created only in test fixtures. A real tenant must configure its
  own calendar and shifts through the existing authorized routes.
- Three historical fragment-test failures remain as reproduced above. Human
  visual acceptance and production certification remain pending.

Models, migrations, business services and calculation authority received no
changes from this remediation. Existing unrelated local changes were retained.
No commit or push was performed.
