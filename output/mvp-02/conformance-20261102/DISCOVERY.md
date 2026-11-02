# MVP-02 conformance discovery — 2026-11-02

Authority: explicit bounded user request; non-production UI only. Entry is clean
`main`, HEAD/origin/main `d9adfa0d418bba1fa8831d0f7bbcb9e598c2015f` (local refs).
No Git write, schema/domain/permission change or downstream package is authorized.

Sources reconciled: current UI guidelines §§10–17, 30, 37–42, 46–51; frozen D1–D7;
Roadmap §10; original MVP-02 completion and earlier UI remediation; central
`CAPABILITIES`, MVP route overrides, registered URLs, actual views/templates;
Contracts list/create/detail and Procurement/Inventory list/detail patterns.
Historical report acceptance remains pending. Existing shared pattern scope is
extended to these workforce pages by this request only.

## Discovered surface (before implementation)

All entries are MVP-visible subject to their existing business permissions and
tenant/object scope. URL prefixes are `/workforce/` and `/timekeeping/`.
`{id}` denotes the existing UUID route parameter, never a visible business label.

| Route suffix / name | Template | Purpose / type / journey | Before deficiency → target |
| --- | --- | --- | --- |
| workforce `field/` / field_list | workforce/field_list.html (app) | Worker master / List / navigation → find worker | Basic filter grid; no chips, count, sort, mobile cards, menu → shared Reference List |
| workforce `field/new/`, `field/{id}/edit/` | workforce/field_form.html (app) | Identity create/edit / Create / Edit Form / list → save → detail | Undifferentiated field grid → shared grouped Reference Form |
| workforce `field/{id}/` | workforce/field_detail.html (app) | Operational identity / Detail / worker → assignment or time | Surname title, repeated identity, edit-centric CTA, inline status → full identity, state badge, valid operational CTA, secondary menu |
| workforce `field/{id}/assign/` | workforce/field_form.html (app) | Named worker assignment / Create / Edit Form / worker → scoped assignment | Flat fields → grouped Form; retain fixed worker and scoped selectors |
| workforce `assignments/` | workforce/assignment_list.html | Assignment history / List / workforce tab → find assignment | No business search/chips/count; raw start date; wide mobile table → Reference List and existing end/cancel in menu |
| workforce `assignments/create/` | workforce/assignment_form.html | Assignment / Create / Edit Form / history → scoped assignment | Flat fields → grouped Reference Form |
| workforce `teams/` | workforce/work_team_list.html | Company crews / List / workforce tab → crew | Three text filters, exposed archive, no paging UI/mobile cards → Reference List |
| workforce `teams/create/` | workforce/form.html | Company crew / Create / Edit Form / crew list → create → list | Already scoped and compact; needs section grouping/footer → Reference Form |
| timekeeping root / workbench | timekeeping/workbench.html | Source-separated histories and repetitive entry / Operational Workspace | Large filter area, actions below filters, sparse state/context summaries → compact operational workspace, shared filter summary, counts, state badges and clear next steps |
| timekeeping `attendance/new/` | timekeeping/form.html | Attendance / Create / Edit Form / worker or workspace → capture | Flat form → identity/context, dates/time, details sections |
| timekeeping `attendance/{id}/corrections/new/` | timekeeping/form.html | Correction / Action / Transition Form / finalized attendance → correction | Flat form → grouped form and retained source/back context |
| timekeeping `leave-mission/new/`, `overtime/new/` | timekeeping/form.html | Distinct requests / Create / Edit Form / workspace → request | Flat fields → grouped Reference Form |
| timekeeping `timesheets/new/` | timekeeping/form.html | Work period / Create / Edit Form / workspace → draft | Flat fields → grouped Reference Form |
| timekeeping `timesheets/{id}/` | timekeeping/timesheet_detail.html | Allocation and history / Detail + Operational Workspace | Weak identity/state; review form can overflow; prepare/submit shown to non-preparer → state/actor-aware controls, responsive allocation grid |
| timekeeping `records/{kind}/{id}/`, kind attendance/correction/leave/overtime | components/read_only_record_detail.html | Source record / Detail / workspace → history | Generic key/value dead end, missing attendance context and next action → dedicated Timekeeping state-aware Detail |
| timekeeping `calendars/new/`, `holidays/new/`, `shifts/new/`, `shift-breaks/new/` | timekeeping/form.html | Existing operational setup / Create / Edit Form / workspace settings → setup | Flat fields → grouped Reference Form; no new setup capability |
| workforce `field/choices/{kind}/`, `assignments/sites/` | JSON / workforce/_site_options.html | Supporting Selector / Lookup | Already qualified Tom Select/scoped lookup; preserve implementation |
| workforce `assignments/{id}/status/`, `teams/{id}/archive/`, `employees/{id}/status/` | POST only, redirects | Existing Action / Transition controls | Presentation stays with source record; no new transition route |
| timekeeping attendance finalize, correction review, leave/overtime submit/review, timesheet submit/review/preview | POST only, redirects | Existing Action / Transition controls | Render only current state + permission + known actor eligibility; services unchanged |
| workforce legacy root, employees/create, employees/{id} | MVP adapters to field views | Compatibility entries | Share field presentation; no parallel HR surface |

## Explicit exclusions

- All `projects:*`, `apps/projects/**`, `templates/projects/**`: **EXCLUDED — PROJECT PAGE**.
  Project List/Create/Edit/Detail/hub/navigation/layout remain byte-for-byte unchanged.
  Site and Daily Report destination pages are also unchanged. Context/selectors may
  link to existing destinations. Any destination defect is **OUT OF SCOPE — PROJECT PAGE**.
- Full HR/ESS/employment/foundation, Payroll and technical attendance import remain
  UI-hidden. Backend-active is preserved. Profile/catalog/route architecture unchanged.
- Legacy profile-image and archive handlers have no new UI; no hidden HR exposure.

## Intended actual touch set

- Workforce field views/forms and only work-team/assignment presentation seams in
  legacy views; dedicated presentation helper/tag; field/list/detail/form templates.
- Timekeeping views/form labels and presentation-only history/filter integration;
  dedicated Detail template and existing workspace/form/timesheet templates.
- Focused conformance tests and Chrome scenarios reusing the installed-Chrome CDP
  probe; this discovery, dedicated report and `output/mvp-02/conformance-20261102/`.
- Shared components/CSS/JS are reused unchanged. No model, migration, domain service,
  selector authority, Product Surface, project implementation or permission change.

Verification plan: focused boundary regression; real installed Chrome at 1440,
1024, 390 for each principal page/variant; state, validation retention, scoped
lookups, unauthorized/foreign/project-site denials, URL filter/sort/page/refresh/Back;
inspect generated screenshots; compare protected hashes to baseline.

## Implementation delta following browser evidence

The first tablet check found that the Contracts desktop table minimum width must
remain horizontally contained. The table now uses its existing reference wrapper.
The reference popup's absolute positioning clipped row actions inside that scroller;
`apps/workforce/static/workforce/field_list.js` provides bounded viewport positioning
for these existing menus only. It changes no shared component/CSS, Project page or
business state. Native disclosure, keyboard focus, Escape and outside-click behavior
remain provided by the accepted pattern. Menu dates reuse the qualified Jalali
presentation attributes and existing transition-form parsing.
