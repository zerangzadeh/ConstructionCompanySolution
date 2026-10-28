# Product and Business Model

**Status:** approved product-direction reference; commercial terms remain Product Owner decisions

## 1. Product thesis

بنیرا / BONIRA is a Persian-first, multi-tenant platform for construction and
contracting companies. Its long-term vision is Full Construction ERP, connecting
field evidence and commercial documents to approvals, project cost, claims, cash,
accounting, compliance and management decisions.

Its current commercial positioning is **سامانه مدیریت عملیات پیمانکاری و کارگاهی**,
with the canonical tagline **«سامانه مدیریت یکپارچه کارگاه، پیمان و تدارکات عمرانی»**.
The [frozen D1–D7 strategy](PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md) defines
the capability-level MVP surface over the full backend, its exposure families,
release requirements and progressive evolution. MVP is the current commercial
release strategy; it does not abandon the ERP architecture or certify delivery.

The product is not positioned as a generic accounting application, CRM, BPMN
platform, BIM authoring suite or scheduler replacement. It owns construction ERP
business logic and integrates with specialist systems where justified.

## 2. Target customer segments

| Segment | Primary problem | Product response |
| --- | --- | --- |
| Small contractor | Fragmented spreadsheets/paper, owner-dependent approvals, limited specialist staff | Optional structures, owner-fallback workflows, simple masters and guided integrated processes |
| Growing multi-project contractor | Cross-project access, cost/control inconsistency, procurement and claim handoffs | Project/site scope, shared masters, workflow/workbench, Project Cost and reconciliation |
| Formal mid-market/enterprise contractor | Separation of duties, complex commercial/financial control, payroll/compliance, audit and portfolio reporting | Configured routing, effective rules, accounting/Treasury, governed data, operational evidence and production controls |
| Specialist subcontractor/supplier participant | Repeated document/quote/claim submission and status uncertainty | Future invitation-scoped portal, not automatic full tenant/network membership |

One core model supports these segments. Enterprise structures remain optional so
small customers do not inherit unnecessary setup or UI complexity.
The responses above describe the full product vision; financial, payroll and
other hidden capabilities are not current MVP customer-exposure promises.

**Initial focus accepted (2026-09-24, P0-D01):** growing multi-project contractors
lead onboarding and validation; the shared model and small-contractor usability
remain. Pilot customers and representative workload sizes are still open. See
[S03 approval evidence](../ROADMAP_EXECUTION_PLAYBOOK.md#s03-approval-evidence-and-current-decisions).

## 3. Buyer, user, and stakeholder groups

- Economic buyer: owner/executive leadership seeking project profitability,
  cash/commercial control and reduced operational leakage.
- Operational sponsors: project, procurement, commercial, finance, workforce,
  warehouse/equipment, HSE and QA/QC managers.
- Daily users: site supervisors, engineers, quantity surveyors, buyers,
  accountants, storekeepers, payroll/workforce staff and document controllers.
- External participants: suppliers, subcontractors, consultants and clients
  through explicitly approved portal/document workflows.
- Assurance stakeholders: auditors, legal/accounting reviewers, support/security
  operators and statutory authorities through controlled evidence/exports.

These are full-platform stakeholders. MVP daily use focuses on project/site,
commercial, procurement/materials and shared operational services; finance teams
receive structured Excel handoff. Full HR/ESS, Payroll and technical/platform
administration remain outside the MVP user surface as defined by D2.

`USER_CAPABILITY_MAP.md` defines user goals and capability access. Exact
authorization remains code/permission-registry owned.

## 4. Customer value propositions

The following describe long-term platform value. Current MVP delivery focuses on
operational traceability and contractor workflows, with required XLSX/print
outputs; native financial and statutory capabilities are not MVP UI promises.

1. **One traceable operating record:** enter facts once at their source and reuse
   them across workflow, cost, claims, payroll, finance and reporting.
2. **Construction-specific commercial control:** contract/BOQ, progress,
   certificates, retention, advance, guarantees and subcontractor flows.
3. **Project cost integrity:** distinguish budget, commitment, accrual, actual,
   paid, forecast and variance with source drill-through.
4. **Iranian operational fit:** Persian RTL/Jalali/Rial-Toman clarity and
   effective-dated tax, taxpayer-invoice, payroll and insurance integration after
   legal verification.
5. **Controlled flexibility:** small-tenant defaults plus bounded configurable
   workflows for larger organizations—without tenant executable code.
6. **Paperless evidence and exception work:** versioned documents, mobile field
   capture, workbench, reconciliation and overdue/exception queues.
7. **Decision trust:** governed KPIs and explanations tied to source transactions.

## 5. Product capability layers

These architectural layers preserve the full ERP vision. They are not release
packages or an app-level exposure matrix. D2 owns capability-level inclusion:
hidden UI leaves backend services, models and required handoffs intact while
capabilities mature for future exposure.

| Layer | Capabilities | Business role |
| --- | --- | --- |
| Foundation | Tenant, identity, authorization, masters, DMS, workflow, audit, operations | Trustworthy multi-tenant operation |
| Construction operations | Projects/WBS, field, procurement, inventory, equipment, HSE/QA, workforce | Capture and control execution |
| Commercial control | Estimate/BOQ/budget, contracts, variations, claims, guarantees, partner qualification | Manage commitment, progress and exposure |
| Financial control | Accounting, AP/AR, Treasury, payroll, assets, Project Cost and reconciliation | Produce controlled books, cash and profitability facts |
| Knowledge and support | Knowledge, notifications, support platform and cited assistive AI | Reuse experience and reduce resolution time |
| Ecosystem | Private partner portal, later consented network/intelligence | Reduce external handoff friction; network only after governance maturity |

## 6. Packaging and monetization direction

Plan, entitlement and quota capability is approved target scope. On 2026-09-24 the
Product Owner accepted P0-D05: one core plan, versioned entitlements and justified
user/project/storage limits, with initial subscription invoicing administered
externally. Warn before limits and reject usage-increasing operations at the cap
while preserving authorized existing work, history and export. This does not alter
construction Billing/claims scope. Exact commercial and lifecycle parameters remain
open. The product should support a coherent combination of:

- organization subscription state;
- entitled modules/capabilities;
- justified user, project, storage or processing limits;
- grace, suspension and cancellation rules;
- export/retention/offboarding obligations; and
- usage visibility before enforcement.

Do not equate plan enforcement with application authorization. A user still needs
membership, business permission, object scope and valid lifecycle state.

Open Product Owner parameters include trial/onboarding, pricing/metric definitions,
quota values, the named external invoicing operator, overage/upgrade rules, grace
and cancellation policy, contract/support levels, data residency and numeric
RPO/RTO. See [S03 open inputs](../ROADMAP_EXECUTION_PLAYBOOK.md#unresolved-parameters-and-latest-gates).
`ROADMAP.md` P0.3 schedules the foundation; the accepted initial policy does not
include an in-product SaaS subscription billing engine.

## 7. Adoption and operating model

**Accepted direction (2026-09-24, P0-D02–D04):** native Accounting, Treasury and
AP/AR; product-accountable SaaS using managed services subject to suitability; one
core recovery baseline. Provider/residency, named operational owners and quantified
recovery commitments remain open. Approval evidence is in the S03 record linked
above; implementation, detailed ADRs and production certification are separate.

This accepted native financial architecture remains intact behind the MVP
surface. The current MVP financial-system boundary is structured Excel handoff
to finance/accounting teams; direct Sepidar or Hamkaran System API integration
is not claimed or authorized by this strategy.

Current adoption follows the three integrated MVP journeys in
[D6](PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md#6-d6--quality-journeys-and-release-criteria),
then initial customers, feedback, revenue, team expansion, capability maturation
and progressive exposure toward Full BONIRA Construction ERP. Existing backend
availability alone is insufficient for customer exposure. The Roadmap and
canonical contracts retain technical dependency and execution authority.

Onboarding requires organization settings, role/scope design, master-data import,
project structures, numbering/rules, workflow templates, opening financial facts
where applicable, training and reconciliation. Imports are previewed and audited;
the product must not turn spreadsheet inconsistency into authoritative data.

## 8. Service and support model

This is the full-platform operating model. Support capability screens and
technical administration remain MVP UI-hidden; this does not remove the
operator's support, incident or recovery responsibilities.

- Product support uses cases, known issues, feature requests, release linkage,
  safe diagnostics and SLA analytics.
- Normal tenant support access is purpose-limited, scoped, time-bounded, revocable
  and audited, with understandable approval by an authorized tenant user plus
  independent platform approval; there is no silent standing access. When tenant
  approval is practically impossible in a genuine emergency, revised Q04-F2
  permits only a separately reviewed, highly restricted, independently approved,
  minimum-scope, short-lived and fully attributed emergency path.
- An AI Support Assistant may retrieve cited approved knowledge and propose
  diagnostics/troubleshooting. It cannot bypass permissions or finalize actions.
- Operational ownership includes incident response, status communication,
  backup/restore, migration/rollback, security patching and dependency review.

## 9. Differentiation strategy

The defensible differentiator is not maximum feature count. It is:

- field-to-finance traceability;
- Iranian contractor/compliance adaptability without hard-coded annual rules;
- clear domain ownership and reconciliation;
- low duplicate entry through reviewed upstream handoffs;
- Persian-first exception-driven UX;
- bounded workflow that supports small and structured contractors; and
- explainable knowledge, partner and KPI evidence.

Commodity infrastructure should be reused. Strategic construction calculations,
posting mappings, commercial rules, project costing, workflow-domain commands and
reconciliation definitions remain product-owned and tested.

## 10. Ecosystem and network strategy

The private supplier/subcontractor portal is a scheduled bilateral collaboration
capability. It allows invited submission into one tenant's controlled process.

The cross-tenant network is a separate deferred program. Potential value includes
verified relationships, discovery, tender/RFQ participation, shared qualification,
capacity/equipment and surplus-material marketplaces, group procurement,
consortium discovery, reputation and anonymized benchmarks/intelligence. It
requires explicit consent, platform identity, moderation, fraud/competition and
privacy controls, adequate opt-in density and a sustainable operating model.

Tenant transactions, contacts, private evaluations and documents are never shared
by default. Network lock-in or data hostage behavior is not an acceptable business
model; export, revocation and purpose limitation remain required.

The [P0-S12 future-network privacy proposal](ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md)
records the planning boundary. It does not select participants, consent terms,
shared claims, commercial terms or launch authority.

## 11. Success metrics

Metrics must be governed and source-traceable. Candidate product outcomes include:

- reduced duplicate entry and paper/manual handoffs;
- approval, sourcing, claim, close and support cycle time;
- percentage of cost/commitment/claim facts with complete source lineage;
- reconciliation exception count/age and close completion;
- budget/forecast variance identified early enough for action;
- on-time certificate, guarantee, qualification and CAPA follow-up;
- mobile field adoption and reviewed downstream reuse;
- support first-response/resolution and known-issue deflection;
- restore/migration/security operational evidence; and
- tenant retention based on legitimate utility and data portability.

Avoid vanity metrics such as raw record count, AI message count or screen usage
without a demonstrated customer outcome.

## 12. Risks and constraints

| Risk | Required response |
| --- | --- |
| Building breadth before authoritative finance/data | Follow P0-P10 dependencies and production gates |
| Hard-coded changing Iranian rules | Effective versions, source/reviewer and «نیازمند بررسی قانونی» until verified |
| Over-complexity for small tenants | Optional structures and starter workflows |
| Weak project/object isolation | Complete P1.1 before sensitive/multi-project launch |
| Confusing MVP finance handoff with ledger ownership | Retain native financial authorities and use structured Excel handoff; no invented direct accounting-system integration |
| Unsafe external/AI access | Least privilege, scoped portal/support, consent and human confirmation |
| Premature network/marketplace | Keep deferred until governance and density triggers |
| Dependency proliferation | Apply Build-vs-Reuse and dependency review policy |

## 13. Non-goals under the current strategy

General-purpose CRM, tenant-programmable BPMN/code, BIM authoring, bespoke
cryptography/security protocols, duplicate domain ledgers/masters/file stores,
unrestricted SQL assistants and autonomous consequential AI actions are rejected
or not recommended. Microservices/event sourcing and a public API platform remain
deferred until demonstrated constraints/consumers exist.
