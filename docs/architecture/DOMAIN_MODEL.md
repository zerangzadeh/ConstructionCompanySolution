# Target Domain Model

**Status:** approved target-domain reference; not schema or implementation authorization

**Current implementation:** `DOMAIN_AND_DATA_MODEL.md`

**Delivery order:** `../../ROADMAP.md`

## 1. Purpose and authority

This document defines the intended product domains, their ownership boundaries,
and the business problems they solve. It prevents future work from creating
parallel masters, ledgers, workflows, documents, or metrics. Django models,
migrations, services, and tests remain authoritative for what is implemented now.

Target concepts named here are not current entities unless the current-model
document and code confirm them. Every implementation still requires an approved
roadmap work package, permissions, tenant-isolation tests, migration design, and
acceptance criteria.

## 2. Domain principles

- `Organization` is the tenant root; business domains are tenant-owned unless a
  platform catalogue is explicitly global.
- One business fact has one authoritative owner. Other domains consume immutable
  references, snapshots, registered commands, or rebuildable read models.
- Operational domains own source documents; Accounting owns journals; Treasury
  owns cash/instruments; Project Controls owns integrated cost projections.
- A normal cross-domain handoff has one authoritative source owner and one consumer
  owning the resulting fact. A multi-source derived calculation owns only its
  immutable result and has no mutation authority over its referenced sources.
- `User` is authentication identity; `Employee` is workforce identity;
  `BusinessParty` is counterparty identity. They are related but not interchangeable.
- WBS describes work. CBS/cost center classifies money. Chart of accounts
  classifies ledger postings. Mappings connect them; none replaces the others.
- Workflow coordinates registered domain transitions. It does not own arbitrary
  domain status or become a general tenant-programmable BPM engine.
- Finalized history changes through revision, reversal, adjustment, void, release,
  or supersession—not silent edit or deletion.
- Effective-dated rules, contract terms, rates, responsibilities, qualifications,
  and regulatory parameters preserve historical truth.
- Enterprise structures are optional. Small contractors can use owner/default
  routes without departments, positions, teams, or complex approval chains.

## 3. Domain landscape

| Domain | Authoritative responsibility | Current position | Target boundary |
| --- | --- | --- | --- |
| Platform and Tenant | Tenant lifecycle, settings, entitlements, quotas, retention, export/offboarding, support-access grants | Partial | Commercial SaaS controls and lifecycle operations without embedding domain data |
| Identity and Authorization | Global login identity, membership, business permissions, project/site scope, elevation and separation rules | Partial | MFA/optional SSO, canonical role policy and object scope; positions never grant permission |
| Parties and Partner Lifecycle | Counterparty identity, roles, contacts, tax/bank/qualification profiles and relationship history | Partial | One party master extended by qualification/performance; no duplicate supplier/subcontractor masters |
| Materials and UOM | Tenant material identity, category, code/alias, technical attributes, units/conversions, approval and price-source history | Partial | Governed tenant catalogue first; cross-tenant overlay deferred |
| Projects and Project Controls | Project/site/phase/WBS/activity plus versioned CBS/cost centers, accepted planning budgets, bounded accepted-budget/expense comparison, incomplete multi-source cost-evidence reconciliation and audited exports, inert cost projections, draft schedule revisions/milestones/dependencies, evidence registers and immutable change/rebaseline proposals; producer activation and policy-dependent schedule/change acceptance remain disabled | Partial | One project structure connecting field, commercial, schedule, cost and financial facts without becoming a parallel ledger or contractual authority |
| Workforce | Employee, organization structure, effective responsibilities, skills, qualification, training, performance and labor-rate facts | Partial | Identity separated from payroll and authorization; capability evidence is effective-dated |
| Time, Attendance, Payroll and Insurance | Calendars, attendance/time, leave, payroll calculation, tax/insurance outputs, liabilities and distribution | Missing | Effective regulatory/pay rules; finalized runs feed Accounting, Treasury and Project Cost |
| Estimation, BOQ and Budget | Estimate revisions/resource evidence and explicit accepted budget handoff are implemented; coefficient application and external price books remain gated while integrated cost consumes only approved source contracts | Partial | Contractual BOQ, internal estimate and approved budget are distinct versioned facts |
| Contracts and Commercial Control | Receivable/payable contracts, terms, items, variations/amendments, guarantees and commercial exposure | Partial | Versioned terms and instruments drive claims, commitments and compliance evidence |
| Measurement and Billing | Baselines, progress, receivable/payable claims/certificates, adjustments, retention/advance and settlement evidence | Receivable baseline delivered | Correct contract/regulatory ownership, AP/AR/posting and statutory integration |
| Procurement and Sourcing | Request, RFQ, sealed quote metadata, immutable deadline-close custody, pre-production supplier-package custody and independently approved exact-revision opening/access are implemented; commercial admissibility, comparison, award, PO/change, receipt/service acceptance and production storage are not activated | Partial | Source-to-pay handoffs without owning supplier-invoice, AP, Treasury or Inventory facts |
| Inventory | Warehouse quantity, reservation, traceability, counts, transfer custody and valuation layers | Quantity ledger delivered | Posted/reversed movement authority with Project Cost and Accounting reconciliation |
| Equipment and Fixed Assets | Operational equipment usage/fuel/maintenance and financial asset capitalization/depreciation/disposal | Equipment partial; assets missing | Link but do not collapse operational equipment and financial asset identities |
| Expenses and Cost Evidence | Operational expense evidence, classification, allocation, approval and settlement reference | P4-S26–S30 lifecycle, source controls, conserved coding, manual recurrence proposals and advisory accepted-budget assessment delivered; P4-S35–S37 adds exact retry/concurrency hardening and read-only incomplete reconciliation; downstream settlement/posting absent | AP/Treasury/Accounting retain liability, cash and journal ownership; Project Cost activation requires a separate approved producer contract |
| Accounting | COA/dimensions, fiscal periods, immutable balanced journals, posting rules, close/reopen and statements | Partial — core ledger, manual/opening registry, immutable reversal/replacement, source identity, posted snapshots, opening import, retained reconciliation runs/tie-outs/dispositions/sign-off, posted-line-only retained trial balance/balance sheet/profit-loss with exact drill-through, append-only close/reopen evidence, controlled adjustment lineage, tenant-scoped Admin/RTL UI and PostgreSQL contention/cutoff hardening implemented; operational producers and controlled export remain open | Sole general-ledger authority; no domain-local ledgers |
| Treasury and AP/AR | Bank/cash/instruments, cheques, transfers, requests, advances, statements, reconciliation, supplier-invoice evidence, obligations, allocations and aging | Treasury through bank reconciliation plus the AP/AR authority, capped Treasury settlement/reversal, exact as-of aging, retained reconciliation and independent signed cash-to-GL/subledger review are delivered. Supplier-invoice evidence, matching, AP/AR source/posting activation, write-off approval, bucket policy, scheduling, non-cash substantiation and provider adapters/production limits remain gated; legacy Payment is retained separately | AP/Finance owns supplier-invoice evidence and payable disposition; matching owns only derived evidence; Treasury, AP and AR remain distinct from journals and operational source documents |
| Daily Site and Field Operations | Daily conditions, work fronts, labor/equipment/material observations, visits, meetings, instructions and media evidence | Partial | Mobile/context-aware capture proposes reviewed downstream transactions |
| HSE | Risk, inspections, permits, toolbox/PPE/training controls, incidents, investigation, CAPA and metrics | Incident baseline delivered | Evidence-backed lifecycle and escalation integrated with qualification and knowledge |
| Quality | ITP, inspection requests, checklists, tests, material/sample approval, punch/NCR/rework/CAPA and verification | Issue baseline delivered | Independent verification and immutable closure evidence |
| DMS and Document Control | Private blobs, immutable versions, metadata, links, OCR/search, signatures, transmittals, RFI/submittal/drawing control, retention/export | Versioned baseline delivered | One file/version authority reused by media and every business domain |
| Workflow and Work Management | Registered workflow catalogue, tenant definitions/versions, runtime, candidates, delegation, assignments and workbench | Delivered | Bounded declarative coordination; domains remain authoritative |
| Knowledge | Reviewed lessons, practices, technical notes, procedures, articles, cases, recurrence and reuse evidence | Missing | Promotes reviewed source evidence into governed reusable knowledge |
| Partner Performance | Qualification and evidence plus delivery, quality, safety and commercial evaluation | Missing | Explainable category/time-specific facts extending `BusinessParty` |
| Notifications and Support | Delivery preferences, support cases, known issues/features, SLA, diagnostics and time-limited support access | Missing | Audit is not notification; support access is explicit, scoped and expiring |
| AI Assistance | Cited support retrieval and later governed management/KPI guidance | Missing/deferred by tier | No unrestricted SQL, permission bypass, autonomous posting or finalization |
| Reporting, Metrics and Reconciliation | Governed semantic metrics, read models, drill-through and exception workbenches | Partial read models | Projections are rebuildable and reconcile to authoritative transactions |
| Controlled Business Network | Opt-in verified relationships, discovery, shared qualification and privacy-safe intelligence | Deferred | Separate platform boundary; tenant transactions/evaluations private by default |

## 4. Strategic aggregate boundaries

| Aggregate/root | Owns | Must not own |
| --- | --- | --- |
| `Organization` | Tenant state, settings authority, entitlements and lifecycle evidence | Project transactions or global user identity |
| `OrganizationMembership` | Tenant access relationship, independent membership-scoped role assignments and effective grants | Employment facts, workflow position or a global User role set |
| `BusinessParty` | Counterparty identity and tenant-local roles/profile | Contract, invoice, evaluation or cash balances |
| `Project` | Project hierarchy/context and approved control structures | Editable authoritative actual-cost total |
| `Estimate`/revision | Versioned assumptions, lines and calculated estimate | Approved budget or contract value without explicit handoff |
| Contract/term version | Commercial commitment and effective terms | Cash, journal or regulatory rule authority |
| Claim/certificate | Certified commercial amount and source measurements | Cash movement or journal balance |
| Procurement document | Need, offer, order and acceptance evidence | Supplier invoice/liability, cash or inventory balance |
| Supplier invoice/revision | AP/Finance-owned supplier assertion, tax/terms and payable-source evidence | Procurement order/acceptance facts, journal, stock or cash authority |
| Stock transaction/valuation layer | Quantity/value movement evidence | Project forecast or GL account balance |
| Payroll run | Employee/component calculation and liability distribution | Cash settlement or ledger mutation outside posting contract |
| Journal entry | Balanced accounting fact and reversal lineage | Operational workflow state |
| Treasury transaction/instrument | Cash/instrument state and clearing evidence | General-ledger balance or invoice authority |
| Document/version | Immutable file and metadata history | Owning business record lifecycle |
| Workflow instance/work item | Coordination, responsibility and decision evidence | Generic mutation of domain status |
| Knowledge publication | Reviewed reusable content/version | Rewriting source incident, NCR or project history |

The target authorization relation is many-to-many within Tenant context:
`User -> OrganizationMembership -> MembershipRoleAssignment -> Role`. One
Membership may hold multiple independent roles, while the same User may hold a
different set in another Tenant. Common combinations such as Tenant Owner plus
Tenant Admin plus Project Manager do not justify composite roles. Each assignment
and revocation is independent and auditable. Permissions from all active applicable
role assignments are unioned within that Membership, then intersected with every
other authorization factor, including active Membership and Tenant, explicit
grants, object scope, delegation, workflow eligibility and policy constraints.

## 5. Cross-domain value streams

```text
Estimate/BOQ -> accepted Budget -> Commitment -> Accrual/Actual -> Forecast/KPI
Request -> RFQ/Quote -> PO -> Receipt/Acceptance -> Supplier Invoice -> AP -> Treasury -> GL
Contract -> Baseline/Progress -> Claim/Certificate -> AR/AP -> Treasury -> GL
Field evidence -> reviewed Progress/Time/Usage/Movement -> Cost/Claim/Payroll
Attendance/Time -> Payroll -> Liability/Posting -> Payment -> Reconciliation
Incident/NCR -> CAPA -> reviewed Knowledge -> Checklist/Training/Control/Partner evidence
Document/Media -> immutable Version -> business Link -> workflow/audit/search/export
```

Every handoff identifies tenant, source type/id/version, producer status,
idempotency key where retryable, target owner, reversal/correction behavior, audit
evidence and reconciliation control.

## 6. Current, target, deferred, and rejected boundaries

- **Current:** use `DOMAIN_AND_DATA_MODEL.md` and code. Naming a target aggregate
  here never makes it implemented.
- **Scheduled target:** packages P0-P10 in `ROADMAP.md` provide the only delivery
  disposition and dependencies.
- **Deferred:** cross-tenant network/intelligence, shared catalogue overlay,
  broad offline sync, governed ERP Assistant, GIS platform, predictive AI,
  public API platform, and architecture distribution wait for roadmap triggers.
  The [P0-S12 privacy proposal](ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md) keeps
  tenant-private data outside that future boundary unless an explicitly authorized,
  purpose-specific publication is later accepted; it does not activate the network.
- **Rejected/not recommended:** parallel ledgers/workflows/masters/file stores,
  custom security protocols/cryptography, unrestricted SQL AI, tenant executable
  workflow code, general-purpose CRM/BPMN and BIM authoring.

## 7. Open product decisions

Initial customer segment, native-vs-integrated Accounting, statutory filing
scope, currency, inventory valuation, payroll/employment model, SaaS packaging,
price-book licensing, material coding, portal identity, signature/legal evidence,
hosting/data residency, GIS/offline/media scope, AI provider and network consent
remain roadmap gates. They do not justify inventing defaults or hiding scope.
