# BONIRA Product Vision and MVP Release Strategy

**Status:** approved and frozen Product Decision Baseline D1–D7, reconciled 2026-10-28.
**Role:** canonical product positioning, capability exposure and release strategy.
**Boundary:** documentation direction only; no product implementation or production authorization.

## 1. D1 — Vision and positioning

The official product name is **بنیرا / BONIRA**. Its long-term vision is a full
multi-tenant Construction ERP for construction contractors. Its current commercial
positioning is **سامانه مدیریت عملیات پیمانکاری و کارگاهی** and its canonical
tagline is **«سامانه مدیریت یکپارچه کارگاه، پیمان و تدارکات عمرانی»**.

The current commercial release strategy is an MVP-focused product surface over
the full platform. Full Construction ERP remains the future vision. Capability
inclusion below defines approved MVP exposure requirements; it does not claim
that a released or centrally gated MVP surface already exists.

This document records the Human-approved D1–D7 baseline. It does not amend CEP
Scope/AC/DoD, dependencies, live Registry state, domain authority, financial rules,
or existing production gates. The [program authority](../governance/CEP_PROGRAM_AUTHORITY.md),
[execution policy](../governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md),
[Roadmap](../../ROADMAP.md) and [Registry](../../CEP_EXECUTION_REGISTRY.yaml)
retain their established responsibilities. Dated snapshots, prompts, completion
reports, decision packets and audit/execution evidence retain their original meaning.

## 2. D2 — Capability-level MVP surface

The MVP is a **Capability-level Product Surface** over the existing full platform;
it is not a reduced backend. Exposure is determined per capability, not necessarily
per Django app. A mixed domain may contribute an MVP operation while its other
surfaces remain hidden.

### Approved MVP-visible capability families

| Family | Included capabilities |
| --- | --- |
| Project & Site Operations | Projects / Sites / WBS / Phases; Daily Reports; Field Workers / simplified Workforce UI; Timekeeping; Equipment; Expenses / Petty Cash; Safety; Quality |
| Contract & Claims | Estimates / BOQ; Contracts; subcontractor-related capabilities; Billing / Progress Claims; Adjustments; Deductions |
| Procurement & Materials | PR; RFQ; PO; GRN; Materials; Inventory |
| Shared Business Services | Parties; Documents; Workflows / My Tasks; Operational Reports; Excel/XLSX exports; Print outputs |
| Platform Foundation | Accounts; customer-facing Organization/user/access administration; appropriate Audit visibility |

### Backend-active, MVP UI-hidden capabilities

Accounting, Subledgers, Treasury, Financials, Fixed Assets, Payroll, Full HR / ESS,
non-MVP Commercial capabilities, Compliance, Partner Qualification, Support,
Knowledge, technical/platform administration surfaces, and technical
reconciliation/reporting surfaces remain outside the MVP user surface.

**UI-Hidden** means excluded from MVP customer exposure. It does not mean removed,
deprecated, abandoned or backend-disabled, nor does backend-active imply that all
future behavior or statutory/production activation is implemented or authorized.
Existing domain-specific fail-closed activation controls remain authoritative.

No Django app, existing model, FK, migration, domain relationship, required handoff,
workflow, resolver or service is removed merely because its UI is hidden. Existing
backend workflows and required integrations retain their ownership and contracts.
Future additive schema evolution remains allowed for explicitly approved MVP gaps
under separately authorized, non-destructive implementation work. Tender and claim
concepts stay within existing domains; no independent `tenders` or `claims` Django
apps are introduced by this strategy.

Capabilities are hidden to focus onboarding, usability and release verification
on contractor operations, contracts and materials while the broader ERP matures.
Their existing backend value and future ERP role are preserved.

## 3. D3 — Centralized exposure authority and navigation

All UI exposure should eventually follow **one centralized Product Surface
Exposure authority**. Its implementation mechanism is deliberately not frozen
here. Scattered ad-hoc hiding logic must not become the product architecture.

Gating covers navigation, dashboards, search, quick actions, cross-module links,
breadcrumbs, shortcuts and direct user-facing URL access. Backend-active does not
entitle an MVP user to browse a hidden capability's URL. Required backend handoffs
remain intact; a visible operation must not depend on exposing a hidden workspace.

Product Surface Gating never replaces Authentication, Authorization, Tenant
Isolation, Business Permissions or Object/Project/Site Scope. Exposure is an
additional product boundary, not a permission grant or an alternative security
system.

The final MVP navigation groups are:

| Group | Persian label |
| --- | --- |
| `PROJECT & SITE OPERATIONS` | عملیات پروژه و کارگاه |
| `CONTRACT & CLAIMS` | پیمان، متره و صورت‌وضعیت |
| `PROCUREMENT & MATERIALS` | تدارکات، مصالح و انبار |
| `SHARED BUSINESS SERVICES` | کارتابل، اسناد و گزارش‌ها |
| `PLATFORM FOUNDATION` | تنظیمات و مدیریت دسترسی |

These are approved navigation targets, not a statement about current menus or routes.

## 4. D4 — Field workforce

MVP field-worker functionality reuses the existing `workforce` and `timekeeping`
domains. There is no new parallel `Worker` domain/model. The simplified UI target
includes identity/basic personnel information, role/skill, crew, project/site
assignment, active state, attendance and work time. Full HR, Payroll and full ESS
remain UI-hidden.

Preserve `User` authentication identity, tenant-owned `Person`, effective-dated
`WorkRelationship` and governed legacy `Employee` compatibility boundaries.
Do not infer workforce identity or grant access from an email, username, role/skill
or crew assignment. Attendance, Timesheet and Overtime remain distinct backend
concepts even if a future UI combines them into one simple operator workflow.

`national_id` for non-login field workers is an **approved MVP Gap** requiring
future additive, non-destructive design. Existing login-user national ID support
does not close that gap or authorize a migration in this task.

## 5. D5 — Excel, operational reporting, print and finance handoff

`.xlsx` export is required for the MVP. Future implementation should use a shared
export foundation rather than unrelated per-domain implementations. Fields must
come from real domain sources of truth or explicitly approved and implemented MVP
gaps. Invented fields, formulas, rates or semantics must never be represented as
existing functionality. Existing CSV, JSON, document-upload support or export
manifests alone do not prove the required XLSX outputs.

| Priority | Ordered Excel targets |
| --- | --- |
| P0 | 1. Billing; 2. Procurement; 3. Inventory; 4. Expenses |
| P1 | 5. Daily Reports; 6. Estimates; 7. Timekeeping / Equipment |

BONIRA's current MVP financial-system boundary is **structured Excel handoff to
finance/accounting teams**. Direct Sepidar or Hamkaran System API integration is
not claimed; any such integration needs actual implementation and separate
approval. This commercial boundary does not transfer Treasury cash authority,
Accounting GL authority, AP/AR, Payroll, Inventory value or Project Controls cost
authority to exports or reports.

Required MVP print targets are Progress Claim / Billing, Purchase Order, GRN,
Daily Report, and Expense / Petty Cash summary. A target is not proof that its
print layout already exists or is qualified.

MVP Reporting focuses on operational/project/site/contract/procurement/inventory/
workforce/equipment/safety/quality views. Technical accounting reconciliation and
internal reporting surfaces remain hidden. Reports and exports remain scoped,
permission-checked projections over source-owned records, never financial or
transaction authorities.

## 6. D6 — Quality, journeys and release criteria

MVP does not mean prototype-quality UI. Visible screens target Persian-first,
true RTL, responsive, enterprise-quality, business-user-friendly operation with
zero critical technical leakage. The [UI guidelines](../ui-guidelines.md) retain
their design-system role.

Core MVP journeys are:

1. `Project → Site → Daily Report → Workers/Timekeeping → Equipment → Safety/Quality`
2. `Estimate → Contract → Progress Claim → Adjustments/Deductions → Approval → Excel/Print`
3. `PR → RFQ → PO → GRN → Inventory`

These are user journeys, not authorization for new automatic domain effects.
Existing source/consumer contracts govern every handoff.

The testing strategy recognizes two explicit surface profiles:

| Profile | Purpose |
| --- | --- |
| `MVP` | Verification of the approved customer surface and core journeys |
| `FULL_ERP` | Internal/verification surface concept for broader platform regression safety |

`FULL_ERP` is not evidence of production readiness or commercial exposure. These
profile names do not establish runtime configuration or profile-switch behavior.
Preserve historical UAT scenarios and their evidence: MVP-related scenarios become
release-gate evidence within their proven coverage/build limits; hidden-capability
scenarios remain regression-safety evidence. A historical PASS never proves new
gating, a new output or an untested journey. Existing journey `CORRECT`, finding
closure and CEP completion states are not MVP exposure decisions.

MVP release direction requires browser-level journey verification, tenant/permission
isolation, P0 Excel outputs, critical print outputs, no blocking MVP defect and
Human UAT. These criteria supplement rather than rewrite canonical production
gates; this documentation issues no release PASS, Human Sign-off or certification.

## 7. D7 — Progressive evolution

Hidden capabilities remain part of BONIRA's future ERP vision. The evolution path is:

`MVP → Initial Customers → Feedback → Revenue → Team Expansion → Capability Maturation → Progressive Capability Exposure → Full BONIRA Construction ERP`

A future capability does not become customer-visible merely because a model,
view or service exists. Exposure requires appropriate acceptance criteria, usable
UI, browser verification, authorization/tenant isolation, required outputs and
integrations where applicable, absence of release blockers, and Human UAT.
Capability maturity and progressive exposure preserve the full architecture;
neither backend existence nor UI hiding changes domain authority.

## 8. Implementation and evidence boundary

This reconciliation itself grants no implementation authority. Under the separate
2026-10-29 MVP-01 instruction, the bounded Development exposure foundation is now
implemented in `core/product_surface.py`: default `MVP`, an explicit server-owned
`FULL_ERP` internal verification setting, shared navigation/Home/shortcut filtering,
and direct HTTP denial for hidden capabilities. There is no customer profile switch.
[MVP-01 evidence](../governance/mvp/MVP-01_COMPLETION_REPORT.md) records the bounded
browser, authorization and backend-preservation verification and baseline findings.

New Workers UI, non-login workforce national-ID migration, shared XLSX framework,
required print layouts and complete browser E2E coverage remain requirements for
separately authorized work. Existing screens, exports and tests retain only their
verified scope. This implementation issues no commercial-readiness claim, Human
Sign-off or Production Certification.

Code, migrations, tests and configured environment behavior remain implementation
reality. The [current model guide](DOMAIN_AND_DATA_MODEL.md) describes backend
boundaries; target domain/data references describe the full future platform;
neither is a customer-exposure matrix. The [dated project record](../PROJECT_STATUS.md)
and retained historical evidence are not rewritten to match this strategy.
