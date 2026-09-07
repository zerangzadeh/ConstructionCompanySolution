# ERP UI/UX Guidelines

## Purpose

This document defines the approved UI/UX direction for the ERP application.

It is the shared visual and implementation reference for all future UI work, especially when work is performed in a separate Codex account or session.

The objective is to maintain a professional, elegant, Persian-first, enterprise-grade interface while preserving all existing backend behavior.

---

## Scope

UI/UX work may include:

- Django Templates
- shared layouts
- template partials/includes
- Tailwind CSS
- frontend styling
- Persian RTL presentation
- responsive behavior
- accessibility improvements
- UI-only JavaScript
- HTMX behavior only where it does not change business semantics
- visual consistency across modules

The following are strictly out of scope unless explicitly approved:

- models
- services
- repositories
- permissions
- authorization logic
- tenant isolation
- workflows
- business rules
- database behavior
- migrations
- domain logic
- validation semantics
- lifecycle behavior
- backend architecture

Backend files may be inspected when necessary to understand the existing application, but they must not be modified as part of UI/UX work.

---

## Design Direction

The ERP interface should feel:

- professional
- elegant
- modern
- calm
- reliable
- enterprise-grade
- information-dense without feeling crowded
- suitable for long daily use
- visually consistent
- efficient for operational users

Avoid:

- excessive gradients
- glassmorphism
- decorative dashboards
- oversized cards
- excessive whitespace
- overly rounded elements
- flashy animations
- consumer-app styling
- inconsistent colors
- excessive icons
- unnecessary frontend dependencies

The desired visual character is:

**clarity + reliability + precision + restraint**

---

## Persian and RTL

The application is Persian-first.

Use:

```html
<html lang="fa" dir="rtl">
```

RTL is the default reading direction.

Use a high-quality Persian UI font, preferably:

**Vazirmatn**

Typography must be centralized globally.

Do not automatically convert business or technical values to Persian digits.

Use explicit LTR rendering where needed for:

- project codes
- contract numbers
- payment numbers
- UUIDs
- email addresses
- URLs
- IP addresses
- technical identifiers
- version numbers

Mixed Persian/English values must not appear visually reversed.

---

## Application Shell

### Desktop

Use:

- right-side sidebar
- compact top header
- central content area
- light neutral application background
- white content surfaces

Recommended sidebar width:

**240–270px**

Sidebar should be visually quiet and support:

- active item state
- hover state
- compact icons
- clear Persian labels
- grouped navigation where useful

### Mobile / Tablet

Use:

- off-canvas navigation
- compact header
- accessible actions
- responsive spacing

Do not force desktop navigation into narrow screens.

---

## Typography

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

Prioritize readability and compact enterprise usage.

---

## Colors

Use:

- neutral application background
- white surfaces
- subtle gray borders
- dark neutral text
- muted secondary text
- one controlled primary accent color

Preferred primary direction:

**professional blue / indigo / slate-blue**

Do not use strong saturated colors across large surfaces.

---

## Semantic Status System

Use only five semantic badge families:

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

Do not create arbitrary colors for individual statuses.

Existing business status values must not be changed.

---

## Surfaces

Cards and panels should use:

- white background
- subtle border
- very light shadow only when useful
- approximately 10–12px border radius

Prefer borders and spacing over heavy shadows.

---

## Spacing

Use the existing Tailwind spacing scale.

Keep spacing consistent for:

- page padding
- card padding
- section gaps
- form grids
- table cells
- action groups
- filters

Avoid arbitrary pixel values where Tailwind spacing utilities already exist.

ERP screens should be compact enough for productivity.

---

## Buttons

Use four standard button styles:

### Primary
Main action:
- Create
- Save
- Submit
- Confirm

### Secondary
Supporting action:
- Edit
- Export
- Back
- Duplicate

### Danger
Destructive action:
- Delete
- Revoke
- Permanent cancel

### Ghost
Low-priority action:
- More
- View
- inline actions
- menu triggers

All buttons should have:

- consistent height
- hover state
- focus state
- disabled state
- consistent icon placement

Avoid multiple dominant primary buttons on one page.

---

## Forms

Forms should follow these rules:

- RTL reading order
- label above input
- approximately 42–44px field height
- clear focus state
- subtle borders
- consistent radius
- two-column desktop layout where appropriate
- one-column mobile layout
- logical section grouping
- help text near the field
- validation errors immediately below the related field
- clear required/optional distinction
- visually distinct read-only/disabled states

Preserve all existing Django validation behavior.

Recommended sections:

- basic information
- classification / organization
- dates / planning
- financial information
- additional information

Do not introduce new workflow actions.

---

## Tables

ERP tables are a primary interaction pattern.

Use:

- compact readable rows
- consistent header height
- consistent row height
- clear hover state
- right-aligned Persian text
- explicit LTR for technical values
- consistent numeric alignment
- semantic badges
- consistent action column
- row-actions menu
- pagination
- empty state
- responsive behavior

For wide ERP tables:

**Prefer horizontal scrolling instead of converting rows into cards.**

Preserve tabular readability.

---

## Search and Filters

Use a reusable filter toolbar.

Typical fields may include:

- keyword search
- status
- category/type
- organization
- manager/user
- date filters

Desktop:

- inline toolbar

Mobile:

- collapsible filter panel

Do not expose filters unsupported by the backend.

---

## Empty States

Use two patterns.

### No Records Yet

Example:

> هنوز پروژه‌ای ثبت نشده است.

Provide the relevant primary action when permitted.

### No Search Results

Example:

> نتیجه‌ای مطابق فیلترهای انتخاب‌شده پیدا نشد.

Provide a clear-filter action.

Avoid decorative illustrations.

---

## Breadcrumb

Use a compact breadcrumb.

Example:

`پروژه‌ها / پیاده‌سازی ERP / جزئیات`

Breadcrumb should remain visually secondary.

---

## Tabs

Use tabs for complex entity detail pages.

Example Project Detail tabs:

- خلاصه
- اطلاعات پروژه
- قراردادها
- برآوردها
- پرداخت‌ها
- اسناد
- گزارش‌های روزانه
- اعضای پروژه
- فعالیت‌ها

Only show sections supported by the application.

Tabs should:

- support RTL
- clearly indicate active state
- remain compact
- scroll horizontally on mobile when required

---

## Detail Page Pattern

Entity Detail pages should generally follow:

1. Breadcrumb
2. Entity header
3. Name / code / status
4. Primary actions
5. Optional summary/KPI cards
6. Tabs / section navigation
7. Main information sections
8. Related-domain lists
9. Activity / metadata where available

Detail pages must support fast scanning.

Do not render read-only information as disabled form inputs unless necessary.

---

## KPI Cards

Use KPI cards only for useful summary information already provided by business logic.

Examples:

- status
- completion percentage
- approved amount
- paid amount
- remaining amount
- start date
- end date

Do not invent new calculations in templates or JavaScript.

Keep KPI cards compact.

---

## Related Lists

Use compact related-domain sections for:

- contracts
- estimates
- payments
- documents
- daily reports
- users/team

Typical structure:

- section title
- count if available
- view-all action
- compact list/table
- create action when permitted

Avoid large nested tables on overview screens.

---

## Project Reference Pages

The approved visual reference for the ERP should be established through:

### 1. Project List

Reference for:

- table
- search
- filters
- status badges
- pagination
- row actions
- empty states

### 2. Project Create/Edit

Reference for:

- enterprise forms
- grouped fields
- validation
- responsive layout
- action hierarchy

### 3. Project Detail

Reference for:

- breadcrumb
- page header
- code/status
- primary actions
- summary/KPI cards
- tabs
- information sections
- related-domain lists

Once approved, these pages become the authoritative UI reference for:

- Contracts
- Estimates
- Payments
- Documents
- Organizations
- Reports
- other ERP modules

Future modules should reuse the established patterns rather than create new visual conventions.

---

## Dashboard

Dashboard design should prioritize operational usefulness.

Use existing reliable data only.

Possible elements:

- active projects
- contracts requiring attention
- pending estimates
- outstanding payments
- recent reports/documents
- recent activity

Do not add fake metrics or random charts.

If reliable chart data is unavailable, use summary cards and lists.

---

## Responsive Principles

Desktop is the primary ERP experience.

### Desktop
- right sidebar
- multi-column forms
- wide tables
- full action toolbar

### Tablet
- reduced spacing
- compact/off-canvas sidebar

### Mobile
- off-canvas navigation
- one-column forms
- horizontally scrollable tables
- compact page header
- accessible actions

Do not sacrifice desktop usability in order to force mobile card layouts.

---

## Accessibility

Ensure:

- visible keyboard focus
- sufficient contrast
- semantic form labels
- accessible button states
- accessible icon-only controls
- understandable validation messages
- keyboard-friendly inputs

Preserve existing Django accessibility behavior.

---

## Template Architecture

Prefer reuse of existing templates and partials.

A reasonable target structure may include:

```text
templates/
    base.html
    layouts/
        app_shell.html
    partials/
        sidebar.html
        header.html
        breadcrumb.html
        page_header.html
        messages.html
        pagination.html
        empty_state.html
    components/
        button.html
        badge.html
        form_field.html
        section_card.html
        tabs.html
        description_list.html
        stat_card.html
```

Do not blindly create this structure.

First inspect the existing project and reuse current components where possible.

Avoid duplicate templates and parallel UI systems.

---

## Tailwind Rules

Use the existing Tailwind setup.

Prefer:

- reusable utility combinations
- shared template partials
- centralized global typography
- minimal global CSS

Avoid:

- per-page CSS
- large custom CSS files
- unnecessary arbitrary values
- new design dependencies

---

## Interaction Principles

Interactions should feel:

- predictable
- immediate
- calm
- consistent

Avoid unnecessary animation.

If transitions are used, keep them subtle and functional.

---

## ERP Usability Principles

Design for users who may spend many hours per day in the system.

Optimize for:

- scanability
- low cognitive load
- consistency
- efficient data entry
- predictable actions
- clear feedback
- readable tables
- quick navigation
- minimal visual noise

The interface should remain professional over time.

---

## Django Admin

Django Admin should use the same visual language but does not need to copy the operational ERP layout exactly.

Use the same:

- Persian typography
- RTL direction
- primary colors
- semantic status system
- table density
- form styling
- spacing
- technical LTR rules

Preserve native Django Admin behavior and administrative workflows.

Principle:

**Same design language, different interaction pattern.**

---

## Codex Working Rules

When working on UI/UX:

1. Inspect the current frontend structure first.
2. Read backend files only when necessary to understand existing behavior.
3. Do not modify backend/domain files.
4. Prefer existing templates and partials.
5. Avoid unrelated refactoring.
6. Keep changes incremental.
7. Reuse established UI patterns.
8. Run relevant checks/tests after changes.
9. Review `git diff` for accidental backend changes.
10. Report genuine blockers only.

---

## Approval Rule

Once the Project reference pages are approved, future UI work must treat them and this document as authoritative.

Future Codex sessions should begin with:

> Read `docs/ui-guidelines.md` and inspect the approved Project pages before making UI changes. Reuse the established patterns. Do not redesign the UI system unless explicitly requested.

---

## Final Principle

UI work must improve presentation and usability without changing application behavior.

**Read backend if necessary; do not modify backend.**

**Reuse before creating.**

**Consistency before novelty.**

**Enterprise usability before decoration.**
