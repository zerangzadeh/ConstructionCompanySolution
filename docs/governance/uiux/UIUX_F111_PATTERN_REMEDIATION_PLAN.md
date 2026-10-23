# BONIRA F-111 Pattern Remediation Clustering & Execution Plan

## Baseline

Planning date: 2026-10-22, Asia/Tehran. Authority: the Human's bounded planning
request for UIUX-F-113 through UIUX-F-127. This document is a proposed execution
contract for future separately bounded tasks; it does not authorize implementation.

- Branch `main`; HEAD, upstream `origin/main`, and local `origin/main` reference:
  `43ac319c6e73e48ca9626461b73987922c498ec3`. No network fetch was performed.
- Existing eight modified product files contain the prior F-111 remediation:
  Daily Reports, Equipment, Procurement and Workforce forms/views, 180 insertions
  and 50 deletions. Existing UIUX evidence, Graphify output,
  `tests/test_uiux_f111_scope.py`, and three untracked generated-PDF directories
  are preserved. These changes are baseline, not work performed by this plan.
- UIUX-F-111 remains `RUNTIME_VERIFIED_RESOLVED`; its historical implementation
  status is retained. It is not reopened or included in a batch.
- Sweep: `COMPLETE`, decision `F111_PATTERN_SWEEP_FINDINGS_CONFIRMED`;
  42 units = 15 affected + 4 safe + 22 not applicable + 1 awaiting runtime
  confirmation. All 15 in-scope findings remain `finding_status: OPEN`,
  `status: STATIC_CONFIRMED`, `runtime_status: NOT_EXECUTED`.
- Wave C and broad UI remediation remain `NOT_STARTED`. CEP-078 and CEP-079
  remain unexecuted; their Registry execution fields are `NOT_STARTED` and their
  eligibility is `NOT_ELIGIBLE`. This plan does not change either record.
- No application, browser, HTTP, database, fixture or migration execution occurred
  in this planning task. Runtime reachability below is source-proved, not newly
  exercised.

Evidence read:
[sweep](UIUX_F111_SAME_PATTERN_SECURITY_SWEEP.md),
[findings register](UIUX_FINDINGS_REGISTER.yaml),
[original remediation](UIUX_F111_REMEDIATION_REPORT.md),
[original runtime retest](UIUX_F111_RUNTIME_RETEST_REPORT.md),
[source trace](f111_same_pattern_evidence/SOURCE_TRACE.json),
[gate matrix](f111_same_pattern_evidence/SCOPE_GATE_MATRIX.json),
[metrics](f111_same_pattern_evidence/METRICS.json), and
[verification](f111_same_pattern_evidence/VERIFICATION.json).
All 129 trace excerpts match current source at their recorded spans; all eight
artifact hashes listed by the prior verification match. The existing Graphify
graph was queried in memory for navigation only; no graph artifacts were written.

Current source controls over historical graph locations and reports. In
particular, the older remediation report's pending status does not supersede the
later F-111 runtime retest. Repository operating authority remains
[Agents.md](../../../Agents.md), the
[Execution Policy](../BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md), and
[Program Authority](../CEP_PROGRAM_AUTHORITY.md). No CEP is being executed here.

## Findings In Scope

| Finding | Module | Surface | Severity | Root Cause |
| --- | --- | --- | --- | --- |
| UIUX-F-113 | Procurement | SP-001 Purchase Request create | MEDIUM | Project choices omit effective project-scope intersection. |
| UIUX-F-114 | Procurement | SP-002 Goods Receipt create | HIGH | Issued Purchase Order choices omit inherited project authority. |
| UIUX-F-115 | Equipment | SP-003 Maintenance Record create | MEDIUM | Project/Site choices omit effective object scope. |
| UIUX-F-116 | Contracts | SP-007 Contract create | MEDIUM | Project choices omit effective project authority. |
| UIUX-F-117 | Inventory | SP-009 Warehouse create | MEDIUM | Optional Project choices omit effective project authority. |
| UIUX-F-118 | Inventory | SP-010 Stock Transaction create | HIGH | Project, warehouse and posted receipt-item choices omit their existing project authority. |
| UIUX-F-119 | Expenses | SP-011 Expense allocation | HIGH | Authorized parent read does not scope allocation Project/WBS/Activity choices. |
| UIUX-F-120 | Expenses | SP-013 Recurring templates | HIGH | Both Project choices and rendered template collection are tenant-wide. |
| UIUX-F-121 | Billing | SP-019 Three commercial create forms | HIGH | Shared commercial configuration omits Contract scope and canonical DMS visibility. |
| UIUX-F-122 | Billing | SP-020 Retention release clearance source | HIGH | Additional approved-clearance queryset bypasses its canonical reader gate. |
| UIUX-F-123 | Billing | SP-022 Payable measurement create | HIGH | ContractItem choices omit authority inherited through Contract.project. |
| UIUX-F-124 | Billing | SP-023 Payable certificate create | HIGH | Payable subcontract choices omit project authority. |
| UIUX-F-125 | Workforce | SP-030 Training Requirement create | MEDIUM | Optional Project choices omit project authority before later service checks. |
| UIUX-F-126 | Quality | SP-035 Quality issue create | MEDIUM | Five related-object choices omit effective project/site scope. |
| UIUX-F-127 | Safety | SP-036 Safety incident create | MEDIUM | Five related-object choices omit effective project/site scope. |

### Trace conventions and canonical rules

The per-finding records below include module, surface and severity through the
table above. Source references use repository-relative paths and current one-based
line anchors. Every named form is a single form, not a formset.

For **all 15** findings, the HTTP path requires authenticated active-organization
context followed by `organization_permission_required` for the stated capability.
The namespace is the capability prefix before `.`. Each prefix is already in
`OBJECT_SCOPED_PERMISSION_NAMESPACES`, so a qualifying limited object grant can
enter: **YES**. The decorator validates trusted membership but does not return it
to these constructors. Membership supplied to every affected constructor today:
**NO**. Resolve it server-side using
`get_active_membership(user=request.user, organization=request.organization)`;
never accept membership or organization from posted data.

Current gates and helpers:
`apps/organizations/decorators.py:16`,
`apps/organizations/authorization.py:315,388,440`, and
`apps/organizations/form_scoping.py:22,38,59`.
`scope_queryset()` narrows tenant and effective grants; it does not replace a
business-permission check. Preserve those checks independently.

- **Project authority only:** `scope_queryset(..., project_lookup="pk")` for a
  Project catalogue, or the actual project relation for a source object. Leave
  `include_site_parent=False`. A site grant alone does not authorize that project
  or a project-owned commercial/financial source.
- **Site-aware context:** `scoped_projects_for_form()` may expose the parent of a
  granted site for context. Scope actual children with their project and site
  lookups; that parent visibility never grants siblings or project-only records.
- `selected_form_project()` resolves only within an authorized Project queryset.
  `scope_project_related_choices()` is available when a constructor already has
  an actual selected/persisted parent. No new cascade, forced initial parent, or
  automatic context selection is required. Initial forms may retain all
  authorized child options; bound combinations must obey existing domain rules.
- Before any missing/invalid-membership return, explicitly empty **every protected
  field**, including Django ModelForm-generated querysets. Missing membership,
  wrong-tenant membership and invalid grants must never produce tenant-wide
  fallback choices. Preserve existing status, archival, ordering and tenant-master
  predicates; do not silently introduce new lifecycle policy.
- No global helper or namespace-registry change is proposed. Local integration
  code delegates grant evaluation to the canonical helpers/readers.

For the ordinary create records below, GET and bound POST use the same
constructor; invalid form or service-error redisplay uses those same querysets.
Today those redisplays remain tenant-wide for the claimed fields. After a fix,
GET, bound validation and redisplay must all use the same protected querysets.
Expense allocation is the explicit exception: invalid POST returns a bare 400.

### UIUX-F-113 — PROJECT_ONLY_FORM_CHOICES

- Gate: `purchase_requests.create`; entry
  `apps/procurement/views.py:395` (`purchase_request_create`), route
  `/procurement/requests/create/`.
- Form/query: `apps/procurement/forms.py:30` (`PurchaseRequestForm`),
  `project` = tenant + non-deleted Projects, no grant intersection.
- Safe seam: project-only `scope_queryset(Project, project_lookup="pk")`.
  Do not use the site-parent-inclusive helper unchanged.
- POST/redisplay: ordinary shared constructor behavior described above.
- Mutation: `apps/procurement/services.py:258` (`create_purchase_request`)
  checks create permission against the Project and validates tenant/lifecycle.
  Preserve that denial and transaction boundary.
- Likely implementation: the named form and create view. Focused coverage:
  BATCH-08 project-catalogue tests plus existing Procurement panel/service tests.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-114 — ISSUED_ORDER_PROJECT_CHOICES

- Gate: `goods_receipts.create`; `apps/procurement/views.py:777`
  (`goods_receipt_create`), `/procurement/receipts/create/`.
- Form/query: `apps/procurement/forms.py:184` (`GoodsReceiptForm`),
  `purchase_order` = tenant + issued + non-deleted parent Project. Missing
  intersection is `PurchaseOrder.project_id` against effective project grants.
- Safe seam: `scope_queryset(..., project_lookup="project_id")` on the existing
  issued-order queryset. No site-parent authority and no new order-view capability.
- POST/redisplay: ordinary shared constructor behavior; test order number and
  actual model label as well as UUID.
- Mutation: `apps/procurement/services.py:1040` (`create_goods_receipt`) locks
  the tenant order, checks create permission for its Project, issued status and
  governing version. Preserve all of these.
- Likely implementation: named form/view only; BATCH-04 tests and existing
  Procurement receipt/panel/service controls.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-115 — SITE_AWARE_OPERATIONAL_CHOICES

- Gate: `maintenance_records.create`; `apps/equipment/views.py:926`
  (`maintenance_create`), `/equipment/maintenance/create/`.
- Form/query: `apps/equipment/forms.py:126` (`MaintenanceRecordForm`),
  optional `project` = tenant + non-deleted; optional `site` = tenant + active +
  non-deleted parent. Equipment/provider are separate tenant masters.
- Safe seam: `scoped_projects_for_form()` and `scope_queryset(ProjectSite,
  project_lookup="project_id", site_lookup="pk")`. Match existing maintenance
  readers and service site-parent handling; do not broaden unassigned mutation.
- POST/redisplay: preserve site-to-project validation, optional blank choices and
  all authorized initial options. A posted unauthorized parent must not repopulate
  child choices or rejected labels.
- Mutation: `apps/equipment/services.py:433` (`create_maintenance_record`)
  checks project/site permission, locks Equipment, checks same tenant and structure.
- Likely implementation: named form/view; BATCH-09 tests, maintenance service
  regression and prior F-111 Equipment Assignment controls.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-116 — PROJECT_ONLY_FORM_CHOICES

- Gate: `contracts.create`; `apps/contracts/views.py:105` (`contract_create`),
  `/contracts/create/`.
- Form/query: `apps/contracts/forms.py:16` (`ContractForm`),
  `project` = tenant + non-deleted, no project-grant intersection. BusinessParty
  remains a tenant master.
- Safe seam: project-only `scope_queryset(Project, project_lookup="pk")`.
- POST/redisplay: ordinary shared constructor behavior; preserve Jalali/date,
  number normalization and Contract status validation.
- Mutation: `apps/contracts/services.py:241` (`create_contract`) checks
  project-specific create permission and tenant/party/lifecycle conditions.
- Likely implementation: named form/view; BATCH-08 tests and
  `apps/contracts/tests.py:ContractServiceTests`.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-117 — PROJECT_ONLY_FORM_CHOICES

- Gate: `warehouses.create`; `apps/inventory/views.py:115` (`warehouse_create`),
  `/inventory/create/`.
- Form/query: `apps/inventory/forms.py:23` (`WarehouseForm`), optional `project`
  = tenant + non-deleted, without project authority.
- Safe seam: project-only `scope_queryset(Project, project_lookup="pk")`.
  Preserve the central-warehouse empty option; an empty option is not a stored
  central warehouse object or an organization grant.
- POST/redisplay: ordinary constructor behavior. Limited actors may see their
  authorized Projects; a blank central-warehouse submission retains the existing
  service denial unless organization scope exists.
- Mutation: `apps/inventory/services.py:211` (`create_warehouse`) validates
  Project and checks permission for that Project, or organization scope when null.
- Likely implementation: named form/view; BATCH-08 tests and Warehouse service/
  panel controls. No stock-transaction changes belong to this seam.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-118 — STOCK_MOVEMENT_SOURCE_CHOICES

- Gate: `stock_transactions.create`; `apps/inventory/views.py:266`
  (`transaction_create`), `/inventory/transactions/create/`.
- Form/query: `apps/inventory/forms.py:43` (`StockTransactionForm`):
  `source_warehouse` and `destination_warehouse` share one tenant/active/unarchived
  queryset; `project` is tenant/non-deleted; `goods_receipt_item` is tenant +
  posted receipt + no existing stock transaction. Material/UOM stay tenant masters.
- Missing intersections: Warehouse `project_id`, Project `pk`, GoodsReceiptItem
  `goods_receipt__project_id`. Canonical safe helper: `scope_queryset()` with
  those lookups and no site-parent promotion. Its organization-grant behavior
  retains central warehouses; limited project grants do not disclose them.
- POST/redisplay: preserve transaction-type required-field matrix, different
  source/destination, Material matching, receipt Project consistency and existing
  receipt-derived Project assignment. Reject out-of-scope IDs before `clean()`
  can derive context from an unauthorized receipt.
- Mutation: `apps/inventory/services.py:311,366` (`create_stock_transaction`,
  `_create_stock_transaction_domain`) preserves tenant locks, effective-Project
  permission, receipt state/version contracts and validated draft creation.
  No new stock posting, valuation or receipt retry behavior is authorized.
- Likely implementation: named form/view; BATCH-05 tests, Inventory service/panel
  tests and `apps/inventory/test_cep034_receipt_contract.py` affected controls.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-119 — ALLOCATION_CODING_CHOICES

- Gates: `expenses.view` for `apps/expenses/views.py:371` (`expense_detail`),
  plus allocation capability/state visibility in `templates/expenses/detail.html`;
  `expenses.allocate` for POST at `apps/expenses/views.py:390` (`expense_allocate`).
  Routes: `/expenses/<uuid:expense_id>/` and its `allocate/` action.
- Form/query: `apps/expenses/forms.py:175` (`ExpenseAllocationForm`),
  Project/WBS/Activity = tenant plus current lifecycle filters. The parent Expense
  is already obtained through a scoped reader; that does not scope these fields.
- Safe seam: project-only `scope_queryset()` on Project `pk`, WBS `project_id`,
  Activity `project_id`. Preserve authorized multi-project allocation behavior:
  do not assume allocation Project must equal the parent Expense's Project.
  Selected allocation Project/WBS may narrow bound children to existing model
  relationships, not invent a new budget or allocation policy.
- Domain rules: `apps/expenses/models.py:526` requires WBS in allocation Project,
  Activity in that Project/WBS, and the accepted governing budget/structure.
  CBS and CostCenter are tenant-owned locked classifications (SP-012), not newly
  project-owned objects; keep their existing predicates.
- POST: form validation then `add_expense_allocation`; invalid form returns 400
  without redisplay. Test that response and a subsequent detail GET; no new error
  page or AJAX behavior is needed.
- Mutation: `apps/expenses/services.py:426` locks Expense, checks allocation
  Project permission, state, accepted budget and amount. It does not prove every
  model relationship is revalidated on every direct service call. Test established
  denials; record any separate service gap without silently extending this patch.
- Likely implementation: named form and both construction sites; BATCH-06 tests
  plus relevant `apps/expenses/tests.py:ExpenseServiceTests`.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-120 — RECURRING_TEMPLATE_COLLECTION_AND_CHOICES

- Gate: `expenses.recurrences_manage`; `apps/expenses/views.py:464`
  (`recurrence_list`), `/expenses/recurrences/`.
- Form/query: `apps/expenses/forms.py:231` (`RecurringExpenseTemplateForm`),
  tenant/non-deleted Project choices; same view loads a tenant-wide related
  template collection. Both require project-only scope intersection (`pk` for
  Projects, `project_id` for templates).
- Safe seam: existing `scope_queryset()` at the form and collection builder.
  No new recurrence scheduling or queue mechanism. Do not add an active-only list
  predicate merely because the existing heading says active templates.
- POST/redisplay: both scoped collections must be reconstructed on invalid POST
  or service-error render. `templates/expenses/recurrences.html` renders template
  descriptions, Project names and proposal-action UUIDs, not template amounts.
- Mutation: `apps/expenses/services.py:711` (`create_recurring_expense_template`)
  and `propose_recurring_expense` validate template Project authority; preserve
  locking, occurrence checks and idempotency. Proposal is a separate existing
  POST path, included as a negative regression target, not a redesign target.
- Likely implementation: named form/list view; BATCH-07 tests and existing Expense
  recurrence service controls.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-121 — COMMERCIAL_CREATE_EVIDENCE_CHOICES

- Gates/routes: `guarantees.manage` at `apps/billing/views.py:742`
  (`guarantee_create`), `/billing/guarantees/new/`;
  `compliance_evidence.manage` at `:898` (`compliance_evidence_create`),
  `/billing/compliance-evidence/new/`;
  `retention_releases.create` at `:998` (`retention_release_create`),
  `/billing/retention-releases/new/`.
- Forms: `GuaranteeForm`, `ComplianceEvidenceForm`, `RetentionReleaseForm`,
  sharing `apps/billing/forms.py:34` (`_CommercialEvidenceForm._configure`).
  Contract = tenant/active/non-deleted/party; DocumentVersion fields =
  tenant/nonarchived Document. Missing: Contract project intersection and DMS
  authorization through **every** linked context.
- Safe seam: one **create-only** configuration method on the existing base form,
  called by all three create constructors. Reuse project-only `scope_queryset()`
  for Contracts, and `get_organization_documents` /
  `get_organization_document` from `apps/documents/services.py:714,806` for
  canonical DMS visibility. Form membership plus trusted actor are required.
  A missing reader permission produces empty DocumentVersion choices.
- DMS rules include all linked target permissions/scopes, sealed evidence,
  expiry, valid links and special context controls. A version has no direct
  Project ownership; neither one allowed link nor Contract.project alone is a
  substitute. The detail reader performs the full context validation. Preserve
  eligible historical versions; do not silently switch to current-version-only
  or download permission. Avoid unbounded repeated reader calls by resolving
  distinct candidate Documents once within the request.
- POST/redisplay: all three constructors and both version-field names must use
  the shared scoped result. Limited actors can enter create even though commercial
  detail/revision readers require organization scope. Preserve those reader gates.
- Mutation: `apps/billing/commercial_services.py:212,427,702` checks the locked
  Contract's Project permission. `_evidence_version` at `:106` checks tenant and
  availability, **not actor-linked DMS access**. Do not claim a pre-existing
  direct-service DMS denial. This batch rejects unauthorized posted versions at
  the form boundary; any proposal to extend mutation-service authority is a
  separately scoped security change, not implicitly included here.
- Likely implementation: named base/create forms and three create views only;
  BATCH-01 tests, CommercialControlTests and DMS reader regression controls.
  Keep the existing revision `_configure` path untouched; SP-042 is a regression
  control, not remediation scope. Do not create an unscoped fallback in create.
- `PRODUCT_DECISION_REQUIRED: NO`: existing DMS readers define visibility.

### UIUX-F-122 — RETENTION_CLEARANCE_READER_INTEGRATION

- Gate: `retention_releases.create`; same create view/route as F-121.
- Form/query: `apps/billing/forms.py:174,197` (`RetentionReleaseForm`),
  additional `clearance_evidence` = tenant + clearance kind + approved.
  It is assigned after shared commercial configuration, so a shared-base fix
  alone does not fix this finding.
- Safe seam: `apps/billing/commercial_services.py:152`
  (`get_compliance_evidence`) then retain kind/approved predicates. Its
  `compliance_evidence.view` check invokes `_require(project=None)` with no
  `allow_any_scope`: it currently requires **organization scope**. Catch denial
  at choice construction and leave choices empty; never replace this with an
  inferred project-level reader. Capability to create a release does not grant
  permission to enumerate clearance evidence.
- POST/redisplay: rejected clearance must remain absent on bound redisplay.
  Do not force a new selected-Contract cascade. `_valid_clearance` at
  `commercial_services.py:673` already enforces matching Contract, effective date,
  expiry, kind and approval when the governing term requires clearance.
- Mutation: `create_retention_release` retains Project permission, term, amount
  and clearance checks. Do not claim that the service currently enforces the
  standalone clearance reader's permission; that check protects enumeration.
- Likely implementation: only this create constructor and its membership/actor
  supply in `retention_release_create`; BATCH-02 tests. Correction form/SP-021
  stays outside remediation scope and retains its earlier organization gate.
- `PRODUCT_DECISION_REQUIRED: NO`: the existing reader is authoritative; making
  limited actors able to read clearance would require separate authorization.

### UIUX-F-123 — PAYABLE_CONTRACT_SOURCE_CHOICES

- Gate: `payable_measurements.record`; `apps/billing/views.py:609`
  (`payable_measurement_create`), `/billing/payable-measurements/new/`.
- Form/query: `apps/billing/forms.py:341` (`PayableMeasurementForm`),
  `contract_item` = tenant + payable/active/non-deleted subcontract parent.
  Missing authority is `contract__project_id`.
- Safe seam: project-only `scope_queryset()` over this queryset. Same payable
  parent contract as F-124; no site-parent promotion. Preserve item order and
  existing lifecycle predicates. No item rate/amount disclosure is asserted.
- POST/redisplay: ordinary shared constructor behavior, including message-error
  redisplay after an existing service rejection.
- Mutation: `apps/billing/payable_services.py:149`
  (`create_payable_measurement`) locks tenant item/Contract, validates payable
  subcontract and checks record permission on Contract.project.
- Likely implementation: named form/view; BATCH-03 tests and payable controls.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-124 — PAYABLE_CONTRACT_SOURCE_CHOICES

- Gate: `payable_certificates.create`; `apps/billing/views.py:411`
  (`payable_certificate_create`), `/billing/payable-certificates/new/`.
- Form/query: `apps/billing/forms.py:371` (`PayableCertificateForm`),
  `contract` = tenant + payable/active/non-deleted subcontract. Missing effective
  intersection is `project_id`.
- Safe seam: same payable-parent project-only scope policy as F-123. Share local
  queryset configuration only where useful; no dependency on F-123 records or a
  new authorization framework is necessary.
- POST/redisplay: ordinary shared constructor behavior; retain date/cutoff and
  overlap validation.
- Mutation: `apps/billing/payable_services.py:375`
  (`create_payable_certificate`) locks Contract and checks Project permission,
  terms and period conditions. Payable list readers themselves have an earlier
  organization gate; do not route create choices through that gate and thereby
  remove existing limited-project create behavior.
- Likely implementation: named form/view; BATCH-03 tests and payable controls.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-125 — PROJECT_ONLY_FORM_CHOICES

- Gate: `workforce_qualifications.manage`; `apps/workforce/views.py:1592`
  (`workforce_training_requirement_create`),
  `/workforce/foundation/training-requirements/create/`; `_foundation_form` at
  `:1493` only renders the supplied form.
- Form/query: `apps/workforce/forms.py:194` (`TrainingRequirementForm`),
  optional `project` = tenant/non-deleted. Competency/Position are tenant masters.
- Safe seam: project-only `scope_queryset(Project, project_lookup="pk")` in this
  constructor only, preserving optionality and WorkforceCatalogueForm behavior.
  Do not modify EmployeeTrainingRecordForm or globally scope TrainingRequirements.
- POST/redisplay: ordinary shared constructor behavior through `_foundation_form`.
- Mutation: `apps/workforce/services.py:1382` (`create_training_requirement`)
  calls `_require_workforce_permission` at `:1283`, which first calls the
  organization-only `_require_active_access` at `:63`, then checks Project if
  present. Limited A/B choice visibility does **not** imply successful creation.
  Preserve this existing stricter service denial; organization actors retain the
  known-good create path, including optional Project.
- Likely implementation: named form/create view only; BATCH-08 tests and
  `apps/workforce/test_p7_s01_s05_workforce_foundation.py` affected controls.
- `PRODUCT_DECISION_REQUIRED: NO`. SP-031 catalogue visibility remains separate.

### UIUX-F-126 — SITE_AWARE_OPERATIONAL_CHOICES

- Gate: `quality_issues.create`; `apps/quality/views.py:126` (`issue_create`),
  `/quality/create/`.
- Form/query: `apps/quality/forms.py:24` (`QualityIssueForm`), tenant-based
  `project`, `site`, `phase`, `activity`, `daily_report` with existing lifecycle
  predicates. No effective scope intersection.
- Safe seam: `scoped_projects_for_form()` for Project; `scope_queryset()` for
  Site (`project_id`, `pk`), Phase (`site__project_id`, `site_id`), Activity
  (`project_id`, `site_id`) and DailyReport (`project_id`, `site_id`). Do not make
  project-only Activity visible to a site-only actor merely through parent context.
- POST/redisplay: preserve optional child fields and full structure checks in
  `apps/quality/services.py:91` (`_validate_structure`), including matching
  Project/Site/Phase/Activity/DailyReport. No new AJAX behavior is required.
- Mutation: `_create_quality_issue_domain` at `quality/services.py:192`, called
  by `create_quality_issue` at `:536`, checks project/site authority and domain
  relationships. Workflow fallback is outside the fix.
- Likely implementation: named form/view; BATCH-09 tests and Quality service/view
  controls. No new shared dependency on Safety or Equipment.
- `PRODUCT_DECISION_REQUIRED: NO`.

### UIUX-F-127 — SITE_AWARE_OPERATIONAL_CHOICES

- Gate: `safety_incidents.create`; `apps/safety/views.py:118` (`incident_create`),
  `/safety/create/`.
- Form/query: `apps/safety/forms.py:24` (`SafetyIncidentForm`), same five
  field roles and queryset lifecycle patterns as F-126.
- Safe seam: exactly the project/site lookup mapping documented for F-126;
  canonical helpers are already shared. Keep Safety-specific fields, exceptions,
  state machine and workflow separate.
- POST/redisplay: same bound/invalid scope rule; preserve existing structure
  checks at `apps/safety/services.py:87`, including phase consistency.
- Mutation: `_create_safety_incident_domain` at `safety/services.py:184`, called
  by `create_safety_incident` at `:499`, checks project/site permission and
  structure. No transition or workflow changes.
- Likely implementation: named form/view; BATCH-09 tests and Safety service/view
  controls.
- `PRODUCT_DECISION_REQUIRED: NO`.

## Shared Remediation Seams

The smallest practical plan is **nine batches**, rather than forcing the target
of three to six. F-121's DMS all-context rule, F-122's organization-gated reader,
payable Contract sources, issued-order inheritance, central-warehouse/receipt
semantics, allocation coding, and a rendered recurrence collection are materially
different contracts. Combining those to meet a count would hide independent
authorization or regression boundaries. Nine batches still avoid 15 independent
patches: four plain Project selectors, three site-aware operational constructors,
and two payable constructors are grouped through existing canonical seams.

| Seam | Findings | Shared code | Safe to group |
| --- | --- | --- | --- |
| PROJECT_ONLY_FORM_CHOICES | F-113, F-116, F-117, F-125 | Existing `scope_queryset(Project, project_lookup="pk")`; independent callers | YES, for protected Project enumeration only; no cross-app helper or service unification |
| SITE_AWARE_OPERATIONAL_CHOICES | F-115, F-126, F-127 | Existing `scoped_projects_for_form` and `scope_queryset` project/site lookups | YES; same parent-context versus actual-child authority, with local field subsets |
| PAYABLE_CONTRACT_SOURCE_CHOICES | F-123, F-124 | Payable subcontract predicates, Contract.project and `payable_services._require` | YES; ContractItem inherits the same payable parent Project authority |
| COMMERCIAL_CREATE_EVIDENCE_CHOICES | F-121, all three create forms | Existing `_CommercialEvidenceForm`, new create-only scoped configuration | YES across its three callers; Contract and DMS rules remain separate canonical operations |
| RETENTION_CLEARANCE_READER_INTEGRATION | F-122 | Additional RetentionReleaseForm queryset and canonical evidence reader | Separate from F-121: earlier organization/view gate is materially different |
| ISSUED_ORDER_PROJECT_CHOICES | F-114 | GoodsReceiptForm's issued-order queryset | Separate: issued/versioned purchasing source contract |
| STOCK_MOVEMENT_SOURCE_CHOICES | F-118 | Shared source/destination warehouse queryset and receipt-derived context in `clean()` | YES for its fields; separate from the plain Project-only Warehouse create field |
| ALLOCATION_CODING_CHOICES | F-119 | Allocation form constructed in detail and POST views | YES across these two callers; separate from recurrence's collection exposure |
| RECURRING_TEMPLATE_COLLECTION_AND_CHOICES | F-120 | `recurrence_list` form and template collection | YES as one page boundary; both halves are required for closure |

For every multi-finding seam:

- **PROJECT_ONLY_FORM_CHOICES** — FINDINGS_COVERED: F-113/F-116/F-117/F-125.
  FILES_TOUCHED: Procurement, Contracts, Inventory, Workforce `forms.py` and
  `views.py`, only named constructors/create functions. WHY_SHARED: identical
  missing intersection of tenant/non-deleted Project options with project grants.
  WHY_SAFE_TO_GROUP: one small caller recipe, same negative matrix, no shared
  mutation code. Required/optional fields and stricter Workforce service access
  remain local. DOMAIN_SEMANTICS_COMPATIBLE: **YES for Project choices**.
- **SITE_AWARE_OPERATIONAL_CHOICES** — FINDINGS_COVERED: F-115/F-126/F-127.
  FILES_TOUCHED: Equipment, Quality, Safety `forms.py` and `views.py` at the named
  sites. WHY_SHARED: identical site-aware authority contract already defined by
  canonical helpers/readers; Quality/Safety have matching five-field mappings and
  Maintenance uses their Project/Site subset. WHY_SAFE_TO_GROUP: existing helpers
  serve all; each domain retains its relationships, optionality and mutation rules.
  DOMAIN_SEMANTICS_COMPATIBLE: **YES for these scoped choices**.
- **PAYABLE_CONTRACT_SOURCE_CHOICES** — FINDINGS_COVERED: F-123/F-124.
  FILES_TOUCHED: Billing `forms.py` and `views.py` at two payable create paths.
  WHY_SHARED: payable subcontract Project authority is direct for Contract and
  inherited for its item. WHY_SAFE_TO_GROUP: same lifecycle/source parent and
  service authority, two small constructors, one regression family.
  DOMAIN_SEMANTICS_COMPATIBLE: **YES**.
- **COMMERCIAL_CREATE_EVIDENCE_CHOICES** — FINDINGS_COVERED: F-121's three
  create forms. FILES_TOUCHED: Billing `forms.py` base/create configuration and
  `views.py` three create functions. WHY_SHARED: all three call the same existing
  base configuration with the same Contract and version-field roles.
  WHY_SAFE_TO_GROUP: one create-only integration preserves each canonical
  Contract/DMS rule and the excluded revision behavior.
  DOMAIN_SEMANTICS_COMPATIBLE: **YES across these create callers**, not permission
  to collapse Contract authority and DMS authority into one rule.
- **STOCK_MOVEMENT_SOURCE_CHOICES** — FINDINGS_COVERED: F-118.
  FILES_TOUCHED: Inventory `forms.py:StockTransactionForm` and its create view.
  WHY_SHARED: source/destination choices already share one warehouse queryset;
  the form also validates receipt-derived Project context.
  WHY_SAFE_TO_GROUP: one movement-form boundary, with separate canonical lookups
  for warehouses, receipt items and Projects. DOMAIN_SEMANTICS_COMPATIBLE: **YES
  within this form**, preserving organization-only central warehouse visibility.
- **ALLOCATION_CODING_CHOICES** — FINDINGS_COVERED: F-119.
  FILES_TOUCHED: ExpenseAllocationForm and both Expense view construction sites.
  WHY_SHARED: the same class serves initial detail render and allocation POST.
  WHY_SAFE_TO_GROUP: both use the same allocation Project/WBS/Activity contract.
  DOMAIN_SEMANTICS_COMPATIBLE: **YES**; the different invalid-response shape is
  preserved and tested.
- **RECURRING_TEMPLATE_COLLECTION_AND_CHOICES** — FINDINGS_COVERED: F-120.
  FILES_TOUCHED: RecurringExpenseTemplateForm and recurrence_list.
  WHY_SHARED: both rendered data sources inherit project-only scope on one page.
  WHY_SAFE_TO_GROUP: one request owns both queryset builders; no scheduling or
  mutation authority is combined. DOMAIN_SEMANTICS_COMPATIBLE: **YES**.

The remaining two seams each cover a single distinct source selector:
ISSUED_ORDER_PROJECT_CHOICES (F-114, Procurement GoodsReceiptForm/create view)
and RETENTION_CLEARANCE_READER_INTEGRATION (F-122, Billing RetentionReleaseForm/
create view). Their within-seam DOMAIN_SEMANTICS_COMPATIBLE is **YES**; WHY_SHARED
is the same constructor on GET/bound POST/redisplay, and WHY_SAFE_TO_GROUP is that
single source boundary. Neither has a compatible additional finding to absorb.

F-121 and F-122 are **not** one shared authorization seam:
DOMAIN_SEMANTICS_COMPATIBLE: **NO for a single choice policy**. Similarly,
allocation/recurrence and project-only/site-aware contracts are kept in different
batches. Sharing a Python file or calling `scope_queryset()` is not a dependency.

## Proposed Batches

### Common automated acceptance matrix

Every batch's EXPECTED_TEST_SET includes the following matrix, specialized below.
New test filenames are proposed future files; none is created in this task.

1. In disposable Django test databases, use an ordinary active member with the
   exact existing capability and explicit A/B Project grants, same-tenant
   unauthorized C/D, and Tenant B's X. Prove fixtures qualify for each lifecycle
   filter; an unissued order or unapproved clearance is not a meaningful scope
   negative. Add organization-scope and site-only actors where relevant.
2. Authorized qualifying objects appear in field querysets and rendered GET HTML.
   Unauthorized same-tenant and cross-tenant objects are absent by UUID, actual
   option label and distinctive code/number/title as applicable. Scan the full
   response for the finding's metadata, not just the visible select. Shared generic
   text is not evidence of exposure; use distinguishable synthetic labels.
3. Missing/wrong-tenant membership, absent/revoked/expired/future grants and
   inactive membership/user/tenant fail closed. Verify role/capability absence
   denies HTTP entry; object scope never supplies the missing permission.
4. Bound authorized B remains selectable; manipulated C/D/X and relevant mixed
   parent/child IDs are rejected with no successful business mutation. Check
   status/counts and success-audit absence; preserve legitimate failure auditing.
5. Invalid POST, ordinary missing-required-field redisplay and existing service
   rejection do not reintroduce forbidden metadata. Allocation's bare 400 is
   tested as such. Do not demand a redisplay page that does not exist.
6. Direct calls prove the **existing** service's tenant/object/capability denials
   remain enforced. Do not assert protections that source does not implement.
   Preserve organization-actor success and existing limited-actor success or
   denial, whichever is the actual contract. Use valid synthetic business setup
   in test DBs so a denial is attributable to authorization, not missing terms.
7. Run the batch-focused suite, then affected existing service/view controls and
   the relevant prior F-111/Expense/Estimate/Field Observation controls. Do not
   reopen those findings or rewrite their historical evidence. Run Django checks,
   touched-file lint and whitespace checks when implementing. No migration is
   expected; schema drift is a stop/re-scope condition.

Old F-111 regression evidence contains 199 baseline test-debt failures and one
encoding infrastructure failure. It is not a blanket waiver: reproduce/attribute
any newly encountered failure against the implementation task's own baseline.

### Common runtime and governance acceptance

Each batch is a separate future Codex task/session:

`ANALYZE CURRENT HEAD -> IMPLEMENT BOUNDED FIX -> AUTOMATED TESTS -> RUNTIME SECURITY RETEST -> GOVERNANCE UPDATE -> STOP`

Re-ground HEAD **and dirty file contents**, verify bounded authorization and
collisions, then use current source for the exact final touch set. If runtime
prerequisites are missing, stop pending closure evidence; do not invent a role,
grant, permission, fixture, visibility policy or Product Decision. Any persistent
fixture preparation needs its own bounded authority. Disposable automated test
data does not grant persistent Development fixture authority.

Use a freshly loaded Development process tied to the actual checkout; record
settings/database identity and migration currency without exposing credentials.
The original retest proved an old `--noreload` process can show stale choices.
Reuse existing eligible actors and browser sessions only after capability/grant
preflight. Runtime negative POSTs must pass actual authentication and CSRF and
otherwise be valid. Capture safe option values/labels and sanitized observations;
do not persist cookies, tokens, passwords or raw token-bearing HTML.

Representative runtime means automated coverage of **every named constructor,
field and GET/POST path**, live HTTP observations for **every affected route**,
and browser interaction for the specified representative set. It does not mean
unobserved callers are automatically resolved. Record all covered findings by ID.
No batch is assigned `STATIC_PLUS_AUTOMATED_SUFFICIENT_PENDING_FINAL_SWEEP` as a
closure shortcut: all require the runtime evidence below before resolved status.

For each batch, governance-only future writes are limited to its finding entries,
new scoped evidence/retest report and evidence index where used. Preserve old
evidence and statuses of other findings. No Registry or Roadmap lifecycle change
is implied. Product service/model/template files not in that batch's touch set
are read/test controls, not mutation authority. Unexpected need to change them
requires re-scoping before editing.

### BATCH-01

- **FINDINGS:** UIUX-F-121 (all three commercial create forms).
- **MODULES:** Billing; Documents read-only authority dependency.
- **SHARED_ROOT_CAUSE:** Common organization-only Contract/DocumentVersion
  setup bypasses existing project and DMS readers before render.
- **SHARED_REMEDIATION_SEAM:** COMMERCIAL_CREATE_EVIDENCE_CHOICES. Introduce one
  create-only configuration method in the existing base; integrate all three
  create callers. Use existing DMS readers, including full linked-context checks.
- **AUTHORIZED_TOUCH_SET:** `apps/billing/forms.py` base/create configuration and
  GuaranteeForm/ComplianceEvidenceForm/RetentionReleaseForm create wiring;
  `apps/billing/views.py` three named create functions; proposed
  `tests/test_uiux_f111_pattern_commercial_scope.py`; scoped evidence/governance.
  No Documents code or commercial mutation-service changes. No revision changes.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix; all three forms, both
  document field names, DMS view permission absent/present, all-links-allowed
  versus mixed authorized/forbidden links, sealed/expired/unlinked context,
  eligible historical version and cross-tenant version; posted forbidden version
  against authorized Contract must fail. Verify organization-gated revisions
  retain their pre-existing behavior and direct-service Contract denials remain.
  Reuse `apps/billing/test_commercial_controls.py:CommercialControlTests` and
  affected DMS reader controls.
- **RUNTIME_RETEST_TARGETS / Runtime retest:**
  `REPRESENTATIVE_RUNTIME_RETEST`: live GET/invalid POST on all three create
  routes; browser one Guarantee and one Retention release form to cover both
  general and subcontract filtering. Inspect complete Contract/version option
  sets; one mixed-link DMS negative and one cross-tenant version POST with
  authorized Contract. Compliance create's distinct field name is covered by its
  live HTTP observation and automated render/POST tests, not assumed identical.
- **DEPENDENCIES:** Existing canonical authorization and DMS readers only.
  **CAN_EXECUTE_INDEPENDENTLY: YES**; no prerequisite batch.
- **RISK:** HIGH; broad version metadata and all-linked-context semantics; shared
  base also serves excluded revisions. Create-only integration limits blast radius.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-02

- **FINDINGS:** UIUX-F-122.
- **MODULES:** Billing commercial retention sources.
- **SHARED_ROOT_CAUSE:** Inline clearance queryset is assigned outside shared
  configuration and omits the canonical reader's permission/organization gate.
- **SHARED_REMEDIATION_SEAM:** RETENTION_CLEARANCE_READER_INTEGRATION.
- **AUTHORIZED_TOUCH_SET:** `apps/billing/forms.py:RetentionReleaseForm` additional
  clearance choices; `apps/billing/views.py:retention_release_create` trusted
  actor/membership wiring as needed; proposed
  `tests/test_uiux_f111_pattern_clearance_scope.py`; scoped evidence/governance.
  Correction/revision paths and `commercial_services.py` are read/test only.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix; limited A/B actor has
  no clearance choices even with a view capability but no organization grant;
  organization actor without evidence-view permission also has none. Authorized
  organization/view actor sees qualifying tenant approved clearance; X is absent.
  Preserve kind/approval filters. Reject forced C/D/X clearance IDs for limited
  actor; verify no invalid redisplay leak. Preserve existing term/date/Contract
  matching checks and organization-actor success under approved test terms.
  Do not require authorized A/B clearance visible to an actor the reader denies.
- **RUNTIME_RETEST_TARGETS / Runtime retest:** `FULL_RUNTIME_RETEST` of the single
  retention-create clearance seam: limited actor GET/invalid POST, forced
  same-tenant/cross-tenant IDs, and an existing organization/view actor positive
  GET. This is not a full financial release workflow or a repeat of every F-121
  field. Without a qualifying positive actor/source, closure remains pending.
- **DEPENDENCIES:** Existing `get_compliance_evidence` contract.
  **CAN_EXECUTE_INDEPENDENTLY: YES**. BATCH-01 is recommended immediately before
  it for file/browser reuse, not required. F-121 may remain independently open if
  this batch executes first; do not certify the whole page as secure then.
- **RISK:** HIGH; optional financial source with a stricter reader than create.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-03

- **FINDINGS:** UIUX-F-123, UIUX-F-124.
- **MODULES:** Billing payables.
- **SHARED_ROOT_CAUSE:** Payable subcontract parent predicates applied without
  effective Project authority in either source selector.
- **SHARED_REMEDIATION_SEAM:** PAYABLE_CONTRACT_SOURCE_CHOICES; direct/inherited
  lookup on the same payable Contract. Keep existing business predicates local.
- **AUTHORIZED_TOUCH_SET:** `apps/billing/forms.py:PayableMeasurementForm,
  PayableCertificateForm`; `apps/billing/views.py:payable_measurement_create,
  payable_certificate_create`; proposed
  `tests/test_uiux_f111_pattern_payable_scope.py`; scoped evidence/governance.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix on both constructors;
  A/B payable subcontract and items visible, C/D/X numbers/titles/labels/UUIDs
  absent; site-only grants cannot enumerate Project-owned sources; nonpayable,
  non-subcontract, inactive/deleted parents retain existing exclusions. Direct
  mutation denials and authorized period/term handling remain intact. Run affected
  `apps/billing/test_payable_certificates.py` controls; no certification/posting
  expansion or payable reader-gate change.
- **RUNTIME_RETEST_TARGETS / Runtime retest:**
  `REPRESENTATIVE_RUNTIME_RETEST`: live GET/invalid POST and one forbidden-source
  negative on each of the two routes; browser inspect each single source selector
  once. Include one cross-tenant Contract and one cross-tenant item across those
  paths. Do not retest certificate approval/calculation fields unrelated to choices.
- **DEPENDENCIES:** Existing payable Contract services only.
  **CAN_EXECUTE_INDEPENDENTLY: YES**; no prerequisite batch.
- **RISK:** HIGH; commercial source identifiers, modest two-constructor patch.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-04

- **FINDINGS:** UIUX-F-114.
- **MODULES:** Procurement receiving.
- **SHARED_ROOT_CAUSE:** Issued-order status is substituted for object scope.
- **SHARED_REMEDIATION_SEAM:** ISSUED_ORDER_PROJECT_CHOICES.
- **AUTHORIZED_TOUCH_SET:** `apps/procurement/forms.py:GoodsReceiptForm`,
  `apps/procurement/views.py:goods_receipt_create`; proposed
  `tests/test_uiux_f111_pattern_receipt_scope.py`; scoped evidence/governance.
  Preserve the existing dirty F-111 PurchaseOrderForm/view code.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix; issued/versioned A/B
  orders visible, issued C/D/X orders absent by number/UUID/actual label; site-only
  grants insufficient; invalid source and valid-source/missing-field redisplay;
  direct `create_goods_receipt` denies unauthorized Project. Preserve required
  order version/status and related Procurement panel/service controls.
- **RUNTIME_RETEST_TARGETS / Runtime retest:** `FULL_RUNTIME_RETEST` of this one
  selector: GET, bound invalid, C/D and X order POST negatives, authorized A/B
  options and existing service denial controls. No successful goods receipt is
  required in persistent Development. Existing Purchase Order create is a narrow
  known-good regression control, not a reopened finding.
- **DEPENDENCIES:** Existing issued-order and receipt contracts only.
  **CAN_EXECUTE_INDEPENDENTLY: YES**; no prerequisite batch.
- **RISK:** HIGH; purchase-order metadata, comparatively small form integration.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-05

- **FINDINGS:** UIUX-F-118.
- **MODULES:** Inventory; Procurement receipt sources read-only.
- **SHARED_ROOT_CAUSE:** Related movement choices omit Project intersections;
  receipt selection can also derive Project during form cleaning.
- **SHARED_REMEDIATION_SEAM:** STOCK_MOVEMENT_SOURCE_CHOICES, including the one
  shared source/destination warehouse queryset.
- **AUTHORIZED_TOUCH_SET:** `apps/inventory/forms.py:StockTransactionForm`,
  `apps/inventory/views.py:transaction_create`; proposed
  `tests/test_uiux_f111_pattern_stock_scope.py`; scoped evidence/governance.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix; active warehouses,
  eligible posted/unconsumed receipt items, Project fields; C/D/X absence in both
  warehouse roles and receipt sources; authorized receipt-derived context;
  organization actor retains central warehouse choices, limited actor does not;
  site-only actor gets no project-only sources. Cover receipt, issue, transfer and
  adjustment required-field variants with valid test-DB controls, mixed-source
  attacks, invalid redisplay, direct service denials and unchanged stock balances
  on rejected drafts. Run relevant Inventory model/service/panel and CEP-034
  receipt-contract controls. Do not assume every mixed-source service call already
  has an independent scope check; record any newly proved gap separately.
- **RUNTIME_RETEST_TARGETS / Runtime retest:**
  `REPRESENTATIVE_RUNTIME_RETEST`: one create page covers all protected option
  sets; exercise receipt and transfer variants, an unauthorized warehouse POST and
  a cross-tenant receipt-item POST with otherwise valid Material/context. Observe
  authorized Project and receipt-linked labels; do not post stock or change value.
- **DEPENDENCIES:** Existing posted receipt fixtures/contract only.
  **CAN_EXECUTE_INDEPENDENTLY: YES**; BATCH-04 does not produce a required fixture.
- **RISK:** HIGH; multiple source roles, null Project and receipt-derived context.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-06

- **FINDINGS:** UIUX-F-119.
- **MODULES:** Expenses allocation; Project Controls classifications read-only.
- **SHARED_ROOT_CAUSE:** Both allocation-form construction sites omit membership;
  authorized Expense read is mistaken for child-choice scope.
- **SHARED_REMEDIATION_SEAM:** ALLOCATION_CODING_CHOICES.
- **AUTHORIZED_TOUCH_SET:** `apps/expenses/forms.py:ExpenseAllocationForm`,
  `apps/expenses/views.py:expense_detail,expense_allocate`; proposed
  `tests/test_uiux_f111_pattern_allocation_scope.py`; scoped evidence/governance.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix plus draft/returned
  parent/capability rendering conditions; authorized allocation Project B on
  authorized Expense A remains available if valid under existing coding rules;
  C/D/X Project/WBS/Activity absent; correct Project/WBS/Activity relationships;
  no site-parent authority inferred for project-only coding. Preserve locked
  CBS/CostCenter tenant masters and accepted-budget/amount guards. Negative POST
  yields bare 400, no Allocation/success audit, followed by clean detail GET.
  Direct service Project/capability denial and valid test-DB allocation remain.
- **RUNTIME_RETEST_TARGETS / Runtime retest:** `FULL_RUNTIME_RETEST` of the
  detail/form plus allocate action: authorized eligible parent GET, all three
  choice families, unauthorized allocation Project, mixed unauthorized WBS or
  Activity, and X negative; inspect bare 400 then refreshed detail. No approval
  or financial posting workflow.
- **DEPENDENCIES:** Eligible authorized draft/returned Expense and valid coding
  fixtures for meaningful controls; no other batch.
  **CAN_EXECUTE_INDEPENDENTLY: YES**.
- **RISK:** HIGH; allocation context and cross-project coding must be preserved.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-07

- **FINDINGS:** UIUX-F-120.
- **MODULES:** Expenses recurring proposals.
- **SHARED_ROOT_CAUSE:** One page renders two independent tenant-wide sources:
  Project options and template rows/action identifiers.
- **SHARED_REMEDIATION_SEAM:** RECURRING_TEMPLATE_COLLECTION_AND_CHOICES.
- **AUTHORIZED_TOUCH_SET:** `apps/expenses/forms.py:RecurringExpenseTemplateForm`,
  `apps/expenses/views.py:recurrence_list`; proposed
  `tests/test_uiux_f111_pattern_recurrence_scope.py`; scoped evidence/governance.
  Existing recurrence-proposal view/service is a read/test control only.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix, complete HTML including
  template description/Project label/proposal-action UUID; A/B templates visible,
  C/D/X rows absent on GET and invalid create POST. Missing-field error must not
  restore unscoped collection. Force unauthorized template ID into existing
  proposal action; unchanged service denies without Expense creation. Preserve
  valid recurrence date/idempotency behavior in disposable tests and no automatic
  financial transaction. Test organization actor and site-only exclusion.
- **RUNTIME_RETEST_TARGETS / Runtime retest:** `FULL_RUNTIME_RETEST` of the one
  list/form page: authorized and forbidden row/option observations, invalid create
  POST, and C/D/X template proposal negatives as available with qualifying sources.
  No successful recurring proposal or background scheduling is required.
- **DEPENDENCIES:** Qualifying existing templates/actor only; BATCH-06 not needed.
  **CAN_EXECUTE_INDEPENDENTLY: YES**.
- **RISK:** HIGH; filtering only the form would leave identifying list leakage.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-08

- **FINDINGS:** UIUX-F-113, UIUX-F-116, UIUX-F-117, UIUX-F-125.
- **MODULES:** Procurement, Contracts, Inventory, Workforce.
- **SHARED_ROOT_CAUSE:** Identical organization/non-deleted Project catalogue
  initialization without project-only scope intersection.
- **SHARED_REMEDIATION_SEAM:** PROJECT_ONLY_FORM_CHOICES; use the canonical
  helper directly in four local constructors, without introducing cross-domain
  imports, a new form base or a helper that changes null-Project service policy.
- **AUTHORIZED_TOUCH_SET:** Four apps' `forms.py`/`views.py`, only
  PurchaseRequestForm/purchase_request_create, ContractForm/contract_create,
  WarehouseForm/warehouse_create, TrainingRequirementForm/
  workforce_training_requirement_create; proposed
  `tests/test_uiux_f111_pattern_project_scope.py`; scoped evidence/governance.
  Do not change generic Workforce catalogue forms or `_foundation_form`.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix parameterized across all
  four constructors/HTTP paths, with per-domain service expectations. Project
  grants A/B visible, C/D/X absent and site-only actor's Project choices empty.
  Preserve required Project in Purchase Request/Contract, optional Project in
  Warehouse/Training Requirement, tenant masters and organization-actor success.
  Limited blank central-warehouse and Training Requirement service denials remain.
  Run relevant existing Procurement/Contract/Warehouse/Foundation controls and
  prior F-111 PO/Workforce tests for files already dirty at baseline.
- **RUNTIME_RETEST_TARGETS / Runtime retest:**
  `REPRESENTATIVE_RUNTIME_RETEST`: live GET and invalid POST on **all four** routes;
  browser Purchase Request for the required Project variant and Warehouse for the
  optional variant. Also live HTTP observe Contract and Training Requirement
  options/redisplay and their own C/D/X negatives. The common helper alone does
  not establish correct runtime caller wiring. Training service denial is the
  expected limited-actor result; no TrainingRequirement is created for SP-031.
- **DEPENDENCIES:** None of BATCH-01..07; only existing helper and domain services.
  **CAN_EXECUTE_INDEPENDENTLY: YES**.
- **RISK:** MEDIUM; small repeated field integration over four apps. No whole-file
  formatting or shared authorization edits. Re-ground prior Procurement/Inventory
  batches to preserve their changes when executed in the recommended order.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO for all four findings.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

### BATCH-09

- **FINDINGS:** UIUX-F-115, UIUX-F-126, UIUX-F-127.
- **MODULES:** Equipment, Quality, Safety.
- **SHARED_ROOT_CAUSE:** Same missing membership/helper integration for
  site-aware operational Project and child-object metadata.
- **SHARED_REMEDIATION_SEAM:** SITE_AWARE_OPERATIONAL_CHOICES; existing canonical
  helpers with local field mappings, not a cross-domain business/form framework.
- **AUTHORIZED_TOUCH_SET:** `apps/equipment/forms.py:MaintenanceRecordForm` and
  `views.py:maintenance_create`; `apps/quality/forms.py:QualityIssueForm` and
  `views.py:issue_create`; `apps/safety/forms.py:SafetyIncidentForm` and
  `views.py:incident_create`; proposed
  `tests/test_uiux_f111_pattern_operational_scope.py`; scoped evidence/governance.
- **EXPECTED_TEST_SET / Automated tests:** Common matrix across all three
  constructors/HTTP paths, all local fields. Project/site grants and site-only
  sibling exclusion; authorized parent context is not Project mutation authority.
  Quality/Safety phase via site; Activity with/without site and DailyReport scope;
  cross-parent combinations rejected by existing domain validation. Maintenance
  retains Equipment/provider masters and blank Project/Site handling. Cover missing
  membership on ModelForm-generated fields explicitly. Preserve organization-actor
  success and unchanged workflow/transition rules; run relevant Equipment,
  Quality/Safety service/view controls plus F-111 Equipment/DailyReport controls.
- **RUNTIME_RETEST_TARGETS / Runtime retest:**
  `REPRESENTATIVE_RUNTIME_RETEST`: live GET/invalid POST/negative source controls
  on **all three** routes. Browser Maintenance for the Project/Site subset and
  Quality for the five-field mapping; Safety gets its own live HTTP five-field
  observations and mixed-child negative. Include a site-only sibling negative
  and X child POST. Do not repeat every Quality/Safety field interaction manually
  once the identical mappings have complete automated coverage.
- **DEPENDENCIES:** Existing site-aware helpers/readers only.
  **CAN_EXECUTE_INDEPENDENTLY: YES**; BATCH-08 does not establish its authority.
- **RISK:** MEDIUM exposure, greater regression complexity from optional child
  fields and site-parent semantics. No new workflow, endpoint or cascade.
- **PRODUCT_DECISION_REQUIRED / Product Decision:** NO for all three findings.
- **CROSS_TENANT_NEGATIVE_TEST: YES. MANIPULATED_POST_TEST: YES.**

## Recommended Execution Order

1. **BATCH-01** — widest sensitive commercial/DMS shared constructor exposure.
2. **BATCH-02** — complete the distinct clearance source on the same retention
   create surface while Billing/browser context is available.
3. **BATCH-03** — related financial Contract sources; finish Billing file edits.
4. **BATCH-06** — financial allocation coding and authorized-parent context.
5. **BATCH-07** — remaining Expense collection/form boundary; reuse file context.
6. **BATCH-04** — directly reachable issued-order selector, lower complexity.
7. **BATCH-05** — richer stock/warehouse/receipt-source regression surface.
8. **BATCH-08** — four MEDIUM plain-Project integrations with identical recipe.
9. **BATCH-09** — MEDIUM site-aware operational fields and richer child matrix.

All HIGH findings precede MEDIUM findings. Grouping consecutive Billing and Expense
tasks reduces overlapping edits and browser setup; Goods Receipt precedes Inventory
for source-context reuse. **There are no inter-batch technical prerequisites.**
None requires successful business records from a previous batch. File overlap is
a serial collision control, not a dependency edge. If a batch is incomplete, stop
that task; never silently continue through it or fold another batch into the same
session. A future session may select another independently authorized batch after
collision and blocker review. Do not execute this whole list as one task.

## SP-031 Runtime Follow-up

SP-031 Employee Training Record requirement choices remains
`NEEDS_RUNTIME_CONFIRMATION`, outside every remediation batch. Its optional
Project association may express applicability rather than exclusive ownership;
this plan does not decide otherwise.

Minimum future preparation, in a separately bounded confirmation task:

- Recheck existing P-17's active membership, `workforce_qualifications.manage`,
  explicit A/B grants and absence of C/D/organization authority; retain the actor.
- Locate suitable **active** TrainingRequirements associated with authorized A/B
  and an unauthorized C/D Project; include a cross-tenant requirement negative if
  available. Keep code/name/UUID and parent association distinguishable.
- The prior read-only preflight found no active requirements. If still absent,
  record the prerequisite gap and obtain bounded fixture-preparation authority
  before any persistent creation. Do not add grants or substitute a privileged
  actor to manufacture a limited-grant result.
- Compare actual rendered options and identifiers against the catalogue's
  governed visibility contract. If the contract is genuinely undefined, isolate
  that question for Human Product Decision **then**, not as a precondition for
  the 15 confirmed technical fixes. Respect existing training-service gates.

No fixture creation, TrainingRequirement creation, training-record submission or
catalogue-visibility change occurred in this planning task.

## Cross-Tenant / Manipulated POST Strategy

Historical sweep assertions remain:

`CROSS_TENANT_METADATA_EXPOSURE = NOT_TESTED`

`UNAUTHORIZED_MUTATION_OBSERVED = NOT_TESTED`

These are evidence gaps, not observed failures or inferred PASS. All nine batches
set `CROSS_TENANT_NEGATIVE_TEST: YES` and `MANIPULATED_POST_TEST: YES`, because
every in-scope boundary has a write path. Automated coverage is exhaustive for
its protected fields; runtime uses the documented representative set with
qualifying same-tenant and cross-tenant sources. If a specified runtime negative
cannot be made meaningful with current authorized fixtures, record it as pending
and keep affected closure pending; never replace it with an ineligible empty list.

Inspect HTTP responses, hidden values, option labels/UUIDs, list rows and action
URLs for the metadata actually in scope. Avoid asserting absence of a UUID the
caller supplied in unrelated navigation `next`; fetched forbidden metadata and
protected option values must still be absent. No successful business writes,
posting, payment or authority changes are needed for persistent-runtime negative
controls. Authorized success paths are exercised in disposable automated tests.

Service validation claims stay precise: existing target Project/site/tenant
checks remain regression obligations. F-121's `_evidence_version` does not enforce
actor DMS visibility, F-122's writer does not enforce its enumeration reader gate,
and F-119's direct service does not demonstrate every form/model relationship
check. These are boundaries to document and test truthfully, not permission to
add unrequested service semantics or assert that unauthorized mutation occurred.

## Findings Requiring Product Decision

**NONE among UIUX-F-113 through UIUX-F-127.** All proposed restrictions integrate
already defined object scope or canonical reader contracts. No new role,
permission, grant kind, Project/site inheritance or financial rule is needed.

Do not interpret the stricter clearance/Workforce service gates as a requirement
to broaden them for usability. A future proposal to change such behavior needs
its own authorization. SP-031 is excluded and may expose a separate unresolved
catalogue contract after its dedicated confirmation.

## Expected Closure State

| Finding | Batch | Evidence required before runtime-resolved status |
| --- | --- | --- |
| UIUX-F-113 | BATCH-08 | Project-only matrix and its own live request-create GET/invalid/negative path |
| UIUX-F-114 | BATCH-04 | Issued-order matrix and full single-selector runtime set |
| UIUX-F-115 | BATCH-09 | Maintenance Project/Site matrix and runtime subset controls |
| UIUX-F-116 | BATCH-08 | Contract Project matrix and its own live create/redisplay/negative path |
| UIUX-F-117 | BATCH-08 | Optional Project/central-denial matrix and Warehouse runtime observations |
| UIUX-F-118 | BATCH-05 | All movement-source matrices and receipt/transfer representative runtime set |
| UIUX-F-119 | BATCH-06 | Allocation coding matrix, detail GET, bare-400 negatives and refreshed GET |
| UIUX-F-120 | BATCH-07 | Project AND template-collection matrix plus create/proposal runtime negatives |
| UIUX-F-121 | BATCH-01 | All three forms/DMS matrix and every route's defined representative runtime evidence |
| UIUX-F-122 | BATCH-02 | Exact reader-gate matrix, limited negative and organization/view positive runtime |
| UIUX-F-123 | BATCH-03 | ContractItem matrix and its own measurement-source runtime observations |
| UIUX-F-124 | BATCH-03 | Payable Contract matrix and its own certificate-source runtime observations |
| UIUX-F-125 | BATCH-08 | Project matrix, live training-requirement create/redisplay negatives, stricter service denial preserved |
| UIUX-F-126 | BATCH-09 | Five-field/structure matrix and Quality representative runtime controls |
| UIUX-F-127 | BATCH-09 | Five-field/structure matrix and Safety live HTTP/negative controls |

For **each** finding the intended evidence progression is:

`STATIC_CONFIRMED -> REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST -> RUNTIME_VERIFIED_RESOLVED`

Preserve original static confirmation and historical evidence. In a future batch,
record the implementation status only after the bounded patch and required
automated evidence are satisfactory; keep the finding open while runtime or
regression evidence is pending. Append the runtime-resolved status and closure
evidence only after that finding's defined runtime set passes, all required
negative and known-good controls are supported, and no attributable regression
remains. Shared helper coverage does not automatically close every caller.

After the separate batches, a separately authorized final reconciliation may
verify all 15 evidence sets and current constructor wiring, without a fresh
42-candidate sweep or reopening F-111. That reconciliation must not silently add
SP-031 or other excluded units. Nothing is closed by this planning document.

## Safety Boundary

PRODUCT CODE CHANGED: NO  
FINDING CLOSED: NO  
ROLE CREATED: NO  
PERMISSION CREATED: NO  
AUTHORIZATION SEMANTICS CHANGED: NO  
BUSINESS DATA CREATED: NO  
PRODUCTION ACTION: NO  
CEP-078 EXECUTION: NO  
CEP-079 EXECUTION: NO  
GIT WRITE: NO

Only this Markdown plan is created. No findings-register, canonical prompt,
Registry, Roadmap, historical evidence, existing product/test file, generated PDF
or Graphify artifact is changed. Planning validation is limited to current-source
trace comparison, reference/coverage/whitespace checks and before/after content
preservation; application tests and runtime retests belong to future batches.

Planning validation: 15/15 findings assigned exactly once across nine batches;
no excluded unit assigned; all 11 local Markdown links resolve; all 129 retained
source excerpts and eight prior evidence artifact hashes match. Before/after
SHA-256 comparison preserves all 1,794 inspected existing product, configuration,
template, test, UIUX evidence and Registry files. Only this plan is newly added.
Read-only `git diff --check` passes for tracked changes; the new plan receives its
own Markdown whitespace check because Git does not diff untracked content.

## Final Decision

F111_PATTERN_REMEDIATION_PLAN_READY
