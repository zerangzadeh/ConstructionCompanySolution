# User Capability Map

**Status:** product/UX target reference; not an authorization grant catalogue

**Exact current permissions:** `BusinessPermissionCode`, permission registry,
role defaults, services, views and tests

**Workflow decisions:** `WORKFLOW_AND_PERMISSION_MATRIX.md`

## 1. Purpose

This document maps user groups to goals and product capabilities so roadmap and
UX work do not omit a participant or confuse navigation with authorization. It
describes typical responsibility, not guaranteed access. Every request still
requires active identity/membership, tenant state, business permission,
project/site scope, object lifecycle and—where acting on workflow—current
assignment/candidacy and separation rules.

## 2. Access layers

```text
Authenticated User
  + active OrganizationMembership
  + active tenant/entitlement
  + BusinessPermission
  + project/site/object scope [target]
  + valid record lifecycle
  + workflow assignment/candidacy and separation rule [when acting]
  = permitted operation
```

Position, department, team, employee relationship, UI visibility and possession
of an object UUID do not independently grant access.

## 3. Platform and Tenant roles

Current protected role codes differ from the target vocabulary. Role migration
and default grants require an approved package. Platform and Tenant roles are
independent assignments; one user may explicitly hold multiple roles, but no role
implicitly assigns or merges another.

Tenant/business roles are scoped to the user's Tenant membership. A single User may
therefore be Tenant Owner, Tenant Admin and Project Manager in Tenant A while being
only Project Manager in Tenant B. These are separate assignments in a conceptual
many-to-many `User -> Membership -> MembershipRoleAssignment -> Role` relation,
not a composite role. Assigning or revoking one does not change another and must
retain actor, Tenant, role, time and relevant reason/context. Effective access uses
all active applicable role-derived permissions but still requires explicit grants,
effective project/site scope, delegation/workflow eligibility and applicable policy.

| Platform role | Primary goals | Typical capability boundary |
| --- | --- | --- |
| Superuser | Exceptional highest-level technical/system intervention and Protected Operations | No automatic Tenant business-data access; separate explicit scoped authority is required |
| Platform Admin | Tenant provisioning, global configuration and permitted operational platform administration | Distinct from Superuser; no implicit Superuser capability or ordinary Tenant business-data authority |

The target Tenant responsibility model is:

| Profile | Primary goals | Typical capability boundary |
| --- | --- | --- |
| Tenant Owner | Govern Tenant, appoint responsibility, define/approve high-level Tenant policy and see enterprise health | Does not imply Tenant Admin; explicit scope required; no automatic organization-wide access or Self-Approval |
| Tenant Admin / Local Admin | Operate one Tenant's users, delegated role/access assignment, workflow administration and first-line user support | No other-Tenant/global-platform authority and no unrestricted business-data access from the role alone |
| Tenant Manager | Control projects, budgets, contracts, procurement and operational approvals | Business/operational management only; separate from Tenant and platform administration |
| Accountant | Maintain books/subledgers, posting, periods, reconciliation and financial/statutory outputs | Sensitive financial permissions, period controls and explicit auditable Self-Approval policy where configured |
| Supervisor | Record/review site work, time, materials, equipment, HSE and QA/QC | Assigned project/site operations; no broad tenant finance by default |
| Viewer/Auditor | Read permitted records, evidence and reports | Read/export only when separately granted; no mutation |

Operational job functions such as buyer, quantity surveyor, storekeeper, payroll
specialist, HSE officer, QA/QC inspector and document controller should be built
from business permissions plus object scope, not hard-coded as new authorization
systems.

## 4. Internal user capability matrix

Legend: **Current** means useful repository behavior exists; **Target** means
scheduled roadmap scope; **Controlled** means sensitive or separation-dependent.

| User group | Current capabilities | Target capabilities | Key restrictions |
| --- | --- | --- | --- |
| Tenant Owner | Tenant ownership and high-level policy where explicitly granted | Plans/entitlements/quotas, ownership, export/offboarding and high-level access policy | Does not imply Tenant Admin or unrestricted business access |
| Tenant Admin / Local Admin | Tenant-local settings, users, delegated roles/access, workflow administration and first-line support | Object-scope administration, MFA/support-grant administration where explicitly permitted | No global or other-Tenant authority; no unrestricted business-data access |
| Tenant Manager | Projects and operational records within granted business scope | Portfolio/project management and configured business approvals | No Tenant/platform administration merely from management role |
| Executive/Portfolio Manager | Projects, delivered financial read views, workbench and operational records as permitted | Portfolio cost/cash/forecast/KPI, risk/change, governed management queries | KPI drill-through, project scope, no unrestricted SQL/AI |
| Project Manager | Project/site/WBS/activity, contracts, estimates, daily/operational records, assigned workflow | Budget/commitment/forecast, schedule/risk/change, claims/payables and reconciliations | Project/site scope and configured approval limits |
| Commercial/Quantity Surveyor | Contracts/amendments, estimate revisions, baselines/progress/receivable claims, subcontract certificates, guarantees, insurance/clearance evidence, controlled retention releases, and effect-free Site Instruction/Variation/contractual Claim/EOT evidence | BOQ/resource/coefficient/scenario and later authorized contract/schedule/financial consumption | Contract term/rule versions, object scope, workflow candidacy, SoD and pinned source evidence |
| Procurement/Buyer | Requests, orders, receipts, procurement work items and scoped immutable supplier-invoice match review | RFQ, broader supplier invoice operations and portal collaboration | Bid confidentiality, sourcing SoD, project/cost coding; review grants no force-match or discrepancy override |
| Storekeeper | Warehouses, draft/post/reverse stock movements and balances; P8-S05–S11 reservations, bin/legacy-unlocated custody, risk-based lot/serial/expiry evidence, counts, two-sided transfer acceptance and reconciliation where explicitly permitted | Barcode/QR capture, notifications and later valuation evidence | Dedicated view/prepare/release, traceability, count maker-checker, transfer dispatch/independent acceptance and reconciliation permissions; Tenant/warehouse/project scope |
| Equipment Manager | Equipment operations through accepted P8-S23; P8-S24 adds versioned internal cost-rate and conserved allocation proposals plus reviewed Project Cost proposal envelopes | Later consumer activation | Project/site scope; operational equipment is not the asset ledger; legacy maintenance cost and allocation proposals are not actuals |
| Fixed Asset Specialist | P8-S25–S27 source-backed candidates/register, class/book policies, capitalization, one-book straight-line depreciation, impairment/transfer/disposal and proposal/reconciliation evidence | Later downstream consumer contracts and production activation | Dedicated default-deny finance permissions and maker-checker; Fixed Assets cannot post journals, recognize Project Cost actuals or move cash |
| Workforce/HR | Employees, departments, positions, teams, effective assignments, skills, qualifications, training evidence, reference labor-rate history, Tenant calendars and permissioned time/attendance workbench | Payroll-connected labor costing and any workforce financial consumer | Personal/compensation privacy, effective dates, explicit permissions and project/site scope; Workforce access never grants Payroll access |
| Payroll Specialist | Effective pay configuration/components/rules, Core/statutory calculation, review/finalization, restricted results, and separately granted preparation/review of accepted liability, Accounting-source, payment and Project Cost proposals plus reconciliation | Downstream recognition/execution and live filing | Core, statutory and each handoff family use independent default-denied permissions. Core/statutory audit views are separated; handoff lists/details expose only authorized families; payslip/statutory export requires explicit permission and audit evidence. One user may hold multiple duties only through explicit grants; downstream protected-operation separation remains unchanged. P7-S01–S36 is Product Owner accepted; P8-S01–S04 design creates no Payroll consumer, actual cost or production authority. |
| Accountant | Expenses/payments/allocations and financial read models where granted | COA/journals, AP/AR, periods/statements, tax output and close/reconciliation | Strict SoD, immutable posting, reversal and project/object scope |
| Treasurer | Legacy posted cash/payment records where granted | Bank/cash/cheque/transfer, proposals, statement matching and reconciliation | Maker-checker, bank sensitivity, no journal editing |
| Site Supervisor/Engineer | Daily reports, labor/equipment/material/activity/delay, incidents/issues, scoped attendance capture and timesheet preparation | Work fronts/weather/visits/meetings/instructions/media and later reviewed usage/movement/progress proposals | Assigned site/project; capture/preparation cannot self-review and never finalizes finance/payroll |
| HSE Officer | Safety incident lifecycle and assigned workflow | Risk, inspections, permits, toolbox/PPE/training, investigation/CAPA and metrics | Sensitive-case access and independent closure where configured |
| QA/QC Inspector | Quality issue lifecycle and assigned workflow | ITP, inspection request, checklists/tests/sample approval, punch/NCR/rework/CAPA | Verification independence and immutable closed evidence |
| Document Controller | Versioned documents/links/download/archive where granted | OCR/search, transmittals, RFI/submittal/drawing review, signatures, hold/export | Linked-context permission, retention/legal hold and download audit |
| Knowledge Reviewer | P9-S21–S24 Product Owner accepted | Review/recommend/approve/publish immutable reviewed derivatives; review explicit recurrence and reuse evidence | Exact source/DMS-version provenance, Tenant/Platform scope, audience/sensitivity, author-versus-approval SoD and no AI or automatic downstream publication |
| Support Operator | P9-S16–S20 tenant support cases, consented diagnostics, source-linked in-app attention and approved timed access; no standing tenant access | Later provider/SLA automation and broader releases/features | Purpose, scope, expiry, tenant consent, audit, source revalidation and PII minimization |
| Platform Admin | Permitted operational platform administration and Tenant provisioning | Global configuration and platform operations | Distinct from Superuser; no automatic Tenant business-data access |
| Superuser | Current highest technical/system capability | Exceptional protected technical operations | Distinct from Platform Admin; no automatic Tenant business-data access |

## 5. External and self-service participants

| Participant | Scheduled capability | Access model |
| --- | --- | --- |
| Supplier | Invite-scoped issued-RFQ read and versioned quote submission/correction are implemented; qualification, invoice/evidence submission and broader status remain scheduled | Private Tenant invitation bound to one unambiguous active account/email and no internal membership; least privilege; no competitor/internal-note visibility |
| Subcontractor | Profile/qualification, tender/quote, claim/progress/evidence submission and status | Bilateral portal; contract/project-limited; no ordinary tenant membership by default |
| Consultant/Client reviewer | Selected transmittal/RFI/submittal/drawing/claim review when approved | Explicit record/workflow assignment and expiring external scope |
| Employee self-service | Optional payslip, personal profile/certificate/leave/time interactions | Product Owner decision; employee-to-user link, privacy and dedicated permission |
| Auditor | Time-bounded read/export of evidence, journals/reconciliations and audit trail | Explicit scope, purpose and audit; no mutation |
| Network participant | Future discovery/shared qualification/marketplace/intelligence | Deferred opt-in platform consent; separate from tenant portal and private data |

## 6. Capability map by product area

| Capability family | Primary actors | Review/approval actors | Read/assurance actors | Roadmap disposition |
| --- | --- | --- | --- | --- |
| Tenant lifecycle/entitlements | Tenant Owner / Tenant Admin as explicitly permitted | Tenant Owner / Platform Admin policy split | Tenant Owner/support with grant | P0.3 |
| Identity/roles/object scope | Tenant Owner / Tenant Admin as explicitly permitted | Tenant Owner plus protected platform policy | Auditor/security | P1.1/P1.2 |
| Masters/materials/parties | Authorized master-data users | Data/quality owner | Operational consumers | P1.2/P1.4 |
| Estimate/BOQ/budget | Estimator/QS | Commercial/Project Manager | Finance/executive | P4.0/P4.1 |
| Project cost/forecast | Project controls | Project/finance management | Executive/auditor | P4.1/P10 |
| Expense | Requester/finance clerk | Project/finance approver | Accountant/auditor | P4.3 |
| Procurement/AP | Requester/buyer/storekeeper/AP | Technical/commercial/financial routes | Project/finance/auditor | P5/P3 |
| Contract/claim/guarantee | Commercial/QS | Configured project/commercial/finance route | Accounting/executive/auditor | P6 |
| Time/payroll/insurance | Employee/supervisor/HR/payroll | Supervisor/HR/payroll/accounting | Employee where approved/auditor | P7 |
| Inventory/equipment/assets | Store/equipment/asset staff | Operations/finance route with separated custody, valuation, maintenance, asset and accounting authority | Project Cost/accounting/auditor | P8-S01–S30 Product Owner accepted under C01–C38=A and complete within documented non-production boundaries; production activation gated |
| Field/HSE/QA | Site users capture scoped field evidence and authorized HSE/QA inspections, permits, tests, findings and assigned CAPA work | Profile-authorized reviewers issue/review controls; independent verifier protects implementation; closer/reopen authority is separate and sensitive evidence remains separately permissioned | Project management/auditor through scoped export, reconciliation and derived closeout evidence; precise location remains separately permissioned | P9-S01–S25 Product Owner accepted; S26 closeout complete; P10-S14–S17 may read only with source permission and creates no Field/HSE/QA mutation. |
| Partner qualification/performance | Partner preparer records tenant-local evidence and project evaluation | Independent reviewer approves qualification/category or publishes explainable evaluation | Scoped procurement/project management/auditor; sensitive evidence remains separately permissioned | P9-S12–S15 Product Owner accepted |
| Documents/knowledge | Document author/controller; knowledge author/candidate submitter | Reviewer/approver/publisher with author self-publication denied | Scoped published users, sensitive-provenance viewer and auditor/reconciler | P1.3 implemented boundary; P9-S21–S24 Product Owner accepted |
| Support/AI | Tenant requester/support operator for accepted cases, source-linked in-app attention, consent and timed access | Tenant grant owner and independent Platform approver; AI remains deferred | Tenant/security/auditor | P9-S16–S25 Product Owner accepted under N01–N18=A and F01–F18=A; ERP Assistant deferred |
| Reporting/reconciliation/closeout control | Authorized analyst/finance/project-controls users run synchronous governed metric, reconciliation and nine-family closeout assessments; coordinators append proposals/evidence but cannot mutate sources | Product Owner plus affected source owners and P10 control owner; profile author cannot publish, and preparer/last material disposer cannot solely accept a material closeout assessment | Scoped management/auditor with Reporting, project, source-domain, sensitive-data and DMS authorization rechecked for drill-through/export | P10-S02–S17 Product Owner accepted under `P10-C01`–`P10-C36=A`; P10-S18+ remains gated. |
| Portal/network | Invited external party / future opted-in tenant | Internal owner / future platform governance | Scoped tenant participants | P5.2 / network deferred |

## 7. Workflow and workbench experience

- One active membership has one organization workbench even if its employee holds
  multiple positions.
- Work items explain business object, project/site, current step, due/priority and
  why the user may act (assignment, candidacy or delegation).
- Claiming, release, approval, rejection/return, reassignment and delegation obey
  current permission, scope, candidacy and separation rules inside the transaction.
- Notifications may link to a work item but do not duplicate its lifecycle. Audit
  records evidence but is not a task list.
- Users can see safe disabled-action reasons only when action existence is not
  itself sensitive.

## 8. UX and accessibility obligations

Every capability follows `../ui-guidelines.md`: Persian-first RTL, explicit
tenant/project/site context, Jalali presentation, unambiguous currency/unit,
cascading authorized selectors, mobile/responsive behavior, keyboard/focus and
WCAG target, loading/empty/error/concurrency states, evidence/source links and
explanations for consequential calculation/action.

Delivered screens are remediated through P0.4 by value and risk; this map does
not authorize cosmetic redesign or backend changes hidden as UI work.

## 9. AI capability boundary

The scheduled **AI Support Assistant** retrieves cited approved support/tenant
knowledge, suggests diagnostics and escalates. The deferred **ERP Assistant** may
later answer management questions, explain KPIs and guide operations only through
permission-scoped semantic/read APIs and authorized domain commands.

Neither assistant may query unrestricted SQL, reveal another tenant, grant
permission, bypass workflow, publish knowledge, or autonomously finalize/post/pay/
submit legal or financial actions.

## 10. Capability acceptance rule

A new user-facing capability is complete only when its owner, permission code,
default-role decision, project/site scope, lifecycle, workflow responsibility,
SoD, UI states, audit/evidence, tenant-isolation tests and roadmap disposition are
explicit. Menu visibility or a role label alone is never acceptance evidence.
