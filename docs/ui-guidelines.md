# ERP UI/UX Guidelines

## 1. Purpose

This document defines the approved UI/UX standard for the Persian RTL ERP application.

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

If the logged-in user has permission, standard Add/Create actions must remain visible.

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

---

## 29. Visual Tokens

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
- implement Jalali conversion unless separately approved

Presentation changes must remain presentation-only.

---

## 32. Dates

Do not change stored dates.

Do not introduce Jalali calendar behavior unless explicitly approved as a separate task.

Keep date presentation visually consistent with the Persian interface while preserving original values.

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
- verify desktop/mobile behavior
- verify no corrupted Persian literals remain

Database test-permission problems are environment issues and must not trigger UI/domain changes.

---

## 35. Codex Working Rule

At the start of a new UI/UX session:

> Follow applicable `AGENTS.md` instructions and read `docs/ui-guidelines.md`. Treat the approved Application Shell, Dashboard, Project List, Project Detail, and customized Django Admin patterns as the authoritative visual reference. Reuse established components and do not modify backend/domain behavior.

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

**Admin keeps native behavior while matching the ERP design language.**

**Consistency before novelty.**

**Usability before decoration.**

**Read backend if necessary; do not modify backend for presentation-only work.**
