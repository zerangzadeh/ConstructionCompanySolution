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

P1-S16 keeps `BusinessParty` identity Tenant-local. Normalized display/legal and
existing identifier values are match evidence, not cross-Tenant identity proof and
never trigger automatic merge. Identity changes append immutable snapshots. An
explicit merge records one direct same-Tenant survivor, archives the source for new
selection and preserves every historical FK to that source. Generic restrictions
remain in the party context with explicit Tenant/Platform scope, effect and
effective interval; only the explicit transaction-block effect can make the
unactivated reusable guard deny a new transaction.

P1-S17 adds immutable normalized aliases that resolve only inside the Tenant and
follow an explicit merge survivor without rewriting source evidence. Tenant-owned
category/tag assignments and representative/signatory authority are historical,
effective/revocable records. Representative evidence is neither `User` identity
nor an authorization grant; regulated bank, tax, legal and qualification profiles
are not implemented by these generic records.

Target identity additions include MFA/SSO evidence, invitation/onboarding history,
time-limited support-access grants, entitlements/quotas and project/site scope.
External portal identity is explicitly invitation-scoped and cannot expose the
tenant user directory or imply ordinary membership. P5-S18–S22 implement an
immutable `SupplierPortalPrincipal` bound to a Tenant-local `BusinessParty` and an
existing authenticated `User`, with token-hash-only invitations, exact RFQ-
invitation capability grants, append-only revocation and submission receipts.

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
| Material/category | Materials | canonical tenant code, aliases, category-scoped declarative attributes, sourced observations, immutable relationships and technical approval evidence | Version-pinned governed documents and immutable definition/value/import/approval history; observations are not quotes or ledger facts |
| UOM/conversion | Materials | Tenant family/dimension, one family base and directed conversion to base | Immutable effective version/rounding snapshots; legacy units begin isolated with no invented factor |
| Project/site/WBS/activity | Projects | operational structure and location/context | Approved baseline/rebaseline history separate from current display |
| CBS/cost center | Project Controls | versioned planning cost classification and WBS mapping; integrated cost-fact use remains deferred | Locked structure and mapping/version retained with immutable accepted budget; later cost facts must pin the same evidence explicitly |
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
| Materials | MaterialAlias, MaterialDuplicateCandidate, MaterialSupersession, UnitFamily, UnitConversionVersion, QuantityRoundingPolicyVersion, QuantityConversionSnapshot, MaterialAttributeDefinition/Value, MaterialRelationship, MaterialPriceObservation, MaterialTechnicalApproval, MaterialDocumentLink |
| Workforce | Skill, CompetencyRequirement, EmployeeSkill, Certificate, Training, PerformanceEvaluation, LaborRateVersion |
| Estimate/BOQ | EstimateScenario/Revision, ResourceAnalysis, Coefficient/Adjustment, RateSource, PriceBookVersion/Item, ImportRun/Row, BudgetHandoff |
| Project cost/control | Implemented BudgetVersion/manifest/allocation, CBSNode, CostCenter, ProjectCostSourceContract, append-only ProjectCostFact, ProjectCostCoverage, immutable ProjectCostForecast draft, bounded non-persistent cost-evidence reconciliation, ProjectScheduleRevision/Item/Dependency, ProjectControlItem/StatusEvent, ProjectChangeProposal and ScheduleRebaselineProposal; producer activation and accepted schedule/change/rebaseline policy remain gated |
| Accounting | FiscalYear/Period, Account, JournalEntry/Line, PostingRuleVersion, PostingSource, Reversal/Replacement/Adjustment links, immutable FinancialStatementRun/LineSnapshot, FiscalPeriodControlEvent close/reopen evidence |
| AP/AR | Implemented immutable Obligation, Treasury-linked Allocation/Reversal, WriteOffProposal, exact AgingRun, SubledgerReconciliationRun and independent signed ReconciliationReview; P5-S15–S17 add AP/Finance-owned SupplierInvoice/Version/Line plus immutable derived MatchEvidence/Discrepancy and tolerance versions. Matching owns no source document; payable/source-resolver and posting activation, material match-exception approval, approved write-off decision/reversal and credit/debit adjustment policy remain gated. |
| Treasury | Bank/CashAccount, Receipt/Payment/Transfer, Cheque/Instrument, unscheduled PaymentRequest, Employee/VendorAdvance and cash-return Settlement, retained source-to-GL reconciliation plus independent signed review, BankStatementImport/Line, exact Match/Clearing/Reversal and BankReconciliationRun; PaymentProposal and provider adapters remain target concepts |
| Procurement | Implemented internal RFQ/version/invitation, sealed quote custody/opening/admissibility, P5-S11 comparison and immutable sourcing-only award/allocation successors, plus P5-S12–S17 explicit award-to-PO consumption, immutable issued-PO/change versions and version-pinned goods receipt/service acceptance. AP/Finance-owned supplier-invoice versions and immutable match/tolerance/discrepancy evidence consume these sources without mutating them. Controlled exact-version delivery remains service-owned and generic document paths remain denied. Payable/GL/cost/stock/cash handoffs remain dormant. |
| Contract/Billing | Implemented Billing authorities remain distinct from Contracts-owned `ContractualRecord`/`ContractualRecordEvidence`. P6-S33–S38 retains versioned Site Instruction, Variation/Change Order, contractual Claim and EOT evidence, explicit approved entitlement/amount/delay-responsibility/EOT-day facts, typed source references and linked withdrawal/correction/cancellation history. Existing term, claim/certificate, guarantee/compliance and statutory records remain unchanged. Automatic contract/amendment, budget, schedule, AP/AR, subledger, GL, Treasury/cash and production effects remain gated. |
| Time and attendance | Implemented WorkCalendar/Holiday/Shift/Break, Attendance/Import/Adjustment/Reconciliation, LeaveMissionRequest, OvertimeRequest, Timesheet/Entry/Review and minute-only LaborDistributionPreview |
| Payroll/insurance | P7-S01–S36 is Product Owner accepted and complete within its documented non-production boundary. Immutable `FinancialHandoffProposal` envelopes and lines, review, downstream acknowledgment and reconciliation evidence pin finalized run/result, currency and monetary-policy lineage; Project Cost lines additionally pin approved timesheet entry and coding. Final assurance preserves immutable retention, rule/policy/source version history, explicit retroactivity and family-minimized sensitive access. No recognized obligation, journal, payment/cash movement, Project Cost actual, P8 behavior or production activation exists. |
| Inventory | P8-S05–S17 is Product Owner accepted: existing `StockTransaction` remains posted quantity authority; custody/traceability/count/transfer records plus `InventoryValuationEvent`, `InventoryValuationPool`, `InventoryValuationException` and proposal-only `DownstreamCostSourceEnvelope` add moving-WAC value evidence without journal or Project Cost actual creation. |
| Equipment/assets | P8-S01–S30 is Product Owner accepted and complete within documented non-production boundaries. P8-S24–S27 implements Equipment-owned `EquipmentCostPolicyVersion`, component rates, conserved allocations and proposal envelopes plus distinct Fixed Assets class/book policies, register/source/link records, transaction/depreciation evidence and proposal/reconciliation envelopes. P8-S28–S30 assurance adds conserved transfer/reversal evidence, source-dimension lineage, bounded depreciation sequencing/rounding and one-source-per-consumer handoff protection. C01–C38=A governs the accepted non-production boundary; no downstream journal or Project Cost actual is created. |
| Field operations | Existing DailyReport records plus P9-S01–S05 `FieldObservation`, append-only draft revision/status history, DMS-version-pinned `FieldObservationEvidenceLink`, and `FieldDownstreamProposal`/transition evidence. Field Operations stores no document bytes and proposal records create no downstream fact. |
| HSE/Quality | Product Owner-accepted P9-S06–S11 implements typed `InspectionTemplate`/immutable versions, `Inspection`, `Permit`, `QualityTest`/immutable `TestResult`, `InspectionFinding`, explicit QA `Nonconformance`, `CapaAction`, exact-version `ComplianceEvidenceLink`, lifecycle events and source-only proposals. Existing Incident/QualityIssue remain separate; Risk, Toolbox/PPE, broader ITP/SampleApproval/Punch/Rework and knowledge are later. |
| DMS/media | `Document(type=PHOTO)` and immutable `DocumentVersion` remain the sole photo-byte authority. Metadata-only `PhotoMetadata` records camera/upload provenance and optional capture time; registered `ProjectDocumentLink`, `ProjectSiteDocumentLink`, and existing `DailyReportDocumentLink` provide reusable context. Project Gallery, protected preview and multi-upload are implemented without `GalleryImage` or public media. Broader consumer integrations, classification, OCR/TextExtraction, Transmittal/RFI/Submittal/Drawing control and album concepts remain target scope. |
| Knowledge | P9-S21–S24 Product Owner-accepted bounded runtime adds tenant- or separately Platform-owned Candidate/immutable revision and Publication/immutable version, typed source/DMS-version/hash provenance, governed RecurrenceEvidence and immutable ReuseEvidence. Source domains own facts and DMS owns bytes; focused PostgreSQL acceptance and rollback/reapply pass. |
| Partner | Product Owner-accepted P9-S12–S15 provides tenant-local BusinessParty-linked Qualification, exact DMS Evidence/Expiry, CategoryApproval, ProjectEvaluation and explainable PerformanceMetric/ScoreExplanation. No parallel partner master, inferred history or downstream consumer is created. |
| Support/AI | Product Owner-accepted P9-S16–S20 provides `Notification`, `SupportCase`, Support evidence/access history and source-linked calendar projections. AI interaction/review evidence, providers, queues and external integrations remain future concepts. |
| Reporting/reconciliation | P10-S02–S17 Product Owner accepted: six governed metrics and 13 governed reconciliation pairs retain immutable results, source manifests and append-only exception/rebuild evidence. S14–S17 adds `ProjectCloseoutProfileDefinition` and immutable versions across nine source-authority families; Tenant/project-scoped cases point to immutable assessments/item snapshots; append-only events and exact DMS version/hash links preserve acceptance, reopen and successor lineage; export manifests remain byte-free. No source/downstream authority or automatic backfill is created. Scheduled delivery and P10-S18+ remain future. |
| Future network | PlatformPartyClaim, VerifiedRelationship, PublicationConsent, Discovery/Recommendation, anonymized aggregate with privacy controls |

## 6. Transaction source-of-truth matrix

| Business fact | Authoritative record | Consumers |
| --- | --- | --- |
| Approved commercial commitment | Contract/term/amendment or issued PO version | Project Cost, cash forecast, AP/AR/posting proposal |
| Approved project budget | Accepted BudgetBaseline version | Forecast/variance and commitment control |
| Physical progress | Approved measurement/progress record and evidence | Claim eligibility and earned metrics |
| Certified receivable/payable | Approved claim/certificate version | AR/AP, posting, cash forecast and settlement |
| Supplier invoice evidence | AP/Finance-owned approved invoice version/line | Immutable matching evidence and payable disposition |
| Supplier liability | AP obligation linked to approved supplier-invoice/match evidence or payable certificate | Accounting and Treasury proposal |
| Employee payroll liability | Finalized payroll run/result and immutable Payroll handoff proposal | AP-like liability, Accounting, Treasury and project labor cost; each consumer recognizes independently and acknowledges without Payroll mutation |
| Cash/instrument state | Treasury transaction/instrument plus clearing evidence | Accounting posting and cash position |
| Accounting balance | Posted balanced journal lines | Statements, close and reconciliation |
| Inventory quantity | Posted/reversed stock ledger | On-hand/reservation and valuation |
| Inventory value | Inventory-owned, immutable valuation evidence reconciled to quantity; P8-S12–S17 Product Owner accepted | Accounting journals and Project Cost actuals remain separate consumer authorities |
| Asset carrying value | Fixed-asset transaction/depreciation ledger | Accounting and asset reporting |
| Project actual cost | Classified source posting/subledger facts | Project Cost read model and KPIs |
| Knowledge claim | Reviewed publication version with source evidence | Search, checklist/training/control suggestion |
| KPI | Governed metric definition over authoritative facts | Dashboard/report cache with drill-through |

A normal registered handoff pins one authoritative source owner, one consuming
owner, one semantic event and one resulting fact family. A derived/composite
calculation may pin immutable references from multiple authoritative domains but
owns only its versioned derived result. It cannot mutate source evidence or serve
as a generic cross-domain integration mechanism. Supplier-invoice matching follows
this derived contract across Procurement-owned order/acceptance evidence and
AP/Finance-owned invoice evidence.

P8-S05–S17 applies that rule to Inventory custody and valuation schema, and
P8-S18–S23 applies it to operational Equipment evidence. Procurement goods
receipt, Inventory quantity/custody/valuation, Equipment maintenance, future
Equipment cost proposals and Fixed Asset transactions, Accounting journals and Project Cost facts retain
separate source/version/line/occurrence identities. Operational `Equipment` and
financial `FixedAsset` are linked identities, never one aggregate. Existing stock
may be marked with explicit unknown/unlocated migration evidence, but no bin, lot,
serial, expiry, cost, useful life or depreciation history may be inferred. The
accepted earlier decisions in the existing P8 packets. Accepted P8-C01–C38=A,
the exact S24–S27 runtime boundary and implementation evidence are in
`P8_S24_S27_EQUIPMENT_COST_AND_FIXED_ASSETS_DECISION_PACKET.md`.

P4-S35–S37 does not change this authority matrix. Its reconciliation reads the
governing accepted budget, identically pinned approved/recorded expense
allocations and existing inert Project Cost facts as distinct evidence families.
It persists only audit evidence, labels coverage incomplete, and does not infer
source equivalence, completeness or zero from absence.

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

For the closed accounting-policy catalogue, only
`accounting-money-precision` and `accounting-rounding` are eligible for Tenant
selection. They use code-owned schemas (not free-form JSON) and their published v1
Product-defined contract is money scale `0`, intermediate scale `6`, unrounded
intermediate preservation and `ROUND_HALF_UP` only at the final monetary-line
boundary. Both policy versions are pinned on each posted journal and, for
P7-S13–S22, each locked Payroll run. A published version and its append-only source
links are immutable; correction is a
superseding version. Until a valid effective version is selected, accounting
posting fails closed. These values claim no statutory, legal or external
accounting authority.

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

P1-S19..S22 implement this boundary with immutable Tenant document numbers,
descriptive classification/confidentiality and expiry; domain-owned typed links
behind a closed registry; durable versions whose separate append-only processing
assessment controls availability; provider-neutral signature evidence; versioned
Tenant retention applications, legal holds, non-destructive disposal intents and
export manifests; and reconciled recovery evidence spanning DB, blobs,
policy/hold/audit and key custody. The legacy six-target link row remains an
expand/backfill/rollback compatibility projection and is dual-written; it is not
authorization authority. Unknown scan or retention state fails closed. Production
object storage/scanning, destructive disposal and concrete legal/recovery/quota
values remain unimplemented gates.

## 10. Reconciliation and data lineage

Each cross-domain fact stores or can derive: tenant, project/context, source
type/id/version, effective/document/posted dates, status, unit/currency,
producer/consumer, posting/integration key and reversal/replacement lineage.
Reconciliation exceptions are append-only resolution evidence, not editable
alternate balances. The delivered Accounting boundary retains versioned run scope,
cutoff, input/result hashes, ordered exception and tie-out snapshots, one immutable
disposition per exception and one independent protected review. Review pins the
verified run/disposition hashes and cannot mutate source facts, journals or balances.
The delivered Treasury bank boundary separately retains bounded synchronous
statement/file/row identities, exact match and clearing/reversal lineage, and
immutable as-of bank-reconciliation totals, unmatched/uncleared identifiers,
exceptions and evidence hashes. It neither creates a second cash movement nor
mutates Accounting history; provider parsing and independent review/sign-off are
later gates.
The delivered AP/AR foundation retains exact source/version/hash and party/object
snapshots, capped Treasury allocation/reversal lineage, per-item as-of aging with
undated evidence instead of invented buckets, and explicit missing-journal/control-
mapping reconciliation exceptions. No source adapter, posting mapping or write-off
approval is activated until the recorded Product Owner decisions are supplied.

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
