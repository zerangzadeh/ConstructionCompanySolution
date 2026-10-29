# ERP UI/UX Guidelines

## 1. Purpose

This document defines the approved UI/UX standard for the Persian RTL ERP application.

The interface serves BONIRA's capability-level MVP commercial surface and its
future Full Construction ERP vision with the same enterprise-quality standard.
MVP does not mean prototype-quality UI: visible screens must be Persian-first,
true RTL, responsive, business-user-friendly and free of critical technical
leakage. This quality target does not authorize invented backend capabilities.
The [frozen D1–D7 strategy](architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md)
owns product positioning, capability exposure, outputs and release requirements;
this document owns UI patterns, not proof that those targets are implemented.

It is the authoritative reference for all future UI work across:

- operational ERP pages
- shared layouts/components
- Django Admin
- responsive behavior
- Persian localization
- presentation of technical and financial values

The approved target is:

**Professional, elegant, premium enterprise ERP**

The UI must no longer resemble a generic Django/Tailwind CRUD interface.

---

## 2. Scope

UI/UX work may include:

- Django Templates
- shared layouts
- template partials/includes
- Tailwind CSS
- shared frontend CSS
- Persian RTL presentation
- responsive behavior
- accessibility improvements
- UI-only JavaScript
- Jalali/Shamsi date presentation and date-picker behavior at the UI boundary
- HTMX only where business semantics remain unchanged
- Django Admin template/style overrides

The following are out of scope unless explicitly approved:

- models
- migrations
- database schema
- services
- repositories
- permissions
- tenant isolation
- workflows
- business rules
- lifecycle rules
- backend/domain architecture
- validation semantics

Backend files may be inspected to understand existing behavior, but UI work must not modify backend/domain behavior.

---

## 3. Approved Visual Direction

The ERP should feel:

- professional
- elegant
- premium
- calm
- authoritative
- modern
- information-dense
- highly usable
- visually disciplined
- suitable for long daily use
- enterprise-grade

The desired character is:

**clarity + hierarchy + precision + restraint + polish**

Avoid:

- generic CRUD styling
- default Django appearance
- oversized SaaS cards
- excessive whitespace
- weak visual hierarchy
- decorative gradients
- glassmorphism
- flashy animations
- consumer-app styling
- excessive rounded corners
- excessive icon usage
- arbitrary colors
- inconsistent spacing

---

## 4. Persian-First and RTL

The ERP is Persian-first.

Use:

```html
<html lang="fa" dir="rtl">
```

RTL is the default direction.

All static user-facing text should be Persian, including:

- page titles
- section headings
- navigation labels
- breadcrumbs
- form labels
- button labels
- table headers
- helper text
- empty states
- dashboard labels
- Admin labels where safely overridable
- visible status labels

Internal values must remain unchanged.

Examples:

- `draft` → `پیش‌نویس`
- `active` → `فعال`
- `approved` → `تأییدشده`
- `completed` → `تکمیل‌شده`
- `submitted` → `ارسال‌شده`
- `archived` → `بایگانی‌شده`
- `terminated` → `خاتمه‌یافته`
- `voided` → `باطل‌شده`

Only presentation text is localized.

### Receivables/payables terminology and financial navigation

The Treasury landing page and browser title use `خزانه‌داری` without `میزکار`.
Treasury reconciliation forms, table headings and retained-run labels use
`تاریخ مبنای تطبیق` instead of `تاریخ برش` or `برش`; internal date fields and
cutoff semantics remain unchanged.
Treasury reconciliation exceptions use the Product Owner's terminology:
`مغایرت بانکی` for bank-statement reconciliation and
`مغایرت خزانه با حسابداری` for Treasury-to-ledger reconciliation. These are
presentation labels; exception codes, counts and reconciliation rules are unchanged.

The subledger workbench uses `دریافتنی‌ها و پرداختنی‌ها`, `گزارش سنی`,
`تاریخ مبنا` and `نوع قلم` for AP/AR, aging, as-of and direction. Aging remains
exact and unbucketed. Reconciliation exceptions are `موارد نیازمند بررسی`;
write-off proposals are `پیشنهاد حذف حسابداری مانده`, with an explicit reminder
that this does not delete history. Unimplemented approval/posting paths remain
described as unavailable, without exposing internal decision codes.

The Treasury, subledger and accounting terminology here governs retained
internal/`FULL_ERP` financial surfaces, which are MVP UI-hidden. It does not
define MVP navigation. Legacy labels such as `دریافت و پرداخت (سامانه قبلی)`
and `گزارش مالی پروژه‌ها` never switch source authority or establish a current
settlement path; current domain code and the separately governed Payment
retirement decision remain authoritative. Visible MVP expense and Billing
capabilities use the navigation groups below, with the same desktop/mobile
permission and scope enforcement.

### Supplier portal and invoice-match review

The bounded supplier portal always displays the exact supplier, organization,
project and RFQ context without peer-bid or internal-note content. Submission retry
keys are hidden implementation controls; the visible immutable receipt uses its
receipt identifier. Portal acceptance, RFQ context, submission and receipt
responses are private/non-cacheable. Correction is described as a new superseding
submission; withdrawal, support impersonation and account provisioning are not
offered.

Supplier-invoice match review is Persian-first RTL and read-only. It shows the
invoice and match versions, supplier/project context, governing tolerance-policy
version, source fingerprint, ordered/accepted/previously invoiced/current
quantities, prices, outcome and discrepancy labels. Blocked or incomplete evidence
must direct the user to correct the owned source and run a later match version; the
UI must not offer force-match, material discrepancy override or any downstream
financial/inventory action.

---

## 5. UTF-8 and Persian Text Integrity

All templates and source files containing Persian text must be saved as **UTF-8**.

The UI must never contain corrupted text such as:

- `????`
- `�`
- `Ø`
- `Ù`
- `Û`
- `Â`
- `Ã`

If Persian database values display correctly but static UI labels are corrupted, treat the problem as a template/source encoding issue.

Do not modify correctly stored database data to fix UI encoding.

After UI/localization work, search modified templates for mojibake patterns.

---

## 6. Typography

The approved Persian UI font is:

**Vazirmatn**

It is self-hosted locally in the project.

Use the local `.woff2` files. Do not depend on:

- system-installed fonts
- Google Fonts
- CDN
- external runtime font sources

Recommended weights:

- `400` — Regular
- `500` — Medium
- `600` — SemiBold

Use:

```css
font-display: swap;
```

Recommended hierarchy:

### Page Title
- 22–24px
- semibold

### Major Section Title
- 17–18px
- semibold

### Card / Secondary Heading
- 15–16px
- semibold

### Body
- 14px

### Table
- 13–14px

### Form Label
- 13–14px
- medium

### Helper Text
- 12–13px

### Metadata
- 12px

### Persian Numerals for Business Values

Use Vazirmatn's Persian numeral feature (`ss01`) for every user-facing business
or temporal value that contains digits, including:

- monetary amounts and currency summaries
- quantities, measurements, percentages, counts, and pagination counts
- Jalali dates and user-facing times
- dashboard KPIs, tables, detail metadata, messages, and form values

For values that must be visually aligned for comparison, combine `ss01` with
tabular figures (`tnum`) and use the shared numeric styles. Do not introduce a
second font or page-specific numeral CSS.

Keep technical identifiers such as project codes, contract numbers, SKUs, UUIDs,
and account identifiers canonical and LTR/isolated. Their display formatting
must not alter their stored value or their copy/paste behavior.

For editable money fields, use the shared `erp_money` behavior: show Persian
digits and thousands grouping to the user, then normalize the value before the
existing server-side validation and submission flow. Never use JavaScript number
types or floating-point arithmetic for monetary values.

Typography must be centralized globally.

---

## 7. Technical and LTR Values

Technical/business values must preserve their canonical representation.

Use explicit LTR rendering for:

- project codes
- contract numbers
- estimate numbers
- payment numbers
- UUIDs
- usernames where needed
- emails
- URLs
- IP addresses
- hashes
- file names where appropriate
- technical identifiers
- monetary/numeric values when mixed-direction rendering is confusing

Do not automatically convert technical identifiers to Persian digits.

Mixed Persian/English values must never appear visually reversed.

---

## 8. Financial and Numeric Presentation

Stored values must remain unchanged.

For presentation:

- use thousands separators
- remove unnecessary trailing decimal zeros where safe
- align numeric/financial columns consistently
- preserve units/currency semantics
- use LTR where appropriate

Example:

`75572000000.00 IRR`

may display as:

`75,572,000,000 IRR`

Do not implement new financial calculations in templates.

---

## 9. Application Shell

### Approved MVP navigation and exposure target

Use these five groups for the intended MVP surface:

| Group | Persian label |
| --- | --- |
| `PROJECT & SITE OPERATIONS` | عملیات پروژه و کارگاه |
| `CONTRACT & CLAIMS` | پیمان، متره و صورت‌وضعیت |
| `PROCUREMENT & MATERIALS` | تدارکات، مصالح و انبار |
| `SHARED BUSINESS SERVICES` | کارتابل، اسناد و گزارش‌ها |
| `PLATFORM FOUNDATION` | تنظیمات و مدیریت دسترسی |

Capability membership is defined once in D2 of the canonical strategy. Exposure
should eventually follow one centralized Product Surface Exposure authority;
the implementation mechanism is not frozen. Apply it to navigation, dashboards,
search, quick actions, cross-module links, breadcrumbs, shortcuts and direct
user-facing URLs. Avoid scattered ad-hoc hiding conditions. Gating supplements
Authentication, Authorization, Tenant Isolation, Business Permissions and
Object/Project/Site Scope; it never replaces them.

Customer-facing Organization/user/access administration remains in the MVP;
technical/platform administration, including technical Admin surfaces, remains
hidden. UI hiding preserves backend domains and required handoffs. A visible
journey must not require the user to browse a hidden workspace. These are
approved targets, not claims about the currently rendered shell or routes.

The approved desktop shell uses:

- dark navy/slate right sidebar
- compact top header
- light neutral workspace
- refined white content surfaces
- controlled blue accent
- strong page hierarchy

The previous crowded horizontal desktop navigation is deprecated.

### Sidebar

Recommended desktop width:

**240–270px**

Characteristics:

- dark navy/slate surface
- clear application identity
- grouped navigation
- restrained icons
- clear active state
- compact spacing
- stable icon/title/badge alignment
- subtle scrollbar
- consistent parent/child indentation
- user/settings area near bottom where appropriate

#### Collapsible Groups

For nested navigation:

- groups collapsed by default
- active group auto-expanded
- parent click toggles submenu
- count badges remain visible
- active parent and child states are both clear
- avoid showing all submenus at once

Do not render duplicate navigation systems.

For the MVP Workforce surface, `نیروهای کار` is the primary navigation entry.
Assignment management (`تخصیص نیرو به پروژه و کارگاه`) remains MVP-visible through
one compact, permission-aware internal Workforce navigation alongside `نیروها`
and `گروه‌های کاری`; do not repeat Assignment as a peer sidebar/Home/mobile
primary destination. Keep the Workforce parent active on its assignment and team
pages through the centralized navigation metadata. Preserve direct/contextual
routes, capability exposure, and independent business permissions. Assignment
history and the worker master/current-state projection remain distinct tasks.

Use the shared Workforce header on every MVP list, detail and form page, including
team creation and compatibility entry URLs. Render the three internal tabs in
the same order, immediately after the page header, before Project/Site context
or page content. Put page-level primary actions in the header action area with
the shared near-title layout; do not create a separate primary toolbar above the
tabs. Keep the tabs in one row, with contained horizontal scrolling when needed
on narrow screens. Keep record-specific actions with their record and form submission controls
with their form. Preserve permission-filtered tabs and the active destination.

Workforce breadcrumbs follow `خانه → عملیات پروژه و کارگاه → نیروهای کار`;
the assignment list appends `تخصیص نیرو به پروژه و کارگاه`. Keep the section
inside this chain, without a separate section eyebrow. Home and available parent
destinations are links; Operations links to its existing Home section. Respect
the centralized navigation's permissions/exposure and preserve validated context
on the Workforce parent link. The final current item is non-clickable and uses
`aria-current="page"`. Allow the chain to wrap on mobile.

On the assignment page, keep `تخصیص جدید` beside the title in the header action
area, with a stacked layout on mobile. Use `تاریخ شروع از` / `تاریخ شروع تا` for
its date filters, compact filter rows, and the existing neutral badge for
`بدون تخصیص فعال` in the workforce projection.

For MVP Work Teams, use the Operations → Workforce → Work Teams breadcrumb
hierarchy without the legacy HR eyebrow. Keep create in the shared header action
area. Render the team/department/lead filters, explicit apply and clear together
in one compact RTL block below the tabs, including empty results; suppress the
base layout's automatic duplicate controls through its scoped block override.

Company/Project/Site in the global selector is active application context.
Workforce/Assignment list Project/Site controls are page filters, with a visible
page-filter caption. Default them from the middleware's validated global values
only when no explicit page selection/clear exists. Page filter changes and clear
must never write global session context. Preserve the explicit clear marker,
Project → Site cascading and server validation. Do not repeat the page filter
selection as an unlabelled context summary below the tabs. Mutation forms and
domain source-of-truth behavior retain their existing contracts.


### Top Header

Keep compact.

Use for:

- organization context
- contextual navigation
- search where supported
- notifications where supported
- user/profile controls
- mobile navigation trigger

Do not place all ERP modules in the top header.

---

## 10. Standard Page Structure

Standard page hierarchy:

1. Breadcrumb
2. Page header
3. Optional KPI/summary area
4. Main content
5. Related sections/actions

Page header should contain:

- eyebrow/context where useful
- title
- short description
- primary action

Prefer shared page-header components.

Shared template includes must use valid Django template syntax and must not be duplicated or rendered as literal text.

---

## 11. Dashboard

Dashboard must be operational, not decorative.

Avoid a uniform grid of identical cards.

Use hierarchy such as:

- primary KPI row
- operational overview
- financial summary
- quick actions
- secondary information

Not every card should have equal visual weight.

Use only existing reliable data.

Do not create fake metrics or placeholder charts.
For the MVP, financial summaries are limited to included operational capabilities
such as expenses and Billing; hidden financial/reconciliation workspaces must not
leak through cards, drill-through or quick actions.

---

## 12. Tables and List Pages

ERP list pages should behave like professional data workspaces.

Use:

- compact table/grid structure
- clear table header
- readable row density
- semantic status badges
- aligned financial/numeric columns
- explicit LTR technical values
- consistent row actions
- subtle hover states
- pagination where supported
- professional empty states

For wide tables:

**Use horizontal scrolling inside the result/table container.**

Do not turn complex tables into oversized cards.

Avoid sparse desktop list layouts when a table is more appropriate.

---

## 13. Search and Filters

Search/filter areas should be compact and visually secondary to results.

Desktop pattern:

- compact search toolbar
- filter panel only where supported
- results remain dominant

Do not expose unsupported filters.

---

## 14. Forms

Forms should be:

- RTL
- compact but readable
- grouped into logical sections
- two-column on desktop when appropriate
- one-column on mobile
- label above input
- approximately 42–44px field height
- clear focus/error/disabled states
- consistent action hierarchy

Validation errors must appear directly below the related field.

Preserve Django validation and form binding.

Do not rename underlying Django field names merely for localization.

### 14.1 Form-field localization and terminology

Every newly created or materially changed form must present all user-facing
field labels, option labels, placeholders, helper text, validation messages,
and action buttons in Persian. Use terminology familiar to users of Iranian
accounting, project-management, procurement, and construction software; prefer
the established product glossary and the wording already used in neighboring
screens. For example, use `پروژه`, `توضیحات`, `مبلغ`, `نوع هزینه`, `دوره تکرار`,
`تاریخ شروع`, `تاریخ پایان`, and `پیشوند مرجع سند` rather than their English
equivalents.

This is a presentation rule only. Keep Python field names, model fields,
database columns, enum values, URLs, permission codes, and technical
identifiers in English/canonical form. Set labels and choices at the form or
shared presentation layer, and do not change domain values merely to translate
the UI. A new form is not complete until its rendered labels and choice
options have been checked for English leakage, mixed terminology, and correct
RTL display.

---

## 15. Buttons

Use four visual roles:

### Primary
- Create
- Save
- Submit
- Confirm

### Secondary
- Edit
- Export
- Back
- Duplicate

### Danger
- Delete
- Revoke
- Permanent cancel

### Ghost
- View
- More
- inline/context actions

All buttons should have:

- consistent height
- hover state
- focus state
- disabled state
- consistent icon placement

Avoid several dominant primary buttons on one page.

---

## 16. Semantic Status Badges

Use only five semantic families:

1. `neutral`
2. `info`
3. `success`
4. `warning`
5. `danger`

Examples:

### neutral
- draft
- inactive
- archived

### info
- planned
- under review
- in progress

### success
- active
- approved
- completed
- paid

### warning
- pending
- delayed
- attention required

### danger
- rejected
- overdue
- cancelled
- failed
- voided

Do not invent arbitrary badge colors per model.

---

## 17. Detail Pages

Approved detail-page structure:

1. Breadcrumb
2. Strong entity header
3. Title
4. LTR code/identifier
5. Semantic status badge
6. Primary/secondary actions
7. Compact KPI summary where useful
8. Tabs/section navigation
9. Information sections
10. Related-domain lists

Project Detail remains the strongest operational reference.

Prefer read-only information sections over disabled form inputs.

---

## 18. KPI Cards

KPI cards should be:

- compact
- information-rich
- visually weighted by importance
- restrained in color
- based only on existing business data

Avoid oversized decorative KPI cards.

---

## 19. Empty, Loading, Success and Error States

Use consistent shared patterns.

Distinguish:

- no records yet
- no search/filter results

Use consistent presentation for:

- loading
- success
- warning
- validation failure
- operation failure
- disabled actions

Do not replace server-side validation.

---

## 20. Responsive Behavior

Desktop is the primary ERP experience.

### Desktop
- right sidebar
- compact top header
- multi-column forms
- wide tables
- full action areas

### Tablet
- reduced spacing
- compact/off-canvas navigation where appropriate

### Mobile
- off-canvas navigation
- one-column forms
- horizontally scrollable tables
- compact header
- accessible actions

Do not sacrifice desktop ERP usability to force mobile card layouts.

---

## 21. Accessibility

Ensure:

- visible keyboard focus
- sufficient contrast
- semantic labels
- accessible icon-only controls
- understandable validation messages
- keyboard-friendly inputs
- reasonable click targets

Preserve native Django accessibility behavior.

---

## 22. Django Admin Visual Standard

Django Admin must visually belong to the ERP while preserving native Admin workflows.
This shared design standard does not make technical Admin customer-visible in
the MVP. The rules below apply within separately authorized internal Admin use.

Principle:

**Same design language, different interaction pattern.**

Use:

- Persian RTL
- Vazirmatn
- dark navy/slate right sidebar
- compact top header
- light neutral workspace
- refined white surfaces
- controlled blue accent
- compact tables/forms
- consistent focus states
- correct LTR technical values

Do not replace Django Admin with another framework.

---

## 23. Django Admin Sidebar

Requirements:

- one sidebar only
- no duplicate native/custom navigation
- groups collapsed by default
- active group auto-expanded
- consistent icon/title/badge layout
- consistent child indentation
- count badges aligned
- active state stays inside row bounds
- subtle internal scrollbar
- preserve collapse/expand behavior

Badges/actions must never overlap labels or active backgrounds.

---

## 24. Django Admin Changelist / Select Pages

This is a shared global pattern and should not be fixed per model.

Approved structure:

- Admin shell
- page title/header
- compact search toolbar
- results table as dominant content
- compact filter panel on the right
- paginator/actions in normal flow

Recommended filter width:

**240–280px**

Avoid:

- oversized filter panels
- narrow results areas
- excessive empty whitespace
- browser-level horizontal scrolling
- mixed RTL/LTR layout errors

For wide result tables, scrolling should happen inside the results container.

Preserve native Admin:

- search
- filters
- pagination
- actions
- permission checks
- popup/select behavior

---

## 25. Django Admin Actions and Object Tools

Custom Admin overrides must preserve standard Admin action areas.

Do not accidentally hide:

- Add/Create
- Change
- View
- Delete
- History
- Save
- Save and continue
- Save and add another
- object tools
- submit rows

Within an authorized internal Admin surface, preserve standard Add/Create actions
when the logged-in user has permission. Permission alone does not grant MVP exposure.

Never bypass permission logic.

---

## 26. Django Admin Localization

Where safely overridable, Persianize visible labels such as:

- Site administration
- Recent actions
- My actions
- Add
- Change
- View
- Delete
- Save
- Save and continue editing
- Save and add another
- History
- Log out
- View site
- Change password
- Search
- Filter
- Show counts
- All
- Yes
- No
- Select ... to view

Do not rename database fields, routes, model fields, or stored values for localization.

---

## 27. Shared Components and Architecture

Prefer reuse.

Typical shared UI elements:

- base layout
- application shell
- sidebar
- top header
- page header
- breadcrumb
- form field
- form errors
- messages
- badge
- button
- table
- pagination
- empty state
- stat/KPI card
- tabs
- description list

Avoid duplicate UI systems.

Do not create abstractions unless they are genuinely reusable.

---

## 28. Tailwind and CSS

Use the existing Tailwind architecture.

Prefer:

- shared utility patterns
- shared components
- centralized global CSS
- shared Admin CSS for Admin-wide fixes

Avoid:

- page-specific CSS when a shared fix is possible
- large custom CSS files
- arbitrary values everywhere
- new frontend frameworks
- unnecessary dependencies

### Frontend Build-vs-Reuse and Preferred Toolbox

This section is the main practical authority for frontend utility selection.
Keep simple UI simple. Prefer mature, focused, commercially usable libraries
over custom reimplementation only when they materially improve usability,
maintainability or implementation quality. Follow this decision hierarchy:

1. Native HTML / CSS.
2. Django Templates + Tailwind.
3. HTMX / small Vanilla JS.
4. An approved focused utility library when the preceding options are insufficient.
5. A custom component only when justified by the requirement and available alternatives.

The following are **optional, use-case-driven preferred defaults**, not globally
mandatory dependencies. This policy records selection direction; it does not
claim that any listed library is installed, integrated or qualified in BONIRA.

| Capability | Preferred default | Use when needed | Keep the simpler approach when |
| --- | --- | --- | --- |
| Advanced selects | Tom Select | Large option sets, searchable/multi-select, autocomplete or remote/AJAX lookup for project, site, party, employee, material, contract and similar masters | A short native dropdown is sufficient. Select2 is not the default; do not introduce jQuery solely for a select widget when a strong dependency-free alternative exists. |
| Confirmations and focused dialogs | SweetAlert2 | Important delete, void/cancel, irreversible or submit/approve/reject confirmations, or short success/error interactions that justify a modal under section 47 | Ordinary Django messages, inline validation, simple toast/status feedback or routine reversible actions suffice. Do not turn every message or workflow action into a modal. |
| Advanced data grids | Tabulator | A business table genuinely needs large-dataset handling, advanced filters/sort, grouping, frozen columns, remote pagination or interactive row operations, such as complex inventory/cardex, procurement or reporting views | A normal Django/Tailwind table with server-side sorting/filtering/pagination meets the need. Do not convert simple CRUD lists into grids. |
| Charts | Chart.js | A chart improves a business decision: project progress, expense trends, procurement status, workforce/equipment utilization, safety/quality trends or inventory movements | KPI cards, tables or text communicate the result adequately. Never invent data or placeholder metrics to justify a chart. |
| Jalali date/time input | JalaliDatePicker (`@majidh1/jalalidatepicker`), or a currently verified compatible equivalent when repository constraints justify it | Persian/Jalali input requires more than browser-native Gregorian controls | An existing verified shared solution already meets the requirement. Preserve section 32's `erp_jalali` / `JalaliDateMixin` contract; this preference neither orders replacement nor certifies the current helper as an equivalent library. |

If a future requirement exceeds Tabulator's practical capabilities, evaluate
AG Grid separately. AG Grid Enterprise and any other paid or Enterprise-only
capabilities require an explicit licensing decision before adoption; this
toolbox does not approve them implicitly.

For any later authorized introduction, verify maturity and active maintenance,
commercial-use suitability and license compatibility with BONIRA distribution,
relevant Persian/RTL and accessible keyboard support, Django Templates/HTMX
compatibility, and reasonable bundle/runtime cost. Avoid unnecessary framework
or runtime dependencies and overlapping libraries for the same responsibility.
Pin the selected version when implementation is authorized. An explicit approved
exception is required if a selection criterion cannot be satisfied; listing a
library here does not establish its current license, maintenance or accessibility.

Enhance server-rendered pages progressively. Preserve baseline links, readable
results, native form values/submission and server-rendered errors when an
enhancement is unavailable; do not make the application SPA-first. Initialize
widgets safely after relevant HTMX swaps and clean up replaced instances without
duplicate controls, event handlers or submissions. Load utilities only on
surfaces that need them; Tailwind and the canonical BONIRA tokens remain the
primary styling authority. Do not introduce React, Vue, Alpine or jQuery merely
to implement this policy, or create a frontend framework/plugin registry.

Verify the chosen configuration in Persian, true RTL, mixed-direction data,
responsive layouts, keyboard/focus and screen-reader use, following section 49.
Preserve server-side validation, business rules, authorization, tenant and object
scope, CSRF and D1–D7 surface gating. Remote lookups/grids never broaden access;
client sorting, edits, totals, confirmations and date widgets never become domain
authority. A Jalali widget must preserve canonical server model values and the
existing Gregorian/ISO conversion boundary.

---

## 29. Visual Tokens and Canonical Color System

Keep these consistent:

- dark navy/slate sidebar
- controlled blue primary accent
- neutral light workspace background
- white surfaces
- subtle gray borders
- restrained shadows
- approximately 10–12px radius
- compact enterprise spacing
- consistent focus rings
- semantic status colors only

### Canonical color authority

The authoritative BONIRA color system is maintained separately at:

`design/BONIRA_UI_COLOR_SYSTEM.md`

That file is the **single source of truth** for:

- approved brand colors
- neutral colors
- semantic success/warning/danger colors
- CSS color tokens and aliases
- Tailwind color mapping
- component color rules
- alpha/transparency rules
- approved hexadecimal registry

All UI implementation must use the approved tokens from
`design/BONIRA_UI_COLOR_SYSTEM.md`.

Do not duplicate the full palette in this document. If this document and the
color-system file ever appear to conflict on a color value or color-usage rule,
`design/BONIRA_UI_COLOR_SYSTEM.md` governs color decisions.

Do not introduce arbitrary or near-duplicate colors when an approved BONIRA
token already covers the same semantic purpose. If a genuinely new color is
required, treat it as a Design System change and update the canonical color
system explicitly rather than silently adding a page-local value.

For Tailwind and shared CSS, map the canonical colors once and reuse semantic
tokens/components. Avoid page-specific hard-coded color values.

Official BONIRA logo assets must not be recolored or traced merely to fit a
page-level palette variation.

---

## 30. Approved Reference Pages

The authoritative operational reference is:

- Application Shell
- Dashboard
- Project List
- Project Detail

Other modules should reuse these patterns instead of inventing new visual conventions.

The authoritative Admin reference is the customized Django Admin shell/changelist/changeform patterns defined in this document.

---

## 31. Data and Business Safety

Do NOT:

- modify database schema for UI work
- change table names
- change column names
- rename model fields
- change stored status values
- alter business identifiers
- change permissions
- alter workflows
- change tenant isolation
- move domain logic into templates
- duplicate financial logic in templates/JavaScript
- store Jalali dates in the database
- change model/database date field types for localization
- change API or internal date semantics merely for Jalali presentation
- bypass existing Django validation when converting user-entered Jalali dates

Jalali conversion is explicitly approved only at the user-interface boundary.

Presentation changes must remain presentation-only.

---

## 32. Dates and Jalali Calendar

The ERP is Persian-first, therefore all **user-facing dates** must use the Persian Jalali (Shamsi) calendar.

### Display Rules

Wherever a date is shown to a user, display it in Jalali format.

This includes, where applicable:

- page content
- tables and list pages
- detail pages
- dashboards and KPI/supporting text
- forms showing existing values
- breadcrumbs or contextual metadata
- search/filter summaries
- date-range filters
- reports
- notifications/messages
- Django Admin changelists and change forms
- other user-visible date fields

Use one consistent default format:

`YYYY/MM/DD`

The displayed digits in dates and times must be Persian numerals. This is a
typographic/display rule; it must not alter the canonical stored value.

Example:

Stored/internal Gregorian date:

`2026-09-14`

User-facing Jalali display:

`1405/06/23`

### Date Input Rules

Wherever a user creates, edits, filters, or selects a date:

- provide a Persian Jalali date picker
- the visible/selectable date must be Jalali
- required/optional behavior must remain unchanged
- existing min/max and business validation must remain unchanged
- date-range controls must also use Jalali date selection
- use the same date-picker pattern across the application

Do not force users to manually enter Gregorian dates in Persian-facing forms.

### Storage and Conversion Boundary

Internal storage and backend processing must remain Gregorian/ISO-compatible.

Rules:

- do not change existing model field types
- do not change database schema
- do not migrate stored Gregorian dates to Jalali values
- do not change existing API/internal date semantics
- convert Gregorian → Jalali only for user-facing display
- convert Jalali user input → Gregorian before existing Django validation/storage
- existing saved Gregorian dates must continue to work without data migration
- preserve existing form binding, validation, permissions, workflows, and tenant isolation

The Jalali calendar is a **presentation/input concern**, not a new domain or storage model.

### DateTime Rules

For user-facing `DateTime` values:

- display the date portion in Jalali
- display the time portion with Persian numerals
- preserve the existing time semantics
- do not change timezone behavior
- do not alter stored timestamps
- do not modify technical/API timestamps that are not user-facing

Use the shared Jalali formatter and picker behavior (`erp_jalali`) for both
date and datetime inputs. It must convert a visible Jalali value, including its
time, back to Gregorian/ISO-compatible form before the existing Django
validation and storage flow.

Django forms with `DateField` or `DateTimeField` must inherit
`JalaliDateMixin`; it assigns the shared Jalali widgets and parses submitted
Jalali values before Django validation. A manually authored template date input
must use the shared `erp_jalali` input contract and must not introduce a native
or page-specific Gregorian picker.

### Direction and Digits

Dates should integrate naturally with the Persian RTL interface.

Use explicit direction/isolation where necessary so mixed RTL/LTR content does not become visually reordered.

Do not change canonical technical values merely for appearance.

### Implementation Rules

Prefer one shared, reusable Jalali date formatting/input solution.

Before adding a dependency:

1. inspect the project for an existing Jalali/date-picker library or helper
2. reuse it if suitable
3. do not introduce duplicate date libraries
4. do not introduce a new frontend framework only for date selection

Apply section 28's toolbox and selection criteria without duplicating or
bypassing this shared date-input contract. Any later UI dependency must remain
compatible with Django Templates + Tailwind + HTMX; its adoption needs separate
implementation authority and does not change canonical server-side dates.

### Django Admin

Apply the same Jalali rules to Django Admin where safely possible:

- displayed dates should be Jalali
- editable date fields should use the approved Jalali picker
- native Admin permissions, validation, widgets, save behavior, and workflows must remain intact

### Safety Rule

If Jalali UI conversion cannot be implemented for a specific field without changing business logic, model semantics, database schema, API contracts, or permissions, preserve the existing backend behavior and document the blocker rather than altering the domain layer.

---

## 33. UI Review Strategy

For future work:

1. Prefer shared fixes over page-specific fixes.
2. Do not redesign already approved patterns.
3. Fix real usability/consistency issues only.
4. Validate changes in the running browser.
5. Use screenshots for visual review.
6. Keep changes incremental.
7. Avoid repeated redesign cycles without real user feedback.

Once a pattern is approved, treat it as stable.

---

## 34. Validation After UI Changes

After UI changes, where applicable:

```powershell
.\.venv\Scripts\python.exe manage.py check
git diff --check
```

Also:

- compile modified templates
- verify static files are discovered
- inspect `git diff`
- confirm no unintended backend/domain changes
- manually verify affected pages
- verify RTL/LTR behavior
- verify Jalali display for user-facing dates
- verify Persian-numeral display for business values, amounts, and times
- verify Jalali date pickers for editable/filter date fields
- verify Jalali input converts safely back to existing Gregorian storage behavior
- verify existing Gregorian records render correctly without data migration
- verify desktop/mobile behavior
- verify no corrupted Persian literals remain
- verify modified UI/CSS/templates against `design/BONIRA_UI_COLOR_SYSTEM.md`
- search for newly introduced hard-coded colors and confirm each is an approved
  BONIRA token/derived alpha or a documented Design System change

Database test-permission problems are environment issues and must not trigger UI/domain changes.

---

## 35. Codex Working Rule

At the start of a new UI/UX session:

> Follow applicable `AGENTS.md` instructions and read both `docs/ui-guidelines.md` and `design/BONIRA_UI_COLOR_SYSTEM.md` before UI/UX work. Treat the approved Application Shell, Dashboard, Project List, Project Detail, customized Django Admin patterns, and the canonical BONIRA color tokens as authoritative references. Reuse established components, do not invent near-duplicate colors, and do not modify backend/domain behavior.

In the same session, do not repeat the entire UI specification. Keep prompts task-specific and concise.

---

## 36. Final Principles

**Persian-first.**

**RTL by default.**

**Vazirmatn globally.**

**UTF-8 always.**

**Premium enterprise, not generic CRUD.**

**Right-side navigation, not crowded top navigation.**

**Tables before decorative cards for tabular data.**

**Shared fixes before page-specific hacks.**

**Technical values stay canonical and LTR.**

**Database values remain unchanged.**

**User-facing dates are Jalali; stored/internal dates remain Gregorian/ISO-compatible.**

**All user date entry/filter controls use the approved Jalali date picker.**

**Admin keeps native behavior while matching the ERP design language.**

**`design/BONIRA_UI_COLOR_SYSTEM.md` is the single source of truth for UI colors.**

**Canonical color tokens before arbitrary colors.**

**Consistency before novelty.**

**Usability before decoration.**

**Read backend if necessary; do not modify backend for presentation-only work.**

---

## 37. Tenant, Project, and Site Context

Every business page must make the effective context visible. Context is part of
orientation, not authorization.

- Show the active organization in the shell. On project-owned pages, show the
  project and, when relevant, site/phase in the page header or context bar.
- A context switch must be explicit, preserve only safe filters, and never infer
  access from a URL, hidden field, cookie, or previously selected project.
- Do not render organization IDs as editable business fields. The server resolves
  the organization from the authenticated active membership.
- When a context is unavailable because of permission, tenant state, or archive
  state, render a safe explanation and permitted recovery action. Do not reveal
  names or counts from inaccessible contexts.
- Breadcrumbs describe navigation hierarchy; they do not need to reproduce every
  organization/project label when the context bar already does so.
- Switching project/site must refresh dependent filters and choices. Stale child
  selections are cleared and announced accessibly.

The expected visual order is:

```text
Application shell
  -> organization/project/site context
  -> breadcrumb
  -> page title, status, key actions
  -> alerts/KPIs/tabs
  -> primary content
```

## 38. Context-Aware and Cascading Selection Standard

Use cascading fields whenever one choice constrains another, including:

- organization -> project -> site -> phase
- project -> WBS node -> activity
- party -> role/contact/bank account/contract
- contract -> amendment/item/claim
- warehouse -> available material/bin/lot
- project -> CBS/cost center -> source document
- employee -> effective assignment/project/site

Rules:

1. The server remains authoritative. Client-side filtering improves usability but
   never grants access or replaces cross-tenant/project validation.
2. Initially disable a dependent field until its parent is valid. Its helper text
   must explain what to choose first.
3. On parent change, clear incompatible descendants, cached labels, validation
   errors, and derived values. Never submit an invisible stale identifier.
4. Loading, empty, error, and retry states must be distinct. An empty authorized
   set is not a transport failure.
5. Display only valid and authorized options for the current effective date and
   lifecycle state. Archived items may appear only when required to render
   historical selections, clearly marked as archived/read-only.
6. Preserve the selected label in validation responses. Never leave a raw UUID as
   the only visible value.
7. For HTMX endpoints, apply the same login, CSRF, tenant, permission, object
   scope, and relationship checks as a normal page.
8. Dependent URLs accept the minimum opaque parent identifier. Do not expose a
   general tenant-wide search endpoint when a scoped endpoint is sufficient.
9. Keyboard focus remains predictable after refresh; the result count/change is
   announced through an `aria-live` region when materially useful.
10. Add tests for forged parent/child combinations, cross-tenant IDs, stale
    selection, no-result, permission, and archived-record behavior.

## 39. Searchable Selectors and Large Master Data

Native selects are acceptable for small stable sets. Use a searchable selector
when option count, duplicate names, or remote filtering makes a native select
error-prone.

For MVP-visible forms, references to existing Master Data/business entities must
use one coherent business-facing selector. Free-text canonical names, raw
IDs/UUIDs, duplicate selector/name fields, and multi-control pseudo-selects
(search input + search button + second select) are unacceptable without a
demonstrated business reason. Search belongs inside the selection interaction.
Technical search/result limits are not business UI; load or search further valid
results within the same control. Related masters cascade according to section 38.

MVP-02 uses the shared `SearchChoiceSelect` with locally pinned Tom Select 2.6.2
(core plus virtual-scroll plugin), Persian labels, RTL, escaped business labels,
debounced and paginated authorized lookups, selected-value retention, and the
existing native form submission/validation boundary. Only consuming forms load
its media. The opt-in simple-list fallback evaluates the already scoped queryset
when JavaScript is unavailable; updating dependent lists must not write records.
This implementation is qualified for the remediated MVP-02 surfaces, not an
instruction to rewrite unrelated forms or an assertion of Product Owner approval.

- Search by the identifiers users know: code/number, title/name, and approved
  alternate identifier. Show code plus name, not a name-only ambiguous list.
- Debounce remote requests, enforce a minimum query length where appropriate,
  paginate results, and show total/remaining state without downloading an entire
  master table.
- Scope results before search. Search never broadens tenant/project permission.
- Avoid implicit creation from a selector. “Create new” is a separate authorized
  flow with clear return behavior.
- Preserve selected historical items even if they become inactive, but prevent
  new use when business rules disallow it.
- Apply section 28's optional Tom Select preference when native controls are
  insufficient. A bespoke combobox requires a documented reason plus full
  keyboard, focus, screen-reader and RTL validation; keep dependencies deliberate.

## 40. Inline Item Grids and Transaction Forms

Line-item documents—estimates, orders, receipts, claims, journals, timesheets,
invoices, and similar records—use a reusable grid pattern rather than unrelated
page-specific tables.

- Keep document header/context outside the grid. Freeze or repeat meaningful
  column headers for long lists.
- Every row has a stable client/form identifier. Error messages point to the row
  and field and a summary links to the first error.
- Support keyboard movement and row addition without trapping focus. Never make
  drag-only ordering the sole interaction.
- Numeric cells use `inputmode="decimal"` where useful, canonical submitted
  values, LTR number flow, explicit unit/currency, and server Decimal validation.
- Derived totals are visibly read-only and labelled as provisional until the
  server confirms them. Client calculations do not become authoritative.
- Adding from a master copies only approved snapshot fields; the source link is
  retained when the domain supports it.
- Removing a new draft row may be immediate. Removing a persisted or referenced
  row follows lifecycle rules and may require void/reversal rather than deletion.
- Bulk paste/import requires preview, row-level validation, duplicate detection,
  all-or-nothing vs partial-result disclosure, and a downloadable error report for
  large jobs.
- On mobile, use a row-summary/card editor or horizontal containment with a clear
  primary column. Do not shrink a 12-column grid until it becomes unreadable.

## 41. Enterprise List, Filter, Sort, and Pagination Contract

The list page is a work surface, not just a database dump.

- Store filter, search, sort, page, and page-size state in the URL so permitted
  views can be bookmarked and returned to. Remove empty/default noise.
- Only whitelist server-side sort fields. Use a stable secondary ordering to
  prevent duplicate/missing rows between pages.
- Show active filters as removable chips or a concise summary, a clear-all action,
  and the result count. Do not hide active constraints inside a closed panel.
- Date ranges use the approved Jalali input contract while submitting canonical
  values. Amount/quantity filters always label unit/currency.
- Table headers communicate sort direction and remain usable by keyboard and
  screen reader.
- Bulk actions require an explicit selection model and eligible-count preview.
  Rows the user cannot act on remain excluded; a visible checkbox is never the
  authorization check.
- Use pagination for operational lists. Infinite scroll is unsuitable when users
  must compare rows, select batches, retain position, or cite a result.
- Saved views are a future capability and must preserve permission-safe filter
  definitions, not captured results.
- Consolidate shared filter components; do not create parallel “v2/v3” patterns
  for each domain.

## 42. Detail Pages, Tabs, Source Links, and History

- The header shows title/number, semantic status, primary context, and only the
  actions relevant to the current lifecycle.
- Put summary and exceptions first; use sections for related attributes. Avoid a
  single unstructured key/value wall.
- Tabs are appropriate for substantial, independently addressable sections such
  as items, documents, approvals, settlements, audit, or related costs. Tabs must
  be links with URLs and must not hide validation errors silently.
- Keep the overview light. Large related tables are paginated and permission
  checked independently.
- Show source lineage as human labels and links: “generated from Goods Receipt
  GR-…”, “posted by Journal …”, “based on Rule Version …”. Raw model names and
  UUIDs are secondary diagnostic data, not the main UI.
- Historical records retain the snapshot that was true at finalization. If the
  current master differs, distinguish “recorded value” from “current master”.
- Activity/audit sections show actor, capacity where material, timestamp in tenant
  timezone, action, previous/new status, reason, and source. Sensitive metadata is
  permission filtered.
- Contractual Site Instruction, Variation/Change Order, Claim and EOT pages must
  visibly distinguish requested assumptions from explicitly approved entitlement,
  amount, delay responsibility and EOT days. They must also state that approval
  has no automatic contract-value, schedule-baseline, Billing or financial effect.

## 43. Workflow Actions and My Cartable

The workbench (“کارتابل من”) is the authoritative user action queue; it is not a
copy of Notifications or Audit.

- Each item shows business type/number/title, project/site, current step, why the
  user can act (assignment/candidate/delegation), received/due time, priority, and
  safe preview.
- Group and filter by actionable state, overdue, delegated, project, workflow
  type, and assignment source. Deduplicate multiple candidacies for the same work.
- Claim/release/approve/reject/request-change/reassign actions display current
  state and required reason/evidence. Re-read and authorize inside the transaction.
- A user holding multiple positions remains one identity and one workbench. Show
  the qualifying position as evidence; do not create separate personas.
- After an action, remove or update the item only after server confirmation and
  announce the result. Concurrency conflicts explain that state changed and offer
  a safe refresh; never overwrite another decision.
- High-impact or batch decisions show count, amount/currency, affected project,
  separation-of-duties warning, and a final confirmation.
- Notifications may link to a work item but must not duplicate its lifecycle.

## 44. Financial Values, Calculations, and Reconciliation UX

- Always label currency and distinguish **IRR (ریال)** from **تومان**. Do not use
  an unlabeled “amount”. Conversion for display must be deterministic and must not
  alter stored/accounting values.
- Keep canonical numeric values LTR; localize display separators/digits according
  to the approved convention. Negative amounts need a minus sign plus semantic
  context; color alone is insufficient.
- Quantity shows unit; rate shows its denominator; percentages show the basis.
- Separate budget, commitment, accrued, actual, paid, forecast, and variance.
  Never use one generic “cost” label where meanings differ.
- Calculation panels show formula components, rounding, cap, applied contract-term
  version, applied regulatory-rule version, and source lines when consequential.
- “Draft/proposed/unposted/uncleared/unreconciled” states must be unmistakable.
  Dashboard totals include the statuses and refresh timestamp used.
- Reconciliation views place the two sides, difference, aging, evidence, owner,
  and resolution history together. Resolution never edits source evidence silently.
- Closed-period, posted, paid, or finalized records expose reversal/adjustment/
  replacement actions—not editable fields.

## 45. Attachments, Documents, Imports, and Exports

MVP requires `.xlsx` outputs through a future shared export foundation and the
print targets/priorities in [D5](architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md#5-d5--excel-operational-reporting-print-and-finance-handoff).
Represent only actual source-domain fields and explicitly approved/implemented
gaps; do not invent rates, calculations or financial-system integration. Structured
Excel handoff to finance is the MVP boundary. Required output formats and layouts
are not claimed delivered by this guideline.

- File controls state accepted type, maximum size, confidentiality, and whether
  scanning/processing is pending. Client checks improve feedback; server checks
  remain authoritative.
- Show upload progress, retry/cancel where safe, version number, uploader, time,
  size, checksum/status, links, and classification. Failed uploads are not shown
  as completed documents.
- Preview is permission checked. Download uses a protected endpoint or short-lived
  signed access and is audited where the domain requires it.
- Replacing a finalized file creates a version; it never overwrites evidence.
- Imports use upload -> mapping/options -> validation preview -> explicit commit
  -> result/report. Large imports expose job state and idempotency.
- Exports show scope, active filters, record count when known, sensitivity, format,
  generated-at, expiry, and audit status. Export permission is distinct from view
  permission where data sensitivity requires it.
- OCR/AI extraction displays original evidence, proposed value, confidence or
  warning, reviewer correction, and confirmation. Extraction does not finalize a
  legal or financial record.

## 46. Empty, Loading, Error, Validation, and Disabled States

Every dynamic surface needs all relevant states:

| State | Required behavior |
| --- | --- |
| First-use empty | Explain value and show one permitted next action. |
| Filtered empty | State that no result matches and offer clear filters; do not advertise create unless appropriate. |
| Unauthorized | Safe denial without object existence/detail leakage; give navigation/recovery if permitted. |
| Loading | Preserve layout where possible; announce material asynchronous loading; prevent duplicate submit. |
| Recoverable error | Plain-language cause, retained safe input, retry path, and correlation/reference ID when available. |
| Validation error | Summary plus field/row errors; focus summary; do not discard input or attachments already accepted. |
| Concurrency conflict | Explain that state changed, show current safe state, and require review before retry. |
| Disabled action | Visibly disabled only when the user may know the action exists; explain the exact safe reason and prerequisite. |

Do not disable an action solely to conceal missing permission; omit it when its
existence would leak information. Never rely on disabled HTML controls as a
security control. Server errors must not expose stack traces, SQL, secrets,
internal paths, or other tenants' identifiers.

## 47. Confirmations, Destructive Actions, Archive, Void, and Reversal

- Routine reversible actions do not need confirmation. Ask only when consequence,
  scope, financial/legal effect, or recovery cost justifies interruption.
- A confirmation names the record, action, consequence, related records, and
  recovery mechanism. Do not use a generic “Are you sure?”.
- `Archive` removes a reusable record from new selection while retaining history.
  `Void` declares a transaction invalid with actor/time/reason. `Reverse` creates
  equal-and-opposite evidence. `Delete` is limited to truly disposable drafts or
  approved retention operations.
- Finalized history is never silently edited or deleted. The UI shows the original,
  void/reversal link, replacement if any, reason, actor, and time.
- Typed name/number confirmation is reserved for unusually high-impact actions
  such as tenant cancellation or bulk irreversible operations—not ordinary forms.
- Consequential actions require a reason when the domain requires audit evidence.
  Validate the reason server-side; placeholder text is not evidence.
- Success messages state what changed and what did not, especially when a reversal
  does not itself refund/pay/move cash.

### Accounting control surfaces

Accounting screens distinguish editable drafts from submitted and posted history.
Posted journals, retained reconciliation runs, tie-outs, dispositions, and
independent sign-off evidence are read-only; the UI may initiate only existing
audited service transitions. Present source keys, versions, line identifiers,
reversal/replacement links and opening-import lineage as diagnostic drill-through
evidence, never as editable inputs. Period close/reopen and reversal routes collect
their required reason and independent requester without using the UI as an
authorization decision.

Trial balance, balance sheet and profit/loss screens present explicit IRR scope,
Jalali dates, retained-run hashes and account-to-posted-line drill-through. They
must never merge legacy `financials` or payment projections into ledger facts.
Retained statement and close/reopen history is read-only. A controlled-adjustment
form selects only a posted journal in a closed period and an explicitly configured
open adjustment period, requires reason/evidence/reconciliation references, and
creates a linked draft through the Accounting service; it never edits the source.

## 48. Mobile and Site Workflow Standard

- Design field workflows for sunlight, gloves, intermittent connectivity, one-hand
  use, camera capture, and short attention—not merely a narrower desktop page.
- Prioritize context, task, primary facts, evidence, exceptions, and submit. Hide
  secondary metadata behind progressive disclosure without hiding required rules.
- Touch targets are at least 44 by 44 CSS pixels where practical. Do not place
  destructive and primary actions adjacent without spacing.
- Preserve drafts explicitly. If offline capability is approved, show offline,
  queued, syncing, conflict, failed, and synced states; store the minimum sensitive
  data and define logout/device-loss behavior.
- GPS, camera, QR/barcode, and device data require a clear purpose, permission,
  manual fallback, provenance, and validation. Device data never proves tenant or
  project authorization.
- Provide compressed/resumable upload only after the storage design supports it;
  never silently discard the original required evidence.

## 49. Accessibility, Keyboard, Focus, and Motion

- Meet WCAG 2.2 AA as the product target unless a documented exception is approved.
- All actions, menus, tabs, dialogs, grids, selectors, date pickers, and workbench
  items must be keyboard operable with visible focus. DOM order follows visual RTL
  reading order; do not use positive `tabindex` to patch a broken structure.
- Dialog focus moves to the heading/first meaningful control, is trapped while
  open, and returns to the triggering element on close. Escape closes only when
  cancellation is safe.
- Field errors use programmatic associations; required status is not communicated
  by color/asterisk alone. Status badges have text, not color alone.
- Tables have correct headers/captions and responsive alternatives. Charts include
  a textual summary and accessible data table for decision-critical values.
- Use `aria-live` sparingly for asynchronous validation, list counts, upload and
  workflow results. Avoid repeated noisy announcements.
- Respect reduced-motion preferences. Animation communicates transition/progress;
  it never delays work or becomes the only status cue.
- Mixed Persian/English/numeric content uses appropriate `dir`/`bdi` boundaries.

## 50. Permission-Aware, AI-Assisted, and Audit-Visible Actions

- Navigation and actions reflect permissions to reduce confusion, but every read
  and mutation is re-authorized server-side against tenant, object scope, state,
  assignment/candidacy, separation rule, and tenant lifecycle.
- For a visible-but-unavailable action, explain whether the blocker is state,
  missing required data, closed period, assignment, tenant suspension, or another
  safe prerequisite. Do not expose names of unauthorized approvers or records.
- AI output is labelled as assistance, includes sources/evidence where possible,
  distinguishes extracted fact from generated suggestion, and supports correction.
- Before an AI-assisted consequential action, show the exact structured changes,
  validation results, affected objects and permissions. The user explicitly
  confirms; the ordinary domain service performs the action.
- Record model/provider/version as permitted, prompt/template version, source
  references, reviewer, accepted/rejected result, and resulting domain audit event
  without storing unnecessary sensitive prompt content.
- Audit/history links appear on security, financial, contractual, workflow, master
  governance, import/export, and support-access surfaces when the viewer has the
  dedicated permission. Audit evidence is not editable.

## 51. Pattern Acceptance Checklist

For MVP release, apply the strategy's browser journey verification,
tenant/permission isolation, P0 Excel, critical print, no-blocking-defect and
Human UAT criteria. Recognize `MVP` release and `FULL_ERP` internal verification
profiles without assuming runtime switches exist. Preserve historical
hidden-capability UAT as regression evidence; backend presence or prior finding
closure is not customer-exposure acceptance.

Every UI package requires Human visual acceptance before Product Owner closure.
Automated functional PASS and browser interaction PASS do not grant visual
acceptance. Record remediation as `READY_FOR_HUMAN_REVIEW` only after its required
checks/evidence pass; Product Owner visual acceptance remains `PENDING` until the
Human Product Owner explicitly accepts it.

Before a new or materially changed screen is accepted, verify:

- active tenant/project/site context and server authorization;
- Persian copy, RTL layout, mixed-direction values, Jalali display/input, and
  explicit Rial/Toman/unit behavior;
- desktop, tablet, small mobile, long Persian text, empty, dense, loading, error,
  disabled, unauthorized, archived and finalized states;
- keyboard-only operation, focus order/return, screen-reader names, error summary,
  contrast, reduced motion, and touch targets;
- cascading selectors against forged/stale/cross-tenant choices;
- URL-stable list filters/sort/pagination and stable ordering;
- duplicate-submit and concurrency behavior;
- audit/source lineage, document evidence, reversal/void wording, and calculation
  explanation where relevant;
- template reuse and absence of page-local inline styles or duplicated components;
- compliance with `design/BONIRA_UI_COLOR_SYSTEM.md`, including absence of new
  arbitrary or near-duplicate color values; and
- representative browser verification plus applicable Django/template/tests and
  Ruff checks.
