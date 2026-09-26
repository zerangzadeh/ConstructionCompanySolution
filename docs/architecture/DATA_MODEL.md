# Target Data Model and Source-of-Truth Rules

**Status:** conceptual target reference; Django models and migrations remain the current schema authority

**Domain ownership:** `DOMAIN_MODEL.md`

**Delivery and migration order:** `../../ROADMAP.md`

## 1. Purpose

This document defines how the target product represents identity, ownership,
relationships, history, financial facts, evidence and derived information. It is
not a proposed migration file, physical schema, or instruction to create every
named concept immediately.

## 2. Universal data rules

- Every tenant-owned business row carries an explicit `organization` foreign key,
  including child, history, link and reconciliation rows where practical.
- Never derive tenant authority from an organization ID supplied by a user. Resolve
  active membership, then validate every related record against that organization.
- Important public identifiers use UUIDs; human document numbers use explicit
  organization-scoped numbering rules and remain distinct from primary keys.
- Money and measured quantities use `Decimal` with explicit currency/unit and
  documented quantization. Binary float is prohibited for business calculation.
- Store canonical Gregorian dates/timezone-aware instants; render Jalali and
  tenant timezone at the presentation boundary.
- Finalized facts are append-only or mutation-restricted. Correction uses a linked
  revision, reversal, void, adjustment, release, supersession or replacement.
- Effective records carry `valid_from`, optional `valid_to`, status and approval
  evidence where historical selection matters.
- Rebuildable projections, caches and KPIs identify source records and never
  become transaction authorities.
- Cross-domain generic foreign keys are not the default. Prefer explicit links,
  domain-owned link tables, or an approved constrained registry.

## 3. Identity and tenant topology

```text
User (global authentication identity)
  -> OrganizationMembership (tenant access identity)
       -> MembershipRoleAssignment [target, zero-to-many independent assignments]
            -> Role -> BusinessPermission grants
       -> Project/Site scope grants [target]
       -> Workflow candidacy/assignment [responsibility, not permission]

Employee (tenant workforce identity) -- optional --> User
BusinessParty (tenant counterparty identity) -- independent of --> User/Employee
```

Target identity additions include MFA/SSO evidence, invitation/onboarding history,
time-limited support-access grants, entitlements/quotas and project/site scope.
External portal identity must be explicitly invitation-scoped and cannot expose
the tenant user directory or imply ordinary membership.

Tenant/business role assignment is membership-scoped. The same User may hold
Tenant Owner plus Tenant Admin plus Project Manager in one Tenant and only Project
Manager in another. These remain independent assignment rows; common combinations
must not become composite roles. Effective role permissions are unioned across
active applicable assignments and then intersected with membership, explicit
grants, project/site scope, delegation, workflow eligibility and policy constraints.
Adding or removing one role changes no other role assignment. Assignment/revocation
history retains actor, Tenant, role, timestamp and relevant reason/context.

## 4. Master-data catalogue

| Master | Authoritative domain | Key target facts | Historical rule |
| --- | --- | --- | --- |
| Organization settings | Platform/Tenant | locale, timezone, currency, fiscal/numbering settings | One authority; effective history where calculations depend on it |
| Role/permission/scope | Authorization | code-owned permission, membership-scoped independent role assignments, role grants, project/site scope | Effective grants plus audited role assignment/revocation and elevation/removal |
| Employee/position/team | Workforce | identity, employment state, effective responsibility | Assignment history retained; optional `User` link |
| Skill/qualification/training | Workforce | competency, evidence, issuer, dates, proficiency | Expiry/revocation and applied qualification preserved |
| Party/contact/profile | Parties | legal/tax identity, roles, contacts, bank/qualification facts | Effective/verified state; sensitive-field permissions |
| Material/category | Materials | canonical tenant code, aliases, technical attributes, approval | Merge/alias history; transactions retain snapshot/reference |
| UOM/conversion | Materials | dimension/family, canonical unit and directed conversion | Version/precision where commercial history depends on it |
| Project/site/WBS/activity | Projects | operational structure and location/context | Approved baseline/rebaseline history separate from current display |
| CBS/cost center | Project Controls | financial cost classification and WBS/activity mapping | Mapping/version retained with budget and cost facts |
| COA/dimensions | Accounting | account hierarchy and posting dimensions | Effective status; posted lines retain original account/dimensions |
| Bank/cash account | Treasury | controlled account identity and accounting mapping | Sensitive, effective and approval-controlled |
| Regulatory rule version | Compliance Configuration | jurisdiction, rule type, parameters/schema, source/reviewer | Immutable after activation; document snapshots applied version |
| Workflow catalogue | Platform code | registered step/condition/routing/command types | Code/version controlled; tenant definitions compose only allowed types |

## 5. Target conceptual entity groups

Names are descriptive and may change during an approved detailed design.

| Area | Target concepts |
| --- | --- |
| SaaS lifecycle | Plan, FeatureEntitlement, Quota/Usage, SubscriptionState, TenantExport, RetentionPolicy, OffboardingRun, SupportAccessGrant |
| Authorization | MembershipRoleAssignment/history, ProjectScopeGrant, SiteScopeGrant, Elevation/Delegation evidence, separation policy |
| Materials | MaterialAlias, AttributeDefinition/Value, UOMConversion, MaterialSubstitute, MaterialPriceObservation, MaterialApproval |
| Workforce | Skill, CompetencyRequirement, EmployeeSkill, Certificate, Training, PerformanceEvaluation, LaborRateVersion |
| Estimate/BOQ | EstimateScenario/Revision, ResourceAnalysis, Coefficient/Adjustment, RateSource, PriceBookVersion/Item, ImportRun/Row, BudgetHandoff |
| Project cost/control | BudgetBaseline/Version/Line, CBSNode, CostCenter, Commitment, Accrual, CostFact projection, ForecastVersion/Line, Risk/Change/Schedule baseline |
| Accounting | FiscalYear/Period, Account, JournalEntry/Line, PostingRuleVersion, PostingSource, ReversalLink, Close/Reopen evidence |
| AP/AR | Obligation/OpenItem, Credit/DebitAdjustment, Allocation, Aging projection, SubledgerReconciliation |
| Treasury | Bank/CashAccount, Receipt/Payment/Transfer, Cheque/Instrument, Statement/Line, Match/Reconciliation, PaymentProposal |
| Procurement | RFQ/Invitation, Quote/Revision/Line, Comparison/Award, PO/Change, Receipt/ServiceAcceptance, SupplierInvoice/MatchException |
| Contract/Billing | ContractTermVersion, Variation, Guarantee/Security, Measurement, Claim/Certificate, Adjustment, Retention/Advance balance projection, Settlement |
| Payroll/insurance | WorkCalendar/Shift, Attendance, Timesheet, Leave, PayrollRuleVersion, PayrollRun/EmployeeResult/Component, InsuranceList, Tax/InsuranceSubmission |
| Inventory | Reservation, StockTransaction, Lot/Batch, Serial, Bin, Count/Line, TransferCustody, ValuationLayer |
| Equipment/assets | Meter/Usage, Fuel, OperatorQualification, MaintenancePlan/Work, EquipmentCostRate, FixedAsset, DepreciationRun/Line, Disposal |
| Field operations | DailyReport, WeatherObservation, WorkFront, Visit, Meeting, Instruction, media/evidence link, reviewed downstream proposal |
| HSE/Quality | Risk, Inspection, Permit, Toolbox/PPE control, Incident/Investigation, ITP, InspectionRequest, Test/SampleApproval, Punch/NCR/Rework, CAPA |
| DMS/media | Document, DocumentVersion, classification, domain link, OCR/TextExtraction, SignatureEvidence, Transmittal/RFI/Submittal/Drawing control, MediaAlbum view |
| Knowledge | LessonLearned, BestPractice, TechnicalNote, Procedure, KnowledgeArticle, CaseStudy, Promotion/PublicationVersion, ReuseEvidence |
| Partner | Qualification, Evidence/Expiry, CategoryApproval, ProjectEvaluation, PerformanceMetric/ScoreExplanation |
| Support/AI | Notification, SupportCase, KnownIssue, FeatureRequest, ReleaseLink, DiagnosticConsent, Knowledge source, AIInteraction/Review evidence |
| Reporting/reconciliation | MetricDefinition, ProjectionRefresh, ReconciliationRun/Exception/Resolution, Report/ExportJob |
| Future network | PlatformPartyClaim, VerifiedRelationship, PublicationConsent, Discovery/Recommendation, anonymized aggregate with privacy controls |

## 6. Transaction source-of-truth matrix

| Business fact | Authoritative record | Consumers |
| --- | --- | --- |
| Approved commercial commitment | Contract/term/amendment or issued PO version | Project Cost, cash forecast, AP/AR/posting proposal |
| Approved project budget | Accepted BudgetBaseline version | Forecast/variance and commitment control |
| Physical progress | Approved measurement/progress record and evidence | Claim eligibility and earned metrics |
| Certified receivable/payable | Approved claim/certificate version | AR/AP, posting, cash forecast and settlement |
| Supplier liability | Approved/matched supplier invoice or payable certificate | AP, Accounting and Treasury proposal |
| Employee payroll liability | Finalized payroll run/result | AP-like liability, Accounting, Treasury and project labor cost |
| Cash/instrument state | Treasury transaction/instrument plus clearing evidence | Accounting posting and cash position |
| Accounting balance | Posted balanced journal lines | Statements, close and reconciliation |
| Inventory quantity | Posted/reversed stock ledger | On-hand/reservation and valuation |
| Inventory value | Approved valuation layers reconciled to quantity | Project Cost and Accounting control |
| Asset carrying value | Fixed-asset transaction/depreciation ledger | Accounting and asset reporting |
| Project actual cost | Classified source posting/subledger facts | Project Cost read model and KPIs |
| Knowledge claim | Reviewed publication version with source evidence | Search, checklist/training/control suggestion |
| KPI | Governed metric definition over authoritative facts | Dashboard/report cache with drill-through |

## 7. Financial posting model

An operational document never writes arbitrary ledger rows. A registered,
versioned posting rule converts one finalized source version into a balanced
posting proposal with a unique idempotency key. Accounting validates open period,
dimensions, currency and balance before posting. A posted journal is immutable;
correction creates a reversal and, when needed, replacement.

```text
Finalized source/version
  -> PostingSource + rule version + idempotency key
  -> balanced JournalEntry/JournalLines
  -> subledger/project-cost projections
  -> source-to-subledger-to-GL reconciliation
```

Treasury transactions, AP/AR allocations, claim settlements and project cost
facts are not journal lines. They reconcile to journals through explicit links.

## 8. Effective dating and snapshots

Use effective versions for regulatory rules, contract terms, labor/pay rates,
qualifications, assignments, material conversions/prices where relevant, posting
rules and account mappings. Finalized documents record the applied version plus
material calculated inputs/outputs. A later master/rule edit cannot reinterpret
approved history.

Snapshot text remains valuable for legal/display history even when a master link
exists. Label current master value separately from the recorded value.

## 9. Evidence, documents, and media

`DocumentVersion` or its approved successor remains the private immutable blob
authority. OCR text, thumbnails, previews and signatures are derived/evidence
records tied to a version. Media galleries are views/collections over the same
storage authority. Domain documents such as RFI, Submittal and InspectionRequest
own their business lifecycle and link their evidence; they do not duplicate file
storage.

Retention, legal hold, export, malware/content status and access audit apply at
the document/version/link boundary. Search indexes are rebuildable projections
and must enforce tenant/object permissions before returning results.

## 10. Reconciliation and data lineage

Each cross-domain fact stores or can derive: tenant, project/context, source
type/id/version, effective/document/posted dates, status, unit/currency,
producer/consumer, posting/integration key and reversal/replacement lineage.
Reconciliation exceptions are append-only resolution evidence, not editable
alternate balances.

Required controls include estimate-to-budget, commitment, PO-receipt-invoice,
inventory quantity/value, claim-to-subledger, AP/AR-to-GL, Treasury-to-bank,
payroll, fixed assets and Project Cost source completeness.

## 11. Network and privacy boundary

Tenant-local party, material, qualification, price and performance data remain
private by default. Future network records use separate platform identity/claim,
explicit publication consent, purpose, audience, provenance, verification,
expiry/revocation and abuse controls. Anonymized benchmarking requires a defined
aggregation/privacy threshold and must not permit re-identification.

The [P0-S12 future-network privacy proposal](ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md)
develops ownership, consent, revocation, isolation, retention and acceptance
boundaries without creating these conceptual records or authorizing network scope.

## 12. Schema-evolution policy

Before production, correct high-cost ownership flaws deliberately, but retain
migration history. Use expand -> migrate/backfill -> switch -> validate ->
separately approved contract. Development/demo data may be discarded when safer;
real finalized data later requires revision/reversal-compatible migration.

Every schema package defines constraints, indexes, deletion/protection behavior,
data migration, rollback/recovery, tenant/project validation, concurrency,
idempotency, permissions, audit and PostgreSQL acceptance evidence.
