# Product Capability, Architecture, and Production-Readiness Audit

**Audit date:** 2026-09-24

**Product stage:** pre-production; no real tenant, payroll, accounting, or contractual history is assumed

**Authority:** code, migrations, and tests describe current implementation; this document describes findings and target direction
**Implementation authorization:** none. Every target capability still requires an approved delivery slice.

## 1. Executive summary

The repository is a substantial modular Django monolith, not an early CRUD prototype. It already contains tenant membership and permission enforcement, shared masters, project/WBS structures, versioned estimates and documents, controlled procurement/inventory/equipment operations, workforce structures, auditable domain lifecycles, a bounded tenant workflow runtime and workbench, and receivable progress claims. The code is materially ahead of several older documents.

The product is not yet ready for a first operational deployment. Its largest risks are not missing screens; they are unresolved authoritative ownership and posting boundaries. A mutable organization-wide `BillingPolicy` currently mixes commercial contract terms with regulatory rates. `Project.estimated_budget` and `Project.actual_budget` coexist with more authoritative estimates and transactions. `Payment` combines receipt/disbursement cash events but is not a Treasury or general-ledger journal. Authorization is tenant-wide rather than project/site scoped. Production operations, secure object storage, MFA, dependency locking/auditing, backup restoration, observability, retention/export, and regulatory legal sign-off are incomplete.

The recommended product shape remains a Persian-first construction ERP for Iranian contractors. The differentiator should be traceable integration from field evidence and commercial documents into project cost, claims, Treasury, and Accounting—not an indiscriminate collection of generic ERP modules. Strategic business rules, construction costing, claim calculations, reconciliation, and bounded workflow remain owned code. Commodity security protocols, object storage adapters, job execution, vulnerability scanning, PDF handling, and observability should be evaluated as mature dependencies rather than reimplemented.

### Priority classification

| Class | Conclusion |
| --- | --- |
| **MUST FIX BEFORE FIRST PRODUCTION RELEASE** | Separate effective-dated regulatory configuration from contract commercial terms; decide and implement the Accounting/Treasury posting boundary; establish one budget/actual source of truth and project-cost coding; add project/site object scope; prove secure storage, backup/restore, migration, monitoring, MFA, dependency integrity, retention/export, and support access; obtain legal/accounting review of Iranian rules. |
| **SHOULD FIX BEFORE FIRST PRODUCTION RELEASE** | Normalize duplicated organization locale/currency ownership; canonicalize role semantics and separation of duties; improve party/bank/regulatory identifiers; connect daily labor/equipment observations to masters while retaining snapshots; redesign extensible document linking; add audit correlation/diffs and UOM conversion governance. |
| **SAFE TO DEFER** | Cross-tenant network/catalogue, marketplace, predictive AI, broad offline sync, public APIs, microservices, event sourcing, and general-purpose BPMN. |

## 2. Method and evidence

This audit inspected repository structure, installed apps, models and migrations, service boundaries, forms/views/URLs, templates, permission registration, workflow registries, settings, tests, dependencies, and active architecture documents. Django model introspection found 86 registered model objects. On the audit date:

- `python manage.py check` passed.
- `python manage.py makemigrations --check --dry-run` reported no changes.
- `pytest --collect-only -q` collected 563 tests.
- The environment-level `pip check` failure came from undeclared, apparently unrelated `nltk` packages in the local virtual environment; it is not evidence of a project dependency failure, but it shows that the environment is not reproducible.
- No dependency lock with hashes, CI workflow, or production container/deployment contract was found.

This is a static and test-discovery audit, not a legal opinion, penetration test, load test, disaster-recovery exercise, or production certification.

## 3. Repository current-state assessment

### 3.1 Current capability map

| Domain | Classification | Repository evidence and boundary |
| --- | --- | --- |
| Identity and tenant core | **PARTIALLY IMPLEMENTED** | Custom `User`, `Organization`, settings, memberships, invitations/connection requests, active-tenant session resolution, lifecycle checks, permission catalogue, and audit exist. MFA, SSO, subscription/entitlements, quota enforcement, tenant export/offboarding, and mature invitation governance do not. |
| Authorization | **PARTIALLY IMPLEMENTED** | Deny-by-default tenant permission checks exist and are well tested. There is no first-class project/site access scope. Current role codes also do not map cleanly to the target owner/admin/manager/accountant/supervisor/viewer vocabulary. |
| Parties and shared masters | **IMPLEMENTED / PARTIAL** | `BusinessParty`, roles/contacts, materials, categories, and UOM exist. Bank accounts, regulatory profiles, qualification facts, effective relationships, UOM conversions, merge/deduplication, and governance workflows are absent. |
| Projects and controls | **PARTIALLY IMPLEMENTED** | Projects, sites, phases, WBS, activities, baselines, and progress exist. Formal schedule baselines, CBS/cost centers, risk/change controls, resource planning, earned-value controls, and integrated forecasting are absent. |
| Workforce | **PARTIALLY IMPLEMENTED** | Employees, optional login link, departments, positions, teams, effective assignments, and project/site assignments exist. Skills, qualifications, labor rates, attendance, time capture, leave, payroll, and insurance lists do not. |
| Contracts | **PARTIALLY IMPLEMENTED** | Receivable/payable direction, items, controlled lifecycle, and immutable approved amendments exist. Subcontract administration, change orders/variation valuation, guarantees, insurance evidence, contractual schedules, and payables certification are incomplete. |
| Estimates and budgets | **PARTIALLY IMPLEMENTED** | Versioned estimates and approved revisions exist. Approved-budget control, CBS mapping, commitment control, rate libraries, estimate-to-budget handoff, forecast-at-completion, and coherent replacement of manual project budget fields do not. |
| Workflow/work management | **IMPLEMENTED** | Versioned/published definitions, runtime instances, steps, candidates, work items, assignment history, delegation, bounded registries, position routing, workbench, domain adoption, and PostgreSQL acceptance evidence exist. It is not general BPMN and must remain bounded. |
| Billing/progress claims | **IMPLEMENTED / ARCHITECTURALLY INADEQUATE** | Baselines, progress, policies, claims/items/sources/adjustments, approval workflow, settlements, and receivable payment allocation exist. Policy ownership is too broad and mutable; payable/subcontractor claims, e-invoice integration, party/currency snapshots, guarantees, and accounting postings are absent. |
| Procurement | **PARTIALLY IMPLEMENTED** | Requests, orders, receipts, quantities, lifecycles, and workflow integration exist. Requisitions do not extend through RFQ, quote comparison, sourcing decision, supplier invoice, three-way match, commitment accounting, or automatic stock receipt. |
| Inventory | **PARTIALLY IMPLEMENTED** | Warehouses and immutable/reversible stock ledger movements exist. Reservations, bins, lots/serials, cycle counts, valuation/cost layers, issue-to-activity, and procurement/accounting integration are absent. |
| Equipment | **PARTIALLY IMPLEMENTED** | Master, conflict-safe assignment, and maintenance history exist. Usage meters, operator/certification, fuel, downtime, ownership/lease, cost recovery, fixed-asset linkage, and daily-report integration are absent. |
| Daily site operations | **PARTIALLY IMPLEMENTED** | Reports, labor/equipment/material/activity/delay lines, lifecycle, and master references for some rows exist. Labor and equipment remain free text; mobile/offline capture, timesheet/usage generation, media/evidence capture, and cost propagation are absent. |
| HSE and Quality | **PARTIALLY IMPLEMENTED** | Safety incidents and quality issues have controlled lifecycles, assignments, workflow adoption, and audit. Inspections, risk registers, permits, toolbox talks, test/inspection plans, formal CAPA, knowledge extraction, and generalized document links are absent. |
| Documents | **PARTIALLY IMPLEMENTED** | Private versioned documents, immutable versions, explicit links to six domains, validation, secure download, and audit exist. The wide link table will not scale across all target domains; classification, OCR, signatures, retention, legal holds, antivirus scanning, object storage, and export are absent. |
| Expenses and payments | **IMPLEMENTED / ARCHITECTURALLY INADEQUATE FOR TARGET** | Immutable/voidable expenses, posted receipt/disbursement `Payment`, allocations, and read models exist. These are useful operational records but are not AP/AR, Treasury, bank/cheque management, or double-entry Accounting. |
| Accounting, Treasury, Payroll, Fixed assets | **MISSING** | No ledger accounts, journals, fiscal periods, subledgers, bank/cash/cheques, reconciliation, payroll, insurance list, depreciation, or asset register exists. |
| Audit and observability | **PARTIALLY IMPLEMENTED** | Append-only `AuditEvent` exists with sensitive-key filtering. Correlation/request IDs, structured change sets, security monitoring, metrics, tracing, error tracking, and operational alerting are absent. |
| Reporting/BI | **PARTIALLY IMPLEMENTED** | Financial read models aggregate approved estimates, recorded expenses, and posted payments. There is no governed semantic metric catalogue, warehouse, scheduled reporting, drill-through contract, or reconciliation control. |
| Support and AI | **MISSING** | No support-ticket, tenant support-access grant, knowledge base, AI support assistant, extraction review, model governance, or AI audit trail exists. |

### 3.2 Repository consistency and domain boundaries

The modular-monolith shape is appropriate. Domain services own transitions and workflows invoke registered commands rather than updating arbitrary states. The ORM and explicit foreign keys are appropriate; repository abstractions and microservices are not currently justified. Important inconsistencies are:

1. `Organization` and `OrganizationSettings` duplicate timezone/currency. Compatibility dual-write is a temporary bridge, not a permanent source of truth.
2. `BillingPolicy` combines claim numbering/precision/period controls with tax, insurance, retention, and advance recovery. Those concepts have different owners and effective dates.
3. `Project.estimated_budget` and `Project.actual_budget` are editable summary facts competing with estimates and transaction-derived actuals.
4. `Payment` is both incoming and outgoing cash. That is acceptable as a legacy cash transaction but not as the future Treasury aggregate and never as an accounting journal.
5. `DocumentLink` has one nullable FK per supported domain. Continue explicit relational links, but move toward small domain-owned link tables or an approved link registry—not `GenericForeignKey`—before adding many more targets.
6. Daily labor/equipment rows preserve useful snapshots but lack optional authoritative `Employee`/`WorkTeam`/`Equipment` links, blocking time, usage, and cost lineage.
7. Global role definitions and tenant-wide permissions need canonical target semantics plus project/site scope; positions must continue to route responsibility, not grant authorization.

## 4. Target capability map

| Capability group | Target outcome | Phase | Authority/owner |
| --- | --- | --- | --- |
| Tenant commercial platform | Lifecycle, plan/feature entitlement, quota, onboarding, export, retention, cancellation, support access | Foundation | Organizations/Platform |
| Identity and access | MFA, optional SSO, canonical roles, object scope, separation of duties, audited elevation | Foundation | Accounts/Organizations |
| Regulatory configuration | Effective-dated, versioned, approved rules for tax, payroll, insurance, invoice schemas, calendars, rounding | Foundation | Compliance configuration; not claims or payroll rows |
| Accounting | Chart of accounts, dimensions, fiscal periods, immutable journals/lines, posting registry, reversal, close, subledger reconciliation | Now | Accounting ledger |
| Treasury | Bank/cash accounts, receipt/payment instruments, cheques, transfers, cash forecast, bank statement and reconciliation | Now | Treasury; journal remains Accounting-owned |
| Project costing | Cost centers/CBS, budget, commitments, actuals, accruals, forecast, EAC, variance, drill-through | Now | Project Controls read/semantic layer over source transactions |
| Source-to-pay | Request, RFQ, quote, comparison, award, PO, receipt/service acceptance, invoice, match, payment | Next | Procurement/AP/Treasury, each owning its transaction |
| Hire-to-pay | Employee, attendance, timesheet, leave, payroll calculation, payslip, payroll journal, employee insurance list and tax outputs | Next | Workforce/Payroll; Accounting receives postings |
| Contract-to-cash/pay | Contracts/subcontracts, changes, measurements, claims/certificates, retention/advance/penalties, guarantees, settlements | Next | Contracts/Billing/AP-AR/Treasury |
| Inventory/equipment/assets | Valuation, issue/return, usage/fuel/maintenance costing, asset capitalization/depreciation/disposal | Next | Inventory/Equipment/Fixed Assets |
| Field-to-control | Mobile daily evidence, labor/equipment/material capture, progress, HSE/quality, downstream draft transactions | Later | Operational domains; approved source documents remain authoritative |
| HSE/Quality-to-knowledge | Inspections/CAPA, causal taxonomy, lessons learned, reusable preventive controls | Later | HSE/Quality/Knowledge with reviewed publication |
| Partner lifecycle | Qualification, documents, project performance, risk and renewal | Later | Parties/Partner Performance |
| Support and AI | Ticketing, safe time-limited support access, knowledge retrieval, cited assistance, reviewed extraction/actions | Later | Support/Knowledge; domain services execute approved actions |
| Controlled business network | Explicit opt-in identity claims, invitation/discovery/recommendation, privacy-preserving reputation | Deferred | Separate platform boundary; tenant data private by default |

### 4.1 Gap analysis by business outcome

| Business outcome | Current strength | Material gap | Consequence if ignored |
| --- | --- | --- | --- |
| Trustworthy tenant operation | Strong tenant scoping and lifecycle checks | Project/site scope, MFA, support access, export/retention | Excess access and incomplete customer lifecycle |
| Controlled project delivery | Project/WBS, daily reports, workflow, progress baseline | CBS/cost centers, schedule/risk/change, master-backed field usage | Weak plan-to-cost/progress traceability |
| Commercial control | Contracts/amendments and receivable claims | Term/regulation ownership, payables claims, guarantees, e-invoice | Historical calculation and compliance ambiguity |
| Source-to-pay | Request/order/receipt and stock receipt linkage | Sourcing, invoice, match, AP, automatic controlled handoffs | Re-entry and incomplete liability/commitment control |
| Financial integrity | Immutable expenses/payments and read models | GL, AP/AR, Treasury, close, reconciliations | No authoritative books or cash/subledger tie-out |
| Labor compliance/cost | Workforce assignments | Attendance, timesheet, payroll, tax and insurance list | Missing statutory workflow and major project-cost source |
| Asset/material cost | Quantity ledger, equipment assignments/maintenance | Valuation, usage/fuel, fixed asset and posting | Quantity without full financial carrying/project cost |
| Evidence and learning | Versioned DMS, HSE/quality cases | Retention/scanning, inspections/CAPA, reviewed knowledge | Paper/manual handoffs and repeated failures |
| Management decisions | Useful read models | Governed metrics, drill-through and reconciliation | Conflicting dashboards and low trust |
| Operational SaaS | Secure-setting baseline | Reproducible build, recovery, observability, SLA/support | Unprovable production readiness |

## 5. Newly discovered and accepted capabilities

These capabilities were not consistently represented in the previous roadmap but are justified by repository gaps and construction-ERP patterns:

- **Regulatory configuration registry:** necessary because rates, thresholds, schemas, and filing rules change by effective date and require provenance/approval.
- **Accounting posting registry and idempotency:** necessary to prevent every operational module from creating its own ledger logic.
- **Cost Breakdown Structure (`CBS`) and mapping:** WBS describes work; CBS/cost centers classify money. One must not be overloaded as the other.
- **Commitment and accrual control:** actual cash alone cannot support project cost or period reporting.
- **Guarantees/securities:** bid, performance, advance-payment, retention, and insurance instruments are core contractor exposure.
- **Supplier invoice and three-way match:** receipt and order without invoice matching cannot close source-to-pay or feed AP reliably.
- **Controlled support access:** support staff must not receive silent standing access to tenant data; grants need purpose, expiry, scope, and audit.
- **Knowledge provenance and approval:** lessons extracted from HSE/quality must be reviewed before becoming reusable guidance.
- **Data-quality and reconciliation workbench:** integration failures and unmatched facts need exception queues, not silent corrections.
- **Business continuity evidence:** backup success is insufficient without periodic restore, RPO/RTO, ownership, and recovery rehearsal.

## 6. Data ownership, master catalogue, and source of truth

### 6.1 Master data catalogue

| Master | Authoritative domain | Target governance |
| --- | --- | --- |
| Tenant identity/settings | Organizations | One settings authority; effective history where fiscal/localization facts affect history |
| User identity | Accounts | Global identity; no business employment facts |
| Membership/role/project scope | Organizations/Authorization | Effective-dated grants; positions never replace grants |
| Employee/position/team | Workforce | Optional `User` link; effective assignment history |
| Party/contact/tax/bank profile | Parties | Deduplication, verification status, effective role and sensitive-field permissions |
| Material/category/UOM/conversion | Materials | Versioned conversion where commercial precision requires it; transaction snapshot retained |
| Project/site/WBS/activity | Projects | Project structure; WBS not used as financial account |
| CBS/cost center | Project Controls | Financial coding hierarchy and mappings to WBS/activity/contracts |
| Chart of accounts/dimensions | Accounting | Ledger-only authority; operations reference codes/mappings |
| Bank/cash account | Treasury | Sensitive, approval-controlled; accounting account mapping |
| Regulatory rule set | Compliance Configuration | Effective-dated, sourced, reviewed, immutable after activation |
| Workflow catalogue | Platform code | Platform registered; tenant definitions compose allowed types only |

### 6.2 Transaction and derived-fact source-of-truth map

| Fact | Authoritative source | Derived consumers; never an alternate authority |
| --- | --- | --- |
| Contract commitment | Approved contract/amendment/PO | Project-cost commitment, cash forecast, dashboards |
| Approved budget | Approved budget baseline derived from accepted estimate | Variance and forecast; retire editable project summary fields |
| Physical progress | Approved `ProgressRecord` and source evidence | Claim eligibility, earned metrics |
| Claim receivable | Approved `ProgressClaim` revision and adjustments | AR subledger, accounting posting, collection forecast |
| Supplier liability | Approved/matched supplier invoice or certified payable claim | AP, posting, cash forecast |
| Cash movement | Treasury instrument/transaction and bank evidence | Accounting posting and cash position |
| Accounting balance | Posted immutable journal lines | Trial balance and statutory/management financial statements |
| Inventory quantity | Posted/reversed stock ledger | On-hand projections and valuation; no editable balance |
| Payroll liability | Finalized payroll run | Payslip, insurance/tax output, journal, Treasury payment proposal |
| Asset carrying value | Fixed-asset transaction/depreciation ledger | Financial statement and equipment reporting |
| Project actual cost | Classified source postings/subledger transactions | Project-cost read model; no manual editable actual total |
| KPI | Governed semantic definition over authoritative facts | Dashboard cache/read model with drill-through |

## 7. Integration and dependency architecture

### 7.1 Module integration matrix

| Producer | Consumer | Contract/event | Required control |
| --- | --- | --- | --- |
| Estimates | Budget baseline | Approved revision + mapping | One accepted handoff; immutable revision reference |
| Contracts/Procurement | Project Cost/AP | Commitment/change | Same tenant/project/CBS; idempotent versioned handoff |
| Goods receipt/service acceptance | Inventory/AP | Received quantity and match evidence | No duplicate stock movement; tolerance and reversal |
| Inventory | Project Cost/Accounting | Posted issue/return/valuation | Activity/CBS mapping; valuation method; period state |
| Daily reports | Progress/Timesheet/Equipment usage | Approved observations | Create reviewed drafts, not automatic legal/financial finalization |
| Billing | AR/Accounting/Treasury | Approved claim, settlement | Snapshot terms/rules; one posting key; allocation reconciliation |
| Payroll | Accounting/Treasury/Project Cost | Finalized run and distribution | Effective rules; employee/project allocation; reversal |
| Equipment/Fixed Assets | Project Cost/Accounting | Usage, maintenance, depreciation | Distinguish operating equipment from financial asset |
| HSE/Quality | Workflow/Knowledge | Incident/NCR/CAPA/lesson candidate | Review, privacy, evidence link, publication approval |
| All domains | Audit/Notifications/BI | Action evidence and read-model updates | Audit is not a notification bus; retry/idempotency where async |

### 7.2 Cross-module dependency map

```text
Tenant + Identity + Permission + Project Scope + Regulatory Configuration
        ├─> Accounting Kernel ─> Treasury/AP/AR ─> Reconciliation/Close
        ├─> Masters + Project/WBS/CBS ─> Budget/Commitment/Actual/Forecast
        ├─> Workforce ─> Time/Attendance ─> Payroll/Insurance ─> Posting
        ├─> Parties/Materials ─> Procurement ─> Receipt ─> Inventory/AP
        ├─> Contracts/Baseline/Progress ─> Claims ─> AR/Treasury
        └─> Workflow + DMS + Audit + Notifications support every lifecycle

Field evidence ─> reviewed operational records ─> approved transactions
              ─> postings/read models ─> reconciled KPI with drill-through
```

Accounting, regulatory configuration, master governance, project/CBS coding, and authorization scope are prerequisites—not cleanup after downstream modules.

## 8. Duplicate entry, automation, and paperless analysis

| Current/manual point | Target minimum-entry behavior | Guardrail |
| --- | --- | --- |
| Organization/project/site repeated in forms | Infer from active context; cascade and validate server-side | Never trust hidden/context fields as authorization |
| Daily labor/equipment text | Select master and preserve display snapshot; allow controlled exception text | Do not mutate approved historical snapshot when master changes |
| Receipt-to-stock re-entry | Offer deterministic draft stock movement from posted receipt | Explicit review/post; idempotency; reversal linkage |
| Estimate-to-budget recreation | Promote approved revision through mapped handoff | No silent overwrite of approved budget baseline |
| Progress-to-claim quantities | Propose from eligible approved progress and prior certified quantities | User sees source, exclusion, caps, and rounding |
| Claim-to-accounting entry | Generate posting proposal through registered rule | Final posting only after configured approval and open period |
| PO/receipt/invoice comparison | Automated match with tolerance and exception queue | Human decision for mismatch; evidence retained |
| Timesheet/payroll entry | Reuse approved attendance/time and effective employment/pay rules | Lock inputs by payroll period; adjustment/reversal only |
| Bank matching | Import statement and propose matches | No irreversible auto-match without deterministic confidence policy |
| Document indexing | OCR/extract into reviewable suggestions | Original immutable; extracted value includes confidence/source |
| Party-entered facts | Supplier/subcontractor portal for documents/claims | Least privilege; tenant invitation and submission validation |

Paperless workflows require more than file upload. Every target process needs a document/evidence requirement, structured metadata, versioning, approvals, retention, export, signatures where legally appropriate, and a failure path for unavailable integrations. Printing may remain an output; paper must not be the only authoritative handoff.

## 9. Accounting, Treasury, and project-costing assessment

### 9.1 Posting architecture

The future ledger should use an immutable `JournalEntry` aggregate with balanced `JournalLine` records, fiscal period, document date, posting date, currency/rate policy, organization dimensions, source reference, and unique idempotency key. A code-owned posting registry maps a finalized domain event/version to a reviewed posting rule. Operational modules own their documents; Accounting owns journals. Posted entries are corrected only by reversal and replacement. Closing a fiscal period blocks ordinary posting and requires an audited reopen permission. Draft/proposed entries are distinct from posted books.

Required early ADRs: chart-of-accounts model; project/CBS/cost-center dimensions; fiscal calendar; document numbering; currency/rate scope; posting rule versioning; subledger reconciliation; opening balances; close/reopen; and whether journal proposals are synchronous or queued. Do not let Django signals perform financial posting.

### 9.2 Treasury boundary

Rename or explicitly contain the existing `Payment` concept when Treasury is introduced. Treasury should own bank/cash accounts, instruments, cheques, transfers, payment/receipt lifecycle, bank statement lines, clearing, and reconciliation. Accounting owns the resulting journal. AP/AR own obligations and settlements. A Treasury transaction is not a journal and an allocation is not a ledger line.

### 9.3 Project costing

Project cost must be a governed read model sourced from budget, commitments, receipts/accruals, inventory issues, expenses, payroll distribution, equipment usage/depreciation, subcontract certificates, and posted accounting dimensions. Each amount needs tenant, project, optional site/WBS/activity, CBS/cost center, source type/id/version, transaction date, accounting period, currency, and status. Dashboards must distinguish budget, committed, accrued, actual, paid, forecast, and variance; these are not interchangeable.

## 10. Reconciliation matrix

| Reconciliation | Left side | Right side | Frequency/owner | Exception evidence |
| --- | --- | --- | --- | --- |
| Estimate to budget | Approved estimate revision | Approved budget baseline | On handoff/revision; Project Controls | Mapping difference and approval |
| PO commitment | Issued/changed PO | Project commitment/subledger | Continuous; Procurement/Cost | Missing/duplicate/version mismatch |
| Three-way match | PO | Receipt/service acceptance + supplier invoice | Before AP approval | Quantity/price/tax/tolerance reason |
| Inventory | Stock quantity ledger | Valuation/subledger/accounting control | Periodic and close | Item/warehouse/value difference |
| Claim to AR | Approved claim | AR open item + journal | On posting/close | Source version/posting key |
| Settlement | AR/AP allocation | Treasury cleared movement | Continuous | Unallocated/overallocated/voided |
| Bank | Treasury book | Imported bank statement | Daily/monthly | Unmatched line and resolution |
| Payroll | Final payroll | liabilities + journal + payment batch | Per run | Employee/component/distribution variance |
| Fixed assets | Asset register | GL control accounts | Monthly/close | acquisition/depreciation/disposal variance |
| Project cost | Source subledgers/journals | Cost read model | Incremental + close | Source lineage/rebuild comparison |

## 11. Iranian compliance and regulatory configuration

This section records product requirements, not legal advice. Every rule marked **legal review required** must be confirmed against the current official source before implementation and before each relevant production release.

| Area | Product implication | Configuration requirement | Status |
| --- | --- | --- | --- |
| Taxpayer terminals and electronic invoices (سامانه مودیان) | Invoice types, identifiers, correction/cancellation/reference chains, transmission status, response and retry evidence | Effective schema/version, mappings, credentials, numbering, error catalogue; never hard-code | Missing; **legal/technical review required** |
| VAT | Taxability, exemptions, rates, rounding, credit treatment and reporting | Effective-dated tax codes and rates with source/provenance | Missing; **legal review required** |
| Direct tax/payroll withholding | Payroll taxable components, annual exemption/tiers and filing output | Tax year, effective tables, component mapping, rounding, approval | Missing; **legal review required** |
| Labor law | Minimum wage and annual pay elements affect payroll | Effective annual rule set; employment-contract inputs | Missing; **legal review required** |
| Social insurance | Employee wage/insurance list, contribution components, contractor Article 38 controls, clearance and retention evidence | Effective contribution rules, list schema/status, contract insurance facts; no fixed global percentage | Missing; **legal review required** |
| Contractor claims/retention/advance | Contract-specific retention, insurance deduction, advance recovery, caps and certificates | Snapshot from approved contract term version—not organization default | Current policy inadequate; product/accounting review required |
| Accounting standards and fiscal books | Journal evidence, close, reversals, construction revenue/cost treatment, audit trail | Accounting policy version, fiscal periods, posting rule and disclosure mapping | Missing; professional accounting review required |
| Jalali/Gregorian and currency | Persian UX may display Jalali and Rial/Toman while storage/calculation remains unambiguous | Tenant display preference; canonical stored date/currency/unit; explicit conversion/display labels | Partial |

Regulatory rules need `valid_from`, optional `valid_to`, jurisdiction, rule type/version, status, authoritative source, reviewer/approved-at, structured parameters, and immutable activation history. Historical documents retain the applied rule/version snapshot. Regulatory configuration cannot be a mutable miscellaneous settings row.

## 12. KPI and semantic metrics catalogue

| KPI | Definition boundary | Authoritative inputs | Required drill-through |
| --- | --- | --- | --- |
| Budget variance | Approved budget minus forecast/actual, shown separately | Budget baseline + classified cost facts | Budget line and source transactions |
| Committed cost | Active contractual/PO commitments net of approved changes | Contracts/amendments/PO | Commitment document/version |
| Actual cost | Approved/posted classified costs, never cash alone | AP/expenses/payroll/inventory/equipment/accounting | Journal/subledger/source document |
| Forecast at completion | Actual + open commitments + estimate to complete | Cost facts + controlled forecast version | Assumptions and version |
| Cost performance | Earned value / actual cost only where baseline discipline exists | Baseline/progress/cost facts | Period and source lines |
| Certified progress | Certified cumulative quantity/value | Approved claim/certificate | Claim lines and progress sources |
| Retention receivable/payable | Contractual retained less released/settled | Claims/adjustments/settlements | Term version and movements |
| Cash position/forecast | Cleared cash plus dated expected inflow/outflow | Treasury + AR/AP/commitments | Account, instrument, obligation |
| Procurement cycle time | State-transition durations | Audit/workflow history | Request/order/receipt timeline |
| Safety/quality closure time | Report-to-close and overdue actions | Incident/NCR/CAPA | Case/action history |
| Workforce utilization | Approved productive time / available governed time | Timesheet/attendance/assignment | Employee/project/time source |
| Reconciliation health | Unmatched/aged exceptions by control | Reconciliation runs | Each discrepancy and resolution |

Every KPI definition must state grain, included statuses, time basis, currency/unit, timezone, late corrections, owner, refresh, and source links. A cached metric is a projection, not a new authority.

## 13. Knowledge, partner performance, and network assessment

### Knowledge flow

```text
Incident / NCR / delay / change / support case
  -> evidence + taxonomy + root-cause/CAPA
  -> reviewed lesson candidate
  -> approved reusable lesson/control/checklist
  -> suggested at project/task context
  -> acknowledgement and effectiveness feedback
```

AI may suggest classification, summaries, or related lessons, but published knowledge needs a named reviewer, source evidence, sensitivity, scope, version, and expiry/review date.

### Partner performance and qualification

Extend `BusinessParty`; do not create parallel supplier/subcontractor masters. Target facts include qualification questionnaire, capability categories, legal/tax/insurance documents, expiry, financial/compliance risk, tender/project evaluations, safety/quality/delivery/commercial performance, sanctions/blocks, and approved vendor status. Scores must be explainable, time-bounded, category-specific, and traceable to projects; subjective ratings need reviewer and evidence.

### B2B network

The future network can reduce duplicate onboarding and improve discovery only after tenant-local party governance is mature. Use explicit opt-in claims and invitations, tenant-controlled publication, verified attributes, revocable sharing, purpose limitation, and separate platform/network identifiers. Never expose transaction values, private evaluations, contacts, documents, or cross-tenant relationships by default. Recommendation should initially use consented structured attributes, not opaque AI ranking. This remains **SAFE TO DEFER**.

## 14. Competitor and market landscape

Competitor material is used to identify market patterns, not to copy features or accept vendor claims as independently verified product quality.

| Product/group | Publicly evidenced pattern | Relevance | Decision |
| --- | --- | --- | --- |
| Sepidar contractor products | Contractor accounting, price lists, amendments, progress claims, project cost, integration with inventory/cash/payroll, taxpayer workflows | Iranian baseline for accounting/compliance and contractor documents | Accept patterns; design natively around traceability and effective rules |
| Rasam ERP | Contract linkage with purchasing, budget, Treasury, alerts, and caps | Iranian integrated contract-control signal | Accept integration need; source quality is vendor marketing |
| Samanban | Project/task/time/cost/document orientation | Iranian project-operation signal | Useful context; no architecture conclusion from marketing alone |
| Autodesk Construction Cloud | Document control, field/project workflows, RFIs/submittals/daily reports, cost/change/payment/forecast, ecosystem integrations | Strong field/document collaboration pattern | Later field/DMS/portal benchmark; avoid premature ecosystem breadth |
| Oracle Primavera Unifier | Integrated cost/schedule, WBS/CBS, earned value, contracts/change/payment, workflows, cash flow | Enterprise project-control pattern | Accept WBS/CBS distinction, governed controls, integrated cash forecast |
| Procore | Mobile field-cost capture, budgets/forecast, changes, invoices/payments, accounting integrations | Low-friction field-to-finance pattern | Accept exception-driven mobile UX and accounting boundary |
| CMiC | Single-database construction ERP spanning finance, project management, payroll/HCM, equipment/inventory and prequalification | Full-suite integration pattern | Confirms target breadth; does not justify simultaneous implementation |
| Sage Construction | Job cost, payroll, WIP, time/mobile and financials | Construction accounting/payroll pattern | Accept job-cost/payroll integration and WIP reporting requirement |
| Trimble construction products | Estimating/cost libraries, quote comparison, budget/progress/certificates/forecasting | Estimate-to-control and sourcing pattern | Accept rate/library governance and quote comparison |

### Iranian market baseline

For the intended segment, credible parity extends beyond general ledger screens:
contract/amendment and progress-claim documents, retention/advance/insurance and
other deductions, project/job cost, guarantees and expiry follow-up, payroll and
employee insurance output, tax/electronic-invoice workflows, bank/cheque controls,
Persian/Jalali document UX, and integration among purchasing, warehouse, cash and
accounting. Public vendor material establishes these as market signals; exact
legal behavior still requires current official verification.

### International construction ERP patterns

International suites consistently separate but connect field collaboration,
document control, project controls, commercial change, job cost, forecasts,
invoice/payment, payroll/equipment and core accounting. Their useful lesson is
the integration contract and exception-driven experience—not their organizational
size or feature count. WBS/CBS, mobile evidence, source drill-through, controlled
change and integration APIs are accepted patterns; a wholesale suite clone is not.

### Competitive UX and manual-work conclusions

- Market parity requires consistent mobile field capture, global/contextual search, saved filters, bulk review, exception queues, and drill-through—not just more forms.
- Iranian parity requires contractor-specific claims, deductions/retention/advance, guarantees, payroll/insurance, tax/e-invoice, Rial/Toman clarity, Jalali display, and Persian document outputs.
- The credible differentiator is an explainable chain from source evidence to operational approval, project cost, claim, posting, settlement, reconciliation, and KPI.
- A single database is not enough; single source of truth requires explicit domain ownership and reconciliation.
- Do not copy broad CRM, generic task management, BIM authoring, or marketplace features until they solve a verified contractor workflow.

### Product positioning capability assessment

The defensible initial position is an integrated operating and financial-control
system for Iranian construction contractors, not a generic accounting package
and not a BIM/scheduling authoring suite. The product should win on Persian-first
workflow, contractor-specific commercial rules, project/CBS costing, regulatory
adaptability, evidence-to-posting traceability, and low duplicate entry. It should
integrate with specialist schedulers/BIM/accounting endpoints when the customer
segment requires them rather than imitate every specialist surface.

For small contractors, enterprise structures remain optional and owner-fallback
workflows keep setup light. For larger contractors, project scope, separation of
duties, governed masters, multi-stage workflow, reconciliation, and portfolio
controls are mandatory. This one-model/two-operating-depth design is preferable
to separate “small” and “enterprise” products, provided optional structures do
not leak complexity into the default journey.

## 15. Security, tenant isolation, and production readiness

### Current strengths

- Active organization is resolved through membership/session context rather than trusted request organization IDs.
- Service boundaries validate tenant and project relationships; important transitions use transactions and row locks.
- Business permissions are registered and default-deny; audit evidence is append-only at the application layer.
- Production settings require secrets/hosts/database parameters and enable secure cookie/HSTS/no-sniff/frame protections with PostgreSQL TLS verification.
- Finalized operational/financial records generally use revision, void, or reversal rather than destructive edit.

### Gaps and release gates

| Gate | Required evidence before first production tenant |
| --- | --- |
| Tenant isolation | Automated cross-tenant and project/site-scope tests for every capability; object-scope threat model; admin/support-access controls |
| Identity | MFA for privileged roles, password/reset/session policy, optional future SSO boundary, recovery process, privilege-change alert/audit |
| Data protection | Private object storage, encryption/key ownership, signed short-lived download, malware/content scanning decision, backup encryption, sensitive logging review |
| Supply chain | Reproducible lock with hashes, CI checks, dependency/SBOM and vulnerability policy, license review, patch ownership |
| Deployment | Immutable build, environment matrix, migration/rollback rehearsal on PostgreSQL 18.6, zero/controlled downtime plan, seed separation |
| Recovery | Automated backup, restore exercise, RPO/RTO, regional/provider failure plan, evidence and named owner |
| Observability | Structured logs with correlation ID, metrics, error tracking, alert routing, audit-log monitoring, tenant-safe diagnostics |
| Performance | Representative volume profiles and budgets for lists, workbench, posting, costing, imports, reports, and document operations |
| Lifecycle | Retention, legal hold, tenant export, suspension/cancellation behavior, data deletion/anonymization decision |
| Finance/compliance | Accounting sign-off, regulatory-source register, opening/close/reversal tests, reconciliation controls, statutory export validation |
| Operations | Runbooks, incident severity/escalation, support-access grants, status/communication plan, responsible on-call ownership |

## 16. Dependency and library reuse assessment

No package is approved or added by this audit. Each candidate needs a proof of compatibility, license/security review, maintenance check, operational ownership, and an ADR or delivery decision.

| Need | Candidate/evaluation | Recommendation |
| --- | --- | --- |
| MFA/social/OIDC/SAML identity | `django-allauth` | Evaluate rather than build security protocols. Confirm exact edition/extras, threat model, migration, admin UX, and Django compatibility. |
| Object storage | `django-storages` plus provider SDK | Evaluate as adapter; verify Django 5.2 support, private-default behavior, signed URL and metadata controls. Do not move files before retention/export design. |
| Background jobs | Celery when concrete async work exists | Mature candidate for e-invoice transmission, OCR/scanning, reports, notifications. Do not introduce Redis/Celery for synchronous CRUD alone. |
| Dependency audit | `pip-audit` in CI | Prefer PyPA tooling and a documented triage/SLA; pair with a reproducible lock/SBOM. |
| Error tracking | `sentry-sdk` or equivalent | Evaluate data residency, PII scrubbing, tenant tags, sampling, license/service cost. |
| Telemetry | OpenTelemetry stable API/SDK/exporters | Evaluate stable components; avoid depending on beta convenience distribution without justification. |
| PDF inspection/manipulation | `pypdf` | Suitable candidate for generic PDF structure/metadata/forms; it does not provide trust, OCR, or malware scanning. |
| File type detection | maintained `libmagic` binding/service | Evaluate platform packaging and maintainer risk. Extension/content-type/signature checks alone are insufficient; antivirus remains separate. |
| Rules/calculations | Python/Django/Decimal/PostgreSQL constraints | Keep construction, payroll, tax configuration application, posting, and reconciliation rules owned and explicitly tested. Do not adopt a generic rules engine prematurely. |
| Workflow | Existing bounded workflow platform | Keep. Do not replace it with general BPMN unless a demonstrated process cannot be represented safely. |

The current five declared requirements are intentionally small. Do not retain undeclared packages just because they exist in a developer virtual environment. Pinning, hashes, automated updates, and compatibility testing matter more than adding many utilities.

## 17. UI/UX consistency audit

The UI has a strong Persian-first RTL foundation, shared shell, status and table patterns, and increasingly consistent list behavior. Coverage remains uneven across domains. Key gaps are now standardized in `docs/ui-guidelines.md`: explicit tenant/project/site context; cascading selectors; scalable search selectors; line-item grids; URL-stable filters; workbench actions; financial unit/currency display; document/evidence UX; disabled-action reasons; archive/void/reversal confirmation; AI review; audit/source lineage; responsive site workflows; and accessibility.

Current corrective themes:

- Consolidate duplicated/legacy table-filter component variants rather than creating more page-local patterns.
- Avoid wide tables as the only mobile representation; define priority columns and row summaries.
- Permission-aware navigation is useful but cannot replace server authorization or future project scope.
- Daily-entry forms need master-backed context-aware choices before downstream time/equipment costing.
- Every blocked workflow action should explain whether the cause is status, permission, assignment, missing data, closed period, or tenant state without leaking unauthorized facts.

## 18. Documentation audit

| Document | Finding | Action |
| --- | --- | --- |
| `AGENTS.md` | Concise durable engineering rules; aligned with current product | Keep; do not turn into product backlog |
| `ROADMAP.md` | Dependency-based P0-P10 portfolio roadmap, reconciled against accepted capability scope | Keep dispositions explicit as scheduled, deferred with trigger, or rejected with reason |
| `DOMAIN_MODEL.md` | Target domain ownership and bounded-context reference | Keep target-only; current implementation stays in code and `DOMAIN_AND_DATA_MODEL.md` |
| `DATA_MODEL.md` | Target source-of-truth, lineage and conceptual-data rules | Keep conceptual; do not treat as a physical schema or migration instruction |
| `BUSINESS_MODEL.md` | Product/customer/value/packaging/operating-model reference | Keep commercial decisions explicit and separate from implementation status |
| `USER_CAPABILITY_MAP.md` | User groups, goals and capability coverage | Keep separate from exact permission grants and service authorization |
| `WORKFLOW_AND_PERMISSION_MATRIX.md` | Cross-domain lifecycle, permission, scope and SoD policy | Keep exact current codes/transitions subordinate to code/tests |
| `DOMAIN_AND_DATA_MODEL.md` | Stale workflow/billing status and obsolete exclusion of Accounting/Payroll | Correct current/target boundary and link this audit |
| `BILLING_AND_PROGRESS_CLAIMS.md` | Delivered architecture record still contains pre-implementation wording | Mark delivered scope and current known debt |
| `TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md` | Detailed and current acceptance evidence | Keep as domain authority |
| `docs/ui-guidelines.md` | Strong base; missing several requested enterprise patterns | Complete official standards in-place |
| `docs/PROJECT_STATUS.md` | Useful dated historical validation record | Keep historical; never treat as current source of truth |
| `PROJECT_SNAPSHOT.md` | Stale duplicate of status history | Merge useful history into `docs/PROJECT_STATUS.md` and remove duplicate |
| `README.md` | Stale: says workflow/billing are future | Correct concise current status and document links |

## 19. Pre-production correction register

| ID | Class | Correction candidate | Concrete reason and timing |
| --- | --- | --- | --- |
| PPC-01 | **MUST** | Split `BillingPolicy` ownership and effective dates | Prevent wrong historical/legal calculations before first real claim. Contract commercial terms belong to versioned contract terms; regulatory rules to approved rule sets; formatting/numbering to tenant configuration. |
| PPC-02 | **MUST** | Accounting/Treasury/AP/AR boundaries and posting kernel | Financial history becomes expensive to migrate immediately after go-live. Define before building more cash/claim/payroll integrations. |
| PPC-03 | **MUST** | One budget/actual authority and CBS/cost-center model | Manual project totals will conflict with estimate/budget and transaction actuals. Correct before real budgets/cost history. |
| PPC-04 | **MUST** | Project/site object-scope authorization | Tenant-wide permission is too broad for larger contractors and sensitive payroll/finance. Add before real multi-project tenants. |
| PPC-05 | **MUST** | Production security/operations gates | Avoid deploying without MFA, storage, dependency, backup/restore, observability, retention/export, support controls. |
| PPC-06 | **MUST** | Effective-dated regulatory registry and professional review | Annual/changing rules must not live in constants or mutable policy. Required before taxpayer/payroll/insurance features. |
| PPC-07 | **SHOULD** | Consolidate organization settings authority | Avoid permanent dual-write ambiguity before integrations consume locale/currency/fiscal settings. |
| PPC-08 | **SHOULD** | Canonical role vocabulary and separation-of-duties policy | Clarify accountant/supervisor/admin duties while preserving owner invariants; migrate grants explicitly. |
| PPC-09 | **SHOULD** | Master-backed daily labor/equipment links | Unlock payroll/equipment costing while preserving snapshot text for history. |
| PPC-10 | **SHOULD** | Extensible explicit DMS link ownership | Avoid continually widening one nullable-FK table; decide before many new domains adopt DMS. |
| PPC-11 | **SHOULD** | Party regulatory/bank/qualification profiles and UOM conversions | Required for tax, Treasury, sourcing, claims, and reliable quantity conversion. |
| PPC-12 | **SHOULD** | Audit correlation/change metadata | Essential for incident analysis and end-to-end posting/integration traceability. |
| PPC-13 | **DEFER** | Migration-history cleanup/squash | Existing migrations remain history. Consider only as a separate ADR immediately before first deployment if operational benefit outweighs audit/review cost; never delete casually. |

## 20. ADR candidates and product-owner decisions

### Required ADR candidates before affected implementation

1. `ADR: Accounting ledger, posting registry, reversal, period close, and dimensions`.
2. `ADR: Treasury/AP/AR boundaries and migration/containment of Payment`.
3. `ADR: Budget/CBS/cost-center authority and retirement of Project summary totals`.
4. `ADR: Effective-dated regulatory configuration and contract commercial term versioning`.
5. `ADR: Project/site authorization scope and intersection with tenant permissions/workflow candidacy`.
6. `ADR: Private object storage, malware scanning, retention, legal hold, and export`.
7. `ADR: DMS cross-domain linking without GenericForeignKey`.
8. `ADR: Async job/outbox/idempotency boundary for integrations and notifications`.
9. `ADR: Tenant lifecycle, subscription/entitlements/quotas, offboarding, and support access`.
10. `ADR: Controlled business-network identity, consent, privacy, and revocation` before any cross-tenant feature.

### Major product-owner decisions

- Initial production segment: small contractor, mid-market multi-project contractor, or both; this drives project scope, payroll complexity, and support model.
- First production financial boundary: operational ERP integrated with an external accounting package, or native Accounting/Treasury books. Avoid an ambiguous half-ledger.
- Regulatory launch scope: taxpayer invoice submission, payroll tax, employee insurance, contractor Article 38 controls, and which outputs must be legally filed from the product.
- Currency requirement: IRR only initially or multi-currency contracts/settlement; always keep Rial/Toman display explicit.
- Inventory valuation method and whether perpetual financial valuation is in first release.
- Payroll employment/pay components and whether attendance devices/providers are integrated in the initial scope.
- Required document signature/evidence standard and retention periods.
- Hosting/data-residency/support model and acceptable RPO/RTO.
- Network participation model and the minimum verified value that justifies its privacy/operational cost.

## 21. What not to build yet

- No microservice split, event sourcing, generic repository layer, second workflow engine, or tenant-authored executable rules.
- No custom authentication protocols, cryptography, object-storage client, task queue, PDF parser, malware engine, or telemetry protocol when maintained options satisfy the requirement.
- No generic CRM, payroll for every industry, BIM authoring, public marketplace, opaque cross-tenant scoring, broad chatbot with write access, or data warehouse before authoritative facts and metrics stabilize.
- No destructive rewrite of working domains for stylistic purity. Corrections need an ownership, integrity, security, compliance, or unavoidable migration-cost reason.
- No automatic financial/legal action based only on OCR or AI. Consequential operations call ordinary authorized services after review/confirmation.

## 22. Research source register

Sources were accessed 2026-09-23. Vendor pages are evidence of marketed capability, not independent validation. Iranian legal mirrors/secondary pages are discovery aids; implementation requires verification against current official tax, labor, social-security, and accounting authorities.

### Iranian legal and market sources

- Taxpayer terminal/invoice regulations and instruction mirrors: [Nezamat Article 12 instruction](https://nezamat.ir/post-43262/), [Nezamat Article 6 regulation](https://nezamat.ir/post-43316/), [law text mirror](https://law-ir.ir/law/cat/1769/), and [electronic-invoice instruction PDF attributed to the Tax Administration](https://acco.ir/wp-content/uploads/2023/12/%D8%B5%D9%88%D8%B1%D8%AA%D8%AD%D8%B3%D8%A7%D8%A8-%D8%A7%D9%84%DA%A9%D8%AA%D8%B1%D9%88%D9%86%DB%8C%DA%A9%DB%8C-%D8%A2%D8%B0%D8%B1-%DB%B1%DB%B4%DB%B0%DB%B2.pdf).
- [Direct Taxes Act mirror](https://nezamat.ir/post-28895/) and [Labor Law mirror](https://nezamat.ir/post-30105/).
- Social-insurance/contractor sources: [Article 38-related text](https://nezamat.ir/post-41968/), [list-timing-related text](https://nezamat.ir/post-28263/), and Social Security Organization newsroom material on [smart list service](https://newsroom.tamin24.ir/news/nklb-dr-osol-hk-bmh-lst-hoshmnd-tamn-gtmaa-o-m-bh-so-szmn-b/) and [electronic services](https://newsroom.tamin24.ir/news/smndh-o-tshl-khdmt-bmh-fd-sbor-rhsz-smnhh/).
- Iranian product sources: [Sepidar contractor accounting](https://www.sepidarsystem.com/products/sepidar/contractor-accounting-software/), [Sepidar contractor system](https://www.sepidarsystem.com/products/sepidar/contractor-system/), [Sepidar taxpayer system](https://www.sepidarsystem.com/products/sepidar/taxpayer-system/), [Rasam contract management](https://rasamerp.com/contract-management/), and [Samanban project-oriented companies](https://www.samanban.com/project-oriented-companies/).

### International product sources

- Autodesk: [Construction Cloud](https://construction.autodesk.com/), [document management](https://construction.autodesk.com/workflows/construction-document-management/), and [cost management](https://construction.autodesk.com/workflows/construction-cost-management/).
- Oracle: [Primavera Unifier project controls and asset management](https://www.oracle.com/construction-engineering/primavera-unifier-project-controls-asset-management/).
- Procore: [financial management](https://www.procore.com/financial-management) and [cost management](https://www.procore.com/cost-management).
- CMiC: [platform](https://cmicglobal.com/), [payroll/HCM](https://cmicglobal.com/products/construction-financials/human-capital-management-and-payroll), and [financials solution brief](https://cmicglobal.com/wp-content/uploads/2019/04/CMiC-Financials-Accounting-Solution-Brief_.pdf).
- Sage: [construction](https://www.sage.com/en-us/sage-construction/) and [construction payroll](https://www.sage.com/en-us/sage-construction/payroll/).
- Trimble: [Quest](https://construction.trimble.com/en/products/quest) and [ProContractor help](https://help.trimble.com/nl-nl/procontractor/procontractor/welcome-to-procontractor).

### Dependency sources

- [django-allauth](https://pypi.org/project/django-allauth/), [django-storages](https://pypi.org/project/django-storages/), [Celery](https://pypi.org/project/celery/), [pip-audit](https://pypi.org/project/pip-audit/), [Sentry SDK](https://pypi.org/project/sentry-sdk/), [OpenTelemetry distro](https://pypi.org/project/opentelemetry-distro/), [pypdf](https://pypi.org/project/pypdf/), and [python-magic-standalone](https://pypi.org/project/python-magic-standalone/).

## 23. Audit acceptance checklist

- Current and target states are explicitly separated; workflow runtime and Billing are not re-planned as missing.
- Payroll, employee insurance lists, Accounting, Treasury, project costing, fixed assets, guarantees, HSE/Quality-to-Knowledge, partner performance, controlled network, support, AI support, and reconciliation remain in target scope.
- Duplicate authorities and pre-production correction candidates are explicit.
- No current regulatory rate/schema is hard-coded or presented as legal advice.
- Tenant filtering and UI visibility are never treated as authorization; project/site scope is a release prerequisite.
- Every financial/KPI target has an authoritative source and drill-through expectation.
- Roadmap phases are dependency-ordered and do not authorize implementation.
- No application code, behavior, package, or migration is changed by this audit.
