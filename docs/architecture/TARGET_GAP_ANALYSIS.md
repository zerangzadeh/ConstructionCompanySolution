# Target Domain Model v1.0 — Gap Analysis

> Compared against the repository state inspected on 2026-09-03  
> Target authority: the **Target Domain Model** in `AGENTS.md`  
> This is a planning artifact only; no schema or application change is authorized.

## 1. Classification summary

Each current or target entity appears exactly once in the catalog below. A
renamed/evolved current entity is represented as one row, for example
`ProjectDocument -> Document`, rather than being counted twice.

| Classification | Count | Meaning in this plan |
|---|---:|---|
| KEEP | 7 | Responsibility and schema are already close to v1.0. |
| EXTEND | 5 | Preserve the entity and add target relationships/behavior. |
| REFACTOR | 6 | Preserve data and identity while changing the aggregate/history model. |
| DEPRECATE | 0 | No whole entity should be removed now; only legacy fields are later contract candidates. |
| ADD | 40 | Required target entity is absent. |
| DEFER | 3 | Approved target concept, deliberately outside the near-term core sequence. |
| **Total** | **61** | Current and target entity catalog. |

Risk reflects migration, tenant isolation, history, and workflow complexity—not
the estimated amount of code alone.

## 2. Tenant, identity, and settings

### User — KEEP

- **Current:** global UUID `AbstractUser` identity with unique username and optional email/phone. **Target:** authentication identity, distinct from employment.
- **Schema:** none required. **Services:** keep authentication and membership boundaries. **Forms/views/admin:** do not add workforce fields to user forms. **Tests:** preserve authentication and cross-tenant membership tests.
- **Data migration:** none. **Tenant isolation:** intentionally no organization FK; access comes from memberships. **Compatibility:** full. **Risk:** LOW. **Dependencies:** OrganizationMembership; future Employee may optionally reference User.

### Organization — EXTEND

- **Current:** UUID tenant root with status, timezone, currency, actor fields, and soft deletion. **Target:** stable company/tenant identity and lifecycle root.
- **Schema:** retain current columns; add a one-to-one settings relation rather than moving fields immediately. **Services:** preserve atomic owner creation and lifecycle checks. **Forms/views/admin:** expose settings separately and harden admin scope. **Tests:** settings fallback plus existing lifecycle/isolation tests.
- **Data migration:** copy current timezone/currency into settings after expansion. **Tenant isolation:** root of all new entities. **Compatibility:** read legacy fields until settings backfill is validated. **Risk:** MEDIUM. **Dependencies:** OrganizationSettings.

### OrganizationSettings — ADD

- **Current:** absent; timezone/currency are on Organization. **Target:** organization-specific timezone, currency, fiscal settings, numbering schemes, feature/plan configuration where approved.
- **Schema:** required one-to-one organization FK, UUID/timestamps, configuration fields and scoped constraints. **Services:** get/create defaults, update with authorization/audit. **Forms/views/admin:** dedicated settings form; tenant-scoped admin. **Tests:** one-per-tenant, permissions, defaults, isolation.
- **Data migration:** backfill one row per organization from existing values. **Tenant isolation:** organization is mandatory and never user-selected. **Compatibility:** keep Organization fields during transition. **Risk:** MEDIUM. **Dependencies:** Organization.

### OrganizationMembership — KEEP

- **Current:** UUID tenant/user join with active-state and broad role. **Target:** source of truth for tenant RBAC, potentially supplemented by project/site restrictions.
- **Schema:** no immediate change. **Services:** preserve active membership lookup; future restrictions should supplement, not replace it. **Forms/views/admin:** admin mutations must use scoped, audited workflows. **Tests:** role/status transitions, escalation prevention, and tenant scope.
- **Data migration:** none. **Tenant isolation:** foundational. **Compatibility:** full. **Risk:** LOW for entity; HIGH if admin bypass remains. **Dependencies:** User, Organization; future EmployeeProjectAssignment or a separate approved access model.

### OrganizationInvitation — KEEP

- **Current:** hashed-token invitation lifecycle for existing users. **Target:** tenant membership onboarding workflow.
- **Schema:** no target-driven change. **Services:** retain atomic acceptance, expiry, and role checks. **Forms/views/admin:** restrict direct admin mutation. **Tests:** keep invitee/tenant/expiry/concurrency coverage.
- **Data migration:** none. **Tenant isolation:** organization and invitee are rechecked. **Compatibility:** full. **Risk:** LOW. **Dependencies:** User, Organization, OrganizationMembership.

## 3. Party master

### BusinessParty — ADD

- **Current:** absent; names are repeated in Contract, Payment, and Expense. **Target:** organization-owned person/company master used as client, vendor, subcontractor, supplier, or other counterparty.
- **Schema:** UUID, organization, legal/display names, party kind, identifiers, active/archive state, actor/timestamps, and tenant-scoped business-key indexes. **Services:** create/update/archive and safe party matching; deny cross-tenant references. **Forms/views/admin:** tenant-scoped selectors and management UI. **Tests:** duplicate policy, archive, permissions, and isolation.
- **Data migration:** cautious per-tenant backfill from legacy name fields; ambiguous names remain legacy-only until reviewed. **Tenant isolation:** mandatory organization FK and explicit equality checks on every reference. **Compatibility:** nullable new FKs plus retained name snapshots. **Risk:** HIGH. **Dependencies:** Organization; PartyRole and PartyContact.

### PartyRole — ADD

- **Current:** absent; party meaning is inferred from where a name is used. **Target:** allow one BusinessParty to carry client/vendor/subcontractor/supplier roles without duplicate identities.
- **Schema:** organization and party FKs, role choice/code, active dates/state, unique tenant-party-role constraint. **Services:** role assignment/removal with dependency checks and audit. **Forms/views/admin:** role management within party scope. **Tests:** role uniqueness, authorization, and cross-tenant rejection.
- **Data migration:** infer only roles supported by unambiguous source usage; allow review. **Tenant isolation:** validate both organization columns. **Compatibility:** existing records do not require roles until switched. **Risk:** MEDIUM. **Dependencies:** BusinessParty.

### PartyContact — ADD

- **Current:** absent. **Target:** organization-owned contact details for a BusinessParty, with primary/contact-type semantics.
- **Schema:** organization/party FKs, contact type/value, label, primary flag, active/archive state, actor/timestamps, and appropriate scoped indexes. **Services:** validated contact mutation and primary-contact invariant. **Forms/views/admin:** nested tenant-scoped contacts. **Tests:** normalization, primary behavior, permissions, isolation.
- **Data migration:** none unless later sources are discovered. **Tenant isolation:** organization must equal party organization. **Compatibility:** additive. **Risk:** LOW. **Dependencies:** BusinessParty.

## 4. Workforce

### Employee — ADD

- **Current:** absent; User is sometimes the only person reference and daily labor uses team text. **Target:** organization-owned employment/person record distinct from login identity.
- **Schema:** organization FK, optional unique-per-tenant employee code, person/employment fields, optional User link, active/archive state, actor/timestamps. **Services:** lifecycle and optional account association with explicit uniqueness. **Forms/views/admin:** workforce UI separated from account administration. **Tests:** User separation, lifecycle, permissions, isolation.
- **Data migration:** do not automatically turn every User into Employee; map only after business confirmation. **Tenant isolation:** required organization and same-tenant organizational references. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Organization, optionally User, Department, Position.

### Department — ADD

- **Current:** absent. **Target:** organization-owned workforce grouping.
- **Schema:** organization, code/name, optional parent if approved, active/archive state, scoped uniqueness. **Services:** CRUD/archive with dependency validation. **Forms/views/admin:** scoped management. **Tests:** uniqueness, hierarchy if used, and isolation.
- **Data migration:** none. **Tenant isolation:** required. **Compatibility:** additive. **Risk:** LOW. **Dependencies:** Organization; referenced by Employee/Position.

### Position — ADD

- **Current:** absent. **Target:** organization-owned job position/classification, optionally department-specific.
- **Schema:** organization, optional department, code/name, active/archive state, scoped constraints. **Services:** manage and prevent cross-tenant department links. **Forms/views/admin:** scoped selectors. **Tests:** uniqueness and tenant consistency.
- **Data migration:** none. **Tenant isolation:** organization must match department. **Compatibility:** additive. **Risk:** LOW. **Dependencies:** Department, Employee.

### WorkTeam — ADD

- **Current:** daily labor stores `team_name`. **Target:** reusable organization-owned team, optionally project/site aware through assignments.
- **Schema:** organization, code/name, leader if approved, active/archive state, actor/timestamps. **Services:** manage membership/availability; resolve legacy labels conservatively. **Forms/views/admin:** tenant-scoped team selectors. **Tests:** scoped uniqueness, archive, isolation.
- **Data migration:** staged per-tenant candidates from distinct daily `team_name`; preserve historical label snapshots. **Tenant isolation:** required. **Compatibility:** nullable daily-entry FK plus old name. **Risk:** MEDIUM. **Dependencies:** Employee, EmployeeProjectAssignment.

### EmployeeProjectAssignment — ADD

- **Current:** absent. **Target:** time-bounded employee/team assignment to a project/site/role without changing tenant membership.
- **Schema:** organization, employee, project, optional site/team, assignment role, dates/status, constraints preventing duplicate active assignments. **Services:** atomic assignment and release with hierarchy checks. **Forms/views/admin:** scoped dependent selectors. **Tests:** date overlap policy, permissions, hierarchy, isolation.
- **Data migration:** none expected. **Tenant isolation:** every referenced object must share organization and site must belong to project. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Employee, Project, ProjectSite, WorkTeam.

## 5. Projects and controls

### Project — KEEP

- **Current:** UUID tenant project root with scoped code, lifecycle, budget, dates, and archive. **Target:** construction project identity/root.
- **Schema:** retain; add references from new control entities rather than overload Project. **Services:** preserve create/archive and add target-aware orchestration only when needed. **Forms/views/admin:** incremental navigation; harden admin. **Tests:** preserve current suite and add new relationship isolation.
- **Data migration:** none. **Tenant isolation:** current service scoping is strong. **Compatibility:** full. **Risk:** LOW. **Dependencies:** Organization, ProjectSite, future CostCenter/WBS/Baseline.

### ProjectSite — KEEP

- **Current:** organization/project child with scoped code and active flag. **Target:** physical/operational site under a project.
- **Schema:** retain. **Services:** add a reusable hierarchy validator and eliminate inferred parent consistency. **Forms/views/admin:** harden admin related choices. **Tests:** direct/inconsistent parent scenarios.
- **Data migration:** none unless integrity scan finds bad rows. **Tenant isolation:** organization must equal project organization. **Compatibility:** full. **Risk:** MEDIUM because DB does not enforce equality. **Dependencies:** Project.

### ProjectPhase — KEEP

- **Current:** site child with explicit transition service. **Target:** project/site execution phase, separate from WBS/activity.
- **Schema:** retain unless target usage later needs an explicit project FK; avoid duplication initially. **Services:** strengthen parent-chain validation. **Forms/views/admin:** tenant-scoped and state-aware. **Tests:** corrupted-parent and admin isolation coverage.
- **Data migration:** only if integrity issues are detected. **Tenant isolation:** organization/site/project chain must agree. **Compatibility:** full. **Risk:** MEDIUM. **Dependencies:** ProjectSite; referenced by existing financial/daily records.

### CostCenter — ADD

- **Current:** absent. **Target:** organization/project cost classification used across budgets, commitments, actuals, and claims.
- **Schema:** organization, optional project depending business scope, code/name, parent if approved, active/archive state, scoped constraints. **Services:** manage hierarchy and prevent invalid reassignment. **Forms/views/admin:** scoped selectors. **Tests:** uniqueness, hierarchy, tenant isolation.
- **Data migration:** none; do not infer from free-text categories. **Tenant isolation:** mandatory and project consistency when project-specific. **Compatibility:** additive nullable references first. **Risk:** MEDIUM. **Dependencies:** Project and OrganizationSettings numbering policy.

### WBSNode — ADD

- **Current:** absent; ProjectPhase is the only work breakdown concept. **Target:** hierarchical work breakdown under a project, distinct from site/phase.
- **Schema:** organization/project, parent node, code/title, ordering, lifecycle, actor/timestamps, scoped uniqueness and indexes. **Services:** hierarchy creation/move with cycle prevention and row locking where needed. **Forms/views/admin:** tree-aware scoped UI. **Tests:** cycles, project/parent scope, permissions, isolation.
- **Data migration:** do not auto-convert phases unless the business confirms semantic equivalence. **Tenant isolation:** organization/project/parent chain must agree. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Project.

### Activity — ADD

- **Current:** absent; work performed is free text. **Target:** planned/controlled unit of work linked to WBS, phase/site as required.
- **Schema:** organization/project/WBS node, optional site/phase, code/name, unit and planned quantities/dates/status. **Services:** validate hierarchy and transitions. **Forms/views/admin:** scoped dependent selection. **Tests:** hierarchy, quantities, lifecycle, isolation.
- **Data migration:** none from narrative text without explicit mapping. **Tenant isolation:** all project hierarchy references must agree. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** WBSNode, Project, optionally ProjectSite/Phase, UnitOfMeasure.

### ProjectBaseline — ADD

- **Current:** absent. **Target:** immutable/versioned approved project plan snapshot.
- **Schema:** organization/project, version, status, approval actor/time, effective data or linked baseline items as later approved, unique version per project. **Services:** draft/create/approve without overwriting approved history. **Forms/views/admin:** read-only finalized baseline UI. **Tests:** versioning, approval concurrency, immutability, isolation.
- **Data migration:** no safe baseline can be inferred from current project dates/budget alone. **Tenant isolation:** organization/project equality. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Project, WBSNode, Activity.

### ProgressRecord — ADD

- **Current:** daily report has narrative `progress_summary`. **Target:** dated, quantitative progress against project/WBS/activity/baseline.
- **Schema:** organization/project, activity/WBS, date, quantity/percent, unit, source/report reference, actor/timestamps, scoped uniqueness policy. **Services:** validate baseline/activity and correction rules. **Forms/views/admin:** tenant-scoped progress entry/history. **Tests:** Decimal precision, duplicates, hierarchy, finalization, isolation.
- **Data migration:** narrative progress is not safely backfillable. **Tenant isolation:** all references must share organization/project. **Compatibility:** keep daily narrative as snapshot. **Risk:** HIGH. **Dependencies:** Activity, ProjectBaseline, UnitOfMeasure, optionally DailyReport.

## 6. Contracts and estimates

### Contract — REFACTOR

- **Current:** project header with free-text counterparty, value, status, and no controlled transitions. **Target:** directional client/vendor/subcontract contract root with BusinessParty, lines, and amendment history.
- **Schema:** add nullable counterparty FK and direction/type; later add constraints and retain `counterparty_name` snapshot. **Services:** add explicit lifecycle transitions, immutable finalized fields, amendment-driven changes, tenant checks. **Forms/views/admin:** party/direction selection; finalized admin read-only. **Tests:** backfill, transitions, immutability, hierarchy, isolation.
- **Data migration:** phased party backfill; direction requires business mapping and must not receive an unsafe default. **Tenant isolation:** party/project/contract organization equality. **Compatibility:** dual-read/write during transition; remove name only in a separately approved contract phase. **Risk:** HIGH. **Dependencies:** BusinessParty, ContractItem, ContractAmendment, Project.

### ContractItem — ADD

- **Current:** absent; only a header total exists. **Target:** contractual scope/value line, optionally tied to WBS/activity/cost center and UOM.
- **Schema:** organization/contract, description, quantity, UOM, unit price/value, ordering, optional control references. **Services:** line mutation only while contract state permits; recalculate/validate totals. **Forms/views/admin:** inline workflow through services, not unrestricted admin inline. **Tests:** Decimal, total, lock, tenant links.
- **Data migration:** do not synthesize a single line unless business explicitly approves; legacy header value remains authoritative initially. **Tenant isolation:** all references match contract tenant/project. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Contract, UnitOfMeasure, optionally WBSNode/Activity/CostCenter.

### ContractAmendment — ADD

- **Current:** absent; current values can be overwritten. **Target:** versioned, approved change to contract scope/value/dates without erasing history.
- **Schema:** organization/contract, amendment number, status, reason, Decimal effects, effective/approval fields and actor history. **Services:** draft/approve/void with transactions and row locks. **Forms/views/admin:** finalized amendments read-only. **Tests:** numbering, concurrency, immutable history, total effects, isolation.
- **Data migration:** none for unknown historical amendments. **Tenant isolation:** organization must match contract. **Compatibility:** current contract remains base value; derived current value can adopt amendments later. **Risk:** HIGH. **Dependencies:** Contract, possibly ContractItem.

### Estimate — REFACTOR

- **Current:** header with items, status, optional phase/contract, and direct approval. **Target:** stable estimate identity with explicit revision history and approval per revision.
- **Schema:** move revision-specific content/status/approval to EstimateRevision incrementally; keep current columns during transition. **Services:** create revisions, approve one immutable revision, prevent all finalized writes. **Forms/views/admin:** revision-aware UI and read-only approved history. **Tests:** current lock regression, revision sequence, concurrency, isolation.
- **Data migration:** create revision 1 for every existing estimate, preserving approval actor/time/status. **Tenant isolation:** estimate/revision/project/phase/contract organization chains. **Compatibility:** dual-read current fields then switch; later contract legacy columns. **Risk:** HIGH. **Dependencies:** EstimateRevision, Contract, Project.

### EstimateRevision — ADD

- **Current:** absent despite a `revised` status. **Target:** immutable/versioned estimate snapshot carrying status, notes, approval, and lines.
- **Schema:** organization/estimate, revision number, lifecycle/approval fields, unique `(estimate, revision_number)`, timestamps/actors. **Services:** atomic next-revision creation and approval with locking. **Forms/views/admin:** revision history and explicit copy/edit. **Tests:** sequencing, concurrent creation, approval lock, isolation.
- **Data migration:** one revision per current estimate. **Tenant isolation:** organization must equal estimate organization. **Compatibility:** back-reference/current revision pointer may be nullable until validated. **Risk:** HIGH. **Dependencies:** Estimate and EstimateItem.

### EstimateItem — REFACTOR

- **Current:** item belongs directly to Estimate and uses free-text unit. **Target:** item belongs to an EstimateRevision and uses canonical UOM where appropriate.
- **Schema:** add nullable revision FK and nullable UOM FK; retain estimate FK and unit snapshot initially. **Services:** write only to editable revision and validate tenant/UOM. **Forms/views/admin:** revision-aware lines; no direct finalized edit. **Tests:** backfill, totals, lock, UOM and tenant scope.
- **Data migration:** link existing items to generated revision 1; map known unit strings per tenant. **Tenant isolation:** revision/estimate/UOM organizations must agree, except approved global UOM policy if chosen. **Compatibility:** keep estimate FK and text unit through validation. **Risk:** HIGH. **Dependencies:** EstimateRevision, UnitOfMeasure.

## 7. Daily reporting and resource masters

### DailyReport — EXTEND

- **Current:** site/date root with draft-submit-approve and narrative work/progress/delay/safety/quality fields. **Target:** same root plus structured activities, resource usage, and delays.
- **Schema:** preserve root; add children and optional correction/version policy rather than replacing current text. **Services:** retain transactional transitions and enforce approved immutability across all children. **Forms/views/admin:** structured entry sections; finalized read-only. **Tests:** existing workflow plus child integration and correction rules.
- **Data migration:** narrative fields remain historical snapshots; no unsafe parsing. **Tenant isolation:** every child/reference must match report organization/project/site. **Compatibility:** additive. **Risk:** MEDIUM. **Dependencies:** DailyActivity, DelayEvent, resource masters.

### DailyActivity — ADD

- **Current:** absent; work is described in `work_performed`. **Target:** structured daily progress/activity entry linked to Activity when known.
- **Schema:** organization/report, optional Activity, description snapshot, quantities/UOM/progress, notes, actor/time. **Services:** draft-only creation and hierarchy validation. **Forms/views/admin:** scoped activity choices. **Tests:** quantity, lifecycle, activity/report project match, isolation.
- **Data migration:** do not parse narrative work automatically. **Tenant isolation:** organization/project chain must agree. **Compatibility:** keep narrative field. **Risk:** MEDIUM. **Dependencies:** DailyReport, Activity, UnitOfMeasure.

### DailyReportLaborEntry -> DailyLaborEntry — EXTEND

- **Current:** report child with free-text team name, worker count, and Decimal hours. **Target:** labor usage linked to WorkTeam and/or employee assignments while preserving historical labels.
- **Schema:** add nullable team/assignment references; rename only if value outweighs compatibility cost. **Services:** validate assignment/report project/date and keep draft lock. **Forms/views/admin:** scoped team selectors. **Tests:** backfill, unavailable assignments, finalization, isolation.
- **Data migration:** map reviewed team names after workforce rollout. **Tenant isolation:** team/assignment/report organization and project must agree. **Compatibility:** keep `team_name` as immutable snapshot. **Risk:** MEDIUM. **Dependencies:** WorkTeam, EmployeeProjectAssignment, DailyReport.

### DailyReportMaterialEntry -> DailyMaterialEntry — EXTEND

- **Current:** report child with free-text material and unit plus Decimal quantity. **Target:** structured usage linked to Material and UOM.
- **Schema:** add nullable material/UOM FKs; keep name/unit snapshots. **Services:** validate report/material/UOM tenant and material's canonical UOM; keep draft lock. **Forms/views/admin:** tenant-scoped selectors. **Tests:** conversion policy, finalization, backfill, isolation.
- **Data migration:** staged mapping by organization and reviewed normalized names/units. **Tenant isolation:** report/material organization equality. **Compatibility:** dual fields until coverage is complete. **Risk:** HIGH. **Dependencies:** Material, UnitOfMeasure, DailyReport.

### DailyReportEquipmentEntry -> DailyEquipmentEntry — EXTEND

- **Current:** report child with free-text equipment and Decimal hours. **Target:** usage linked to equipment/assignment with a preserved label snapshot.
- **Schema:** later add nullable Equipment and EquipmentAssignment FKs. **Services:** validate assignment project/site/date and draft status. **Forms/views/admin:** scoped equipment choices after equipment module exists. **Tests:** assignment validity, backfill, finalization, isolation.
- **Data migration:** reviewed matching after equipment master rollout. **Tenant isolation:** all references share organization and hierarchy. **Compatibility:** keep `equipment_name`. **Risk:** MEDIUM. **Dependencies:** Equipment, EquipmentAssignment, DailyReport.

### DelayEvent — ADD

- **Current:** delay information is free text in DailyReport. **Target:** structured delay occurrence with dates/duration, category, cause, impact, responsibility, and status as approved.
- **Schema:** organization/report/project, optional activity/WBS, structured fields, actor/timestamps. **Services:** draft-only creation and explicit resolution/correction rules. **Forms/views/admin:** structured section. **Tests:** durations, hierarchy, lifecycle, isolation.
- **Data migration:** keep historical narrative; no automatic extraction. **Tenant isolation:** report/project/activity chain. **Compatibility:** additive. **Risk:** MEDIUM. **Dependencies:** DailyReport, optionally Activity/WBSNode.

### UnitOfMeasure — ADD

- **Current:** units are free text on EstimateItem and daily material entries. **Target:** canonical unit identity used by materials, activities, contract/estimate lines, and resource usage.
- **Schema:** decide global immutable catalog versus organization-owned extensions; code/name/symbol/category/precision and active state. **Services:** controlled lookup and creation policy. **Forms/views/admin:** scoped/global selectors. **Tests:** uniqueness, Decimal precision, isolation policy.
- **Data migration:** normalize distinct legacy strings with review; preserve original snapshots. **Tenant isolation:** must explicitly define global versus tenant-owned records before schema. **Compatibility:** nullable FKs plus legacy unit strings. **Risk:** HIGH pending ownership decision. **Dependencies:** Organization policy.

### MaterialCategory — ADD

- **Current:** absent. **Target:** organization-owned material grouping.
- **Schema:** organization, code/name, optional parent, active/archive state, scoped constraints. **Services:** manage hierarchy and dependencies. **Forms/views/admin:** tenant-scoped management. **Tests:** uniqueness, cycles if hierarchical, isolation.
- **Data migration:** none reliably available. **Tenant isolation:** required. **Compatibility:** additive. **Risk:** LOW. **Dependencies:** Organization, Material.

### Material — ADD

- **Current:** daily usage stores names and units as text. **Target:** organization-owned material master with category and canonical UOM.
- **Schema:** organization, code/name, category, UOM, specifications, active/archive state, actor/timestamps, scoped constraints. **Services:** manage and prevent invalid category/UOM changes when referenced. **Forms/views/admin:** scoped master and selectors. **Tests:** uniqueness, references, archive, isolation.
- **Data migration:** reviewed candidates from daily names; do not merge solely by spelling. **Tenant isolation:** category/material organization equality and defined UOM ownership. **Compatibility:** legacy snapshots retained. **Risk:** HIGH. **Dependencies:** MaterialCategory, UnitOfMeasure.

## 8. Expenses, payments, and billing

### ExpenseCategory — ADD

- **Current:** Expense uses a fixed string choice. **Target:** organization-owned or approved seeded category master supporting reporting and lifecycle.
- **Schema:** organization, code/name, active/archive state, sort order, scoped uniqueness. **Services:** seed/default creation and guarded archive. **Forms/views/admin:** category management and scoped selection. **Tests:** seed idempotency, archive, reporting, isolation.
- **Data migration:** create per-tenant rows for each current choice actually used and map exactly. **Tenant isolation:** required. **Compatibility:** keep legacy `category` string until reports switch. **Risk:** MEDIUM. **Dependencies:** Organization, Expense.

### Expense — REFACTOR

- **Current:** Decimal project cost with optional phase, free-text vendor, category string, and void workflow. **Target:** historical expense referencing BusinessParty and ExpenseCategory, with controlled corrections.
- **Schema:** add nullable vendor/counterparty FK and category FK; retain name/category snapshots; add lifecycle consistency constraints where practical. **Services:** preserve void workflow, force creation as recorded, validate references. **Forms/views/admin:** scoped selectors and finalized read-only. **Tests:** backfills, void invariants, reporting parity, isolation.
- **Data migration:** staged party/category mapping. **Tenant isolation:** vendor/category/project/phase organization equality. **Compatibility:** dual fields and unchanged current reports until validation. **Risk:** HIGH. **Dependencies:** BusinessParty, ExpenseCategory, Project.

### Payment — REFACTOR

- **Current:** posted receipt/disbursement with free-text counterparty, optional project/contract/phase, and void workflow. **Target:** party-linked payment root with explicit allocations and immutable history.
- **Schema:** add nullable BusinessParty FK; later allocations; retain counterparty snapshot and current direct links. **Services:** preserve post/void, validate party, allocate atomically without exceeding amount. **Forms/views/admin:** party and allocation UI; posted records read-only. **Tests:** allocation totals/concurrency, void behavior, backfill, isolation.
- **Data migration:** cautious party mapping; existing project/contract links do not automatically imply allocation amounts. **Tenant isolation:** payment/party/allocation targets share tenant/project rules. **Compatibility:** current direct references remain until consumers switch. **Risk:** HIGH. **Dependencies:** BusinessParty, PaymentAllocation, Contract, future ProgressClaim.

### PaymentAllocation — ADD

- **Current:** absent; a payment points directly to a project and optionally contract/phase. **Target:** explicit distribution of a posted payment across approved payable/receivable targets.
- **Schema:** organization/payment, allocation target strategy, Decimal amount, timestamps/actor, constraints. Prefer explicit target FKs for approved domains over an unconstrained generic reference. **Services:** atomic allocate/reallocate/reverse with sum checks. **Forms/views/admin:** allocation workflow, finalized history read-only. **Tests:** over-allocation, concurrency, void interaction, isolation.
- **Data migration:** initially leave existing payments unallocated or create only unambiguous allocations after business rules are approved. **Tenant isolation:** all targets share organization and allowable project. **Compatibility:** direct payment links remain during transition. **Risk:** HIGH. **Dependencies:** Payment, Contract and/or ProgressClaim/billing targets.

### ProgressClaim — ADD

- **Current:** absent. **Target:** directional project/contract billing claim root with explicit lifecycle and immutable approved/posted history.
- **Schema:** organization/project/contract/party, claim number, period, status, totals, approval/posting/void actors and timestamps, scoped constraints. **Services:** draft/submit/approve/post/void transitions under transaction. **Forms/views/admin:** workflow UI; finalized read-only. **Tests:** calculations, transitions, concurrency, isolation.
- **Data migration:** none. **Tenant isolation:** all references share tenant/project/contract. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Contract, BusinessParty, ProgressClaimItem, ClaimAdjustment, PaymentAllocation.

### ProgressClaimItem — ADD

- **Current:** absent. **Target:** quantified/value line within a progress claim, linked to contract/control scope where approved.
- **Schema:** organization/claim, contract item/WBS/activity references, prior/current quantities and values, retention/tax only if approved. **Services:** calculate Decimal totals and lock with parent. **Forms/views/admin:** controlled line editor. **Tests:** cumulative limits, rounding, history, isolation.
- **Data migration:** none. **Tenant isolation:** all referenced records share claim tenant/project. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** ProgressClaim, ContractItem, WBSNode/Activity.

### ClaimAdjustment — ADD

- **Current:** absent. **Target:** explicit addition/deduction/reversal against a claim without silently rewriting claim lines.
- **Schema:** organization/claim, type, Decimal amount, reason, status, actor/approval fields. **Services:** atomic apply/void with parent-state checks. **Forms/views/admin:** explicit adjustment history. **Tests:** sign/rounding, lifecycle, immutability, isolation.
- **Data migration:** none. **Tenant isolation:** organization equals claim organization. **Compatibility:** additive. **Risk:** MEDIUM. **Dependencies:** ProgressClaim.

## 9. Procurement and inventory

### PurchaseRequest — ADD

- **Current:** absent. **Target:** tenant/project request workflow for materials/services.
- **Schema:** organization/project/site/requester, number, dates/status, approval fields, timestamps/actors, scoped uniqueness. **Services:** draft-submit-approve/reject with transactions. **Forms/views/admin:** workflow UI and scoped selectors. **Tests:** transitions, roles, numbering, isolation.
- **Data migration:** none. **Tenant isolation:** all hierarchy references agree. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** PurchaseRequestItem, Project, Employee/User policy.

### PurchaseRequestItem — ADD

- **Current:** absent. **Target:** requested material/service quantity tied to a PurchaseRequest.
- **Schema:** organization/request, optional material, description snapshot, quantity/UOM, needed date, optional WBS/cost center. **Services:** parent-draft mutation and hierarchy validation. **Forms/views/admin:** controlled lines. **Tests:** quantity, lock, scope.
- **Data migration:** none. **Tenant isolation:** references share tenant/project. **Compatibility:** additive. **Risk:** MEDIUM. **Dependencies:** PurchaseRequest, Material, UnitOfMeasure.

### PurchaseOrder — ADD

- **Current:** absent. **Target:** approved commitment to a BusinessParty supplier, optionally sourced from requests.
- **Schema:** organization/project/supplier, order number, dates/status, Decimal totals, approval/void fields, scoped uniqueness. **Services:** create/approve/issue/close/void with immutable finalized terms. **Forms/views/admin:** supplier and request selection; finalized read-only. **Tests:** totals, transitions, concurrency, isolation.
- **Data migration:** none. **Tenant isolation:** supplier role and all references match organization. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** BusinessParty/PartyRole, PurchaseOrderItem, PurchaseRequest.

### PurchaseOrderItem — ADD

- **Current:** absent. **Target:** committed material/service line and request linkage.
- **Schema:** organization/order, optional request item/material, description snapshot, quantity/UOM/price, received totals. **Services:** draft mutation and controlled quantity/value rules. **Forms/views/admin:** controlled lines. **Tests:** Decimal, request limits, parent lock, isolation.
- **Data migration:** none. **Tenant isolation:** all references share tenant/project. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** PurchaseOrder, Material, UnitOfMeasure, PurchaseRequestItem.

### GoodsReceipt — ADD

- **Current:** absent. **Target:** posted receipt of ordered goods into a site/warehouse with immutable history.
- **Schema:** organization/project/order/warehouse, receipt number/date/status, receiver, posting/void fields. **Services:** receive/post/void atomically and create stock effects idempotently. **Forms/views/admin:** receipt workflow; posted read-only. **Tests:** duplicate posting, order limits, concurrency, isolation.
- **Data migration:** none. **Tenant isolation:** order/warehouse/project chain. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** GoodsReceiptItem, PurchaseOrder, Warehouse, StockTransaction.

### GoodsReceiptItem — ADD

- **Current:** absent. **Target:** received quantity against an order line and material.
- **Schema:** organization/receipt/order item/material/UOM, quantity, condition/notes. **Services:** validate remaining quantity and stock-posting effects. **Forms/views/admin:** controlled receipt lines. **Tests:** Decimal, over-receipt policy, posting, isolation.
- **Data migration:** none. **Tenant isolation:** all parent and material references match. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** GoodsReceipt, PurchaseOrderItem, Material.

### Warehouse — ADD

- **Current:** absent. **Target:** organization-owned storage location, optionally project/site specific.
- **Schema:** organization, optional project/site, code/name, active/archive state, scoped uniqueness. **Services:** manage and prevent invalid archive with stock. **Forms/views/admin:** scoped location management. **Tests:** hierarchy, uniqueness, archive, isolation.
- **Data migration:** none. **Tenant isolation:** project/site chain must match organization. **Compatibility:** additive. **Risk:** MEDIUM. **Dependencies:** Project/ProjectSite.

### StockTransaction — ADD

- **Current:** absent. **Target:** immutable, posted material movement ledger for receipts, issues, returns, and transfers—not a general ledger.
- **Schema:** organization/material/UOM, source/destination warehouse, type, Decimal quantity, occurred/posted fields, source business key and idempotency constraint. **Services:** atomic post/reverse; never edit posted movement. **Forms/views/admin:** controlled workflows and read-only history. **Tests:** balance, transfer symmetry, idempotency, concurrency, isolation.
- **Data migration:** none. **Tenant isolation:** material and warehouses share organization; project rules explicit. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Material, Warehouse, GoodsReceipt.

## 10. Equipment

### Equipment — ADD

- **Current:** daily use stores equipment name only. **Target:** organization-owned equipment identity with status and operational attributes.
- **Schema:** organization, code/name, equipment category/type fields as approved, ownership/status, active/archive state, timestamps/actors, scoped uniqueness. **Services:** lifecycle and availability. **Forms/views/admin:** scoped master. **Tests:** uniqueness, archive, status, isolation.
- **Data migration:** reviewed candidates from daily names; preserve snapshots. **Tenant isolation:** required. **Compatibility:** additive. **Risk:** MEDIUM. **Dependencies:** Organization.

### EquipmentAssignment — ADD

- **Current:** absent. **Target:** time-bounded equipment assignment to project/site, providing valid context for daily usage.
- **Schema:** organization/equipment/project, optional site, dates/status, meter fields if approved, constraints for overlapping active assignments. **Services:** assign/release atomically and validate availability. **Forms/views/admin:** scoped assignment UI. **Tests:** overlap, hierarchy, lifecycle, isolation.
- **Data migration:** none. **Tenant isolation:** equipment/project/site organizations agree. **Compatibility:** additive. **Risk:** HIGH. **Dependencies:** Equipment, Project, ProjectSite.

### MaintenanceRecord — ADD

- **Current:** absent. **Target:** equipment maintenance event/history with planned/completed/void lifecycle.
- **Schema:** organization/equipment, type, dates, meter readings, description, Decimal cost if approved, status/actors. **Services:** schedule/complete/void; finalized records immutable. **Forms/views/admin:** scoped maintenance history. **Tests:** date/meter rules, lifecycle, isolation.
- **Data migration:** none. **Tenant isolation:** organization equals equipment organization. **Compatibility:** additive. **Risk:** MEDIUM. **Dependencies:** Equipment; optionally Expense/BusinessParty later.

## 11. Documents, safety, quality, and system

### ProjectDocument -> Document — REFACTOR

- **Current:** secure single-version project attachment optionally linked to Payment. **Target:** stable tenant document identity with version history and reusable business links.
- **Schema:** introduce/rename toward Document root without destructive rename, move physical-file metadata to DocumentVersion, preserve project/payment links during expansion. **Services:** retain validation/download/archive and add atomic version creation. **Forms/views/admin:** version/link UI; direct file mutation prohibited. **Tests:** migration parity, download security, immutable versions, isolation.
- **Data migration:** each existing ProjectDocument becomes a Document plus version 1 and equivalent links. **Tenant isolation:** document/version/link/target organizations must agree. **Compatibility:** keep old URLs/identifiers or adapter services until switched. **Risk:** HIGH. **Dependencies:** DocumentVersion, DocumentLink and linked domain models.

### DocumentVersion — ADD

- **Current:** absent; current file metadata is on ProjectDocument. **Target:** immutable file version with content metadata, uploader, and sequence.
- **Schema:** organization/document, version number, file, original filename, MIME, size, hash, uploader/timestamp, unique document/version. **Services:** validate before write; never replace a stored version. **Forms/views/admin:** version upload/history/download. **Tests:** signature/size/hash, sequencing, immutability, isolation.
- **Data migration:** create version 1 from every current document. **Tenant isolation:** organization equals document. **Compatibility:** current download path resolves migrated first/current version. **Risk:** HIGH. **Dependencies:** Document.

### DocumentLink — ADD

- **Current:** ProjectDocument has fixed project and optional payment FKs. **Target:** explicit links from one document to approved business objects.
- **Schema:** organization/document plus constrained link target design. Prefer enumerated link type and validated explicit identifiers/FKs over unrestricted generic relations. **Services:** link/unlink with object lookup under tenant. **Forms/views/admin:** type-aware scoped selection. **Tests:** target existence/type, isolation, duplicate links.
- **Data migration:** generate project and payment links from current columns. **Tenant isolation:** link service must resolve target within the same organization. **Compatibility:** retain legacy columns until all consumers switch. **Risk:** HIGH. **Dependencies:** Document and each permitted target model.

### SafetyIncident — DEFER

- **Current:** only DailyReport safety notes. **Target:** optional structured incident lifecycle and corrective-action history.
- **Schema:** none in near-term; later organization/project/site/report, severity/status, event/closure fields. **Services/UI/admin:** deferred pending requirements. **Tests:** later lifecycle, privacy, permissions, isolation.
- **Data migration:** do not parse notes. **Tenant isolation:** mandatory when added. **Compatibility:** keep notes. **Risk:** HIGH domain/compliance ambiguity. **Dependencies:** DailyReport, ProjectSite, possibly Employee/Document.

### QualityIssue — DEFER

- **Current:** only DailyReport quality notes. **Target:** optional non-conformity/quality issue with disposition and corrective actions.
- **Schema/services/UI/tests:** deferred until workflow and retention rules are approved. **Data migration:** do not parse notes. **Tenant isolation:** mandatory when added. **Compatibility:** keep notes.
- **Risk:** HIGH domain ambiguity. **Dependencies:** DailyReport, Activity/WBS, Employee, Document.

### AuditEvent — KEEP

- **Current:** organization-aware append-only application record with protected manager/queryset and safe metadata service. **Target:** immutable business/security audit infrastructure.
- **Schema:** no immediate entity change; database-level hardening may be evaluated operationally. **Services:** add caller/actor membership assertions where organization-scoped. **Forms/views/admin:** remain read-only. **Tests:** preserve append-only tests and add misuse/isolation cases.
- **Data migration:** none. **Tenant isolation:** nullable only for intentional global events. **Compatibility:** full. **Risk:** MEDIUM. **Dependencies:** all mutation services.

### Notification — DEFER

- **Current:** absent. **Target:** system/user notification only when concrete workflows require it.
- **Schema/services/UI/tests:** deferred; do not add queues or background jobs. **Data migration:** none. **Tenant isolation:** future notifications require organization and recipient scope. **Compatibility:** additive later.
- **Risk:** LOW while deferred. **Dependencies:** approved triggering workflows and delivery requirements.

## 12. Database evolution for legacy business references

All refactors below must use **EXPAND -> BACKFILL/MIGRATE -> SWITCH READS/WRITES
-> VALIDATE -> CONTRACT**. Contract steps are separate, explicitly approved
releases—not cleanup bundled into the expansion.

### 12.1 `Contract.counterparty_name`

1. **Expand:** add BusinessParty/PartyRole; add nullable Contract counterparty FK
   and nullable direction/type. Keep the name column.
2. **Backfill:** generate per-tenant matching candidates from normalized names.
   Never merge across organizations. Require review for spelling collisions,
   empty names, or party-type ambiguity. Do not infer contract direction from the
   name alone.
3. **Switch:** forms select an organization-scoped party and direction; services
   dual-write an immutable display-name snapshot.
4. **Validate:** report unmapped contracts, invalid party roles, duplicate
   candidates, and cross-tenant links; prove read/report parity.
5. **Contract:** only after approval, stop depending on legacy name as identity.
   Retaining it permanently as a historical snapshot is preferable to erasing it.

### 12.2 `Payment.counterparty_name` and `Expense.vendor_name`

1. **Expand:** nullable BusinessParty FK on each model; retain text.
2. **Backfill:** reuse reviewed parties within each organization. Payment
   direction may suggest payer/payee semantics but is not enough to auto-merge.
3. **Switch:** scoped party selectors; new writes require a party when the
   approved workflow says it is mandatory and also store the display snapshot.
4. **Validate:** unmapped rows, role suitability, report totals, and tenant
   equality.
5. **Contract:** stop using names for joins/filter identity. Keep snapshots for
   historical display unless retention policy says otherwise.

### 12.3 `EstimateItem.unit` and `DailyReportMaterialEntry.unit`

1. **Expand:** UnitOfMeasure and nullable UOM FKs; retain text.
2. **Backfill:** inventory exact and normalized unit strings per organization;
   map only approved aliases. Decide whether the catalog is global, tenant-owned,
   or global-with-tenant-extension before migration.
3. **Switch:** new forms use UOM selection; services store a symbol/name snapshot.
4. **Validate:** unmapped/ambiguous units, precision, and tenant policy.
5. **Contract:** stop using text as a relational key. Historical text should
   remain available.

### 12.4 `DailyReportMaterialEntry.material_name`

1. **Expand:** MaterialCategory/Material and nullable material FK on daily entry.
2. **Backfill:** create reviewed candidates using organization + normalized name
   + mapped UOM. Do not collapse items that differ in specification or unit.
3. **Switch:** tenant-scoped material choice with name/UOM snapshot; validate the
   material belongs to the report tenant.
4. **Validate:** coverage, duplicate candidates, category/UOM consistency, and
   financial/operational report parity.
5. **Contract:** stop using the name as identity; retain snapshot for history.

### 12.5 `DailyReportEquipmentEntry.equipment_name`

1. **Expand:** keep text through daily-report evolution; later add Equipment and
   nullable equipment/assignment FKs in the equipment phase.
2. **Backfill:** reviewed per-tenant matching after the equipment master is live.
3. **Switch:** validate equipment assignment against report project/site/date and
   dual-write the label snapshot.
4. **Validate:** unmatched usage and assignment conflicts.
5. **Contract:** text ceases to be identity but remains historical display data.

### 12.6 `DailyReportLaborEntry.team_name`

1. **Expand:** keep text; later add WorkTeam and nullable team/assignment FKs.
2. **Backfill:** reviewed per-tenant team matching. Do not infer Employees from a
   team label.
3. **Switch:** scoped team/assignment selection and snapshot write.
4. **Validate:** team/report project/date consistency and unmapped rows.
5. **Contract:** remove reliance on text as identity, not necessarily the text
   snapshot itself.

### 12.7 `Expense.category`

1. **Expand:** add ExpenseCategory and nullable category FK; keep choice column.
2. **Backfill:** seed idempotent per-tenant categories for each current choice and
   map existing values exactly.
3. **Switch:** forms/services use category FK and preserve legacy code during the
   compatibility window.
4. **Validate:** every non-deleted and historical expense maps; reports match
   before/after.
5. **Contract:** switch reports to category relation; remove legacy code only in
   a later approved migration if historical snapshots are not required.

### 12.8 Status and role strings

Choice-backed status/role fields should not be generically normalized into lookup
tables. They encode domain state machines and RBAC constants. The correct refactor
is stronger transition services, state metadata constraints, locked finalized
records, and audited changes—not a generic status/role engine.

## 13. Stable components that must not be rewritten

| Component | Decision | Narrowly scoped evolution |
|---|---|---|
| Custom User | **KEEP AS-IS** | Link Employee optionally; never merge the concepts. |
| Organization / Membership / Invitation | **KEEP WITH MINOR CHANGES** | Add settings relation and close admin bypass paths. |
| Active organization resolution | **KEEP AS-IS** | Reuse it for every new app. |
| Tenant middleware/decorators/services | **KEEP WITH MINOR CHANGES** | Centralize parent-chain assertions where repetition is proven. |
| Thin-view/service-layer architecture | **KEEP AS-IS** | New workflows must follow it. |
| UUID strategy | **KEEP AS-IS** | Apply to every new important entity. |
| Decimal handling and `ROUND_HALF_UP` | **KEEP AS-IS** | Define precision per new financial/quantity field. |
| Audit infrastructure | **KEEP WITH MINOR CHANGES** | Strengthen actor/tenant assertions and keep admin read-only. |
| Expense void workflow | **KEEP WITH MINOR CHANGES** | Force recorded creation and add reference evolution. |
| Payment void workflow | **KEEP WITH MINOR CHANGES** | Add parties/allocations without overwriting posted history. |
| Approved estimate service lock | **KEEP WITH MINOR CHANGES** | Move approval to revisions and enforce lock on every path. |
| Project/site/phase relationships | **KEEP WITH MINOR CHANGES** | Add integrity checks; do not conflate phase and WBS. |
| Document validation/security | **KEEP WITH MINOR CHANGES** | Reuse it for every DocumentVersion. |
| Financial reporting read layer | **KEEP WITH MINOR CHANGES** | Extend sources incrementally; do not build a general ledger. |

## 14. Highest-risk gaps

1. Unscoped/direct Django admin paths can bypass tenant, hierarchy, audit, and
   finalized-state rules.
2. The database cannot currently prevent tenant A children from referencing
   tenant B parents; services are the principal integrity boundary.
3. Approved/finalized Contract, Estimate, DailyReport, Expense, Payment, and file
   history is not universally immutable outside the intended service paths.
4. Party, material, equipment, team, unit, and expense-category meanings are
   stored as text, and safe matching is business-dependent.
5. Contract amendments, estimate revisions, payment allocations, and billing
   claims are absent, so historical corrections lack target v1.0 structures.

## 15. Business decisions required before implementation

- Whether UOMs are global immutable records, tenant-owned, or a global catalog
  with tenant extensions.
- Contract direction/type vocabulary and how existing contracts are classified.
- BusinessParty duplicate/matching rules and whether individuals and companies
  share one table with a party-kind discriminator.
- Whether legacy party/material/team/equipment names must remain permanent legal
  snapshots after relational links exist.
- Estimate revision semantics: which revision is current, whether approval makes
  the whole estimate or only one revision final, and how supersession works.
- Expense category ownership, seed policy, and whether tenants may customize it.
- Payment allocation targets and reversal/reallocation rules.
- Project/site access requirements beyond broad organization roles.
- WBS versus phase boundaries, baseline content, and quantitative progress units.
- DocumentLink target strategy and the exact business objects permitted.
- Whether Django admin is superuser operations-only or must support tenant staff.
