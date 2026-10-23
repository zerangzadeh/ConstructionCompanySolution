# BONIRA UI/UX Audit Charter

## 1. Mission

Evaluate whether BONIRA V1 is understandable, coherent, efficient, predictable, and usable enough for reliable role-based Product Owner review and subsequent Verification/UAT.

This is a **product UI/UX audit**, not a cosmetic redesign exercise.

The primary concern is whether a business user can understand:

- where they are;
- what the page is for;
- what they can do;
- what they should do next;
- what information is required;
- what state the business object or process is in;
- what the result of an action will be.

## 2. Audit baseline

Authoritative audit baseline:

- Repository: `zerangzadeh/ConstructionCompanySolution`
- Branch: `main`
- Commit: `43ac319c6e73e48ca9626461b73987922c498ec3`
- Local Product Owner path: `E:\Construction_Company_Solution`

See `UIUX_AUDIT_BASELINE.md`.

## 3. Why this audit exists

V1 implementation through `CEP-068` is complete, but Product Owner review identified repeated UI/UX patterns that can obstruct reliable business testing.

Observed risk patterns include, but are not limited to:

- technical or governance terminology leaking into operational UI;
- internal domain/workflow commands exposed directly as user actions;
- excessive manual data entry;
- fields that could potentially be inferred, defaulted, or hidden;
- inconsistent interaction patterns across similar pages;
- weak action hierarchy;
- weak workflow guidance;
- unclear distinction between current state, next action, and exceptional action;
- weak empty/error/unauthorized states;
- inconsistent task framing;
- forms that appear model-oriented rather than task-oriented.

These observations are **audit hypotheses**, not universal findings until verified systematically.

## 4. Audit objectives

The audit shall:

1. inventory user-facing V1 surfaces;
2. classify surfaces by module, route, page type, role, and primary user task;
3. identify UI/UX defects and recurring root patterns;
4. distinguish presentation debt from suspected domain/business defects;
5. identify inconsistencies across modules;
6. evaluate form complexity and data-entry burden;
7. evaluate terminology and user-facing language;
8. evaluate workflow/task guidance;
9. evaluate role-aware experience;
10. evaluate Persian-first, RTL, Jalali, responsive, and accessibility behavior where observable;
11. produce standards and a bounded remediation backlog;
12. establish whether BONIRA is ready for role-based UAT after remediation;
13. validate materially distinct operational, managerial, tenant-administration, platform-administration and document-control personas rather than treating broad privileged users as universal representatives.

## 5. Audit scope

### In scope

- application shell and navigation;
- dashboards and workspaces;
- list, detail, create, edit, review, approval, and workflow surfaces;
- search, filters, pagination, breadcrumbs, tabs, modals, notifications, and status presentation;
- forms and field behavior;
- empty, error, unauthorized, disabled, pending, approved, rejected, and archived states;
- user-visible terminology;
- action hierarchy;
- user guidance and contextual help;
- cross-module interaction consistency;
- role-aware presentation;
- employee self-service surfaces;
- administration surfaces where they are part of the operational product experience;
- Tenant Owner, Tenant Admin and Platform Admin experiences as distinct authority/persona shapes;
- Project Manager oversight and exception-oriented experience;
- document-control/versioning/linking experience;
- responsive/accessibility observations relevant to V1 product use.

### Out of scope unless separately authorized

- changing business rules;
- changing domain semantics;
- changing source-of-truth ownership;
- changing permissions or authority boundaries;
- changing tenant isolation;
- changing workflow semantics merely to simplify UI;
- database/schema/migration changes;
- Production deployment/cutover;
- re-accepting or reopening historical CEPs solely because UI debt exists;
- replacing Verification/UAT with this audit.

## 6. Audit principles

### 6.1 Task-first, not model-first
A page should be organized around the user's task, not around the database or internal service model.

### 6.2 Minimum necessary input
For every user-editable field, determine whether it should instead be system-derived, context-derived, defaulted, read-only, progressively disclosed, or removed from the normal path.

### 6.3 Business language over implementation language
Internal identifiers, technical state names, governance terminology, framework concepts, and command names should not appear in normal operational UI unless they provide real user value.

### 6.4 Predictable interaction
Equivalent actions should behave consistently across modules.

### 6.5 State-aware actions
The UI should emphasize the valid next action for the current state and avoid presenting exceptional or invalid actions as peers.

### 6.6 Progressive disclosure
Advanced, rare, technical, or exceptional controls should not dominate ordinary task execution.

### 6.7 Explain the next step
Empty states, warnings, and process pages should help the user understand what to do next.

### 6.8 Consistency before novelty
Shared product patterns take precedence over page-specific inventions.

### 6.9 Do not hide domain defects with UI changes
When a finding suggests a problem in domain logic, workflow rules, permissions, or source-of-truth semantics, classify it separately for domain review.

### 6.10 Form intelligence and data reuse
Do not ask users to re-enter data that is already known from the authenticated user, active organization/context, parent record, or selected business object. Prefer authorized selection from existing data, cascade dependent choices early, default safely when context is known, and keep server-side authorization and relationship validation authoritative.

### 6.11 Home / Dashboard experience
Evaluate Home and dashboards for role awareness, task priority, attention signals, visual hierarchy, actionability, and enterprise professionalism. Product Owner design drafts may be used as reference evidence but are not mandatory pixel specifications.

### 6.12 Route candidate is not screen proof
The surface inventory begins from routes, but POST-only actions, exports, media endpoints and redirect-only actions are not rendered screens. Reclassify them when source/runtime evidence proves their actual behavior.

### 6.13 Persona separation and authority realism
Runtime persona coverage must reflect materially different user goals and authority shapes.

At minimum, distinguish:

- ordinary tenant user;
- operational project user;
- Project Manager;
- Tenant Owner;
- Tenant Admin;
- Platform Admin;
- specialist operational personas;
- Document Controller;
- Payroll Specialist;
- Personnel Decree / Employment Records Specialist;
- Inventory / Storekeeper;
- Contracts & Commercial Specialist;
- Project Controls / Technical Office Specialist;
- Quality / QA-QC Specialist;
- External Supplier / Partner Portal User;
- employee self-service;
- accessibility-oriented validation.

`Tenant Owner ≠ Tenant Admin ≠ Platform Admin`.

The same person may hold multiple real roles, but the audit must not use a broad privileged account
as a universal substitute for least-privileged personas. Persona names never create product authority;
runtime authorization is proven only by actual membership, permission and scope evidence.

## 7. Audit dimensions

| Dimension | Core question |
| --- | --- |
| Information architecture | Can users locate the capability and understand where it belongs? |
| Navigation | Is movement through the product predictable? |
| Interaction consistency | Do equivalent controls and page types behave consistently? |
| Form UX | Is input minimal, understandable, and appropriately grouped? |
| Terminology | Does the UI use clear business language consistently? |
| Workflow UX | Is current state, next action, and process progression clear? |
| Role-aware UX | Do materially distinct personas (ordinary, project manager, Owner, Tenant Admin, Platform Admin, specialists, ESS) receive the right task-oriented experience without authority conflation? |
| State design | Are empty/error/pending/disabled/unauthorized states useful? |
| Localization | Is Persian-first RTL/Jalali behavior coherent and natural? |
| Accessibility/responsive | Is the experience usable across supported conditions? |

## 8. Finding categories

Initial taxonomy:

- `IA`
- `NAV`
- `CONSISTENCY`
- `FORM`
- `TERMINOLOGY`
- `WORKFLOW`
- `ROLE`
- `STATE`
- `SEARCH_FILTER`
- `LOCALIZATION`
- `ACCESSIBILITY`
- `RESPONSIVE`
- `VISUAL_HIERARCHY`
- `HELP`
- `SUSPECTED_DOMAIN`

The taxonomy may be calibrated during the pilot audit.

## 9. Severity model

### CRITICAL
The UI can cause or strongly enable destructive, financially material, security-sensitive, compliance-sensitive, or fundamentally incorrect user action, or prevents a critical task from being completed.

### HIGH
The user cannot reliably understand or complete an important journey, or has a substantial risk of choosing the wrong action.

### MEDIUM
The task is possible but materially confusing, inefficient, inconsistent, or unnecessarily difficult.

### LOW
Limited usability, presentation, wording, spacing, or polish issue with low operational impact.

Severity is based on user/business impact, not implementation effort.

## 10. Finding contract

Each finding should contain, where applicable:

- `finding_id`
- `module`
- `surface_id`
- `route`
- `page_title`
- `roles`
- `category`
- `severity`
- `problem`
- `evidence`
- `user_impact`
- `root_pattern_candidate`
- `recommendation`
- `business_logic_impact`
- `needs_domain_review`
- `related_cep`
- `related_standard`
- `status`

## 11. Audit method

### Phase 0 — Baseline
Freeze and record the audit baseline.

### Phase 1 — Surface Inventory
Create the authoritative `UIUX_SURFACE_CATALOGUE.yaml`.

### Phase 2 — Pilot Audit
Audit a representative set of high-value surfaces across different page types and modules.

### Phase 3 — Full Audit
Audit all material V1 user-facing surfaces using the calibrated model. Static review may use representative-pattern equivalence for low-variance sibling surfaces, but a route candidate is never silently treated as a rendered screen and representative equivalence never closes a finding or replaces runtime validation.

### Phase 4 — Root-pattern Analysis
Group individual findings into systemic root patterns and prefer shared remediation over repeated page-specific patches.

### Phase 5 — Standards
Produce or amend interaction, form, terminology, workflow, and reusable component/pattern standards.

### Phase 6 — Remediation Backlog
Convert approved findings/root patterns into bounded remediation packages.

### Phase 7 — UX Readiness Review
Re-evaluate the product after remediation and determine whether role-based UAT can begin reliably.

## 12. Required outputs

Planned canonical artefacts under `docs/governance/uiux/`:

- `UIUX_AUDIT_CHARTER.md`
- `UIUX_AUDIT_BASELINE.md`
- `UIUX_SURFACE_CATALOGUE.yaml`
- `UIUX_FINDINGS_REGISTER.yaml`
- `UIUX_ROOT_PATTERN_CATALOGUE.md`
- `UIUX_INTERACTION_STANDARD.md`
- `UIUX_FORM_DESIGN_STANDARD.md`
- `UIUX_TERMINOLOGY_DICTIONARY.md`
- `UIUX_WORKFLOW_UX_STANDARD.md`
- `UIUX_REMEDIATION_MASTER_BACKLOG.yaml`
- `UIUX_REMEDIATION_EXECUTION_PLAYBOOK.md`
- `UIUX_AUDIT_COMPLETION_REPORT.md`
- `CODEX_UIUX_REMEDIATION_HANDOFF.md`

Artefacts should be created only when they have substantive content.

## 13. Remediation governance

The audit itself does not authorize remediation.

Before a remediation package is executed, it should define scope, findings addressed, affected surfaces, allowed and forbidden change types, acceptance criteria, regression boundary, evidence requirements, and dependencies.

Codex must execute bounded remediation packages, not a vague instruction to "fix the whole UI".

## 14. Relationship to Verification/UAT

UI/UX remediation should precede final role-based UAT where UI ambiguity would otherwise make business-test outcomes unreliable.

UI/UX acceptance and UAT acceptance are separate. Neither substitutes for the other.

## 15. Product Owner authority

The Product Owner approves the audit scope and baseline, adjudicates product-language and user-experience decisions where required, approves the remediation backlog, and retains final authority over Product Acceptance.

## 16. Initial audit status

- Charter status: `ACTIVE_WORKING_CHARTER`
- Baseline: `43ac319c6e73e48ca9626461b73987922c498ec3`
- Surface inventory: `ROUTE_INVENTORY_COMPLETE_SCREEN_CONFIRMATION_IN_PROGRESS`
- Pilot audit: `COMPLETE`
- Full audit: `STATIC_PATTERN_COVERAGE_REVIEW_READY`
- Direct static-reviewed rendered-surface candidates: `102`
- Modules with direct static representation: `33/33`
- Confirmed non-screen action endpoints reclassified: `6`
- Runtime validation: `PLAN_FROZEN_EXECUTION_NOT_STARTED`
- Runtime execution playbook: `PREPARED`
- Runtime persona/data matrix: `PREPARED`
- Runtime entry status: `WAITING_FOR_RUNTIME_ENTRY_EVIDENCE`
- Remediation: `NOT_STARTED`
- UX Readiness: `NOT_EVALUATED`

## Persona coverage revision — Checkpoints 11–12

Two pre-runtime reviews corrected persona granularity before runtime execution.

Checkpoint 11 added:
- `P-15` Tenant Owner
- `P-16` Tenant Admin
- `P-17` Project Manager
- `P-18` Platform Admin
- `P-19` Document Controller

Checkpoint 12 added:
- `P-20` Payroll Specialist
- `P-21` Personnel Decree / Employment Records Specialist
- `P-22` Inventory / Storekeeper
- `P-23` Contracts & Commercial Specialist
- `P-24` Project Controls / Technical Office Specialist
- `P-25` Quality / QA-QC Specialist
- `P-26` External Supplier / Partner Portal User

Checkpoint 12 also narrows several previously over-broad personas:
`P-04` Equipment/Fleet, `P-07` Billing/Claims/AP-AR, `P-08` HR Operations,
`P-10` Timekeeping, and `P-11` HSE/Safety.

The audit now carries 26 runtime persona archetypes and 33 audit-specific runtime scenarios.

These corrections do **not**:
- rerun the static audit;
- change the 108 existing static findings;
- create BONIRA product roles or permissions;
- authorize remediation;
- execute CEP-078 or CEP-079.

## Reference persona retention decision — Checkpoint 13

Human Product Decision Authority approved persistent reference personas.

Once provisioned, a BONIRA UI/UX reference persona:

- is retained for future validation/regression use;
- is not deleted or automatically deactivated merely because a wave completed;
- does not require a Persian display title; a stable persona/account identifier is sufficient;
- must be discoverable in a governed administrative/reference-persona UI;
- keeps traceable role/scope mapping;
- must not expose credentials/secrets;
- must not gain broader authority merely to force a scenario to PASS.

`Persona ≠ Role`

A reference-persona UI does not imply or authorize impersonation.

Canonical policy:
`UIUX_REFERENCE_PERSONA_RETENTION_POLICY.md`

Canonical catalogue:
`UIUX_REFERENCE_PERSONA_CATALOGUE.yaml`


## Reference persona display amendment — Checkpoint 14

The prior requirement for a Persian display title is withdrawn.

Reference personas must remain persistent and discoverable for later reuse, but the product UI may
identify them by stable username, Persona ID, or another existing display name.

Persian labels in governance documents remain descriptive metadata only.

This amendment does not change the 26-persona catalogue, 33-scenario runtime plan, retention policy,
authorization boundaries, or prohibition on impersonation.


## Checkpoint 15 documentation reconciliation

Checkpoint 15 reconciles actual reference-persona aliases/readiness and supersedes older cleanup guidance
without rewriting historical evidence. Persona count, scenario count, authority model and static findings are unchanged.
