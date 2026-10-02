# Product Development Roadmap

**Status date:** 2026-09-30

**Product stage:** pre-production

**Purpose:** dependency-ordered delivery plan; a listed item is not implementation authorization

**Current/target audit:** `docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`

Construction ERP is a Persian-first, multi-tenant construction SaaS. Models,
migrations, services, and tests remain the source of truth for current behavior.
This roadmap separates delivered capability, pre-production corrections, and
future target scope. Only a separately approved work package may be implemented.

## Authoritative planning references

- `docs/architecture/DOMAIN_MODEL.md`: target bounded contexts and ownership.
- `docs/architecture/DATA_MODEL.md`: target data/source-of-truth and lineage rules.
- `docs/architecture/BUSINESS_MODEL.md`: customers, value, packaging, operation and non-goals.
- `docs/architecture/USER_CAPABILITY_MAP.md`: user groups, goals and capability disposition.
- `docs/architecture/WORKFLOW_AND_PERMISSION_MATRIX.md`: lifecycle, permission,
  scope and separation policy.
- `docs/architecture/DOMAIN_AND_DATA_MODEL.md` plus code/migrations: current implementation.
- `docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`: evidence, gaps and readiness.
- `docs/ui-guidelines.md`: authoritative UI/UX interaction and accessibility standard.

Execution companion: `docs/ROADMAP_EXECUTION_PLAYBOOK.md` translates an approved
work package into resource-aware sessions and model/reasoning guidance; it does
not authorize implementation or override roadmap scope/status.

When these sources disagree, current code defines what exists; the target
documents define approved direction; this roadmap defines sequencing/disposition.

## Status and priority vocabulary

- **DELIVERED:** implemented and validated at its documented acceptance level;
  production certification is separate.
- **PARTIAL:** useful implementation exists but the target capability is not complete.
- **NEXT-CANDIDATE:** dependency-ready planning candidate, not approval.
- **PLANNED:** accepted product direction whose prerequisites are not complete.
- **DEFERRED:** intentionally postponed until a stated trigger.
- **MUST / SHOULD / DEFER:** pre-production correction priority.

Effort is relative: **S** (one bounded slice), **M** (several slices), **L**
(multi-domain program), **XL** (portfolio capability). Risk combines financial,
compliance, security, migration, and integration consequences.

## Delivered baseline — do not re-plan as missing

| ID | Status | Delivered boundary |
| --- | --- | --- |
| F1 Workforce | **DELIVERED** | Employees, departments, positions, teams, effective position/project assignments, optional `User` link, images, permission/audit/tenant checks. Attendance, time, payroll, skills, and rates are not delivered. |
| F2 Procurement | **DELIVERED expanding baseline** | Purchase request/order/goods receipt and the Product Owner-accepted P5-S01–S22 baseline are implemented. P5-S23–S25 add bounded Persian-first internal/external UI adapters over the portal and sealed-evidence services; broader portal collaboration, payable/GL/Treasury/Inventory activation remain deferred. |
| F3 Inventory | **DELIVERED baseline** | Warehouse and posted/reversible stock-quantity ledger. Valuation, reservations, bins/lots/serials, and accounting are not delivered. |
| F4 Equipment | **DELIVERED baseline** | Equipment, conflict-safe assignments, maintenance. Usage/fuel/cost/fixed-asset integration is not delivered. |
| F5 Workflow & Work Management | **DELIVERED** | Versioned definitions, bounded registries, runtime, candidate/assignment/delegation history, work items/workbench with due/overdue and escalation routing, position routing, domain adoption, PostgreSQL acceptance gates. |
| F6 Billing & Progress Claims | **DELIVERED receivable baseline** | Baseline/progress/claims/items/sources/adjustments, workflow, settlements and payment allocation. Policy ownership needs pre-production correction; payable claims and posting are not delivered. |
| F7 Documents v2 | **DELIVERED baseline** | Private versioned documents and explicit links to supported records. Retention/export/object storage/scanning and broader links are not delivered. |
| F8 Safety & Quality | **PARTIAL** | Incident and quality-issue lifecycles/workflow exist. Inspections, formal CAPA, risk, and knowledge integration remain. |
| Foundation | **DELIVERED baseline** | Tenant/session/membership/RBAC, shared masters, projects/sites/phases/WBS/activities, contracts/amendments, estimates/revisions, expenses, payments/allocations, daily reports, audit, financial read models. |

Historic validation detail belongs in `docs/PROJECT_STATUS.md`, not in this
forward roadmap.

## Mandatory delivery contract for every future work package

Every approved package must define and test:

1. owner aggregate and source of truth; tenant/project/site scope; lifecycle,
   finalization, revision/reversal, concurrency, and idempotency;
2. `BusinessPermissionCode`, permission registration and default-role data
   migration, service/view enforcement, object scope, separation of duties, and
   cross-tenant/cross-project negative tests;
3. `Decimal`, currency/unit/timezone/date behavior; effective dating and snapshot
   rules; organization-scoped uniqueness and database constraints;
4. integration producer/consumer contract, source reference/version, failure and
   retry behavior, reconciliation, audit, and KPI lineage;
5. Persian-first RTL UI, context-aware cascading choices, accessibility,
   responsive/site behavior, empty/loading/error/disabled states, and evidence;
6. legal/accounting review where relevant; annual/regulatory values are data,
   never constants;
7. expand -> migrate/backfill -> switch -> validate -> separately approved
   contract/removal when existing schema changes;
8. smallest relevant unit/integration tests followed by `manage.py check`, full
   PostgreSQL tests where risk demands it, Ruff, migration/rollback rehearsal,
   performance and security checks;
9. documentation updates limited to authoritative active documents; and
10. explicit rollout, observability, recovery, and operator ownership; and
11. a Build-vs-Reuse decision for generic technical capability: consider the
    Python standard library, Django/PostgreSQL built-ins, existing dependencies,
    then mature maintained libraries before justified custom code. Significant
    dependencies require security, maintenance, adoption, documentation,
    compatibility, SaaS-license, transitive-dependency, architecture-fit, and
    exit-risk review. Strategic construction-ERP rules remain product-owned.

## Dependency overview

```text
P0 Decisions + Security/Operations Foundations
 ├─> P0 Tenant Lifecycle + Existing-UI Remediation
 ├─> P1 Master/Data/Auth Corrections
 │    ├─> P2 Accounting Kernel ─> P3 Treasury + AP/AR
 │    │                          ├─> P4 Project Costing
 │    │                          ├─> P5 Source-to-Pay
 │    │                          └─> P7 Payroll/Insurance
 │    ├─> P6 Contract/Billing Expansion
 │    └─> P8 Inventory/Equipment/Fixed Assets
 ├─> P9 Field/HSE/Quality/DMS/Knowledge
 └─> P10 Production Certification

P3 + P4 + P5/P6/P7/P8 reconciliations -> governed BI/KPIs
Stable masters + consent/privacy + support operations -> future network/AI
```

## P0 — Pre-production decisions and operational foundation

### P0.1 Architecture decisions and correction plan

- **Status / priority:** **NEXT-CANDIDATE / MUST**
- **Planning progress (2026-09-25):** P0-S01–S03 evidence, decision preparation and
  [release-assumption clarification](docs/ROADMAP_EXECUTION_PLAYBOOK.md#28-p0-s03-release-assumptions-and-s04-handoff)
  are complete. P0-S04 prepared the
  [Accounting/posting and Treasury/AP/AR source-contract proposal](docs/architecture/ADR_P0_S04_ACCOUNTING_POSTING.md)
  with Payment containment, reversal/close and reconciliation walkthroughs;
  [S04 evidence and S05 handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#29-p0-s04-accounting-posting-adr-proposal-and-s05-handoff)
  record that bounded result. P0-S05 prepared the
  [budget/CBS/cost-center and project-cost authority proposal](docs/architecture/ADR_P0_S05_BUDGET_PROJECT_COST.md),
  including pinned estimate handoff, commitment/actual/paid distinctions and
  legacy Project-field containment; see the
  [S05 evidence and S06 handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#30-p0-s05-budget-and-project-cost-adr-proposal-and-s06-handoff).
  P0-S06 prepared the
  [regulatory rules, contract terms and tenant policy proposal](docs/architecture/ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md);
  [S06 evidence and S07 handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#31-p0-s06-regulatory-and-commercial-policy-adr-proposal-and-s07-handoff)
  record field ownership, version/snapshot rules and legacy behavior gaps.
  P0-S07 prepared the
  [project/site authorization and workflow-intersection proposal](docs/architecture/ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md);
  [S07 evidence and handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#32-p0-s07-projectsite-authorization-adr-proposal-and-handoff)
  record current privileged-path differences, proposed scope semantics and Q04 gates.
  P0-S08 prepared the
  [private document storage, upload safety and retention proposal](docs/architecture/ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md);
  [S08 evidence and S09 handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#33-p0-s08-private-document-storage-adr-proposal-and-s09-handoff)
  record quarantine/availability, hold/export, migration and recovery gates.
  P0-S09 prepared the
  [explicit DMS domain-link proposal](docs/architecture/ADR_P0_S09_DMS_DOMAIN_LINKS.md);
  [S09 evidence and S10 handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#34-p0-s09-dms-domain-link-adr-proposal-and-s10-handoff)
  record typed-link/registry alternatives, every-context access and lineage/cutover gates.
  P0-S10 prepared the
  [async/outbox and idempotency proposal](docs/architecture/ADR_P0_S10_ASYNC_OUTBOX_IDEMPOTENCY.md);
  [S10 evidence and S11 handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#35-p0-s10-asyncoutbox-adr-proposal-and-s11-handoff)
  record atomic intent, delivery/authority separation, uncertain outcomes and recovery gates.
  P0-S11 prepared the
  [tenant lifecycle, entitlements, quotas, offboarding and support-access proposal](docs/architecture/ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md);
  [S11 evidence and S12 handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#36-p0-s11-tenant-lifecycle-adr-proposal-and-s12-handoff)
  record current access restrictions, capacity/retention boundaries and unresolved authority.
  P0-S12 prepared the
  [future-network privacy, consent and shared-data proposal](docs/architecture/ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md);
  [S12 evidence and bounded handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#37-p0-s12-future-network-privacy-adr-proposal-and-handoff)
  keep tenant data private by default and define separate publication, revocation,
  provenance, isolation, retention and acceptance boundaries without activating
  the deferred network. All nine ADRs remain PROPOSED, not accepted or implemented.
  The Product Owner accepted the S02 recommendations; D03–D05 parameters and S03
  release questions remain open. S07 preparation and P0-G02 remediation are complete;
  P1.1 has been implemented under the bounded Product Owner authorization; its
  acceptance evidence is recorded with the P1.1 closeout, while P0 remains
  incomplete and no later P1 package is implied.
  S08 preparation is complete; D03-D05/Q03 storage gates remain open, while Q04
  design constraints are recorded for any future storage implementation.
  S09 preparation is complete; PPC-10/P1.3 remain incomplete and Q03 plus the
  relevant Q04 design constraints remain applicable.
  S10 preparation is complete; async delivery and affected packages remain unimplemented by this session.
  S11 preparation is complete; P0.3 remains PLANNED and D03-D05/Q03 plus the
  relevant Q04 design constraints remain applicable.
  S12 preparation is complete; the controlled B2B network remains deferred and its
  consent, identity, legal/commercial, moderation, privacy/competition and operating decisions remain open.
  P0-S13 prepared the consolidated
  [P0.1 ADR review and decision packet](docs/architecture/P0_S13_P01_ADR_REVIEW_PACKET.md);
  [S13 evidence and handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#38-p0-s13-p01-adr-review-packet-and-handoff)
  find the proposals conditionally coherent, group their shared blockers and retain
  every disposition/owner assignment as OPEN. All nine ADRs remain PROPOSED. The
  next bounded handoff is explicit Product Owner dispositions and named reviewers,
  with Q04 recommended first if review is incremental; no implementation session
  is inferred. P0-S14 prepared the bounded
  [Q04 Product Owner decision packet](docs/architecture/P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md);
  [S14 evidence and handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#39-p0-s14-q04-product-owner-decision-packet-and-handoff)
  compare eight explicit choices for project/site grants, inheritance/delegation,
  privileged/support access, maker-checker separation and workflow fallback. All
  choice, rationale, reviewer-name and review-evidence fields initially OPEN.
  P0-S15 recorded the Product Owner's A1/B1/C1/D1/E1, revised F2, final
  G3 — Revised with Protected Operations, and H1
  selections in that packet and reconciled the affected proposals and policy
  references. Revised F2 adds a separately controlled emergency path when tenant
  approval is practically impossible. The final **G3 — Revised with Protected
  Operations** explicitly revises original G1 and replaces every earlier Q04-G
  response: Protected Operations never allow Self-Approval and Tenant configuration
  cannot override that restriction, while other business operations may use auditable
  platform- and tenant-level configuration. The original G1 recommendation remains
  intentionally rejected. Reviewer
  names and review evidence remain OPEN, all ADRs remain PROPOSED, current behavior
  is unchanged, and no implementation is authorized. See the
  [S15 record and handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#40-p0-s15-q04-decision-recording-and-review-handoff).
  The [final Q04-G decision record](docs/ROADMAP_EXECUTION_PLAYBOOK.md#41-final-q04-g-product-owner-decision-and-handoff)
  supersedes only the earlier G3 wording and preserves all other Q04 decisions.
  Directly affected authorization documentation now uses the authoritative role
  vocabulary: independent Superuser and Platform Admin roles at platform level,
  and independent Tenant Owner, Tenant Admin / Local Admin and Tenant Manager roles
  at Tenant level. Multiple roles require explicit assignment and never imply one
  another. The authoritative target now also requires Tenant-membership-scoped
  many-to-many role assignments: one Membership may hold several independent roles,
  the same User may have different role sets in different Tenants, and role-derived
  permissions are unioned before intersection with all remaining authorization
  factors. Current single-role membership behavior remains unchanged. This is
  documentation normalization, not role implementation. See the
  [multi-role rule record](docs/ROADMAP_EXECUTION_PLAYBOOK.md#43-membership-scoped-multi-role-authorization-rule).
  P0-S16 then recorded the explicitly supplied accountable-review status: the
  Q04-A through Q04-H Product Owner decisions remain recorded, but no accountable
  review is complete. Reviewer names, outcomes, evidence/version and review dates,
  unresolved objections and resulting reviewer-feedback revisions all remain
  OPEN. The [per-item responsibility register](docs/architecture/P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#3-accountable-review-requirements)
  identifies the still-required reviewer responsibilities; the
  [S16 record and handoff](docs/ROADMAP_EXECUTION_PLAYBOOK.md#44-p0-s16-q04-accountable-review-pending-record)
  closes no gate, accepts no ADR and authorizes no implementation.
  P0-S17 records only the Product Owner-supplied assignments of Azam Zerangzadeh
  as Security / Authorization Reviewer for Q04-A/B/C/D/E/F/H, Workflow / Control
  Reviewer for Q04-C/G/H, Accounting / Control Reviewer for Q04-G, and Operations /
  Privacy Reviewer for Q04-E/F. All unassigned reviewer responsibilities, review
  outcomes, evidence/version, dates, unresolved objections and resulting revisions
  remain OPEN. The [S17 record](docs/ROADMAP_EXECUTION_PLAYBOOK.md#45-p0-s17-q04-reviewer-assignment-record)
  records no review or approval, closes no gate, accepts no ADR and authorizes no
  implementation.
  P0-S18 records the explicit Product Owner decision that Azam Zerangzadeh is the
  final accountable reviewer for every required responsibility across Q04-A through
  Q04-H and explicitly overrides the packet's reviewer-independence expectation
  where applicable. The [S18 record](docs/ROADMAP_EXECUTION_PLAYBOOK.md#46-p0-s18-q04-final-accountable-reviewer-and-independence-override)
  preserves the conflict and concentration risk without replacing or rejecting the
  decision. All review outcomes/evidence remain OPEN; no ADR is accepted and no
  implementation is authorized.
  P0-S19 records the P0-S18 handoff without adding an inferred review: for every
  Q04-A through Q04-H responsibility, review outcome, evidence/version, review
  date, unresolved objection and resulting revision remain OPEN. Azam Zerangzadeh
  remains the final accountable reviewer under the recorded Product Owner
  independence override; the concentration and external-independence risks remain
  explicit. The [S19 record](docs/ROADMAP_EXECUTION_PLAYBOOK.md#47-p0-s19-q04-review-outcome-recording-from-s18-handoff)
  accepts no ADR and authorizes no implementation.
  P0-S21 then performed the documentation-only
  [P0 readiness and unresolved-risk review](docs/architecture/P0_S21_READINESS_AND_UNRESOLVED_RISK_REVIEW.md).
  At that historical review, Q04 selection/assignment records and the D03-D05
  directional records were narrow completed decisions while every Q04 accountable
  review and every S04-S12 ADR disposition remained OPEN. Later P1-S14 governance
  accepts S04-S06 as target architecture only; the historical P0-S21 finding did
  not authorize implementation, and P0 remains incomplete.
  P0-S22 completed the documentation-only
  [P0 closeout and conditional P1 handoff](docs/architecture/P0_S22_DOCUMENTATION_CLOSEOUT_AND_P1_HANDOFF.md).
  The packet carries the unresolved decision/evidence queue forward and explicitly
  blocks P0 phase exit and P1 entry; it does not change any gate or authorize
  implementation.
  P0-G01 then completed the bounded documentation-only
  [Q04 accountable review](docs/architecture/P0_G01_Q04_ACCOUNTABLE_REVIEW_EVIDENCE_MATRIX.md#3-p0-g01-accountable-review-findings): A/B/F are accepted with conditions and
  C/D/E/G/H require revision. The findings retain every implementation,
  compliance and independence condition, accept no ADR and authorize neither P1
  nor a runtime change.
  P0-G02 reconciled those findings into the complete
  [S07 P1.1 implementation contract](docs/architecture/ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#6-p0-g02-remediation-and-complete-p11-implementation-contract).
  The P1.1 foundation is **IMPLEMENTED** under its bounded authorization. D03-D05/Q03,
  P0.2/P0.3/P0.4 and unrelated ADR dispositions remain gates only for their directly
  governed packages or release/enablement behavior. P0 as a whole remains incomplete.
  The release contract is not frozen and P0/P0.1 are not complete.
- **Outcome and rationale:** decide authoritative boundaries before real financial,
  payroll, document, and tenant history makes change expensive.
- **Prerequisites:** repository audit accepted; initial customer segment and
  native-vs-external accounting boundary decided by product owner.
- **Scope:** ADRs for Accounting/posting, Treasury/AP/AR, budget/CBS/cost center,
  regulatory configuration/contract terms, project authorization, storage/DMS,
  async/outbox, tenant lifecycle/support access, and future network privacy.
- **Data/migration:** inventory affected fields and compatibility bridges;
  migrations remain history. Any squash/reset is a separate decision before the
  first tenant and is not assumed.
- **Integration/accounting/compliance:** specify source/version/idempotency and
  reconciliation before downstream code.
- **Security/UI:** threat-model object scope and support access; define visible
  context and denied/disabled behavior.
- **Validation:** ADR review against code, sample posting/lineage walkthroughs,
  regulatory/accounting professional review plan.
- **Effort / risk:** **M / Critical**.

### P0.2 Reproducible delivery, security, and recovery baseline

- **Status / priority:** **NEXT-CANDIDATE / MUST**
- **Outcome:** CI, dependency lock/hashes/SBOM and vulnerability policy; MFA for
  privileged users; secure private object storage decision; secrets/key policy;
  structured correlation-aware logging, metrics/error tracking and alerting;
  backups and proven restore; migration/rollback deployment runbook; retention,
  export, incident and support-access operations.
- **Prerequisites:** P0.1 hosting/data-residency and RPO/RTO decisions.
- **Decision state:** D03/D04 managed-service and shared-recovery directions are
  approved; residency/provider/operator and numeric RPO/RTO remain open. These
  unresolved parameters still gate implementation and service commitments.
- **P0-S21 readiness:** **OPEN.** D03/D04 parameter gates and separate package
  authorization are absent; no implementation, restore, deployment or operational
  acceptance evidence is inferred from the completed directional decisions.
- **Libraries to evaluate:** `django-allauth`, `django-storages`, `pip-audit`,
  `sentry-sdk` or equivalent, stable OpenTelemetry components. No package is pre-approved.
- **Data/migration:** production storage migration and backup compatibility plan;
  no movement until integrity checks and rollback exist.
- **UI/security:** MFA/recovery/session screens, export/job state, time-limited
  support grant and audit; prevent PII/secrets in telemetry.
- **Validation:** immutable build, clean-environment install, dependency and
  license gates, restore exercise, deployment rehearsal, security review,
  representative load budgets.
- **Effort / risk:** **L / Critical**.

  **2026-09-28 Product Owner operational decision:** Platform Admin assignment
  requires one active Superuser and an auditable reason; the assigning Superuser
  must remain distinct from the target. This does not alter the separate Platform
  Admin/Superuser boundary or create ordinary Tenant-data/support access.

  **2026-09-28 Product Owner Protected Operations decision:** an active Platform
  Admin owns the platform catalogue lifecycle and may create versions or retire a
  current classification alone with an auditable reason. Catalogue ownership does
  not itself grant Tenant-data access or permit a protected business action.

  **2026-09-28 Product Owner role-catalog decision:** Platform Admin manages
  global-custom, tenant-custom and system-role presentation/permission bindings;
  Tenant Admin manages only custom roles of its active Tenant. System roles remain
  non-archivable; custom roles are archived with retained assignment/history and
  audit evidence. Permission codes remain code-and-migration owned.

### P0.3 SaaS plans, entitlements, quotas, and tenant offboarding

- **Status / priority:** **PLANNED / MUST before commercial SaaS launch**
- **Outcome:** versioned plan/feature entitlements; user/project/storage and other
  justified quotas; usage visibility; controlled grace/suspension/cancellation;
  tenant export, retention, legal hold, and offboarding evidence. Initial SaaS
  subscription invoicing is administered externally under accepted P0-D05;
  an in-product subscription billing engine is not part of that initial policy.
- **Policy decision:** one core plan with versioned entitlements and justified
  capacity limits, warnings and protection of existing authorized work/history/export
  is approved. Exact limits, commercial and lifecycle parameters remain open under
  P0-D05 and must be resolved before policy implementation.
- **Prerequisites:** P0.1 tenant-lifecycle/support-access ADR, P0.2 storage/export
  operations, and product-owner packaging/limit decisions.
- **ADR preparation (2026-09-25):** [S11 proposal](docs/architecture/ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md)
  is prepared, not accepted. Current active-tenant access remains unchanged; the
  controlled inactive-tenant export path, quota definitions, lifecycle parameters,
  support/privileged decisions and background-operation authority remain gated.
  No P0.3 implementation or prerequisite completion is implied.
- **P0-S21 readiness:** **OPEN.** S11 remains PROPOSED, P0.2 storage/export
  operations are not accepted, D05 exact capacity/commercial/lifecycle parameters
  remain open and no P0.3 package authorization is recorded.
- **Ownership/integration:** Organizations owns entitlement state; every consuming
  domain enforces it server-side. Identity, storage, projects, jobs, export,
  support and audit consume the same authority rather than local feature flags.
- **UI/security:** plan/usage/limit explanation, safe upgrade/contact path, export
  readiness and cancellation consequences; suspension never weakens retention,
  audit, security or owner access needed for lawful export/offboarding.
- **Migration/testing:** default existing development tenants explicitly; test
  quota races, suspended mutations, cancellation/export/retention, tenant
  isolation and entitlement changes without deleting business history.
- **Effort / risk:** **L / Critical**.

### P0.4 Existing UI consistency and accessibility remediation

- **Status / priority:** **ASSESSED; REMEDIATION DEFERRED / SHOULD; release gate for selected screens**
- **P0-S20 assessment (2026-09-26):** the
  [workbench UI/accessibility assessment](docs/architecture/P0_S20_UI_ACCESSIBILITY_ASSESSMENT.md)
  selects the centralized personal workbench as the first future remediation
  journey, but defers actual UI changes until the relevant multi-role,
  Tenant-role separation, project/site scope, Q04-G and Q04-H server semantics are
  accepted and implemented. Semantic-neutral accessibility improvements are
  recorded as a safe backlog, not implemented by this session. Q04 review fields
  remain OPEN, S07 remains PROPOSED and no implementation is authorized.
- **P0-S21 readiness:** the S20 assessment/deferral decision is **VERIFIED
  CLOSED**, but authorization-dependent prerequisites, actual remediation and all
  browser/device/keyboard, RTL/Jalali/unit, component and permission-safe
  acceptance evidence remain **OPEN**.
- **Outcome:** inventory already delivered screens against `docs/ui-guidelines.md`
  and remediate by reusable pattern: tenant/project/site context, cascading and
  searchable choices, list/filter/table consistency, workflow/cartable actions,
  responsive/mobile behavior, disabled/error/empty/loading states, financial
  labels, keyboard/focus/accessibility, and source/audit visibility.
- **Prerequisites:** authoritative UI guidelines; coordinate context/permission
  behavior with P1.1. Remediation may proceed incrementally by user journey.
- **Boundary:** prioritize correctness, task completion, error prevention and
  accessibility. Do not cosmetically rewrite working screens, fork page-local
  components, or change backend behavior under a presentation task.
- **Validation:** representative browser/device and keyboard review, RTL/LTR and
  Jalali/Rial-Toman checks, template/component tests, permission-safe states and
  visual regression evidence where a maintained approach is justified.
- **Migration/integration:** no data migration by default; backend gaps discovered
  during review become separately approved domain work rather than hidden UI fixes.
- **Effort / risk:** **L incremental / Medium-High**.

## P1 — Authoritative masters, configuration, and authorization

### P1.1 Project/site object-scope authorization

- **Status / priority:** **CLOSED / MUST — acceptance criteria verified 2026-09-28**
- **Authority and contract:** P0-G01/P0-G02 findings were reconciled into the S07
  contract and separately authorized for P1.1. P1.1 implements only that bounded
  contract; it neither accepts the ADR nor completes P0 as a whole.
- **Boundary against unrelated P0 gates:** D03-D05/Q03, P0.2/P0.3/P0.4 and
  unrelated ADR dispositions do not block P1.1 coding unless the authorized slice
  enables their support/emergency, storage/export, quota/lifecycle, UI or
  financial/regulatory behavior.
- **Outcome:** permissions are the intersection of active tenant membership,
  the union of permissions from all active applicable membership-scoped role
  assignments, explicit grants, object scope, tenant status, delegation, policy,
  and—only for workflow actions—assignment/candidacy. Positions continue to route,
  never grant; common role combinations never become composite roles.
- **Prerequisites:** P0.1 scope ADR and target role vocabulary.
- **Models/services:** independent auditable Membership-role assignments (a
  Tenant-preserving many-to-many relation), effective project/site grants or
  restricted assignments, scope selectors, service checks, queryset helpers,
  role/grant history; preserve the
  independent Tenant Owner/Tenant Admin/Tenant Manager and Platform Admin/
  Superuser boundaries in ordinary and emergency/support access.
- **Integration:** every domain and workbench; payroll/finance scopes are stricter.
- **UI/security:** explicit tenant/project/site context, safe empty results,
  no unauthorized option leakage; UI visibility is never authorization.
- **Migration/testing:** expand and backfill the current single-role Membership
  compatibility fields without inventing composite roles or cross-Tenant carryover;
  backfill unrestricted scope only by explicit policy; test independent role
  add/remove, permission union, audit evidence and different per-Tenant role sets,
  plus exhaustive cross-tenant/cross-project and query/performance review.
- **Closeout evidence (2026-09-28):** organizations migrations `0030`–`0035`
  and audit migration `0030` now cover authorization foundation, restrictive
  backfill, single-Superuser Platform Admin assignment compatibility, Protected
  Operations lifecycle, role-catalog lifecycle, active `admin` bootstrap and a
  lossy-rollback guard. Focused service/route tests verify Platform Admin and
  Tenant Admin boundaries, system-role non-archival, active permission-catalog
  bindings, exact-Tenant role assignment, archival/history retention and
  before/after audit evidence. Persian-first RTL role-catalog and Protected
  Operations screens are available from the platform journey. No P1.2 scope is
  implemented by this closeout.
- **Effort / risk:** **L / Critical**.

### P1.2 Configuration and master-governance corrections

- **Status / priority:** **P1-S14 THROUGH P1-S18 COMPLETE / MUST+SHOULD**
- **P1-S14 entry-gate result (2026-09-28):** the Product Owner supplied explicit
  bounded package authorization and the P1.1 authorization foundation is present,
  and the later Product Owner disposition accepted
  S04-S06 as target architecture and closed the Q01 product choices plus Q02
  filing/source-hierarchy choices. The final 2026-09-29 Product Owner decision
  removed mandatory professional-review authority and D14-11 as global development
  gates while retaining source/version requirements for affected activation. The
  pre-implementation compatibility inventory confirmed duplicate
  `Organization.timezone`/`currency` and `OrganizationSettings.timezone`/`currency`,
  service dual-write/read-repair and direct legacy timezone consumers. The later
  P1-S14A split authorized correction of those regulatory-independent paths;
  final closeout below supersedes the former P1-S14B global block.
- **Accepted P1-S14 configuration-ownership decision (2026-09-28):**
  `OrganizationSettings` is the single authoritative owner of every
  organization-level configurable setting, including timezone, currency, fiscal
  settings, locale and numbering schemes. `Organization` owns only Tenant identity
  and core organization-domain attributes. Its duplicate timezone/currency fields
  are temporary compatibility fields: a later authorized implementation must use
  expand -> migrate/backfill -> switch -> validate and a separately controlled
  contract step to remove legacy reads/writes and fields. This decision records
  ownership only; this governance session changes no schema, data or runtime path
  and supplies no Q01/Q02 value or legal/accounting rule.
- **P1-S14 decision record (2026-09-28):** the
  [P1-S14 decision packet](docs/architecture/P1_S14_REMAINING_DECISION_PACKET.md)
  records D14-01 through D14-09 Product Owner dispositions. Revised D14-10 makes
  professional evidence optional metadata rather than a role/gate; revised D14-11
  is closed as a global development gate. S04-S06 remain accepted target
  architecture; this grants no statutory rate, Chart of Accounts, filing behavior
  or regulated-value authority.
- **P1-S14 split and P1-S14A closeout (2026-09-28):** the Product Owner split the
  package into executable **P1-S14A — Configuration Authority** and blocked
  **P1-S14B — Regulatory/Accounting Validation**. Organizations migration `0036`
  establishes the IRR-only current base-currency guard and fail-closed backfill;
  authoritative reads no longer repair from legacy fields, settings updates no
  longer dual-write `Organization.timezone`/`currency`, and audit evidence records
  before/after values plus changed fields. Equipment, Safety and Quality workflow
  deadlines now consume `OrganizationSettings.timezone`; Tenant creation writes
  configuration only to `OrganizationSettings`. Legacy fields remain physically
  present and inert pending a separately authorized contract stage. Targeted 30
  tests, Django checks/migration-state validation and Ruff passed. No tax/VAT,
  filing, unverified precision/rounding, valuation or other regulated behavior was
  activated. P1-S14A completion does not complete P1-S14 or authorize P1-S15.
- **Historical P1-S14B execution gate recheck (2026-09-29):** bounded execution authority was
  present, but the repository still contains no actual official source versions,
  named qualified independent reviewer evidence, completed professional review of
  the affected baseline/precision facts, or D14-11 disposition. The gate therefore
  failed before implementation; no code, schema, migration or runtime behavior was
  changed. The later final Product Owner decision supersedes only its global
  reviewer/D14-11 blocking semantics; the missing source facts remain absent.
- **Source/evidence register (2026-09-29):** the
  [source and optional-review register](docs/architecture/P1_S14B_PROFESSIONAL_EVIDENCE_REGISTER.md)
  preserves provenance and optional professional-validation metadata. A missing
  source fails closed only where the affected policy explicitly requires one;
  optional review is not an ERP actor or global stage gate.
- **P1-S14 final closeout (2026-09-29):** `OrganizationSettings` remains the sole
  direct Tenant-settings authority. The accepted configuration flow is external
  source -> versioned Platform policy/localization catalogue -> Tenant Owner
  selection -> authorized Tenant configuration/runtime use. Platform Admin owns
  Platform/localization structures and values, while Tenant Owner/Tenant Admin may
  decide or maintain field-specific Tenant values within RBAC boundaries. Unknown
  required regulated/accounting values remain unset/inactive and no rule,
  filing, valuation, precision or rounding fact was invented. P1-S14 is complete;
  legacy Organization columns remain for a separately controlled contract stage.
- **P1-S15 closeout (2026-09-29):** migration `organizations.0037` adds immutable
  source provenance, Platform policy definitions/versions, optional professional
  evidence and Tenant selections. Services enforce Platform Admin catalogue
  authority, Tenant Owner approval, Tenant Admin application, active Tenant and
  membership checks, dedicated permissions, audit evidence, effective dates,
  non-overlap, explicit per-policy source requirements and fail-closed resolution.
  Direct Tenant operational values remain in `OrganizationSettings`; future
  field-specific Tenant parameters may be authorized, but unrestricted parameter
  bags and executable formulas are prohibited. Fourteen targeted
  policy/permission-registry tests (plus 11
  subtests) passed; no regulated value or consumer activation,
  `BillingPolicy` switch, autonomous filing, BusinessParty governance or P1-S16
  work is included.
- **Accounting-policy foundation supplement (2026-10-01):** migrations
  `organizations.0056`/`0057` and `accounting.0010` narrow
  `accounting-money-precision` and
  `accounting-rounding` to a closed code-owned catalogue. Their versions accept
  only an approved policy-specific schema, and accounting submission validates the
  exact code and consumer contract before preserving both applied version links on
  the journal. Published versions and their append-only source links are immutable;
  retirement/supersession cannot reinterpret historical journals. Platform Admin
  may initialize the two definitions, while Tenant Admin may select/apply an
  already-valid published version under existing permissions; neither UI exposes
  arbitrary policy JSON, publication nor activation while the Product Owner has
  supplied no financial values. Consequently every accounting post remains
  fail-closed. Source provenance is required only for external-authority claims;
  every lifecycle action retains actor, reason, time and before/after evidence.
  **Activation execution (2026-09-30):** Product Owner then selected Product-defined
  IRR money scale `0`, intermediate calculation scale `6`, `ROUND_HALF_UP` and
  final-monetary-line-only rounding/tie behavior. Both v1 policy versions were
  published with audited Product Owner rationale and effective date `2026-12-22`,
  derived as the next open-period start for `demo-construction-01`; no external
  authority is claimed. Future Tenant selection is unsupported, so neither policy
  is selected/applied before that date and posting remains fail-closed. The exact
  closed values, deterministic boundary utility, manual/opening final-line
  validation and historical version-pin checks are implemented without FX, tax,
  valuation or an operational producer. تصمیم‌ها و TINF-01 در
  [بسته تصمیم فعال‌سازی سیاست‌های حسابداری](docs/architecture/P2_ACCOUNTING_POLICY_ACTIVATION_DECISION_PACKET.md)
  ثبت شده‌اند.
- **P1-S16 execution contract (2026-09-29):** the Product Owner authorized the
  smallest coherent generic `BusinessParty` foundation. The slice owns
  Tenant-local canonical identity and normalized duplicate candidates without
  silent merge; preservation of original/current identity evidence; explicit,
  permission-controlled merge lineage whose survivor is canonical and whose
  historical foreign keys are not rewritten; and generic Tenant/Platform-scoped,
  effective-dated restrictions plus a reusable explicit transaction guard.
  Platform restriction imposition must not create Platform Admin access to Tenant
  business data; that write path is deferred while the schema/enforcement contract
  prevents Tenant actors from weakening Platform restrictions. P1-S16 adds no
  regulated meaning or consumer activation. Tax/insurance rules, accounting,
  regulatory consumers, qualification, bank/legal profiles, speculative workflow,
  destructive deduplication and P1-S17+ are excluded. Acceptance requires
  deterministic canonicalization, non-destructive duplicate/merge behavior,
  immutable identity/merge traceability, scoped restriction precedence, dedicated
  RBAC and audit, negative Tenant tests, fail-closed migration collision handling,
  and S15 regression coverage.
- **P1-S16 closeout (2026-09-29):** migrations `organizations.0038`, `audit.0031`
  and `parties.0003` deliver dedicated merge/restriction permissions and default
  grants, audit actions, deterministic Unicode-aware match keys, fail-closed
  identifier backfill, append-only identity snapshots, non-destructive direct
  merge lineage and generic effective-dated Tenant/Platform restriction records.
  Services provide explainable Tenant-local duplicate candidates, canonical-party
  resolution, locked/audited merge recording, Tenant restriction create/revoke
  and an explicit transaction guard. Merge never rewrites historical foreign keys;
  Tenant services cannot revoke Platform restrictions. The Platform restriction
  imposition path and all consuming-domain activation remain deferred so Platform
  Admin gains no Tenant business-data access. Eight P1-S16 tests and twelve
  existing party/P1-S15 regression tests passed, as did Django system/migration
  checks and targeted Ruff. No regulated value, rule, filing, tax/insurance,
  accounting, qualification/profile or P1-S17+ behavior was introduced.
- **P1-S17 entry-gate result (2026-09-29):** **NOT SATISFIED; no implementation
  started.** The Product Owner explicitly authorized P1-S17 only, and the completed
  P1-S14 through P1-S16 foundations and dirty-worktree boundary were verified.
  However, neither this roadmap nor the execution playbook defines a standalone
  P1-S17 goal, assigns the combined P1-S17..S18 outcomes between the two sessions,
  or supplies P1-S17 decisions, exclusions and acceptance criteria. The combined
  P1.2 outcome mixes categories/tags, representative/signatory evidence,
  regulated and bank/legal/qualification profiles, qualification lifecycle,
  restriction/violation history and consuming-domain enforcement with regulatory
  rule/contract-term versioning. Choosing any subset would invent scope and could
  activate expressly deferred regulated or restriction behavior. Before P1-S17
  can execute, the Product Owner must approve its exact bounded allocation and
  acceptance criteria, including which party records/lifecycles (if any) belong to
  S17 and confirmation that Platform restriction imposition, consuming-domain
  enforcement, regulated values/profiles, accounting, workflow and destructive
  deduplication remain deferred unless expressly included with their own satisfied
  gates. P1-S18 and later work remains unauthorized and not started.
- **P1-S17 derived contract and closeout (2026-09-29):** the Product Owner later
  authorized autonomous derivation of the smallest coherent contracts for all
  remaining P1 stages, superseding only the missing-contract blocker above.
  P1-S17 owns generic, non-regulated party governance: immutable normalized aliases
  with Tenant-local resolution through preserved merge lineage; Tenant category/tag
  vocabularies with non-destructive assignment/revocation history; and effective-
  dated representative/signatory evidence with explicit evidence reference and
  revocation history. Migrations `organizations.0039`, `audit.0032` and
  `parties.0004` add dedicated RBAC/default grants, audit actions, models,
  constraints and indexes. Five focused tests and eight S16 regression tests pass;
  migration-state and targeted Ruff checks pass. Bank, tax, insurance, legal and
  qualification profiles, Platform restriction imposition, consuming-domain
  enforcement, workflow and destructive deduplication remain deferred.
- **P1-S18 reconciliation and closeout (2026-09-29):** the smallest coherent
  regulatory-version contract is already implemented by P1-S15 and is not
  duplicated: `PolicySource`, `PlatformPolicy`, immutable-after-publication
  `PlatformPolicyVersion`, optional review evidence and explicit Tenant selection
  provide source/version/effective-date/supersession lineage, controlled declarative
  parameters, non-overlap and fail-closed resolution. The accepted architecture
  assigns actual contract commercial terms to Contracts and resolved calculation
  snapshots to consuming domains, so inventing parallel models in P1-S18 would
  violate ownership. Seven focused S15/S18 tests pass. No actual regulated value,
  applicability rule, calculator, filing, `BillingPolicy` switch, Tenant activation
  or consuming-domain behavior was added. Those remain gated by source facts and
  their later owning packages.
- **Outcome:** one owner for organization timezone/currency/fiscal settings;
  effective-dated approved regulatory rule sets; versioned contract commercial
  terms; governed UOM conversions; canonical roles and separation-of-duties
  policy. `BusinessParty` remains the single counterparty master and gains
  tenant-scoped duplicate detection/canonicalization, controlled merge with
  alias/identifier/history preservation, categories/tags, authorized
  representative/signatory evidence, tax/bank/legal/qualification profiles,
  qualification state, restriction/blacklist and violation history, enforced
  transaction restrictions, and inactive/archive lifecycle. Regulatory scope explicitly
  includes annual VAT/tax, taxpayer-invoice schema, payroll-tax, monthly employee
  insurance, contractor-insurance/clearance parameters, calendars and rounding;
  every unverified rule remains **«نیازمند بررسی قانونی»**.
- **Prerequisites:** P0.1 and applicable legal/accounting source records remain
  required for affected regulated/accounting activation and later P1.2 slices;
  the separately authorized P1-S15 technical foundation does not validate values.
- **Models:** `RegulatoryRuleSet`/version (final naming by design), contract term
  versions, party profile/representative/alias/merge/restriction evidence, UOM
  conversions, effective grants. Split the current `BillingPolicy` into its
  correct owners; do not create supplier/customer/subcontractor masters beside
  `BusinessParty`.
- **Integration:** Billing, Payroll, taxpayer invoices, Treasury, Procurement,
  Inventory, reporting; historical documents store applied versions/snapshots.
- **UI:** effective date, provenance, reviewer, impact preview, dual control,
  unambiguous Rial-only monetary display and Jalali presentation over canonical
  UTC/ISO-compatible persistence; explain duplicate/merge and
  restriction decisions, including transaction-block reason and retained history.
- **Migration/testing:** pre-production data may be discarded/backfilled if that
  is safer, but migrations remain; golden calculations by rule version and
  cross-tenant validation. Test merge lineage, alias resolution, representative
  validity, inactive/archive selection and restriction enforcement without
  rewriting historical transactions.
- **Effort / risk:** **L / Critical**.

### P1.3 DMS and audit extensibility

- **Status / priority:** **P1-S19..S22 COMPLETE / SHOULD**
- **Entry-gate result (2026-09-29):** **NOT SATISFIED; no P1.3 implementation
  started.** S08 private-storage and S09 domain-link ADRs remain explicitly
  `PROPOSED`, with acceptance/implementation pending. Q03 retention, hold,
  disposal, export and signature/evidence decisions remain open; D03-D05 provider,
  location, operator, recovery and quota inputs are also unresolved. These are
  direct data-ownership, access, lifecycle and migration dependencies—not optional
  implementation detail. Numbering/classification cannot be safely released as an
  isolated P1-S19 completion because the roadmap acceptance outcome also requires
  confidentiality/access expiry and the approved document authority; doing so
  would establish a competing partial governance contract. Existing immutable
  versions, hashes, six typed links and all-linked-context permission checks remain
  unchanged. S19-S22 are not partially marked complete.
- **Product Owner decision packet (2026-09-29):**
  [P1-S19–S22 decision packet](docs/architecture/P1_S19_S22_PRODUCT_OWNER_DECISION_PACKET.md)
  records the minimum S08/S09, Q03 and D03-D05 dispositions required to unblock
  implementation, with recommended defaults and explicitly deferrable parameters.
  Preparing the packet changes no runtime behavior and does not itself accept an
  ADR or authorize S19-S22 implementation.
- **Decision disposition (2026-09-29):** the Product Owner accepted S08/S09 and
  supplied `D19-01..D19-10` as recorded in the decision packet. The selected P1
  boundary uses protected filesystem storage behind an adapter without a
  production-readiness claim; unscanned/unknown content is unavailable; typed
  links are append-only and all retained links govern access; Tenant retention,
  hold, export and non-destructive disposal intent use dedicated permissions;
  storage/recovery, key custody and restore-evidence approval are separated
  Platform duties. Every named deferral remains open without an invented value.
- **P1-S19 closeout (2026-09-30):** documents migration `0005`, organizations
  migration `0040` and audit migration `0033` add immutable Tenant-sequenced
  document numbers, descriptive Tenant categories, closed `internal` /
  `confidential` / `restricted` levels and access expiry. Existing versions and
  links are preserved; expired access fails closed.
- **P1-S20 closeout (2026-09-30):** domain migrations in Projects `0005`,
  Contracts/Estimates/Expenses/Daily Reports `0004` and Payments `0006`, plus
  documents migration `0006`, establish domain-owned typed links and deterministic
  six-type backfill preserving UUID/actor/time lineage. The closed registry is the
  authorization/query authority; compatibility rows remain dual-written for
  presentation and rollback. Missing parity fails closed; mutation, removal and
  access-releasing correction remain absent.
- **P1-S21 closeout (2026-09-30):** organizations migration `0041`, audit
  migration `0034` and documents migration `0007` add separated Platform duties,
  audit correlation/change metadata, protected-filesystem storage abstraction,
  append-only scan/OCR assessments, fail-closed availability, PostgreSQL
  permission-scoped search, version comparison and provider-neutral signature
  evidence. No real scanner/OCR/signature provider or async transport is claimed.
- **P1-S22 closeout (2026-09-30):** organizations migrations `0042`/`0043` and
  documents migration `0008` add versioned Tenant retention policy/application,
  protected legal-hold release and disposal-intent review, manifest-only export,
  separated key/recovery/restore evidence and byte accounting for originals,
  quarantine, derivatives and export bundles. Unknown duration and active hold
  block disposal; no destructive executor exists. Recovery evidence unifies DB,
  blobs, policy/hold/audit and key custody without numeric RPO/RTO or production
  readiness. Seventeen focused/regression document tests pass with Django checks,
  migration-state validation and targeted Ruff.
- **Outcome:** explicit scalable domain links; governed document numbering,
  classification and confidentiality; access expiry; retention/legal hold/export;
  upload security pipeline; OCR and permission-scoped full-text search; versioning
  and version comparison; electronic/digital-signature integration boundary;
  audit correlation/change metadata; and immutable processing provenance.
- **Prerequisites:** P0.1 storage/link ADR and P0.2 private storage.
- **Models/integration:** domain-owned explicit link tables or approved registry;
  do not use `GenericForeignKey`. Reuse the version/blob authority for drawings,
  inspection documents and media rather than create parallel file stores. Audit
  remains evidence, not notification bus. Signature trust/legal effect and
  provider choice require an explicit decision; do not implement cryptography.
- **UI:** document workspace, upload/scan/OCR/signature state, searchable content,
  version compare, source/audit visibility, retention/hold/export controls.
- **Testing/migration:** preserve document hashes and versions; link parity,
  permission and search isolation, download, retention/hold/export, OCR failure,
  signature verification-state and malware-failure tests.
- **Effort / risk:** **M-L / High**.

### P1.4 Material catalogue and UOM governance

- **Status / priority:** **P1-S23 through P1-S28 COMPLETE / ACCEPTED / SHOULD
  before advanced estimating, sourcing, and valuation**
- **Historical entry-gate result (2026-09-30):** the Product Owner selected D23-01=A,
  D23-02=A, D24-01=A, D24-02=A, D25-01=A and D26-01=A. Material/UOM product-policy
  and execution-contract gates are satisfied. No P1.4 implementation started in
  this decision-recording session; S23 remains blocked only until the separately
  executing S19-S22 work completes the required P1.3 technical-document boundary.
  Existing Tenant-local `Material`, `MaterialCategory` and `UnitOfMeasure` behavior
  remains unchanged meanwhile.
- **Product Owner decision packet (2026-09-29):**
  [P1-S23–S28 decision packet](docs/architecture/P1_S23_S28_PRODUCT_OWNER_DECISION_PACKET.md)
  records the accepted Option A boundaries, S23-S28 execution contracts, mandatory
  S27 evidence, non-deferrable failures and explicit later-phase deferrals. D28-01=A
  is only the closeout rule; final P1 acceptance still requires S27 evidence. This
  record does not reopen or restate S19-S22 or change runtime behavior.
- **P1-S23 closeout (2026-09-30):** materials migration `0004` and organizations
  migration `0044` add dedicated stewardship/merge permissions, immutable aliases,
  manual duplicate candidates and locked non-destructive supersession. Existing
  Tenant codes are adopted; a code becomes immutable after transactional use.
  Losing records, historical FKs and snapshots remain unchanged, while new
  identifier resolution follows the survivor. Five focused/regression material
  tests pass; no cross-Tenant catalogue, probabilistic matching or bulk merge was
  added. P1-S24 proceeded under D24-01/02=A.
- **P1-S24 closeout (2026-09-30):** materials migrations `0005`–`0007` and
  organizations migration `0045` add Tenant-local conversion families, one family
  base, immutable effective-dated factors to that base, versioned rounding policy
  and immutable conversion snapshots. Existing units are safely backfilled to
  isolated families; no factor is invented. Cross-Tenant, incompatible, overlapping
  or under-precision conversion fails closed. Eight focused/regression material
  tests pass. Formula/compound units and external feeds remain deferred. P1-S25 is
  next under D25-01=A.
- **P1-S25 closeout (2026-09-30):** materials migrations `0008`–`0009`,
  organizations migration `0046` and audit migration `0035` add Platform-closed
  declarative value types/operators, Tenant/category-scoped immutable definition
  versions and values, reviewable idempotent row imports, bounded attribute search,
  and sourced currency/unit price observations. Observations are not quotes or a
  financial ledger. Invalid, version-mismatched and cross-Tenant data fails closed;
  no executable Tenant content, formulas, taxonomy synchronization or shared
  templates were added. Two targeted tests pass.
- **P1-S26 closeout (2026-09-30):** materials migration `0010`, organizations
  migration `0047` and audit migration `0036` add immutable Tenant-local
  equivalent/substitute records, version-pinned technical-document links, and
  separated technical review evidence. Existing materials are migrated only to
  `legacy_unreviewed`; no approval is fabricated. Controlled decisions require a
  non-submitter, a reason and supersede a prior effective revision rather than
  rewriting it. Three focused S26 tests pass.
- **P1-S27 integrated acceptance (2026-09-30):** 26 targeted document/material
  regression tests passed for Tenant isolation, permission boundaries, immutable
  lineage, deterministic conversions and document availability/access behavior.
  No non-deferrable failure was found.
- **P1-S28 Product Owner acceptance (2026-09-30):** the Product Owner reported that
  P0/P1 went well, accepted the completed P1 result and requested that P2 start.
  P1 is therefore **ACCEPTED** against the bounded S19-S27 evidence and its explicit
  deferrals. This is not P10 production certification and does not fabricate
  still-open P0.2/P0.3 operating parameters. The conditional P2 handoff is active.
- **Outcome:** governed canonical tenant material codes and aliases; UOM families
  and explicit conversions; category-specific technical/dynamic attributes;
  brand/model/manufacturer/country; substitutes/equivalents; effective price
  history with source/currency/unit; technical documents; and technical/quality
  approval states.
- **Prerequisites:** existing Material/UOM masters, P1.3 document boundary, and
  product decisions on coding, conversion precision and approval ownership.
- **Ownership/integration:** Materials owns identity, attributes and conversions;
  Procurement owns quotes/purchases, Inventory owns movements/valuation,
  Estimates owns rate usage, and Quality owns approval evidence. Transactions
  snapshot the applied identity/unit/rate; price history is not a financial ledger.
- **UI/security:** context-aware material search, code/name/brand display,
  conversion explanation, duplicate/merge review, substitute approval and
  technical-document status; tenant scope remains authoritative.
- **Migration/testing:** reconcile text-only material/unit snapshots incrementally;
  test conversion precision/direction, duplicate aliases, inactive/approved
  selection, source history and cross-tenant isolation.
- **Build-vs-Reuse:** evaluate maintained attribute/search/import components only
  for commodity mechanics; retain material governance and construction semantics.
- **Effort / risk:** **L / High**.

## P2 — Accounting kernel

### P2.1 Ledger, fiscal periods, and posting registry

- **Status / priority:** **P2-S01–S38 COMPLETE; P2 SESSION PACKAGE CLOSED;
  P3 ENTRY REMAINS PRODUCT-OWNER GATED /
  MUST before native financial go-live**
- **P2-S01 entry result (2026-09-30):** P1-S28 acceptance and the Product Owner's
  request to start P2 authorize the bounded policy/ADR entry session. The
  [P2-S01–S04 decision packet](docs/architecture/P2_S01_S04_ACCOUNTING_DECISION_PACKET.md)
  preserves P0-D02 and P1-S14 decisions and presents the minimum executable choices
  for native-book scope, COA/dimensions, fiscal periods, precision activation,
  opening balances, close/reopen, sign-off and the first producer. No ledger code,
  schema, permission or statutory value is authorized until those choices are
  explicit and S02-S04 validate the resulting implementation contract.
- **P2-S02–S04 decision/contract closeout (2026-09-30):** the Product Owner selected
  D2-01 through D2-08 = A and supplied the binding authority, dimension,
  history, fail-closed policy, opening-provenance, Protected Operation,
  permission-based SoD and synchronous/manual-source clarifications recorded in
  the packet. S02-S04 found no conflict with S04 target architecture or the P1
  foundations. The first expand-only foundation slice adds Tenant-scoped Account,
  FiscalYear/Period and manual/opening JournalEntry/Line authority, accounting
  permissions/protected classifications, version pinning, balance/period checks,
  independent posting and audited period close/reopen.
- **P2-S05–S12 implementation closeout (2026-09-30):** the ledger/schema and
  opening-data group is complete. It strengthens leaf-account and non-overlapping
  fiscal controls, keeps organization-scoped numbering transactional, freezes
  posted account/dimension snapshots, and adds code-owned manual/opening/reversal/
  replacement contracts with durable source/version/event identity, canonical
  payload hashes, duplicate conflict handling and concurrent idempotent posting.
  Reversal and replacement are linked immutable journals. Opening imports retain
  cutoff, source evidence and reconciliation, require independent protected
  acceptance, and create one balanced opening journal without fabricated history.
  The approved continuation pulled this bounded registry/reversal kernel forward
  from the earlier S13–S22 plan; operational producers and their adapters remain
  unimplemented. Precision/rounding values remain unset and correctly block
  submission without blocking development. Targeted PostgreSQL tests and a fresh
  migration run pass.
- **P2-S13 lineage/reconciliation foundation (2026-09-30):** the S13–S22
  contract was recalibrated to the accepted D2-08=A boundary. The closed
  code-owned registry now declares Accounting ownership and exact source/source-
  line models, journal lines retain immutable source-line UUIDs (including exact
  opening-import and reversal lineage), and a synchronous Tenant-scoped read-only
  preflight reports manual/opening/correction counts, totals, pending facts and
  explicit lineage exceptions through a cutoff. This is not a retained or signed
  reconciliation run. No operational producer is registered; durable runs,
  exception resolution and protected independent sign-off remain S14–S19 work.
- **P2-S14–S15 retained reconciliation evidence (2026-09-30):** Accounting now
  retains immutable Tenant-scoped manual/opening/correction runs with a versioned
  scope, cutoff, deterministic scope/input/result SHA-256 evidence, counts/totals,
  creator membership and immutable exception snapshots. Identical input retries
  return the same run and one audit event; a dedicated run permission is enforced.
  Five targeted PostgreSQL tests passed at that checkpoint. Expanded tie-outs were
  then closed by S16–S17 below; exception disposition, protected independent
  review/sign-off and operational producers remain separately gated.
- **P2-S16–S17 retained tie-out closeout (2026-09-30):** retained runs now include
  immutable per-source manual, opening and correction tie-out snapshots. Each
  snapshot pins source version, source/journal line counts and debit/credit totals,
  exact line UUID/account/amount evidence, dimension IDs and posted snapshots, plus
  explicit count, amount, version, line, dimension and correction-chain results.
  Accepted opening imports reconcile to their exact posted lines; reversals require
  inverted amounts with the same source lines/dimensions; replacements retain the
  linked prior version while allowing corrected line/amount shape. The run scope is
  version 2 and its result hash covers the ordered tie-outs. Eight targeted
  PostgreSQL reconciliation tests pass. That slice added no exception disposition,
  protected sign-off or operational producer.
- **P2-S18 controlled exception disposition (2026-09-30):** each retained
  exception can now receive exactly one immutable Tenant-scoped disposition from
  the bounded correction-required, explained-variance or not-applicable catalogue.
  A dedicated permission, mandatory reason, optional evidence reference,
  membership actor and append-only audit event are retained. Identical retries
  return the same disposition; conflicting rewrites, deletion, unauthorized and
  cross-Tenant action fail closed. Disposition never changes the run, exception,
  tie-out or journal balance. Ten focused PostgreSQL reconciliation tests pass.
  At that checkpoint protected independent review/sign-off remained P2-S19 and no
  operational producer was added.
- **P2-S19 protected reconciliation sign-off (2026-09-30):** a retained run can
  now receive one immutable independent review through a dedicated permission,
  mandatory reason and append-only audit event. The reviewer must differ from the
  run creator and every disposer on that run; all exceptions must be dispositioned
  first. Sign-off pins the scope, input, result, disposition and combined evidence
  hashes after verifying the retained snapshots and creation audit. It does not
  edit dispositions, evidence, journals or balances.
- **P2-S20–S21 focused acceptance (2026-09-30):** twelve targeted PostgreSQL
  tests pass for Tenant and permission boundaries, sign-off SoD, exact-retry and
  concurrent run/sign-off idempotency, cutoff stability, retained-evidence tamper
  detection, immutable controls and missing-policy fail-closed behavior.
- **P2-S22 closeout and producer handoff (2026-09-30):** the bounded
  manual/opening/correction reconciliation contract is closed and authoritative
  documents are reconciled. An operational producer remains a separate Product
  Owner approval: it must name the producer and owner and approve finalized-source
  eligibility, source/version/line identity, recognition and mapping policy,
  precision, idempotency/atomicity, correction/reversal/close, cutoff/opening,
  Tenant/authorization, exception/reconciliation and rollout/rollback contracts.
  No producer, adapter, Treasury/AP/AR behavior or asynchronous path was selected,
  registered or implemented.
- **P2-S23–S27 Accounting Admin/UI closeout (2026-09-30):** Persian-first RTL
  tenant routes now expose existing service-backed accounts, fiscal controls,
  manual/opening journals, immutable posted/reversal/replacement history, retained
  reconciliation/tie-out/disposition/sign-off evidence and source-to-journal
  drill-through. Django Admin is tenant-filtered inspection only, so it cannot
  bypass audited services or mutate finalized evidence. No producer, Treasury/AP/AR,
  statement, trial-balance, background-job or dependency scope was added.
- **P2-S28–S34 statements and close-control closeout (2026-09-30):** Accounting
  now derives trial balance, account turnover/general-ledger drill-through,
  balance sheet and profit/loss read models only from posted immutable journal
  lines and retained account/dimension snapshots. Permission-controlled retained
  statement runs pin scope/input/result hashes and exact source-line evidence.
  Period close now rejects draft/proposed journals and pending opening imports,
  requires a cutoff-matched independently signed reconciliation, retains the three
  close statements and an append-only hash-pinned close event; reopen retains a
  separate linked event and enforces independence from the close approver.
  Authorized late corrections may be prepared only as linked manual journals in
  an explicitly configured open adjustment period, retaining reason, evidence and
  reconciliation references without changing the closed source journal. Persian
  RTL reporting/adjustment UI and read-only Admin inspection use the same services.
  No producer, Treasury/AP/AR, export, background job, dependency or later scope
  was added at that checkpoint. Seven focused PostgreSQL tests pass for reporting accuracy, Tenant/
  permission boundaries, cutoff/immutability, close/reopen SoD and controlled-
  adjustment lineage; the recovered S23–S27 UI slice also passes three tests.
- **P2-S35–S37 financial hardening and integrated acceptance (2026-09-30):**
  Accounting financial mutations now acquire one Tenant accounting coordination
  lock before narrower rows, so posting/number allocation, statement retention,
  reconciliation/sign-off, close/reopen and linked correction paths serialize
  consistently without duplicate journals, numbers, runs, events, reversals or
  adjustments. Close re-verifies the signed cutoff against current posted facts;
  stale reconciliation cannot race a posting into a close. Exact close/reopen and
  retained-statement retries are idempotent, while conflicting state fails closed.
  Retained statement rows and signed reconciliation/audit hashes are re-verified
  before reuse. Forty-seven focused PostgreSQL Accounting tests pass, including eight
  S35–S37 tests and an Accounting `0009` rollback/reapply rehearsal. No schema
  change, producer, Treasury/AP/AR, cash/bank reconciliation, payroll, export,
  background job, dependency or P2-S38 scope was added.
- **P2-S38 documentation closeout and P3 handoff (2026-09-30):** the completed
  P2 session package is reconciled across this roadmap, the execution playbook,
  Accounting ADR and readiness audit. The
  [P2-S38 P3 handoff packet](docs/architecture/P2_S38_P3_HANDOFF_PACKET.md)
  records the sole-GL-authority boundary, retained-evidence invariants, verified
  PostgreSQL/migration evidence, non-goals and named P3 entry gates. It does not
  authorize P3, a producer, Treasury/AP/AR, exports or any operational posting.
- **Post-close accounting-policy UI/RBAC correction (2026-10-01):** Tenant policy
  selection now presents only published, schema-valid versions effective on the
  current date; future versions remain read-only. The unused
  `tenant_policies.approve` catalog entry is deprecated/inactive, with no added
  approval path; Tenant Admin continues to select and apply through
  `tenant_policies.apply`.
- **Outcome:** chart of accounts and dimensions; fiscal year/period; balanced
  immutable journal entries/lines; proposed vs posted state; numbering;
  close/reopen; reversal/replacement; source version and idempotency; opening
  balances; controlled posting-rule catalogue.
- **Prerequisites:** P0.1, P1.1, P1.2; product-owner decision on native books.
- **Ownership:** operational domains own source documents; Accounting alone owns
  journals. No posting from signals and no editable posted entries.
- **Integration:** P2.1 currently permits controlled manual/opening journals only;
  add a pilot producer later only with separate approval and its reconciliation
  contract.
- **Compliance:** professional review of Iranian accounting/tax book requirements;
  rule versions and fiscal locks.
- **UI/security:** Persian journal entry/review, balanced totals, dimension
  cascading, source drill-through, close/reopen and reversal reasons; strict SoD.
- **Migration/testing:** current `financials` read models remain projections;
  do not synthesize authoritative historical journals from demo totals. Property
  tests for balance/precision, concurrency/idempotency, close/reversal, tenant
  isolation, high-volume posting and migration rollback.
- **Effort / risk:** **XL / Critical**.

### P2.2 Accounting statements and close controls

- **Status / priority:** **PARTIAL — P2-S28–S38 REPORTING/CLOSE CORE AND SESSION
  CLOSEOUT COMPLETE; controlled export remains separately planned/unapproved**
- **Outcome:** trial balance, general ledger, account turnover, balance sheet,
  profit/loss and controlled exports with drill-through and close checklist.
- **Prerequisites:** P2.1 stable postings and reconciled opening balances.
- **Data:** read models/caches are rebuildable; journal remains authoritative.
- **UI/testing:** filters state URL, Jalali period display, explicit currency,
  export permission/audit; statement tie-out and source-line lineage tests.
- **Effort / risk:** **L / High**.

## P3 — Treasury and subledgers

### P3.1 Treasury and bank reconciliation

- **Status / priority:** **P3-S01–S27 FOUNDATION COMPLETE; P3-S28–S29
  WORKBENCH IMPLEMENTATION COMPLETE / ACCEPTANCE PENDING; P3-S30–S31 COMPLETE /
  ACCEPTED; P3-S32 DOCUMENTATION CLOSEOUT / P4 HANDOFF COMPLETE; P3 activation
  remains unauthorized / MUST for native cash and subledger control**
- **P3-S01–S04 decision closeout (2026-10-01):** the
  [Treasury/subledger and legacy Payment decision packet](docs/architecture/P3_S01_S04_TREASURY_SUBLEDGER_DECISION_PACKET.md)
  reconciles current Payment/allocation/claim-settlement evidence with the P2
  handoff and records D3-01 through D3-08 = A, D3-09 = A-Revised, and D3-10
  through D3-12 = A. The accepted ownership, account/movement/instrument, Accounting
  producer, permission/SoD, party-bank-profile, cheque, statement-import and
  migration/rollback contracts preserve platform-policy-controlled Self-Approval:
  Protected Operations never allow it, while other Treasury business operations
  follow explicit versioned scope-bound platform/Tenant policy and fail closed
  when required configuration is missing. No model, migration, permission,
  producer, backfill, UI, bank integration or P3-S05 implementation was authorized.
- **P3-S05–S11 implementation closeout (2026-10-01):** explicit Product Owner
  authorization delivered the Tenant-scoped `treasury` authority for bank, cash
  and petty-cash accounts; masked identifier retention; controlled account and
  versioned Accounting-mapping lifecycle; direct receipts, disbursements and
  atomic two-leg transfers; cheque custody/clearing/bounce lifecycle; immutable
  movement and reversal evidence; and the synchronous atomic
  `treasury.movement.posted.v1` Accounting producer. Exact source/version/line,
  occurrence, rule, mapping, approval/precision/rounding policy and fiscal-period
  identities are retained with Treasury-to-GL reconciliation evidence. Six
  focused PostgreSQL tests passed, including tenant isolation, permissions/SoD,
  masking, idempotency, atomic transfer, cheque cash-on-clear, linked bounce
  reversal, reconciliation and concurrent account uniqueness. TINF-01 is now
  closed for the flush seed-loss root cause: idempotent `post_migrate` catalog
  bootstrap restores authorization roles/permissions and registry-owned workflow
  types; the three retained Accounting regressions and the 29-test Accounting
  foundation set passed after the fix. The independent
  `MATERIAL_DOCUMENTS_LINK` registry failure remains separate and unchanged.
  At that closeout, P3-S12+, legacy cutover/backfill, pilot activation, UI,
  statements, AP/AR, integrations and background work remained unauthorized.
- **P3-S12–S17 implementation closeout (2026-10-01):** explicit Product Owner
  authorization first produced the bounded
  [implementation contract](docs/architecture/P3_S12_S17_IMPLEMENTATION_CONTRACT.md),
  then delivered unscheduled Tenant payment requests; employee/vendor advance
  opening from exact posted disbursements; cash-return settlement against exact
  posted receipts; policy-controlled Self-Approval; dedicated permissions and
  audit; integrated protected reversal; and immutable advance-to-Treasury-to-GL
  reconciliation evidence. Migrations `treasury.0004`, `organizations.0060`, and
  `audit.0042` are expand-only and perform no legacy backfill or cutover. Nine
  focused PostgreSQL Treasury tests, including concurrent settlement-cap control,
  and three retained Accounting regressions passed; four focused permission/
  catalog tests and eleven role-default subtests passed. The broader permission
  registry suite still has the independently pre-existing model/namespace and
  `MATERIAL_DOCUMENTS_LINK` failures; this tranche neither absorbs nor changes
  them. Payment scheduling/proposals, all numeric thresholds, non-cash advance
  substantiation, legacy migration, activation, statements, AP/AR, integrations,
  UI, background work and P3-S18+ remain deferred/not authorized.
- **P3-S18–S22 implementation closeout (2026-10-01):** explicit Product Owner
  authorization first finalized the bounded
  [statement and bank-reconciliation implementation contract](docs/architecture/P3_S18_S22_IMPLEMENTATION_CONTRACT.md),
  then delivered expand-only Tenant bank-statement import/row evidence; explicit
  synchronous byte/row bounds with no defaults; file, provider-row and exact-row
  duplicate controls; import/reconciliation idempotency; exact-only deterministic
  or ambiguous match suggestions; policy-controlled independent acceptance and
  confirmation; immutable clearing and forward reversal; and retained bank-to-
  Treasury reconciliation hashes/exceptions without mutating Treasury movements
  or Accounting journals. Migrations `treasury.0005`–`0006`,
  `organizations.0061`, and `audit.0043` add no legacy backfill, cutover or
  activation. Four focused PostgreSQL statement tests and one migration rollback/
  reapply rehearsal passed, together with three retained Accounting regressions.
  Two focused permission checks plus eleven role-default subtests passed; the
  broader registry still reports only the pre-existing namespace and
  `MATERIAL_DOCUMENTS_LINK` gaps. Provider adapters/formats, approved production
  byte/row limits, source-file storage/retention, tolerances, UI, background work,
  external bank integration, legacy `Payment` transition, AP/AR, activation and
  P3-S23+ remain separate gates.
- **P3-S23–S27 implementation closeout (2026-10-01):** explicit Product Owner
  authorization first finalized the bounded
  [AP/AR implementation contract](docs/architecture/P3_S23_S27_IMPLEMENTATION_CONTRACT.md),
  then delivered the expand-only `subledgers` authority for immutable AP/AR
  obligations, Treasury-linked partial settlement and reversal, exact per-item
  as-of aging without invented buckets, retained reconciliation exceptions,
  dedicated permissions/audit, concurrency caps and Treasury reversal protection.
  No source adapter or Accounting producer is activated: recognition/posting
  remains fail-closed pending implementation of the later accepted Q01/Q02 choices.
  Write-off proposals are retained, while approval/reversal receive no default-role
  grant and remain disabled pending implementation of accepted Q03 A-Revised;
  accepted Q04 retains exact unbucketed aging. Migrations are expand-only and
  perform no legacy `Payment` or claim-settlement backfill/cutover. Six focused
  PostgreSQL tests, including concurrent over-allocation and migration rollback/
  reapply, six retained Treasury/Accounting regressions, and three focused
  permission/catalog checks with eleven role-default subtests passed. The broad
  registry audit retains only its pre-existing model/namespace and
  `MATERIAL_DOCUMENTS_LINK` gaps. P3-S28+, UI, activation and external/background
  work remain separate gates.
- **P3-S28–S29 UI and exception-workbench closeout (2026-10-01):** authorized
  Persian-first RTL Treasury, statement/reconciliation and AP/AR workbenches now
  expose only retained implemented evidence and existing service transitions.
  Every route resolves the active Organization server-side and enforces tenant
  lifecycle, membership, permission and service-level object scope. Allocation
  selects only an exact posted Treasury movement—not a cash-account posting—and
  displays the retained lineage. Source recognition, Accounting posting,
  write-off approval/reversal, thresholds, buckets, activation, legacy cutover,
  adapters and background work remain unavailable. Focused UI coverage adds CSRF,
  masking, tenant isolation, suspended-Tenant, accessibility/RTL and fail-closed
  assertions are added. The later S30–S31 isolated acceptance run also passed
  this focused workbench coverage; at the S28–S29 closeout, P3-S30+ was still a
  separate authorization gate.
- **P3-S30–S31 reconciliation-control closeout (2026-10-01):** explicit Product
  Owner authorization delivered dedicated Treasury and AP/AR reconciliation-review
  permissions, expand-only immutable one-to-one review evidence, direct independent
  maker-checker enforcement, signed retained-evidence hashes, idempotent identical
  retries, tamper verification, append-only audit and permission-aware RTL review
  actions. Existing file-hash, provider-row, exact-row and idempotency controls
  remain the only statement duplicate protections; no override, tolerance or
  provider policy was invented. Eight focused control/duplicate/UI tests passed
  against an isolated PostgreSQL test database, together with Django checks,
  migration-state checks and targeted Ruff. The three retained Treasury,
  subledger and Accounting regressions subsequently passed from a clean isolated
  PostgreSQL database. Investigation established that the earlier apparent stall
  was orphaned diagnostic pytest processes retaining a partial disposable test
  database, not a product-code fault; no runtime or test-behaviour change was
  required. **P3-S30–S31 are COMPLETE / ACCEPTED.** Activation, legacy
  cutover/backfill, external/background work and `MATERIAL_DOCUMENTS_LINK`
  remediation remain unauthorized.
- **User-authorized financial UI terminology refinement (2026-10-01):**
  localized the AP/AR workbench and feedback, clarified legacy Payment and
  project-report navigation labels, and grouped Treasury beside Accounting and
  receivables/payables. The subsequent requested Treasury page/browser title
  simplification to `خزانه‌داری` passed a database-free template render check.
  Follow-up Product Owner terminology (`مغایرت بانکی` and
  `مغایرت خزانه با حسابداری`) is applied to Treasury and statement templates;
  rendering checks passed for both, including the ledger-reconciliation row.
  Treasury cutoff labels now use `تاریخ مبنای تطبیق` in the bank form, bank
  results table and ledger-reconciliation history. Database-free rendering
  verified all three labels and preservation of the `as_of_date` form field.
  Routes, permissions, financial rules and activation gates
  are unchanged; this is not acceptance of the pending P3-S28–S29 package.
  Django checks, Ruff lint and database-free template/menu rendering passed.
  Three focused workbench tests were blocked during test-database setup by a
  duplicate `documents_documentdisposalintent` database type/table; no test body
  ran. Ruff format check also reports existing formatting differences in the
  touched view module; broad reformatting was left out of this copy-only change.
  Browser visual acceptance remains outstanding. Terminology is recorded in
  [UI guidelines](docs/ui-guidelines.md).
- **P3-S32 documentation closeout and P4 handoff (2026-10-01):** the
  [closeout/handoff packet](docs/architecture/P3_S32_CLOSEOUT_AND_P4_HANDOFF.md)
  reconciles the verified P3 result and records the P4 consumption boundary:
  Treasury cash and AP/AR settlement evidence do not establish a project actual,
  budget classification or accounting entry. P4 remains separately authorized and
  must define its own source/classification, version, reconciliation and
  migration contracts. This does not accept the separately pending P3-S28–S29
  workbench result or activate any P3 path.
- **P3-S23–S27 activation decision packet (2026-10-01):** the concise
  [Q01–Q04 packet](docs/architecture/P3_S23_S27_ACTIVATION_DECISION_PACKET.md)
  now records **Q01 = A, Q02 = A with exact Treasury directional-clearing
  semantics, Q03 = A-Revised under the existing Platform/Tenant Self-Approval
  policy, and Q04 = A** as accepted Product Owner decisions. The four decision
  gates are closed, but the packet changes no runtime, activates no AP/AR path and
  does not authorize legacy cutover/backfill, UI, external/background work or
  P3-S28+.
- **Outcome:** bank/cash accounts including petty cash; payment requests,
  scheduling and proposals; receipts, payments and bank transfers; employee/vendor
  advances and advance settlement; cheque lifecycle, clearing, statement import,
  match suggestions, reconciliation, cash position and cash-flow forecast.
- **Prerequisites:** P2.1; implement the accepted Party-owned bank-profile and
  Treasury object-scope boundaries; D3-11 selects bounded synchronous statement
  import initially, while exact provider/file sources and limits remain open.
- **Migration:** contain/rename current `Payment`; map it only with explicit
  semantics. `PaymentAllocation` is not a journal line.
- **Integration:** AP/AR, claims, payroll, guarantees and Accounting postings.
- **Boundary:** Treasury owns cash movement and instruments; AP/AR owns
  obligations/open items; Accounting owns journals. Petty cash, advances,
  allocations and bank matches must not become competing ledgers.
- **UI/security:** sensitive account masking; platform-policy-controlled
  Self-Approval with no Self-Approval for Protected Operations and an independent
  checker when disabled or when an additional threshold applies; batch approval,
  unmatched exception queue, bank evidence and reversal.
- **Testing:** duplicate import/idempotency, cheque/clearing states, match
  confidence, allocation caps, reconciliation and tenant isolation.
- **Effort / risk:** **XL / Critical**.

### P3.2 AP/AR obligations and settlement

- **Status / priority:** **P3-S23–S27 FOUNDATION COMPLETE; P3-S28–S29 UI
  IMPLEMENTATION COMPLETE / ACCEPTANCE PENDING; P3-S30–S31 CONTROL COMPLETE /
  ACCEPTED; P3-S32 DOCUMENTATION CLOSEOUT / P4 HANDOFF COMPLETE; Q01–Q04
  ACCEPTED; IMPLEMENTATION/ACTIVATION NOT AUTHORIZED**
- **Activation decisions:** Q01–Q04 dispositions are recorded in the
  [activation decision packet](docs/architecture/P3_S23_S27_ACTIVATION_DECISION_PACKET.md);
  they close only the Product Owner decision gates and do not authorize runtime
  changes or activation.
- **Outcome:** customer/supplier open items, due dates, credit/debit adjustments,
  allocations, aging, collection/payment status and subledger-to-GL reconciliation.
- **Prerequisites:** P2.1 and P3.1; producer contracts from Billing/Procurement.
- **Integration:** claims, supplier invoices, payroll liabilities, Treasury and GL.
- **Compliance/UI:** source document and tax identity snapshots; aging and
  settlement drill-through; controlled write-off/reversal.
- **Migration/testing:** reuse existing claim settlement evidence where semantic
  mapping is exact; reconciliation, over-allocation, void and closed-period tests.
- **Effort / risk:** **L / Critical**.

## P4 — Project costing and controls

### P4.0 Estimate, BOQ, and budget-preparation depth

- **Status / priority:** **P4-S01–S38 SAFE AUTHORIZED SCOPE IMPLEMENTED; P5 NOT STARTED**
- **P4-S01–S06 implementation boundary (2026-10-01):** immutable planning-only
  revision comparison, draft resource composition, recorded assumption/coefficient
  evidence, immutable internal price-source/rate lineage and a formula-free,
  non-persistent CSV preview profile are implemented. No coefficient/rate
  calculation or activation, external price-book ingestion, estimate-to-budget
  handoff, CBS/cost-center, financial fact, legacy cutover/backfill, or P4-S07+
  behavior was included in that slice. Three focused PostgreSQL tests pass. “Planning-only”
  is a financial-ownership boundary: it does not mean the models, services,
  migrations or permissions are merely proposed. P4-G01 coefficient/calculation policy, P4-G02
  resource-rate ownership, P4-G03 lawful external price-book source/version,
  P4-G04 spreadsheet-template authority and P4-G05 budget-handoff authority
  remain fail-closed Product Owner gates; see
  `docs/architecture/P4_S01_S06_IMPLEMENTATION_CONTRACT.md`.
- **Outcome:** extend current approved revisions with side-by-side revision and
  scenario comparison; material/activity links; labor/material/equipment resource
  analysis; overhead, regional, mobilization and other governed coefficients;
  escalation/inflation assumptions; reusable rate/price sources; previewed Excel
  import; and licensed/versioned Iranian price-book (فهرست‌بها) import where the
  product owner approves a lawful source.
- **Prerequisites:** P1.4 material/UOM governance, existing Estimate lifecycle and
  workflow foundation, plus decisions on price-book licensing/version, coefficient
  policy, resource-rate ownership and Excel templates.
- **Source of truth:** distinguish contractual BOQ, internal estimate/scenario and
  approved budget baseline. An estimate revision is calculation evidence; only an
  explicit accepted handoff creates a P4.1 budget baseline.
- **Integration/accounting:** WBS/activity/material/equipment/workforce inputs feed
  estimating; P4.1 consumes the accepted output. Estimates never post journals or
  silently change contract value.
- **UI/security:** large accessible line grid, grouped resources/coefficients,
  comparison and assumption traceability, import mapping/preview/error report,
  protected rate/price-book access and explicit unit/currency.
- **Migration/testing:** retain approved revisions; add links/snapshots through
  expand/backfill/switch. Golden calculations, coefficient order/rounding,
  scenario/revision immutability, duplicate import, formula-free safe Excel parse,
  tenant scope and representative-volume tests.
- **Build-vs-Reuse:** evaluate mature spreadsheet parsers and safe tabular import;
  own BOQ, coefficient, scenario and budget-handoff rules.
- **Effort / risk:** **XL / High**.

### P4.1 Budget/CBS/cost center and integrated project cost

- **Status / priority:** **P4-S07–S38 SAFE COST, CONTROL, AND EXPENSE FOUNDATION IMPLEMENTED; P5 NOT STARTED**
- **P4-S07–S13 implementation boundary (2026-10-01):** delivered the explicit
  current-approved-Estimate handoff, complete source manifest, versioned/locked
  CBS and cost centers, conserved leaf-CBS/project-WBS allocations, immutable
  accepted budget versions, one governing project pointer, dedicated permissions,
  direct SoD, audit, idempotency/stale-predecessor locking and a planning-only read
  model. Seven focused PostgreSQL service tests and one rollback/reapply test pass.
  No commitment, actual, payable, receivable, revenue, cash, Treasury, AP/AR,
  journal, forecast, expense, payment or contract-value behavior is created or
  mutated; legacy Project totals are unchanged. P4-G06–G10 remain fail-closed as
  recorded in `docs/architecture/P4_S07_S13_IMPLEMENTATION_CONTRACT.md`.
- **P4-S14–S20 implementation boundary (2026-10-01):** delivered versioned
  producer-source contracts before dependent facts; independently approved,
  immutable and idempotent commitment/accrual/actual projections; exact reversal
  and accrual-replacement lineage; explicit producer coverage/watermarks; immutable
  draft forecast snapshots; and permission-scoped project-detail source
  drill-through. Twelve focused/retained PostgreSQL service/UI tests and the expanded
  rollback/reapply migration suite pass. No operational producer is wired, no
  production behavior or external integration is activated, no journal/source
  record is mutated, and no backfill/cutover or legacy replacement occurs.
  Forecast approval, real-producer recognition mappings, activation/cutoff and
  warning-versus-hard-stop remain fail-closed; see
  `docs/architecture/P4_S14_S20_IMPLEMENTATION_CONTRACT.md`.
- **Outcome:** accepted estimate-to-budget handoff, explicit mapping among
  contractual BOQ/internal estimate/approved budget baseline, CBS/cost-center
  mappings, budget versions, commitments, accruals, actuals, forecast/ETC/EAC,
  variance, WIP and source drill-through.
- **Prerequisites:** P1.2; P2.1 dimension decision. Useful operational costing can
  start before all producers, but must not become a parallel ledger.
- **Migration:** retire `Project.estimated_budget`/`actual_budget` as authorities
  through expand/backfill/switch; preserve only clearly labelled snapshots if
  needed. Demo data need not block correction.
- **Integration:** Estimates, Contracts, Procurement, Inventory, Expenses,
  Payroll, Equipment, Claims and Accounting.
- **UI:** WBS/CBS mapping, baseline comparison, commitment/actual/paid distinction,
  exception-led forecast, source breadcrumb.
- **Testing:** mapping completeness, revision/concurrency, classification,
  multi-source reconciliation, Decimal/currency and volume tests.
- **Effort / risk:** **XL / Critical**.

### P4.2 Schedule, risk, change, and earned-value controls

- **Status / priority:** **P4-S21–S25 SAFE FOUNDATION IMPLEMENTED AND VERIFIED; ACCEPTANCE/SCORING/INTEGRATION GATES OPEN**
- **P4-S21–S25 implementation boundary (2026-10-01):** delivered versioned
  draft schedules, milestones, cycle-safe dependencies, constraint/issue/risk/delay
  evidence with append-only lifecycle, and immutable change/rebaseline proposals.
  Dedicated Tenant/object-scoped permissions, audit, idempotency, locking and
  PostgreSQL immutability are enforced. Baseline/change/rebaseline acceptance,
  risk scoring, delay responsibility, contractual impact, external schedulers and
  earned value remain fail-closed under P4-G11–G18. Seven focused PostgreSQL tests
  and one rollback/reapply test pass; see
  `docs/architecture/P4_S21_S25_IMPLEMENTATION_CONTRACT.md`.
- **Outcome:** schedule baseline/milestones/dependencies; issue, constraint, risk
  and delay registers; change control; approved rebaseline; distinct physical and
  financial progress; and earned metrics where input discipline supports them.
- **Prerequisites:** P4.1, mature progress capture, owner decision on scheduler
  depth and integrations.
- **Boundary:** do not build a full Primavera replacement or BIM authoring tool.
- **Ownership boundary:** Project Controls owns schedule/baseline, issue,
  constraint, delay and integrated impact views; P6.4 owns contractual entitlement,
  contract-value change and EOT evidence.
- **Integration/UI/testing:** WBS/progress/contracts/cost/forecast; baseline/version
  comparison, critical exceptions, import validation and reproducible calculations.
- **Effort / risk:** **L-XL / High**.

### P4.3 Expense approval, allocation, and budget control

- **Status / priority:** **P4-S26–S38 SAFE AUTHORIZED SCOPE IMPLEMENTED; P5 NOT STARTED**
- **Outcome:** workflow-backed draft/submission/approval/return/void; required
  invoice/source evidence; direct/indirect classification; recurring-expense
  templates that create reviewable drafts; allocation across projects; explicit
  Project/WBS/Activity/CBS/CostCenter coding; employee/vendor settlement status;
  and budget/period/duplicate controls.
- **Prerequisites:** P1.1 object scope, P4.1 coding/budget, DMS evidence and
  workflow foundation; P2/P3 for journal, payable and cash settlement completion.
- **Ownership/integration:** Expenses owns operational cost evidence; AP owns
  liability, Treasury owns cash, Accounting owns journals, and Project Cost
  consumes classified approved/posted facts. Recurrence is a proposal schedule,
  not an automatically finalized expense.
- **Compliance/UI/security:** tax/e-invoice relevance is rule-versioned and
  «نیازمند بررسی قانونی»; source preview, split-allocation grid, budget warning vs
  hard-stop policy, maker-checker and sensitive-evidence access.
- **Migration/testing:** preserve existing recorded/void history; introduce new
  lifecycle through explicit compatibility/backfill. Test allocation totals,
  duplicate evidence, budget race, recurrence idempotency, reversal/settlement,
  posting reconciliation and tenant/project isolation.
- **Effort / risk:** **L / Critical**.

- **P4-S26–S30 closeout (2026-10-01):** the legacy `recorded -> void`
  history remains compatible while new expenses can use an audited
  `draft -> submitted -> approved/returned -> void` lifecycle with direct
  maker/checker enforcement. Tenant/object permissions, retained source
  reference and fingerprint, request idempotency, active-source duplicate
  rejection, explicit Project/WBS/optional Activity/leaf-CBS/required-cost-center
  allocation, and exact amount conservation are enforced. Manual weekly/monthly
  recurrence creates one idempotent reviewable draft per occurrence and never
  approves or posts it. Submission snapshots matching accepted-budget facts and
  prior coded approved expenses; P4-G10 remains open, so an overrun is retained as
  `advisory_only` evidence and cannot warn, block, reserve, post, or mutate a
  baseline. Approval creates no AP, GL, Treasury, cash, contract, schedule,
  forecast, Project Cost, or other bounded-context fact. The Persian RTL expense
  list, draft/detail, split-allocation, transition, budget-evidence and recurrence
  proposal views are available under dedicated permissions. See
  [P4-S26–S30 implementation contract](docs/architecture/P4_S26_S30_IMPLEMENTATION_CONTRACT.md).
- **P4-S31–S34 closeout (2026-10-01):** Persian-first RTL Project Controls
  screens now provide separately permissioned, object-scoped read-only comparison
  of governing accepted-budget allocations with identically coded
  approved/recorded expense evidence; clearly labelled advisory overrun evidence
  and permitted open control-register observations; and a bounded UTF-8 CSV.
  Each export retains an append-only audit manifest. Unallocated expense evidence,
  schedule/risk/delay/change/rebaseline/earned-value/forecast data, Project Cost,
  and all financial/source-producer facts are excluded. P4-G10 creates no warning,
  stop, reservation or approval. See
  [P4-S31–S34 implementation contract](docs/architecture/P4_S31_S34_IMPLEMENTATION_CONTRACT.md).
- **P4-S35–S37 closeout (2026-10-01):** exact expense retry payloads,
  same-budget expense assessment, coded-dimension Project Cost reversal/relief
  conservation and deterministic PostgreSQL locking are hardened. A separately
  permissioned and audited Persian RTL read model/CSV places the governing
  accepted budget, approved/recorded expense allocations and existing inert
  Project Cost actual facts side by side. Coverage and source equivalence remain
  explicitly incomplete; excluded/uncomparable evidence and unresolved
  differences are retained, and missing evidence is never presented as zero.
  No producer, posting, AP/GL/Treasury/cash/settlement, policy enforcement,
  accepted forecast, schedule/change/EV authority or contractual effect is
  activated. See the
  [P4-S35–S37 implementation contract](docs/architecture/P4_S35_S37_IMPLEMENTATION_CONTRACT.md).
- **P4-S38 closeout (2026-10-01):** documentation closeout and the
  [P4 closeout/P5 handoff packet](docs/architecture/P4_S38_CLOSEOUT_AND_P5_HANDOFF.md)
  reconcile verified P4-S01–S37 evidence, current ownership boundaries,
  unresolved Product Owner gates, validation status and P5 entry conditions.
  P4-S38 changes no runtime, schema, data, permission, financial policy or
  production state. The separately authorized P5-S01–S04 planning/design tranche
  is now complete as recorded below; it did not activate P5 runtime behavior.

## P5 — Source-to-pay

### P5.1 Sourcing and supplier invoice match

- **Status / priority:** **P5-S01–S28 COMPLETE / ACCEPTED; P5-S29+ UNAUTHORIZED / UNDEFINED**
- **Planning disposition (2026-10-01):** the
  [P5-S01–S04 decision packet](docs/architecture/P5_S01_S04_SOURCE_TO_AWARD_DECISION_PACKET.md)
  defines the internal RFQ-to-award lifecycle, SoD/confidentiality boundary,
  immutable evidence, legacy containment, dormant downstream handoff envelopes
  and a bounded conditional P5-S05 contract. P5-D01–P5-D08 Option A were accepted
  with clarification on 2026-10-02. P5-S05 implemented the accepted internal RFQ
  foundation: tenant/project-scoped RFQ drafts with approved-request lineage,
  immutable issued/addendum snapshots, internal supplier invitations, deadlines,
  permission/object scope, audit, locking and idempotency. P5-S06 adds only sealed,
  internal supplier-attributed quote-envelope and immutable revision metadata,
  linked to the effective RFQ/invitation version and retained with SHA-256 integrity
  evidence, idempotency and supersession/withdrawal lineage. P5-S07 adds explicit
  synchronous deadline closure under the dedicated, object-scoped and default-
  ungranted `rfqs.close_custody` permission. It atomically freezes one immutable,
  metadata-only manifest for the effective RFQ version with one entry per invitation
  and at most one mechanically effective timely submitted revision. Captured but
  unsubmitted, withdrawn, superseded, late, absent and post-close evidence remains
  retained outside the effective selection; post-close evidence never changes the
  manifest. P5-S08 adds synchronous pre-production custody for the permitted package
  of an existing effective `QuoteRevision`: exactly one `supplier_original` followed
  by zero to 20 distinct `supplier_attachment` items, each pinned to immutable
  Documents/DMS identities and canonical hashes under the code-owned
  `sealed_supplier_quote_evidence` retention classification. The dedicated object-
  scoped `rfqs.custody_sealed_evidence` permission has no default-role, Owner/Admin,
  platform, uploader or support bypass. Accepted bytes remain quarantined and
  unavailable; generic document views, download, search, export and Admin paths deny
  them. The locking transaction revalidates the P5-S07 effective-revision lineage,
  permission and scope, enforces code-owned type/size/count/package limits, and commits
  the immutable version, custody row, evidence link and redacted audit atomically with
  evidence-item idempotency and protected temporary-byte cleanup. P5-S08 does not
  mutate or supplement the P5-S07 manifest and creates no opening/reveal, comparison,
  evaluation, award, portal, handoff or production activation. A bounded
  clean-PostgreSQL migration review confirmed that Documents processing assessments
  and Treasury cheque instruments are current, singly owned target-domain records;
  earlier duplicate-table reports came from interrupted scratch migration runs, not
  a migration-chain conflict. Full clean migration, P5-S05/P5-S06 rollback/reapply,
  focused PostgreSQL RFQ/Procurement tests, P5-S07/P5-S08 rollback/reapply,
  migration-drift checks, Django checks and Ruff pass. P5-D05 confirms
  AP/Finance ownership of supplier-invoice evidence/payable disposition; P5-D06
  retains tenant-local `BusinessParty` as the sole supplier identity and keeps
  external identity/portal capability deferred. P5-D07 accepts owner-controlled
  registered handoffs and source-read-only multi-source derived calculations;
  every handoff and activation remains separately gated.
  P5-S09 implements the accepted protected opening/reveal contract recorded in
  [P5-S09 Product Owner decisions](docs/architecture/P5_S09_PRODUCT_OWNER_DECISIONS.md).
  Default-ungranted `rfq_quotes.open`, `rfq_quotes.approve_open`,
  `rfq_quotes.view_confidential` and `rfq_quotes.manage_confidential_access` have
  no Owner/Admin/platform/support bypass. The first valid opening request permanently
  freezes the exact P5-S08 evidence IDs, slots, pinned versions and hashes. A
  different active actor must approve after locked boundary, lineage, scope, SoD,
  package and package-wide current CLEAN/hash revalidation; approval atomically
  creates one immutable revision-specific opening event. Viewing additionally needs
  an active explicit revision grant, permission and project scope. Delivery returns
  only one exact pinned version synchronously with attachment-only/no-sniff metadata,
  per-access byte/hash revalidation and redacted success/denial audit. Revocation is
  append-only. Generic Documents paths, preview/render/OCR/search/cache/derivatives,
  bulk export, commercial admissibility and break-glass remain absent.
  P5-S10 implements the accepted revision-specific commercial-admissibility
  contract in [P5-S10 Product Owner decisions](docs/architecture/P5_S10_PRODUCT_OWNER_DECISIONS.md):
  immutable `prepare -> approve` evidence yields only `ADMISSIBLE`,
  `INADMISSIBLE` or `REVIEW_REQUIRED`; controlled v1 reasons, the P5-S07 close
  manifest, P5-S09 opening/package fingerprint and confidential rationale remain
  pinned per revision. Dedicated default-ungranted prepare/approve permissions,
  active revision-specific confidential grants, scope and prerequisite revalidation
  are mandatory. The code-owned Platform/Tenant self-approval policy is pinned to
  each decision and missing policy fails closed. Pending preparations can be
  append-only withdrawn; approved decisions are immutable and corrections explicitly
  supersede the previous decision. P5-S11 adds the accepted, sourcing-only
  commercial layer: immutable asserted line/lot inputs, closed normalization-v1
  calculation lineage, explicit evaluator appointments/conflicts and independent
  disposition, closed non-material exception-v1 lifecycle, separate comparison/
  exception/finalization permissions, and policy-pinned self-finalization only
  where explicitly enabled. Final comparisons and sourcing awards are immutable
  successor records; explicit ties require `TIE_REVIEW_REQUIRED`, `NO_AWARD`
  retains evidence, and single/multi-award allocations are conserved against the
  explicit scope. S11 creates no PO, contract, AP, GL, Treasury, cash, budget or
  other downstream fact, no portal and no production activation.
  P5-S12–S17 add the separately authorized internal continuation: explicit S11
  award-allocation consumption into immutable issued-PO versions; independently
  approved append-only PO changes; version-pinned goods receipts and service
  acceptances with quantity conservation; AP/Finance-owned immutable supplier-
  invoice identities, versions and lines with independent approval; and
  independently approved, effective-dated Tenant match-tolerance versions. Match
  runs retain immutable two/three-way line and cumulative-coverage evidence with
  exact source/version lineage and explicit `MATCHED`, `WITHIN_TOLERANCE`,
  `BLOCKED` or `INCOMPLETE` outcomes. Missing policy/acceptance, unsupported tax or
  charge policy, cross-Tenant scope, overbilling and out-of-tolerance evidence fail
  closed. No match creates a payable, journal, stock/cost fact, payment or exception
  override. Supplier-invoice self-approval and force-match remain absent. P5-S18–S22
  add only the controlled portal foundation: token-hash-only expiring invitations,
  authenticated pre-existing-user acceptance bound to Tenant-local `BusinessParty`,
  immutable invitation-specific grants and revocation, least-privilege issued-RFQ
  reads, and idempotent external submissions that reuse `QuoteRevision` succession
  and receipt/audit evidence. They create no Tenant membership, account, outbound
  delivery, UI, upload/content-custody path or downstream fact. P5-S23–S25 add
  only thin HTTP/template adapters to those services plus internal sealed-custody
  intake; no new lifecycle or external upload authority exists. P5-S26–S27 harden
  accepted portal identity against ambiguous-email, email-rebind and internal-
  membership impersonation; keep browser retries on one hidden stable idempotency
  key; apply private/no-cache delivery; and add a permissioned, project-scoped,
  read-only invoice-match evidence review. They add no override, approval or
  downstream mutation. P5-S28 adds documentation closeout only; P5-S29+ and
  production activation remain unauthorized.
- **Outcome:** RFQ, invited suppliers, versioned quotes, normalized comparison,
  sourcing approval/award, PO changes, service acceptance, supplier invoice,
  two/three-way match, tolerance and discrepancy workflow.
- **Prerequisites:** Parties/P1.2, P1.1, P4 cost coding; AP/GL for financial
  completion; workflow foundation already delivered.
- **Integration:** commitment to Project Cost, receipt to Inventory, AP/Finance-
  owned supplier invoice and payable to Accounting, payment proposal to Treasury,
  and performance to partner profile.
- **Compliance/UI:** tax/invoice snapshots, attachment evidence; comparison grid,
  bid confidentiality, line-level match and exception queue.
- **Migration/testing:** existing PO/receipt remain valid; add links incrementally.
  Quote privacy, tolerance, duplicates, partial receipt/invoice, reversal and
  reconciliation tests.
- **Effort / risk:** **XL / High**.
  - **Verification (2026-10-02):** a clean disposable PostgreSQL migration apply,
    rollback and reapply completed. The final focused acceptance run passed all
    9 P5-S11 cases (including two admitted/opened revisions, ties, `NO_AWARD`,
    permitted/denied split allocations, policy enabled/disabled self-finalization,
    PostgreSQL contention/idempotency, correction lineage and downstream
    non-mutation) and 10 retained P5-S07–S10 custody/opening/admissibility
    regressions. The demonstrated normalized-amount precision issue was corrected
    without a rounding policy; PostgreSQL governing-award lock selection was made
    compatible with its outer-join locking restriction. P5-S11 was Product Owner
    accepted as implemented and PostgreSQL-verified on 2026-10-02. The separately
    authorized P5-S12–S17 batch completed one PostgreSQL migration
    apply/rollback/reapply boundary, 6 focused source-to-pay tests, and 40 retained
    Procurement/P5-S09–S11 regression tests plus 9 subtests. Two PostgreSQL
    nullable-outer-join locking defects, one variance-evidence scale defect and one
    exact source-price representation defect were corrected and rerun. The Product
    Owner accepted P5-S12–S17 as implemented and PostgreSQL-verified on 2026-10-02.
    The authorized P5-S18–S22 batch then passed 7 focused PostgreSQL tests, 62
    retained P5-S05–S17 tests plus 4 subtests, and one migration rollback/reapply
    boundary. A nullable-outer-join locking defect found by PostgreSQL was corrected.
    P5-S18–S22 are Product Owner accepted. P5-S23–S25 passed 5 focused UI tests,
    7 retained P5-S18–S22 tests, 6 bounded P5-S12–S17 regressions and one retained
    sealed-content denial test on one clean disposable PostgreSQL database. No new
    migration was added. The Product Owner accepted P5-S23–S25 as implemented and
    PostgreSQL-verified on 2026-10-02. The authorized P5-S26–S27 slice then ran
    19 PostgreSQL cases on the same uniquely named disposable database: 9 retained
    P5-S18–S22 cases, 5 retained P5-S23–S25 cases, 2 focused read-only match-review
    cases and 3 minimum P5-S12–S17 match regressions. Eighteen passed in the final
    combined run and the one corrected authorization-test fixture passed on focused
    rerun; all 19 scoped cases are green. Full test-schema migration apply and
    disposal succeeded; no migration was added. The Product Owner accepted
    P5-S26–S27 as implemented and PostgreSQL-verified on 2026-10-02. P5-S01–S27
    is the current accepted baseline. P5-S28 documentation closeout and P6
    handoff are recorded in the [P5-S28 closeout packet](docs/architecture/P5_S28_CLOSEOUT_AND_P6_HANDOFF.md);
    P5-S29+ remains unauthorized/undefined.

### P5.2 Controlled supplier and subcontractor portal

- **Status / priority:** **P5-S18–S27 COMPLETE / ACCEPTED; broader collaboration remains planned**
- **P5-S18–S25 disposition:** P5-S18–S22 are accepted service/model foundation.
  P5-S23–S25 add invitation acceptance, exact-RFQ context, idempotent submission
  receipt, internal invitation/grant revocation and internal sealed-evidence custody
  views. They create no outbound invitation delivery, account provisioning,
  external upload path, portal withdrawal or support bypass.
- **P5-S26–S27 disposition:** portal use now fails closed for ambiguous active
  email ownership, changed invited email or an active internal membership; exact
  supplier/RFQ privacy and sealed isolation remain unchanged. Duplicate browser
  submissions reuse a hidden stable retry key. Authorized internal users can
  review immutable, Tenant/project-scoped match lines and discrepancies through a
  read-only Persian RTL screen; no force-match or discrepancy override exists.
  The Product Owner accepted this PostgreSQL-verified scope on 2026-10-02;
  P5-S28 is documentation closeout only; P5-S29+ remains unauthorized/undefined.
- **P5-S28 closeout (2026-10-02):** the [P5-S28 closeout and P6 handoff packet](docs/architecture/P5_S28_CLOSEOUT_AND_P6_HANDOFF.md)
  reconciles the accepted P5-S01–S28 baseline, verified PostgreSQL evidence,
  ownership, deferred/fail-closed behavior and P6 entry conditions. It changes
  no runtime, schema, data, permission, financial policy or production state.
- **Outcome:** invite-scoped external collaboration for party profile/document and
  qualification-evidence submission, RFQ participation, versioned quotation,
  supplier invoice/supporting documents, subcontractor claim/evidence submission,
  clarification and status visibility.
- **Prerequisites:** P1.1 authorization/object scope, P1.3 DMS/security, P5.1,
  P6.2 for subcontract claims, P9.3 qualification, identity/onboarding and external
  support decisions. Portal users receive least-privilege capabilities, not normal
  tenant membership or cross-tenant discovery.
- **Ownership/integration:** internal domains remain authoritative and convert an
  external submission into a reviewed draft/version. This private bilateral portal
  is separate from the deferred public/cross-tenant business network.
- **UI/security:** Persian responsive external journey, invitation expiry,
  organization/context clarity, safe upload, submission receipt, correction loop,
  rate limiting, MFA/risk controls where justified and no internal notes leakage.
- **Testing:** invitation replay/expiry, party impersonation, bid confidentiality,
  object/tenant isolation, duplicate submission/idempotency, malware/failure,
  withdrawal/version history and internal approval handoff.
- **Effort / risk:** **L-XL / Critical**.

## P6 — Contract, claim, guarantee, and revenue/cost control

### P6.1 Correct receivable Billing terms and accounting integration

- **Status / priority:** **PLANNED / MUST correction**
- **Outcome:** move retention/advance/insurance/other commercial rules to approved
  contract-term versions; apply effective regulatory versions; snapshot party,
  currency and rules; generate AR/posting proposals and taxpayer-invoice status.
- **Prerequisites:** P1.2; P2/P3 for posting/settlement; legal/accounting decision.
- **Migration:** map current `BillingPolicy` deliberately; pre-production claim
  data may be discarded/recreated, but finalized behavior changes need explicit
  migration and tests.
- **UI/testing:** calculation explanation and sources, amendment impact, prior
  certified quantities, deductions, correction/cancellation states; golden,
  rounding, cap, concurrency, version and reconciliation tests.
- **Effort / risk:** **L / Critical**.

### P6.2 Subcontracts, payable certificates, and guarantees

- **Status / priority:** **PLANNED**
- **Outcome:** subcontract administration, measured work, payable certificate,
  retention/advance recovery, back-charge, insurance clearance, bid/performance/
  advance/retention guarantees, expiry/renewal/release and exposure.
- **Prerequisites:** P6.1 terms model, AP/Treasury, project costing, partner master.
- **Integration:** commitments/actuals, AP, Treasury, DMS, notifications,
  partner performance and Accounting.
- **Boundary:** subcontract contractual changes, claims and EOT use P6.4; this
  package owns payable certification and guarantee/clearance operations.
- **Compliance/UI:** Article 38/clearance and guarantee rules require legal review;
  expiry workbench, exposure dashboard and evidence.
- **Testing:** contract caps, versioned terms, duplicate certification, releases,
  expired instruments, allocation and reconciliation.
- **Effort / risk:** **XL / Critical**.

### P6.3 Iranian tax and contractor-compliance integration

- **Status / priority:** **PLANNED / legally gated**
- **Outcome:** apply effective VAT/tax codes; produce and track سامانه مؤدیان
  electronic-invoice original/correction/cancellation submissions where approved;
  manage contractor-insurance facts, deductions, مفاصاحساب/clearance evidence and
  expiry/status; and provide versioned statutory export/submission evidence.
- **Prerequisites:** P1.2 regulatory rule/version authority, P6.1 corrected claim
  terms and snapshots, P1.3 DMS, async/idempotency decision, credentials/security,
  and confirmation of launch filing scope. Payroll tax and monthly employee
  insurance lists remain in P7.2 but share the rule/source registry.
- **Compliance:** all schemas, rates, thresholds, calendars and filing behavior are
  effective-dated with source/reviewer and are **«نیازمند بررسی قانونی»** until
  verified against current official authorities. Preserve request, response,
  correction chain, retry and human-resolution evidence.
- **Integration/accounting:** approved commercial documents feed AR/AP and
  posting proposals; external acceptance does not rewrite the source document or
  replace subledger/GL reconciliation.
- **UI/security/testing:** preflight validation, transmission status/error queue,
  controlled correction/cancellation, credential isolation, correlation ID and
  audit; certified-schema fixtures, idempotent retry, provider outage, period/rule
  rollover and source-to-submission reconciliation tests.
- **Build-vs-Reuse:** use official/provider protocols and maintained security/
  transport components; never custom-build cryptography or authentication.
- **Effort / risk:** **XL / Critical**.

### P6.4 Contractual changes, claims, and extension of time

- **Status / priority:** **PLANNED after contract-term and project-control boundaries stabilize**
- **Outcome:** governed Site Instruction, Variation Order/Change Order,
  contractual Claim and Extension of Time lifecycles with versioned evidence,
  entitlement/approval, valuation and cost impact, schedule impact, contract-value
  impact, amendment relationship, and relevant contract insurance/policy evidence.
- **Boundary:** these are contractual change/entitlement records, not ordinary
  `ProgressClaim`/Payment Certificate processing. Approved measurement may support
  either flow, but neither silently changes the other, the contract value, budget,
  schedule baseline, AP/AR or journals.
- **Prerequisites/integration:** P1.2 term versions, P4.2 controls, P6.1/P6.2
  commercial boundaries, DMS, workflow and project-cost/forecast handoffs.
- **UI/testing:** linked instruction-to-claim/change/EOT timeline, evidence and
  impact comparison; duplicate claim, concurrent change, rejected/withdrawn claim,
  cap, approval, amendment, baseline and posting-handoff tests.
- **Effort / risk:** **L-XL / High**.

## P7 — Time, payroll, and employee insurance

### P7.0 Workforce skills, qualifications, development, and labor rates

- **Status / priority:** **PLANNED; delivered workforce structure retained**
- **Outcome:** governed skill/competency catalogue; employee proficiency and
  evidence; certificates/licenses with issuer, validity and expiry escalation;
  required/attended training; role/project competency requirements; explainable
  performance evaluations; effective labor rates/cost components; and complete
  effective responsibility/assignment history.
- **Prerequisites:** current Employee/Position/assignment model, P1.1 scope,
  P1.3 documents/notifications and product decisions on evaluation privacy,
  labor-rate visibility and HSE/QA qualification ownership.
- **Ownership/integration:** Workforce owns employee capability/effective history;
  HSE/Quality references qualification requirements, P7.1 time references the
  effective assignment, Payroll owns pay calculation, and Project Cost consumes
  approved labor-cost distributions. Performance is not an authorization source.
- **UI/security:** expiry/training exception workbench, competency gap view,
  evidence and effective-history timeline; restrict compensation, evaluations and
  personal documents through dedicated permissions and project scope.
- **Migration/testing:** preserve existing assignment history; test date overlap,
  expired qualification routing, rate-version selection, privacy/export,
  evaluation evidence and cross-tenant/project isolation.
- **Effort / risk:** **L / High**.

### P7.1 Attendance, timesheets, and labor costing

- **Status / priority:** **PLANNED**
- **Outcome:** holiday/work calendars, shifts, site `AttendanceRecord`, device/file
  import and controlled manual correction; leave, mission and overtime; plus
  project/site/activity timesheets, approval and labor-cost distribution.
- **Prerequisites:** Workforce, P1.1/P1.2, project/CBS coding, device/integration
  scope decision. Add master-backed daily labor links while retaining snapshots.
- **Integration:** Daily Reports, Payroll, Project Cost, workflow/audit.
- **Boundary:** attendance records when a person was present; timesheets record
  where/how approved time was consumed. Payroll consumes approved time/attendance
  facts and adjustments rather than inventing or rewriting attendance history.
- **UI/security:** mobile/site entry, supervisor bulk review, exception queue,
  employee privacy and scope.
- **Testing:** overlapping time, calendar/timezone, approval locks, import
  idempotency, allocation totals and cross-project access.
- **Effort / risk:** **L / High**.

### P7.2 Payroll, payroll tax, and employee insurance list

- **Status / priority:** **PLANNED / retained target scope**
- **Outcome:** effective employment/pay components, payroll run, arrears/
  adjustments, payslip, allocations, tax/insurance calculations, employee
  insurance-list generation/validation/status, liabilities and posting/payment.
- **Prerequisites:** P7.1; regulatory rule sets with legal review; P2/P3/P4;
  privacy/SoD model.
- **Compliance:** annual values and schemas are effective-dated data with source,
  review and applied-version snapshot; no constants. Confirm current Tax, Labor,
  Social Security, and filing requirements before release.
- **UI/security:** restricted payroll workspace, calculation explanation,
  preflight exceptions, dual approval, employee self-service only if approved.
- **Migration/testing:** no real history exists; prefer correct opening design.
  Golden cases, retroactivity, caps/rounding, run lock/reversal, file/schema,
  posting/reconciliation and privacy tests.
- **Effort / risk:** **XL / Critical**.

## P8 — Inventory, equipment, and fixed assets integration

### P8.1 Inventory valuation and operational depth

- **Status / priority:** **PLANNED**
- **Outcome:** project/activity reservations and release; reorder-point/shortage
  policy and alerts; barcode/QR capture; bins; expiry where applicable; lot/batch
  and serial traceability where justified; physical/cycle count; issue/return to
  work; two-sided transfer dispatch/acceptance and in-transit state; approved
  valuation method; and GL/project-cost reconciliation.
- **Prerequisites:** master UOM conversions, P4 coding, P2 posting; product-owner
  valuation and traceability decisions.
- **Migration/UI/testing:** retain quantity ledger; add optional traceability and
  valuation layers without inventing historical costs. Mobile scan/count,
  reservation/shortage/expiry queues, transfer acceptance and variance approval;
  barcode uniqueness, lot/serial/expiry, reservation availability, count freeze,
  transfer custody, quantity/value conservation, concurrency, reversal and close tests.
- **Effort / risk:** **XL / High**.

### P8.2 Equipment usage, fuel, maintenance cost, and fixed assets

- **Status / priority:** **PLANNED / fixed assets retained target scope**
- **Outcome:** meter readings; operator qualification; equipment insurance,
  inspection and permit/license evidence with expiry; fuel, downtime, preventive
  maintenance plans, usage rates and cost allocation; asset acquisition,
  capitalization, depreciation, impairment, transfer and disposal.
- **Prerequisites:** P4, P2, P8.1 where spare parts apply; accounting policy and
  distinction between operational `Equipment` and financial `FixedAsset`.
- **Integration:** Daily Reports, Inventory/spare parts, Procurement/AP, Payroll,
  Project Cost, Accounting, DMS and expiry notifications/workbench.
- **UI/testing:** mobile readings/scan, maintenance plan, asset register and source
  cost drill-through; meter monotonicity, schedule, depreciation/reversal,
  disposal and reconciliation.
- **Effort / risk:** **XL / High**.

## P9 — Field, HSE/Quality, knowledge, partner, support, and AI

### P9.1 Field operations and paperless evidence

- **Status / priority:** **PLANNED**
- **Outcome:** context-aware mobile daily capture with structured weather, work
  fronts, visits, meetings, instructions, photos/video and source evidence;
  previous-day/template reuse; optional voice-assisted reviewed transcription;
  QR/barcode capture; and reviewed creation of progress/time/equipment/material
  facts. Operational document control covers Transmittal, RFI, Submittal, Method
  Statement, drawings/revisions/review, and inspection documents when approved.
- **Prerequisites:** P1 scopes, P1.3 DMS/search/version/signature boundary, P1.4
  materials, downstream ownership contracts and explicit offline/media decisions.
- **Boundary:** field input proposes downstream records; it does not silently
  finalize payroll, claims, inventory, or journals. `MediaAsset`/album/gallery
  behavior, thumbnails and previews must reuse the DMS blob/version/security
  authority rather than create a duplicate document store.
- **Integration/UI/testing:** visits/meetings/instructions retain actor/source and
  project context; QR/voice/OCR suggestions require confirmation. Use large touch
  targets, camera/upload progress, media gallery, intermittent-network state,
  duplicate sync, conflict resolution, accessibility and tenant/project isolation.
  Broad offline-first sync remains deferred unless the measured use case justifies it.
- **Effort / risk:** **L-XL / High**.

### P9.2 HSE/Quality extensions to governed knowledge

- **Status / priority:** **PLANNED**
- **Outcome:** HSE risk register, inspections, permit-to-work, toolbox meetings,
  PPE controls, training/qualification checks, witnesses, investigation/root cause,
  CAPA, due-date/escalation and performance metrics; plus QA/QC ITP, Inspection
  Request, checklists, laboratory/material/sample tests and approvals, Punch List,
  NCR/rework, root cause, CAPA and independent verification/closure. Closed cases
  generate reviewed knowledge candidates rather than automatic guidance.
- **Prerequisites:** current incidents/issues, DMS, notifications and knowledge
  governance/privacy; P7.0 qualification facts and P1.4 material approvals where used.
- **Integration:** workflow, project controls, workforce qualification, material
  approval, partner performance, DMS, P9.5 knowledge and BI.
- **UI/testing:** mobile inspections/checklists, witness/evidence, risk matrix,
  overdue/escalation and verification workbenches, metric drill-through and lesson
  provenance; closed-history immutability, separation of reporter/closer where
  required, due-date escalation and sensitive-case access.
- **Effort / risk:** **L / Medium-High**.

### P9.3 Partner performance and prequalification

- **Status / priority:** **PLANNED**
- **Outcome:** qualification, expiring evidence, approved vendor/category status,
  project evaluations and explainable delivery/quality/safety/commercial metrics.
- **Prerequisites:** mature party master, Procurement/Contracts/HSE/Quality facts,
  scope/privacy decision.
- **Boundary:** extend `BusinessParty`; avoid duplicate partner masters and opaque
  unchallengeable scores.
- **UI/testing:** evidence/expiry workbench, score drill-through, reviewer conflict
  controls and tenant isolation.
- **Effort / risk:** **L / Medium-High**.

### P9.4 Notifications and support platform

- **Status / priority:** **PLANNED**
- **Outcome:** tenant-aware in-app/email notification preferences and delivery,
  provider-backed SMS only for an approved justified use case, rule-based reminders
  and escalation delivery over existing work-item due/overdue facts, calendar
  aggregation, scheduled operational-task proposals, supervisory workbench and
  permission-safe bulk actions; support cases
  with SLA, `KnownIssue`/`FeatureRequest` classification, release/
  version linkage, Knowledge Base, page/module/object-aware issue reporting,
  correlation ID and permission-safe diagnostics, safe attachments, time-limited
  approved tenant support access, escalation and SLA analytics.
- **Prerequisites:** P0.2 operations, DMS, audit correlation, knowledge governance,
  async/outbox and privacy policy.
- **Boundary:** delivered workflow/work items, candidacy, due dates, overdue state,
  escalation routing and time-bounded delegation remain authoritative; delegation
  is the substitution mechanism unless a distinct policy is later approved within
  that same assignment history. Notifications and calendar views do not create a
  second task/workflow engine. Scheduled jobs and bulk actions invoke
  ordinary authorized domain services and retain per-item results. Audit is not
  notification.
- **Libraries:** evaluate mature queue/email integration components; no package is
  pre-approved.
- **UI/testing:** unified inbox/cartable distinction, delivery state, ticket
  timeline, known-issue/release status, diagnostic consent, support-access timer,
  SLA view; data leakage, stale knowledge, permission, delivery failure and
  human-escalation tests.
- **Effort / risk:** **L / High**.

### P9.5 Enterprise knowledge management and reuse

- **Status / priority:** **PLANNED after knowledge-producing workflows stabilize**
- **Outcome:** governed `LessonLearned`, `BestPractice`, `TechnicalNote`,
  `Procedure`, `KnowledgeArticle` and `CaseStudy` concepts; project-closeout
  knowledge review; repeated-issue and recurring-root-cause detection; reviewed
  promotion from Lesson to Procedure, Checklist, System Control, Training or
  Partner Performance input; contextual discovery, acknowledgement and reuse/
  effectiveness tracking.
- **Prerequisites:** P1.3 search/DMS, P9.2 HSE/QA taxonomy and evidence, project
  closeout ownership, P9.3 partner metrics and notification/search capability.
- **Ownership/integration:** source domains retain case truth; Knowledge owns
  reviewed reusable publication/version. Derived recurrence is explainable and
  links every contributing case. Publishing a control/training/evaluation invokes
  that owning domain's ordinary approval, never generic mutation.
- **UI/security:** author/reviewer/publisher roles, source citations, sensitivity/
  audience, effective/review/expiry dates, related-context suggestions and reuse
  feedback. Any AI clustering/summarization remains governed by the deferred AI
  capabilities and cannot publish knowledge.
- **Testing:** provenance completeness, version immutability, permission/search
  isolation, recurrence reproducibility, promotion approval, expiry/review,
  retraction and reuse-metric lineage.
- **Effort / risk:** **L / High**.

## P10 — Reporting, reconciliation, and first production certification

### P10.1 Governed metrics and management reporting

- **Status / priority:** **PLANNED**
- **Outcome:** semantic metric catalogue, project/portfolio dashboards, scheduled
  reports/exports, saved views, source drill-through and freshness indicators.
- **Prerequisites:** stable authoritative transactions from P2-P8 and explicit
  metric owner/definition. A separate warehouse is not assumed.
- **Integration:** rebuildable read models, reconciliation controls and DMS/export.
- **UI/testing:** Persian RTL dashboards, accessible charts and table fallback,
  currency/unit/period clarity; tie-out, lineage and permission tests.
- **Effort / risk:** **L / High**.

### P10.2 Reconciliation and close workbench

- **Status / priority:** **PLANNED / release-critical for affected modules**
- **Outcome:** estimate-budget, commitment, PO-receipt-invoice, inventory value,
  subledger-GL, bank, claim-settlement and asset reconciliations; plus Employee
  Insurance List-to-payroll, payroll/insurance liabilities-to-Accounting,
  payroll/insurance payments-to-Treasury, Treasury bank/cash-to-GL, and contractor
  insurance/clearance-to-Contract/AP/Accounting reconciliation. Every exception
  has aging, assignment, resolution evidence and reopen controls.
- **Project closeout:** coordinate a status/checklist view over domain-owned
  contract closeout, outstanding claims/issues, document completeness,
  asset/material disposition where relevant, financial reconciliation, reviewed
  lessons learned/knowledge, and final project-performance reporting. This is not
  a generic closeout engine and does not duplicate domain balances or documents.
- **Prerequisites:** each producer/consumer pair stable; workflow foundation;
  closeout evidence from Contracts, DMS, Inventory/Equipment, P9.5 Knowledge and
  affected financial domains.
- **Data:** discrepancies are evidence-backed exceptions, not alternate balances.
- **UI/testing:** exception-driven workbench and drill-through; deliberately
  injected mismatch, rebuild and period-close acceptance tests.
- **Effort / risk:** **L / Critical**.

### P10.3 First production release certification

- **Status / priority:** **PLANNED / MUST**
- **Outcome:** certify only the explicitly selected release scope, not the entire
  long-term roadmap.
- **Prerequisites:** P0 gates; all MUST corrections affecting selected scope;
  legal/accounting/security approvals; reconciliations for every included
  financial flow.
- **Evidence:** clean build and locked dependencies, full PostgreSQL suite,
  migration and rollback rehearsal, restore test, RPO/RTO, performance budgets,
  tenant/object penetration review, storage/export/retention, observability and
  alert exercise, browser/mobile accessibility, runbooks, support/on-call,
  release/rollback decision owners.
- **Effort / risk:** **L / Critical**.

## Deferred until explicit triggers

| Capability | Trigger | Reason for deferral |
| --- | --- | --- |
| Controlled B2B network and intelligence | Mature party/qualification governance, consent/privacy ADR, verified relationships, sufficient opt-in density, abuse/moderation and legal/commercial operations | Preserve future tenant recommendations, supplier/subcontractor discovery, RFQ/tender network, equipment/capacity and surplus-material marketplaces, group procurement, consortium/JV discovery, shared qualification, consented trust/reputation network, anonymous benchmarking and anonymized price/lead-time/performance intelligence; high privacy, identity, competition, trust and cold-start risk keeps the program deferred |
| Shared canonical material/party catalogue with tenant overlay | Proven cross-tenant deduplication/search pain, catalogue stewardship, merge/dispute/version model and consent decision | P1.4 provides tenant catalogues first; cross-tenant identity/overlay creates ownership, privacy and incorrect-merge risk |
| Enterprise SSO/federated identity (OIDC/SAML) | Proven enterprise customer demand, approved IdP/account-linking and tenant-discovery model, recovery/offboarding controls, and accepted MFA/assurance policy | MFA remains an independent privileged-access control; integrate a trusted maintained identity implementation rather than custom-build OAuth/OIDC/SAML protocols |
| Broad offline-first synchronization | Measured field connectivity need, bounded data set, device-loss policy and deterministic conflict model | P9.1 may preserve local drafts; general bidirectional sync has high conflict/security/operational complexity |
| AI Support Assistant | P10 core production certification, stable P9.4 support and P9.5 knowledge authorities, approved AI privacy/residency/retention policy, evaluated retrieval quality and authorization-safe diagnostics | Preserve cited troubleshooting, safe diagnostic gathering and human escalation, but stabilize the support platform and authoritative knowledge first; AI cannot bypass permissions or finalize consequential actions |
| Future governed ERP Assistant | Stable P10 semantic/read-model APIs, P9.5 tenant knowledge, AI privacy/residency policy, evaluated accuracy and authorization-safe tool contracts | Preserve natural-language management queries, KPI explanation, tenant-knowledge queries and guided operations, but prohibit unrestricted SQL and autonomous consequential actions; authoritative data and controls must stabilize first |
| GIS and map platform | Verified logistics, geofencing, portfolio/site-risk or spatial-analysis use case plus privacy/accuracy policy | Lightweight project/site coordinates may be approved separately; heavy GIS infrastructure is unjustified without spatial workflows |
| Equipment GPS/telematics | Proven fleet-utilization, geofence, theft-control or automated-meter need; approved device/provider contract, consent/privacy, retention, accuracy and failure model | P8.2 provides governed manual/imported usage, meter and cost facts first; premature live telemetry adds integration, privacy and operational burden |
| Predictive AI/autonomous optimization | Stable governed data, measurable decision and human override | Current priority is authoritative data and traceability |
| Public/mobile API platform | Approved consumers, OAuth/security/version/SLA model | DRF is not required for current server-rendered product |
| Microservices/event sourcing | Demonstrated scaling/team/deployment boundary | Modular monolith is currently appropriate |

## Rejected / not recommended under the current product strategy

| Capability | Disposition and reason |
| --- | --- |
| General-purpose CRM, tenant-authored BPMN/code, or BIM authoring suite | **REJECTED.** These dilute construction ERP ownership, expand the attack/support surface, and duplicate specialist products. Integrate with approved systems when a concrete workflow requires it. |
| Custom cryptography, password primitives, OAuth/OIDC/SAML or other security protocols | **REJECTED.** Use trusted maintained implementations and platform/framework capabilities after security and license review. |
| Parallel workflow engines, financial ledgers, partner/material masters, document stores, or KPI authorities inside consuming domains | **REJECTED.** They violate the single-source-of-truth and reconciliation model. |
| Unrestricted SQL/chatbot access or autonomous consequential AI actions | **REJECTED.** Use permission-scoped semantic/read APIs, cited output, validation and explicit human confirmation through ordinary domain services. |
| Feature-by-feature microservices or event sourcing without demonstrated constraint | **NOT RECOMMENDED.** The modular monolith is the preferred boundary; reconsider only under the deferred trigger above. |

## Product-owner decision register

**P0-S03 decision status (2026-09-24):** the Product Owner explicitly accepted the
S02 recommendations and requested S03. See the
[approval evidence and accepted choices](docs/ROADMAP_EXECUTION_PLAYBOOK.md#s03-approval-evidence-and-current-decisions);
the [S02 comparisons](docs/ROADMAP_EXECUTION_PLAYBOOK.md#27-p0-s02-decision-packet-and-s03-handoff)
remain historical. Approval of direction does not supply unspecified parameters.

| ID | Decision | Current status | Remaining gate / comparison |
| --- | --- | --- | --- |
| P0-D01 | Initial customer segment | APPROVED | B: growing multi-project contractors; pilot/scale details open; [comparison](docs/ROADMAP_EXECUTION_PLAYBOOK.md#p0-d01-initial-customer-segment) |
| P0-D02 | Accounting/Treasury/AP/AR authority | APPROVED | A: native authorities; detailed ADR/professional review and package authorization still required; [comparison](docs/ROADMAP_EXECUTION_PLAYBOOK.md#p0-d02-financial-authority-boundary) |
| P0-D03 | Hosting, residency and operator | DIRECTION APPROVED; PARAMETERS OPEN | A: managed SaaS; residency/provider/operator before P0.2 implementation or data placement; [comparison](docs/ROADMAP_EXECUTION_PLAYBOOK.md#p0-d03-hosting-residency-and-operational-ownership) |
| P0-D04 | RPO/RTO and loss/outage tolerances | DIRECTION APPROVED; PARAMETERS OPEN | A: one recovery baseline; numeric objectives/scenarios before P0.2 recovery implementation or customer commitment; [comparison](docs/ROADMAP_EXECUTION_PLAYBOOK.md#p0-d04-recovery-objectives) |
| P0-D05 | SaaS packaging, entitlements and quotas | POLICY APPROVED; PARAMETERS OPEN | A: one core plan and external subscription administration; exact limits/lifecycle before P0.3 implementation, terms before sale; [comparison](docs/ROADMAP_EXECUTION_PLAYBOOK.md#p0-d05-saas-packaging-entitlements-and-quotas) |
| P0-D06 | Audit findings/priorities and separate implementation authority | FINDINGS/PRIORITIES APPROVED; IMPLEMENTATION NOT AUTHORIZED | Planning baseline/PPC priorities accepted; separately scoped package approval before application implementation; [comparison](docs/ROADMAP_EXECUTION_PLAYBOOK.md#p0-d06-audit-findings-priorities-and-implementation-authority) |

**P0-S03-Q04 decision status (updated by P0-G01 on 2026-09-27):** Product Owner selections
A1/B1/C1/D1/E1, revised F2, final G3 — Revised with Protected Operations, and H1 are recorded in the
[Q04 decision packet](docs/architecture/P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md).
The P0-S18 final accountable reviewer decision and independence override are
recorded; P0-S19 is historical pre-review evidence. Under the authoritative
Platform/Tenant identity policy, Azam Zerangzadeh is the real accountable reviewer
for Platform-level responsibilities and Tenant examples remain Seed/Test only.
P0-G01 records A/B/F as `accepted with conditions` and C/D/E/G/H as `revision
required`, with stable evidence references, review date, objections, conditions
and independence gaps in the
[P0-G01 evidence matrix](docs/architecture/P0_G01_Q04_ACCOUNTABLE_REVIEW_EVIDENCE_MATRIX.md#3-p0-g01-accountable-review-findings).
The same-person independent-challenge gap remains OPEN; F/G also retain applicable
external legal/compliance independence gaps. S07 and all other P0.1 ADRs remain
PROPOSED. The historical P0-G01 record did not authorize P1.1/P0.2/P0.3; the later
bounded P1.1 authorization and verified closeout above supersede that P1.1 status
without authorizing P0.2/P0.3 or accepting S07.
The authoritative role vocabulary is recorded in the packet and permission matrix;
the additional authoritative multi-role rule requires independent Tenant
Membership-scoped many-to-many role assignments, different role sets per Tenant,
permission union and audited independent assignment/revocation. P1.1 has now
implemented that rule through membership-scoped assignments while retaining the
single-role Membership fields only as compatibility data; later packages remain
separately governed.

**Confirmed direction:** the Product Owner's explicit P0-S02 instruction places
advanced AI, B2B network, GPS/telematics, GIS, enterprise SSO, broad offline work and
architectural distribution after the core. This confirms sequencing, not a reduced
core or a frozen release scope; approval evidence is recorded in the packet.

**P1-S14 Q01/Q02 status (revised 2026-09-29):** D14-04 through D14-09 record the
Product Owner's IRR/no-FX, UTC/ISO plus Jalali UI, explicit fiscal calendar,
versioned precision-category, no-current-financial-valuation, export-only and
official-source-hierarchy decisions. Revised D14-10 makes professional review
optional policy-version evidence, not an authority or global gate; revised
D14-11 is closed as a global development gate. Actual official source versions
and regulated/accounting values remain absent, so each affected activation must
remain unset/inactive and fail closed. See the
[P1-S14 decision record](docs/architecture/P1_S14_REMAINING_DECISION_PACKET.md#5-post-decision-gate-reassessment).

Remaining phase-gated choices/parameters are tracked in the
[S03 open-input register](docs/ROADMAP_EXECUTION_PLAYBOOK.md#unresolved-parameters-and-latest-gates):
pilot scale/owners; actual legal/accounting source versions, qualified independent
review evidence and professional acceptance; payroll employment/pay models and attendance
providers; document signature/retention rules; hosting/data residency/operator and
numeric RPO/RTO; Q04 review outcomes/evidence and the recorded reviewer-concentration risk; exact SaaS limits, lifecycle, pricing and
external invoicing operator. Other existing decisions remain: BOQ/price-book licensing,
coefficient and import-template policy; material coding/catalogue stewardship;
external portal identity/onboarding; electronic-signature legal/provider scope;
enterprise SSO trigger and IdP/account-linking/MFA policy; notification channels
including any SMS use; contractual claim/change/EOT governance; project-closeout
acceptance ownership; GIS/offline/media/equipment-telematics scope; AI provider/
data-residency/tool permissions; and future network consent/business model. The
[bounded Q04 packet](docs/architecture/P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md)
records the current selections, revisions, rationale, accountable-review
requirements and latest gates for the project/site authorization cluster. Reviewer
assignment and independence override are recorded in P0-S18; P0-S19 preserves
every unprovided review field as OPEN and the concentration and external-
independence risks remain explicit. These are decision gates, not reasons to
invent defaults.

## Roadmap governance

- `ROADMAP.md` governs delivery order and status, not detailed domain rules.
- The capability/readiness audit explains why; dedicated architecture documents
  define how after approval; models/migrations/tests define what exists.
- Update status only after implementation and acceptance evidence. Do not use a
  dated status snapshot as current authority.
- A future item remains unimplemented even when its target model is named here.
- Reuse commodity technical capability and own strategic ERP logic. Apply the
  Build-vs-Reuse order and dependency criteria in the mandatory delivery contract;
  no named candidate or roadmap entry pre-approves a package.
- Every accepted capability must remain scheduled in one work package, explicitly
  deferred with a trigger, or rejected/not recommended with a reason. Reconcile
  coverage when target-scope documents or product decisions change.
- Preserve unrelated working behavior. Use the pre-production window only for
  corrections with concrete ownership, integrity, security, compliance, or
  unavoidable future migration value.
