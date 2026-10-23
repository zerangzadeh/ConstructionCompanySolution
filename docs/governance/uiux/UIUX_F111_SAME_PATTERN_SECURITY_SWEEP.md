# BONIRA F-111 Same-Pattern Security Sweep

## Baseline

- Branch: `main`.
- HEAD and `origin/main`: `43ac319c6e73e48ca9626461b73987922c498ec3`, identical to the frozen audit commit.
- Authorized F-111 remediation remains uncommitted in its eight existing form/view files (180 insertions / 50 deletions). The sweep did not modify them or any other product file.
- UIUX-F-111 remains **RUNTIME_VERIFIED_RESOLVED**. Existing original finding/evidence and retest evidence are preserved.
- Development browser/HTTP runtime: **NOT USED**. The sole database operation was a read-only training preflight in `config.settings.development` against the configured Development database, with `default_transaction_read_only=on`. No migrations, authentication/session operation, fixture preparation or business write occurred.
- Date: 2026-10-22, Asia/Tehran.

Entry hashes: [ENTRY_HASHES.json](f111_same_pattern_evidence/ENTRY_HASHES.json). Current source, not the pre-remediation stale process on port 8001, is the implementation authority for this static sweep.

## Scope

Reviewed exactly these retained candidate families, split into the explicit decision units below:

1. Procurement: Purchase Request create; Goods Receipt order selector.
2. Equipment: Maintenance Record; meter/reading, usage, fuel, downtime, plan/work-order, spare-link and operator qualification selectors.
3. Contracts: Contract create; contractual-record Contract choices.
4. Inventory: legacy Warehouse and Stock Transaction choices.
5. Expenses / Fixed Assets: expense allocation dimensions, recurring templates; Asset/AssetTransaction project/site/cost-center dimensions and requested WBS/CBS presence check.
6. Accounting: journal/opening dimensions and scoped-reader entry comparison.
7. Billing: shared commercial Contract/DocumentVersion choices, retention approved-clearance sources, payable ContractItem/Contract choices, approved Claim/Certificate sources and claim-settlement Treasury choices.
8. Documents: ordinary typed targets and the Field Observation target branch.
9. Workforce / Payroll: Employee and its position cascade, Training Requirement, Employee Training Record; payroll employment/rule/input dimensions.
10. Quality / Safety / Compliance: create Project/Site-related choices and all five routed `ScopedModelForm` subclasses.

No other module was added. Original resolved F-111 forms and the prior Expense/Estimate/Field Observation proofs were used as references only, not re-run. Equipment financial policy/handoff workflows, broader workforce/ESS, other financial consumers, workflow acceptance, broad authorization and UI/UX review are outside this sweep.

The retained same-pattern inventory and root-cause discussion are in [the remediation report](UIUX_F111_REMEDIATION_REPORT.md#remaining-same_pattern_review_required-candidates) and its Root Cause Addressed section. No separate root-cause contract was fabricated. The prior retest and Wave A/B histories are unchanged.

## Candidate Results

**42 decision units**; a unit is one selector surface, a field subset with a different visibility contract, an explicitly requested absent dimension, or the requested scoped-reader comparison. Shared constructors with identical gates are grouped explicitly; counts do not claim 42 independent pages or browser tests. Affected means a proven static capability -> constructor -> template path, with an out-of-scope qualifying record, will disclose metadata; it does not claim a newly executed exploit.

| Module | Surface | Membership supplied | Scope filtering | Classification | Evidence |
| --- | --- | --- | --- | --- | --- |
| Procurement | SP-001 — Purchase Request create | No | Tenant + non-deleted only | AFFECTED_CONFIRMED | `apps/procurement/forms.py:30`; `apps/procurement/views.py:393`; UIUX-F-113 |
| Procurement | SP-002 — Goods Receipt issued-order selector | No | Tenant + issued + non-deleted parent only | AFFECTED_CONFIRMED | `apps/procurement/forms.py:184`; `apps/procurement/views.py:775`; UIUX-F-114 |
| Equipment | SP-003 — Maintenance Record Project/Site | No | Tenant/lifecycle only | AFFECTED_CONFIRMED | `apps/equipment/forms.py:126`; `apps/equipment/views.py:924`; UIUX-F-115 |
| Equipment | SP-004 — Meter/reading, usage, fuel, downtime, maintenance-plan and work-order selectors | No; validated at entry | Tenant only; organization grant required before construction | NOT_APPLICABLE | `apps/equipment/forms.py:282`; `apps/equipment/views.py:538` |
| Equipment | SP-005 — Work-order spare StockTransaction selector | No; validated at entry | Organization-only gate + authorized parent record | NOT_APPLICABLE | `apps/equipment/forms.py:408`; `apps/equipment/views.py:608` |
| Equipment | SP-006 — Operator qualification selectors | No; validated at entry | Tenant Employee/qualification/Equipment masters; organization-only gate | NOT_APPLICABLE | `apps/equipment/forms.py:222`; `apps/equipment/views.py:421` |
| Contracts | SP-007 — Contract create Project | No | Tenant + non-deleted only | AFFECTED_CONFIRMED | `apps/contracts/forms.py:16`; `apps/contracts/views.py:103`; UIUX-F-116 |
| Contracts | SP-008 — Contractual-record Contract selector | No; validated at entry | Tenant/active/party only, behind organization gate | NOT_APPLICABLE | `apps/contracts/forms.py:73`; `apps/contracts/views.py:184` |
| Inventory | SP-009 — Legacy Warehouse create Project | No | Tenant + non-deleted only | AFFECTED_CONFIRMED | `apps/inventory/forms.py:23`; `apps/inventory/views.py:113`; UIUX-F-117 |
| Inventory | SP-010 — Legacy Stock Transaction selectors | No | Tenant/lifecycle/status only | AFFECTED_CONFIRMED | `apps/inventory/forms.py:43`; `apps/inventory/views.py:264`; UIUX-F-118 |
| Expenses | SP-011 — Allocation Project/WBS/Activity | No | Tenant + lifecycle only; parent expense lookup does not narrow form | AFFECTED_CONFIRMED | `apps/expenses/forms.py:175`; `apps/expenses/views.py:369`; UIUX-F-119 |
| Expenses | SP-012 — Allocation CBS / CostCenter classifications | No; not needed for project ownership | Tenant + locked structure / leaf predicates | NOT_APPLICABLE | `apps/expenses/forms.py:175`; `apps/expenses/views.py:369` |
| Expenses | SP-013 — Recurring template Project and same-page template list | No | Project choices and template collection are tenant-wide | AFFECTED_CONFIRMED | `apps/expenses/forms.py:231`; `apps/expenses/views.py:462`; UIUX-F-120 |
| Fixed Assets | SP-014 — Asset create Project/Site/CostCenter | No; validated at entry | Tenant choices behind fixed_assets organization gate | NOT_APPLICABLE | `apps/fixed_assets/forms.py:51`; `apps/fixed_assets/views.py:186` |
| Fixed Assets | SP-015 — Asset transaction target Project/Site/CostCenter | No; validated at entry | Tenant choices behind fixed_assets organization gate | NOT_APPLICABLE | `apps/fixed_assets/forms.py:151`; `apps/fixed_assets/views.py:328` |
| Fixed Assets | SP-016 — Requested WBS/CBS selector dimensions | Not applicable | No WBS/CBS choice fields in either candidate form | NOT_APPLICABLE | `apps/fixed_assets/forms.py:51`; `apps/fixed_assets/views.py:186` |
| Accounting | SP-017 — Journal and opening Project/Site/WBS choices | No; validated at entry | Tenant-only JournalLineForm behind organization-only accounting gates | NOT_APPLICABLE | `apps/accounting/forms.py:129`; `apps/accounting/views.py:346` |
| Accounting | SP-018 — Scoped-reader comparison against journal/opening forms | Gate resolves active membership | No organization grant -> denied before any form construction | SAFE | `apps/accounting/forms.py:129`; `apps/accounting/views.py:346` |
| Billing | SP-019 — Shared commercial create Contract / DocumentVersion choices (three create forms) | No | _CommercialEvidenceForm._configure uses organization/lifecycle only | AFFECTED_CONFIRMED | `apps/billing/forms.py:34`; `apps/billing/views.py:739`; UIUX-F-121 |
| Billing | SP-020 — Retention release create approved clearance source | No | Tenant + clearance kind + approved only | AFFECTED_CONFIRMED | `apps/billing/forms.py:174`; `apps/billing/views.py:995`; UIUX-F-122 |
| Billing | SP-021 — Retention release correction approved clearance source | Reader resolves trusted membership | Tenant-only choices behind organization-only parent-reader gate | NOT_APPLICABLE | `apps/billing/forms.py:206`; `apps/billing/views.py:1019` |
| Billing | SP-022 — Payable measurement ContractItem selector | No | Tenant + payable/subcontract/active predicates only | AFFECTED_CONFIRMED | `apps/billing/forms.py:341`; `apps/billing/views.py:606`; UIUX-F-123 |
| Billing | SP-023 — Payable certificate Contract selector | No | Tenant + payable/subcontract/active predicates only | AFFECTED_CONFIRMED | `apps/billing/forms.py:371`; `apps/billing/views.py:408`; UIUX-F-124 |
| Billing | SP-024 — Taxpayer invoice approved Claim / prior invoice selectors | No; validated at entry | Tenant/status only behind organization-only statutory gate | NOT_APPLICABLE | `apps/billing/forms.py:241`; `apps/billing/views.py:1153` |
| Billing | SP-025 — Contractor assessment approved Certificate / clearance selectors | No; validated at entry | Tenant/status only behind organization-only statutory gate | NOT_APPLICABLE | `apps/billing/forms.py:265`; `apps/billing/views.py:1283` |
| Billing | SP-026 — Claim settlement posted Treasury source choices | Validated parent + capability gate | Tenant + authorized parent project/party + posted receipt predicates | SAFE | `apps/billing/forms.py:306`; `apps/billing/views.py:125` |
| Documents | SP-027 — General Project/Contract/Estimate/Expense/Treasury/Daily Report targets | Trusted request.user; membership resolved by has_business_permission | Per-target organization-scope permission or .none() | SAFE | `apps/documents/forms.py:45`; `apps/documents/views.py:122` |
| Documents | SP-028 — Field Observation target choices | Trusted user -> get_active_membership | scope_queryset(project_id, site_id), draft status; earlier gate may already empty choices | SAFE | `apps/documents/forms.py:45`; `apps/documents/views.py:122` |
| Workforce | SP-029 — Employee form and Department->Position cascade | No; trusted organization + account-link capability | Tenant master relationships; organization-only employees.create | NOT_APPLICABLE | `apps/workforce/forms.py:249`; `apps/workforce/views.py:227` |
| Workforce | SP-030 — Training Requirement Project selector | No | Tenant + non-deleted only | AFFECTED_CONFIRMED | `apps/workforce/forms.py:194`; `apps/workforce/views.py:1590`; UIUX-F-125 |
| Workforce | SP-031 — Employee Training Record requirement choices | No | Active tenant TrainingRequirement catalogue only | NEEDS_RUNTIME_CONFIRMATION | `apps/workforce/forms.py:206`; `apps/workforce/views.py:1605` |
| Payroll | SP-032 — Employment configuration Project/Site | No; validated at entry | Tenant predicates behind payroll_configuration organization gate | NOT_APPLICABLE | `apps/payroll/forms.py:89`; `apps/payroll/views.py:238` |
| Payroll | SP-033 — Rule Project/Site | No; validated at entry | Tenant predicates behind payroll_configuration organization gate | NOT_APPLICABLE | `apps/payroll/forms.py:153`; `apps/payroll/views.py:309` |
| Payroll | SP-034 — Input Project/Site/Employee dimensions | No; validated at entry; tenant-validated run | Tenant Project/Site; run-membership Employee filter; organization-only payroll.prepare | NOT_APPLICABLE | `apps/payroll/forms.py:271`; `apps/payroll/views.py:426` |
| Quality | SP-035 — Quality issue Project/Site/Phase/Activity/DailyReport selectors | No | Tenant/lifecycle only | AFFECTED_CONFIRMED | `apps/quality/forms.py:24`; `apps/quality/views.py:124`; UIUX-F-126 |
| Safety | SP-036 — Safety incident Project/Site/Phase/Activity/DailyReport selectors | No | Tenant/lifecycle only | AFFECTED_CONFIRMED | `apps/safety/forms.py:24`; `apps/safety/views.py:116`; UIUX-F-127 |
| Compliance | SP-037 — InspectionForm (inspection) / ScopedModelForm path | No; validated at entry | Tenant-only base and related querysets, behind organization-only compliance.view | NOT_APPLICABLE | `apps/compliance/forms.py:33`; `apps/compliance/views.py:202` |
| Compliance | SP-038 — PermitForm (permit) / ScopedModelForm path | No; validated at entry | Tenant-only base and related querysets, behind organization-only compliance.view | NOT_APPLICABLE | `apps/compliance/forms.py:33`; `apps/compliance/views.py:202` |
| Compliance | SP-039 — QualityTestForm (test) / ScopedModelForm path | No; validated at entry | Tenant-only base and related querysets, behind organization-only compliance.view | NOT_APPLICABLE | `apps/compliance/forms.py:33`; `apps/compliance/views.py:202` |
| Compliance | SP-040 — FindingForm (finding) / ScopedModelForm path | No; validated at entry | Tenant-only base and related querysets, behind organization-only compliance.view | NOT_APPLICABLE | `apps/compliance/forms.py:33`; `apps/compliance/views.py:202` |
| Compliance | SP-041 — CapaForm (capa) / ScopedModelForm path | No; validated at entry | Tenant-only base and related querysets, behind organization-only compliance.view | NOT_APPLICABLE | `apps/compliance/forms.py:33`; `apps/compliance/views.py:202` |
| Billing | SP-042 — Shared commercial revision Contract/DocumentVersion choices (three revision forms) | Parent-reader resolves trusted membership | Organization-only _require(project=None) before revision form construction | NOT_APPLICABLE | `apps/billing/forms.py:86`; `apps/billing/views.py:134` |

Actual permission strings and object-scope/organization-only gate decisions, including the nested Billing reader gate, are in [SCOPE_GATE_MATRIX.json](f111_same_pattern_evidence/SCOPE_GATE_MATRIX.json). Routed URL paths are retained per candidate and new finding.

The form-membership column is distinct from membership validation at the HTTP gate. A permission decorator resolves trusted membership, but for object-scoped namespaces it asks only whether **any** effective scope exists. It does not narrow a field queryset. For namespaces outside that registry, the same gate requires an explicit organization grant; a role name, decorator name, or form class name alone was never used as proof.

Decisive source: `apps/organizations/decorators.py:18`, `apps/organizations/authorization.py:29,94,315,388,440`, `apps/organizations/form_scoping.py:22,41,65`. Effective grant dates/revocation, membership/user/tenant activity, tenant intersection and project/site semantics remain owned by those helpers.

## Confirmed Security Findings

**15 new findings: UIUX-F-113 through UIUX-F-127.** They are reconciled into the canonical register as `STATIC_CONFIRMED`, `runtime_status: NOT_EXECUTED`. Original F-111 was not reopened.

Severity is **MEDIUM** for plain Project/Site/catalogue metadata and **HIGH** for independently protected commercial/financial source references, expense allocation context or broad DMS version metadata. No successful posting, payment, privilege change, personal-file contents, item price, or full document download is claimed. The original F-111 severity is unchanged.

Only SP-019 groups multiple forms under one finding: they share the proven `_CommercialEvidenceForm._configure` seam. The clearance-source constructors are separate decision units because their inline filters are outside that helper; the create path is affected and the correction path is organization-gated. Other independent constructors/remediation seams remain separate findings.

### UIUX-F-113 — Purchase Request create

- Severity: **MEDIUM**; confirmation: **static**, not runtime.
- Affected surface: Procurement / SP-001.
- Exposed metadata: Ungranted Project codes/names and option UUIDs.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + non-deleted only. purchase_requests.create permits any effective grant at entry; Projects require effective project authority. No subsequent GET object check narrows choices.
- Evidence: `apps/procurement/forms.py:30`; `apps/procurement/views.py:393`; rendering templates and exact current source excerpts are indexed under SP-001 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-114 — Goods Receipt issued-order selector

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Procurement / SP-002.
- Exposed metadata: Issued Purchase Order numbers and UUIDs from ungranted projects.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + issued + non-deleted parent only. goods_receipts.create admits limited grants. Purchase Orders have project authority; status=issued is not an authorization predicate.
- Evidence: `apps/procurement/forms.py:184`; `apps/procurement/views.py:775`; rendering templates and exact current source excerpts are indexed under SP-002 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-115 — Maintenance Record Project/Site

- Severity: **MEDIUM**; confirmation: **static**, not runtime.
- Affected surface: Equipment / SP-003.
- Exposed metadata: Project code/name, Site code/name, parent-project label, and UUIDs.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant/lifecycle only. maintenance_records.create supports object scope; capability entry accepts any grant. Tenant Equipment/provider masters are separate from protected Project/Site choices.
- Evidence: `apps/equipment/forms.py:126`; `apps/equipment/views.py:924`; rendering templates and exact current source excerpts are indexed under SP-003 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-116 — Contract create Project

- Severity: **MEDIUM**; confirmation: **static**, not runtime.
- Affected surface: Contracts / SP-007.
- Exposed metadata: Project code/name and UUID.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + non-deleted only. contracts.create permits limited grants; the Project field is neither parent-bound nor scope-intersected. BusinessParty is a tenant master and is not the claimed leak.
- Evidence: `apps/contracts/forms.py:16`; `apps/contracts/views.py:103`; rendering templates and exact current source excerpts are indexed under SP-007 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-117 — Legacy Warehouse create Project

- Severity: **MEDIUM**; confirmation: **static**, not runtime.
- Affected surface: Inventory / SP-009.
- Exposed metadata: Ungranted Project code/name and UUID.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + non-deleted only. warehouses.create admits limited grants. Existing warehouse readers use scope_queryset(project_id). A central-warehouse empty choice does not grant visibility to other Projects.
- Evidence: `apps/inventory/forms.py:23`; `apps/inventory/views.py:113`; rendering templates and exact current source excerpts are indexed under SP-009 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-118 — Legacy Stock Transaction selectors

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Inventory / SP-010.
- Exposed metadata: Ungranted Project/warehouse labels and IDs, and posted GoodsReceiptItem option IDs/labels.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant/lifecycle/status only. stock_transactions.create accepts limited grants. Project-associated warehouses, receipt items and Projects need their existing object-scope intersection; Material is a tenant master, excluded from the finding.
- Evidence: `apps/inventory/forms.py:43`; `apps/inventory/views.py:264`; rendering templates and exact current source excerpts are indexed under SP-010 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-119 — Allocation Project/WBS/Activity

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Expenses / SP-011.
- Exposed metadata: Other-project Project/WBS/Activity option labels and UUIDs.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + lifecycle only; parent expense lookup does not narrow form. expenses.view/allocate support limited grants. An authorized draft/returned expense plus expenses.allocate renders the allocation form. The context processor admits that capability with any applicable grant; it does not narrow child querysets.
- Evidence: `apps/expenses/forms.py:175`; `apps/expenses/views.py:369`; rendering templates and exact current source excerpts are indexed under SP-011 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-120 — Recurring template Project and same-page template list

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Expenses / SP-013.
- Exposed metadata: Project labels/UUIDs in choices; existing out-of-scope template description, project name and occurrence-form identifier in the same page. No template amounts are rendered by this template.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Project choices and template collection are tenant-wide. expenses.recurrences_manage is in the expenses scoped namespace. recurrence_list builds the tenant-wide form and template collection without scope intersection. Both are rendered on this same bounded candidate surface.
- Evidence: `apps/expenses/forms.py:231`; `apps/expenses/views.py:462`; rendering templates and exact current source excerpts are indexed under SP-013 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-121 — Shared commercial create Contract / DocumentVersion choices (three create forms)

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Billing / SP-019.
- Exposed metadata: Other-project Contract numbers/titles/UUIDs and Document titles/version numbers/UUIDs, including versions not authorized through their linked context.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: _CommercialEvidenceForm._configure uses organization/lifecycle only. Guarantee, compliance-evidence and retention-release create namespaces admit limited grants directly. _configure does not use that membership for Contracts or DocumentVersions. Revision/detail paths are separately organization-gated by their reader services and are not included in this confirmation.
- Evidence: `apps/billing/forms.py:34`; `apps/billing/views.py:739`; rendering templates and exact current source excerpts are indexed under SP-019 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-122 — Retention release create approved clearance source

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Billing / SP-020.
- Exposed metadata: Approved out-of-scope clearance evidence option UUIDs and labels.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + clearance kind + approved only. retention_releases.create accepts project-limited grants. The constructor's additional clearance_evidence queryset bypasses both project scope and the canonical get_compliance_evidence selector, independently of the shared Contract/DocumentVersion helper.
- Evidence: `apps/billing/forms.py:174`; `apps/billing/views.py:995`; rendering templates and exact current source excerpts are indexed under SP-020 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-123 — Payable measurement ContractItem selector

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Billing / SP-022.
- Exposed metadata: Other-project payable ContractItem option identifiers and model labels. No item rate/amount disclosure is asserted.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + payable/subcontract/active predicates only. payable_measurements.record supports limited grants. ContractItem project authority is not intersected in the create form; lifecycle and payable direction do not grant scope.
- Evidence: `apps/billing/forms.py:341`; `apps/billing/views.py:606`; rendering templates and exact current source excerpts are indexed under SP-022 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-124 — Payable certificate Contract selector

- Severity: **HIGH**; confirmation: **static**, not runtime.
- Affected surface: Billing / SP-023.
- Exposed metadata: Other-project active subcontract number/title/UUID.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + payable/subcontract/active predicates only. payable_certificates.create supports limited grants. get_payable_certificates uses project scope for reads; the Contract form choice remains tenant-wide instead.
- Evidence: `apps/billing/forms.py:371`; `apps/billing/views.py:408`; rendering templates and exact current source excerpts are indexed under SP-023 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-125 — Training Requirement Project selector

- Severity: **MEDIUM**; confirmation: **static**, not runtime.
- Affected surface: Workforce / SP-030.
- Exposed metadata: Other-project Project codes/names and UUIDs. Tenant competency/position masters are not included in the claim.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant + non-deleted only. workforce_qualifications.manage supports any effective grant at the view. The Project selector is tenant-wide. The training service's later project check cannot protect metadata already rendered by _foundation_form.
- Evidence: `apps/workforce/forms.py:194`; `apps/workforce/views.py:1590`; rendering templates and exact current source excerpts are indexed under SP-030 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-126 — Quality issue Project/Site/Phase/Activity/DailyReport selectors

- Severity: **MEDIUM**; confirmation: **static**, not runtime.
- Affected surface: Quality / SP-035.
- Exposed metadata: Out-of-scope Project/Site/Phase/Activity/DailyReport option identifiers and labels; no issue description/content read is asserted.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant/lifecycle only. quality_issues.create admits limited project/site grants. The canonical issue readers use scope_queryset; create choices do not intersect that scope. Generic form rendering includes every field.
- Evidence: `apps/quality/forms.py:24`; `apps/quality/views.py:124`; rendering templates and exact current source excerpts are indexed under SP-035 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

### UIUX-F-127 — Safety incident Project/Site/Phase/Activity/DailyReport selectors

- Severity: **MEDIUM**; confirmation: **static**, not runtime.
- Affected surface: Safety / SP-036.
- Exposed metadata: Out-of-scope Project/Site/Phase/Activity/DailyReport option identifiers and labels; no incident contents are asserted.
- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.
- Technical root cause: Tenant/lifecycle only. safety_incidents.create admits limited project/site grants. The canonical incident readers use scope_queryset, but initial and bound create choices do not.
- Evidence: `apps/safety/forms.py:24`; `apps/safety/views.py:116`; rendering templates and exact current source excerpts are indexed under SP-036 in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).

## Runtime Confirmations

**None.** Static trace was conclusive for the 15 confirmed exposures and the safe/non-applicable units, so no broad browser run was justified. No completed Wave A/B or F-111 scenario was repeated.

One read-only preflight for SP-031 found that retained P-17 has `workforce_qualifications.manage` with A/B grants, lacks organization scope, and has **zero active TrainingRequirements available in the tenant**. [TRAINING_PREFLIGHT.json](f111_same_pattern_evidence/TRAINING_PREFLIGHT.json). No form/HTTP metadata assertion is claimed from that query, and no data or authority was prepared to force a result.

## SAFE Patterns

- **SP-018 — Scoped-reader comparison against journal/opening forms:** Even when a limited-grant role contains accounting.view, permission_supports_object_scope(accounting.view) is false; membership_has_scope with no object and allow_any_scope=False requires an explicit organization grant. This is a static denied-entry proof, not a new browser scenario.
- **SP-026 — Claim settlement posted Treasury source choices:** _claim resolves through get_progress_claims, whose _require_progress_permission requires organization scope. The detail also requires organization-scope claim_settlements.allocate before constructing/rendering the form; choices are restricted to that claim's project/party. No permission or authority is inferred from Site-parent visibility.
- **SP-027 — General Project/Contract/Estimate/Expense/Treasury/Daily Report targets:** Although the candidate initially builds tenant-wide querysets, each field is cleared unless has_business_permission for that target succeeds with no project and no allow_any_scope. Limited-only grants therefore produce .none(); an organization grant legitimately spans all tenant projects. Existing document exclusion only removes already-linked objects and never adds authority.
- **SP-028 — Field Observation target choices:** The dedicated FieldObservation branch validates active membership, capture capability and effective project/site grants. The earlier organization-style view check can leave a limited actor's queryset empty; that is fail-closed and is not evidence that all authorized observations are usable. No functionality change is authorized here.

Canonical safe reference mechanisms remain `scope_queryset`, `scoped_projects_for_form`, `scope_project_related_choices`, and `selected_form_project`, preserving their domain-specific semantics. Original F-111, Expense/Estimate and Field Observation references were not counted as newly reviewed candidate successes.

## NOT_APPLICABLE Decisions

These are bounded decisions about the current reachable metadata path. They do not certify the entire domain or prescribe that every future actor must have organization scope.

- **SP-004 — Meter/reading, usage, fuel, downtime, maintenance-plan and work-order selectors:** equipment_meters/equipment_usage/equipment_fuel/equipment_downtime/equipment_maintenance_plans/equipment_work_orders are not object-scoped namespaces. Decorators therefore require an organization grant. Equipment/meters/plans are tenant fleet records; a deployment does not transfer master ownership to one project.
- **SP-005 — Work-order spare StockTransaction selector:** equipment_spare_links.manage is organization-gated. A limited project/site grant cannot reach the tenant transaction choices even though the form constructor itself uses only organization/status filters.
- **SP-006 — Operator qualification selectors:** equipment_qualifications.manage requires organization scope at the HTTP gate. Tenant workforce/fleet masters are not exclusively project-owned objects.
- **SP-008 — Contractual-record Contract selector:** contractual_records.prepare is outside OBJECT_SCOPED_PERMISSION_NAMESPACES. The HTTP decorator requires organization scope, regardless of the downstream scoped service semantics; no limited-grant actor reaches this selector.
- **SP-012 — Allocation CBS / CostCenter classifications:** CBSNode and CostCenter are organization-owned versioned classifications; neither model has a project/site owner. Project grants do not define their visibility. The Project/WBS/Activity finding must not be extended automatically to these masters.
- **SP-014 — Asset create Project/Site/CostCenter:** fixed_assets.candidate_prepare is organization-scoped at entry. The constructor is broad but cannot serve these options to an actor with only limited project/site grants; CostCenter is a tenant classification.
- **SP-015 — Asset transaction target Project/Site/CostCenter:** transaction_create requires fixed_assets.view, which requires an organization grant. This prevents limited-grant reachability before constructing AssetTransactionForm, independently of later transaction-service checks.
- **SP-016 — Requested WBS/CBS selector dimensions:** AssetForm and AssetTransactionForm define project/site/cost-center dimensions, not WBS/CBS selectors. No missing selector or new fixed-asset behavior is inferred.
- **SP-017 — Journal and opening Project/Site/WBS choices:** accounting.view and accounting.journals_prepare require an organization grant. Journal/opening detail additionally conditionally render line forms only for applicable draft states and prepare capability. An organization Accountant can legitimately see all tenant dimensions.
- **SP-021 — Retention release correction approved clearance source:** The detail/correction views first call _commercial_record -> get_retention_releases -> _require(project=None), which does not set allow_any_scope. It therefore requires an organization grant and denies limited-only actors before the form is constructed. Its broad clearance queryset is not a reachable limited-scope leak through this caller.
- **SP-024 — Taxpayer invoice approved Claim / prior invoice selectors:** taxpayer_invoices.prepare is not an object-scoped namespace. The HTTP boundary requires organization authority, so its approved claims/prior invoices are not exposed to a limited-grant-only actor by this route.
- **SP-025 — Contractor assessment approved Certificate / clearance selectors:** contractor_compliance.prepare is organization-gated at entry. Its approved Certificate/clearance sources are not reachable by a limited-grant-only actor.
- **SP-029 — Employee form and Department->Position cascade:** Employee/User/Department/Position/WorkTeam are tenant identity/routing masters, not exclusively project-owned. EmployeeForm's account branch is explicitly capability-gated; the cascade filters positions by trusted organization before optional department ID. Project grants do not turn organizational positions into project objects.
- **SP-032 — Employment configuration Project/Site:** payroll_configuration.manage is organization-only at entry. Employee is a tenant master; current limited-only actors are denied before dimension choices are constructed.
- **SP-033 — Rule Project/Site:** RuleForm shares the organization-only configuration boundary. Optional project/site applicability does not expose other projects to actors that cannot enter the form.
- **SP-034 — Input Project/Site/Employee dimensions:** payroll.prepare is organization-gated. The run is fetched using organization plus PK and input employees are restricted to that run's employees. Do not infer payroll_results/ESS reader authority from Payroll preparation authority.
- **SP-037 — InspectionForm (inspection) / ScopedModelForm path:** compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.
- **SP-038 — PermitForm (permit) / ScopedModelForm path:** compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.
- **SP-039 — QualityTestForm (test) / ScopedModelForm path:** compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.
- **SP-040 — FindingForm (finding) / ScopedModelForm path:** compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.
- **SP-041 — CapaForm (capa) / ScopedModelForm path:** compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.
- **SP-042 — Shared commercial revision Contract/DocumentVersion choices (three revision forms):** guarantee_detail, compliance_evidence_detail and retention_release_detail resolve _commercial_record through get_guarantees/get_compliance_evidence/get_retention_releases. Their _require passes project=None with allow_any_scope left False, so limited-only actors are denied even though the outer capability decorators support object scope. A scope_queryset later in the reader does not remove that earlier organization-only requirement. Revision POST handlers use the same parent-reader boundary.

## NEEDS_RUNTIME_CONFIRMATION

**SP-031 — Employee Training Record requirement choices.** Minimum follow-up: reuse an existing limited-grant actor with `workforce_qualifications.manage` (P-17 already qualifies), and existing active A/B plus C/D project-associated TrainingRequirements. Establish the applicable catalogue visibility contract before treating a requirement's optional project applicability as exclusive visibility ownership; compare the actual rendered option label, identifier and UUID against an authorized and unauthorized parent. Include an existing cross-tenant requirement negative if available. None currently exists in the inspected active Development requirement data, so this sweep creates no fixtures. Tenant Employee/Skill/Position masters must not acquire an invented project-scope rule.

This unresolved unit does not weaken or erase the other static confirmations. No other unit is deferred merely because it lacks a browser test.

## Cross-Tenant Assessment

CROSS_TENANT_METADATA_EXPOSURE: **NOT_TESTED**

No cross-tenant exposure was confirmed. Candidate constructors retain tenant predicates (including parent-tenant predicates where applicable), but this static sweep does not promote that observation to a new cross-tenant runtime PASS. No critical-stop condition was encountered.

## Unauthorized Mutation

UNAUTHORIZED_MUTATION_OBSERVED: **NOT_TESTED**

No business POST or other business mutation was attempted. Mutation-service denial cannot repair an initial metadata leak; conversely, metadata disclosure does not prove an unauthorized business write.

## Scope Boundary

PRODUCT CODE CHANGED: NO  
ROLE CREATED: NO  
PERMISSION CREATED: NO  
SCOPE BROADENED: NO  
BUSINESS DATA CREATED: NO  
PRODUCTION ACTION: NO  
CEP-078 EXECUTION: NO  
CEP-079 EXECUTION: NO  
GIT WRITE: NO

No browser, session, credential, migration or fixture manipulation. Existing generated PDFs are preserved, remain untracked, and were neither deleted nor added to Git. Only this report, new static evidence and the authorized findings-register reconciliation were written. All pre-existing finding objects, F-111 status, earlier runtime evidence and other historical files are checked for preservation.

## Sweep Metrics

| Metric | Count |
| --- | ---: |
| CANDIDATES_REVIEWED | 42 |
| SAFE_COUNT | 4 |
| AFFECTED_CONFIRMED_COUNT | 15 |
| NEEDS_RUNTIME_CONFIRMATION_COUNT | 1 |
| NOT_APPLICABLE_COUNT | 22 |

## Detailed Static Trace

The following annotations complete the view -> form -> field -> gate -> membership -> scope -> rendering/invalid-redisplay/cascade chain. Full relevant source excerpts, file hashes, symbols, verified line spans and templates are in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json). The AST relationship map is navigation evidence, not an automatic security classifier. No graph rebuild was performed; source code controls over graph hints.

### SP-001 — Purchase Request create

Authorization contract: purchase_requests.create permits any effective grant at entry; Projects require effective project authority. No subsequent GET object check narrows choices.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-002 — Goods Receipt issued-order selector

Authorization contract: goods_receipts.create admits limited grants. Purchase Orders have project authority; status=issued is not an authorization predicate.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-003 — Maintenance Record Project/Site

Authorization contract: maintenance_records.create supports object scope; capability entry accepts any grant. Tenant Equipment/provider masters are separate from protected Project/Site choices.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-004 — Meter/reading, usage, fuel, downtime, maintenance-plan and work-order selectors

Authorization contract: equipment_meters/equipment_usage/equipment_fuel/equipment_downtime/equipment_maintenance_plans/equipment_work_orders are not object-scoped namespaces. Decorators therefore require an organization grant. Equipment/meters/plans are tenant fleet records; a deployment does not transfer master ownership to one project.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-005 — Work-order spare StockTransaction selector

Authorization contract: equipment_spare_links.manage is organization-gated. A limited project/site grant cannot reach the tenant transaction choices even though the form constructor itself uses only organization/status filters.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-006 — Operator qualification selectors

Authorization contract: equipment_qualifications.manage requires organization scope at the HTTP gate. Tenant workforce/fleet masters are not exclusively project-owned objects.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-007 — Contract create Project

Authorization contract: contracts.create permits limited grants; the Project field is neither parent-bound nor scope-intersected. BusinessParty is a tenant master and is not the claimed leak.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-008 — Contractual-record Contract selector

Authorization contract: contractual_records.prepare is outside OBJECT_SCOPED_PERMISSION_NAMESPACES. The HTTP decorator requires organization scope, regardless of the downstream scoped service semantics; no limited-grant actor reaches this selector.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-009 — Legacy Warehouse create Project

Authorization contract: warehouses.create admits limited grants. Existing warehouse readers use scope_queryset(project_id). A central-warehouse empty choice does not grant visibility to other Projects.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-010 — Legacy Stock Transaction selectors

Authorization contract: stock_transactions.create accepts limited grants. Project-associated warehouses, receipt items and Projects need their existing object-scope intersection; Material is a tenant master, excluded from the finding.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-011 — Allocation Project/WBS/Activity

Authorization contract: expenses.view/allocate support limited grants. An authorized draft/returned expense plus expenses.allocate renders the allocation form. The context processor admits that capability with any applicable grant; it does not narrow child querysets.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Allocation POST returns empty 400 for an invalid form (no invalid form redisplay). Initial eligible expense detail renders all allocation choices.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-012 — Allocation CBS / CostCenter classifications

Authorization contract: CBSNode and CostCenter are organization-owned versioned classifications; neither model has a project/site owner. Project grants do not define their visibility. The Project/WBS/Activity finding must not be extended automatically to these masters.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-013 — Recurring template Project and same-page template list

Authorization contract: expenses.recurrences_manage is in the expenses scoped namespace. recurrence_list builds the tenant-wide form and template collection without scope intersection. Both are rendered on this same bounded candidate surface.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-014 — Asset create Project/Site/CostCenter

Authorization contract: fixed_assets.candidate_prepare is organization-scoped at entry. The constructor is broad but cannot serve these options to an actor with only limited project/site grants; CostCenter is a tenant classification.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-015 — Asset transaction target Project/Site/CostCenter

Authorization contract: transaction_create requires fixed_assets.view, which requires an organization grant. This prevents limited-grant reachability before constructing AssetTransactionForm, independently of later transaction-service checks.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-016 — Requested WBS/CBS selector dimensions

Authorization contract: AssetForm and AssetTransactionForm define project/site/cost-center dimensions, not WBS/CBS selectors. No missing selector or new fixed-asset behavior is inferred.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-017 — Journal and opening Project/Site/WBS choices

Authorization contract: accounting.view and accounting.journals_prepare require an organization grant. Journal/opening detail additionally conditionally render line forms only for applicable draft states and prepare capability. An organization Accountant can legitimately see all tenant dimensions.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Journal invalid POST can re-render the same form, while opening POST redirects. Both require organization scope before construction.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-018 — Scoped-reader comparison against journal/opening forms

Authorization contract: Even when a limited-grant role contains accounting.view, permission_supports_object_scope(accounting.view) is false; membership_has_scope with no object and allow_any_scope=False requires an explicit organization grant. This is a static denied-entry proof, not a new browser scenario.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-019 — Shared commercial create Contract / DocumentVersion choices (three create forms)

Authorization contract: Guarantee, compliance-evidence and retention-release create namespaces admit limited grants directly. _configure does not use that membership for Contracts or DocumentVersions. Revision/detail paths are separately organization-gated by their reader services and are not included in this confirmation.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Create forms render the same choices after invalid submission; this confirmation excludes revision/detail entry paths.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-020 — Retention release create approved clearance source

Authorization contract: retention_releases.create accepts project-limited grants. The constructor's additional clearance_evidence queryset bypasses both project scope and the canonical get_compliance_evidence selector, independently of the shared Contract/DocumentVersion helper.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-021 — Retention release correction approved clearance source

Authorization contract: The detail/correction views first call _commercial_record -> get_retention_releases -> _require(project=None), which does not set allow_any_scope. It therefore requires an organization grant and denies limited-only actors before the form is constructed. Its broad clearance queryset is not a reachable limited-scope leak through this caller.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: POST and initial detail both resolve the organization-authorized parent before constructing correction choices.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-022 — Payable measurement ContractItem selector

Authorization contract: payable_measurements.record supports limited grants. ContractItem project authority is not intersected in the create form; lifecycle and payable direction do not grant scope.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-023 — Payable certificate Contract selector

Authorization contract: payable_certificates.create supports limited grants. get_payable_certificates uses project scope for reads; the Contract form choice remains tenant-wide instead.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-024 — Taxpayer invoice approved Claim / prior invoice selectors

Authorization contract: taxpayer_invoices.prepare is not an object-scoped namespace. The HTTP boundary requires organization authority, so its approved claims/prior invoices are not exposed to a limited-grant-only actor by this route.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-025 — Contractor assessment approved Certificate / clearance selectors

Authorization contract: contractor_compliance.prepare is organization-gated at entry. Its approved Certificate/clearance sources are not reachable by a limited-grant-only actor.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-026 — Claim settlement posted Treasury source choices

Authorization contract: _claim resolves through get_progress_claims, whose _require_progress_permission requires organization scope. The detail also requires organization-scope claim_settlements.allocate before constructing/rendering the form; choices are restricted to that claim's project/party. No permission or authority is inferred from Site-parent visibility.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-027 — General Project/Contract/Estimate/Expense/Treasury/Daily Report targets

Authorization contract: Although the candidate initially builds tenant-wide querysets, each field is cleared unless has_business_permission for that target succeeds with no project and no allow_any_scope. Limited-only grants therefore produce .none(); an organization grant legitimately spans all tenant projects. Existing document exclusion only removes already-linked objects and never adds authority.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Upload and link constructors preserve the same per-target fail-closed policy for bound input; invalid upload redisplays and invalid link returns to governed detail.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-028 — Field Observation target choices

Authorization contract: The dedicated FieldObservation branch validates active membership, capture capability and effective project/site grants. The earlier organization-style view check can leave a limited actor's queryset empty; that is fail-closed and is not evidence that all authorized observations are usable. No functionality change is authorized here.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-029 — Employee form and Department->Position cascade

Authorization contract: Employee/User/Department/Position/WorkTeam are tenant identity/routing masters, not exclusively project-owned. EmployeeForm's account branch is explicitly capability-gated; the cascade filters positions by trusted organization before optional department ID. Project grants do not turn organizational positions into project objects.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: GET employee_positions uses tenant-filtered Position objects and optional department_id; employees.create requires organization scope before execution.

### SP-030 — Training Requirement Project selector

Authorization contract: workforce_qualifications.manage supports any effective grant at the view. The Project selector is tenant-wide. The training service's later project check cannot protect metadata already rendered by _foundation_form.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-031 — Employee Training Record requirement choices

Authorization contract: TrainingRequirement can be global or project-associated; record_employee_training passes requirement.project to its authority check. Need a concrete project-associated requirement and an approved visibility comparison to distinguish catalogue-wide applicability from project-owned visibility; the present data cannot demonstrate the distinction. Employee master choices alone are not a project-scope finding.

Initial HTML / metadata: Not runtime-confirmed: no suitable active requirement data.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: Read-only preflight: retained P-17 has workforce_qualifications.manage with A/B grants and no organization grant; there are zero active TrainingRequirements. No fixture was created; no rendering/HTTP test executed.

### SP-032 — Employment configuration Project/Site

Authorization contract: payroll_configuration.manage is organization-only at entry. Employee is a tenant master; current limited-only actors are denied before dimension choices are constructed.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-033 — Rule Project/Site

Authorization contract: RuleForm shares the organization-only configuration boundary. Optional project/site applicability does not expose other projects to actors that cannot enter the form.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-034 — Input Project/Site/Employee dimensions

Authorization contract: payroll.prepare is organization-gated. The run is fetched using organization plus PK and input employees are restricted to that run's employees. Do not infer payroll_results/ESS reader authority from Payroll preparation authority.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-035 — Quality issue Project/Site/Phase/Activity/DailyReport selectors

Authorization contract: quality_issues.create admits limited project/site grants. The canonical issue readers use scope_queryset; create choices do not intersect that scope. Generic form rendering includes every field.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-036 — Safety incident Project/Site/Phase/Activity/DailyReport selectors

Authorization contract: safety_incidents.create admits limited project/site grants. The canonical incident readers use scope_queryset, but initial and bound create choices do not.

Initial HTML / metadata: Protected choices are rendered on the eligible template path described above.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-037 — InspectionForm (inspection) / ScopedModelForm path

Authorization contract: compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-038 — PermitForm (permit) / ScopedModelForm path

Authorization contract: compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-039 — QualityTestForm (test) / ScopedModelForm path

Authorization contract: compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-040 — FindingForm (finding) / ScopedModelForm path

Authorization contract: compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-041 — CapaForm (capa) / ScopedModelForm path

Authorization contract: compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

### SP-042 — Shared commercial revision Contract/DocumentVersion choices (three revision forms)

Authorization contract: guarantee_detail, compliance_evidence_detail and retention_release_detail resolve _commercial_record through get_guarantees/get_compliance_evidence/get_retention_releases. Their _require passes project=None with allow_any_scope left False, so limited-only actors are denied even though the outer capability decorators support object scope. A scope_queryset later in the reader does not remove that earlier organization-only requirement. Revision POST handlers use the same parent-reader boundary.

Initial HTML / metadata: No claimed disclosure; scope/entry behavior follows the stated contract.

Bound POST / invalid redisplay: Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.

AJAX / cascade: No candidate cascade endpoint found in routed views/templates.

## Final Decision

F111_PATTERN_SWEEP_FINDINGS_CONFIRMED
