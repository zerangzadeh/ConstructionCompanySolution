# BONIRA UI/UX Runtime Validation Execution Playbook

## 1. Purpose

This playbook defines how to execute the audit-specific `UIUX_RUNTIME_VALIDATION_MATRIX.yaml`
after static pattern coverage has been frozen.

It is a **UI/UX audit procedure**. It is not Product remediation, not Production
Certification, not Human Sign-off, and not Representative UAT.

## 2. Governance boundary

The runtime audit intentionally overlaps some browser/accessibility topics owned by
`CEP-078`, but this document does not execute or close that CEP.

`CEP-078` requires its own canonical entry gate, external verification dependency,
runtime evidence and package manifests. Audit evidence created here must not be
renamed or promoted into CEP-078 evidence after the fact.

Likewise, `CEP-079` owns a canonical set of 44 representative UAT scenarios. The 33
UI/UX audit scenarios are a separate product-usability validation set and do not
replace or reduce those UAT scenarios.

The governing rule for this audit is:

> observe → capture evidence → classify → do not silently remediate.

## 3. Entry gate

Do not start runtime execution until all five audit entry gates are checked:

1. `RV-GATE-00` baseline/build SHA is known.
2. `RV-GATE-01` non-production environment is reachable.
3. `RV-GATE-02` scenario personas are mapped to actual test identities and effective permissions.
4. `RV-GATE-03` required scenario data/states exist.
5. `RV-GATE-04` any mutations are safe, disposable or reversible.

Evidence capture readiness (`RV-GATE-05`) is already prepared by the audit artefacts.

If any required gate is not satisfied, record the scenario as `BLOCKED_ENVIRONMENT`,
`BLOCKED_TEST_DATA` or `UTV`. Do not invent data, permissions, workflow state or
production access to obtain a result.

## 4. Baseline drift rule

The static audit is pinned to:

`43ac319c6e73e48ca9626461b73987922c498ec3`

If the runtime environment uses a descendant build:

- record its exact SHA;
- compare whether material UI surfaces changed;
- if changes affect a target scenario, freeze a new UI/UX audit baseline and reconcile
  the affected static artefacts before treating the runtime result as authoritative.

Do not pretend screenshots from a different build prove the frozen baseline.

## 5. Persona rule

`UIUX_RUNTIME_PERSONA_DATA_MATRIX.yaml` defines **test archetypes**, not new BONIRA roles.

The runtime plan contains 26 persona archetypes. The following distinctions are mandatory:

- `P-15 Tenant Owner` is an executive/company-level persona, not Platform Admin.
- `P-16 Tenant Admin` is the tenant/local administration persona, not Tenant Owner by assumption.
- `P-17 Project Manager` is distinct from the field/project-operations persona.
- `P-18 Platform Admin` is a platform-level persona and must not be used as a shortcut for tenant scenarios.
- `P-19 Document Controller` owns the document/version/linking perspective and is not interchangeable with Knowledge curation.
- `P-20 Payroll Specialist` is distinct from `P-10 Timekeeping Specialist`.
- `P-21 Personnel Decree / Employment Records Specialist` is distinct from general HR operations and ESS self-view.
- `P-22 Inventory / Storekeeper` is distinct from `P-04 Equipment/Fleet`.
- `P-23 Contracts & Commercial Specialist` is distinct from Procurement Buyer and Billing specialist.
- `P-24 Project Controls / Technical Office Specialist` is distinct from Project Manager and site operations.
- `P-25 Quality / QA-QC Specialist` is distinct from `P-11 HSE/Safety`.
- `P-26 External Supplier / Partner Portal User` is an external boundary persona, not an ordinary tenant member.

One real human account may hold multiple authorities, but each runtime evidence record must state the **effective authority shape used for that journey**.

Before a scenario, record:

- test user alias;
- active organization;
- active Project/Site context where relevant;
- actual effective permission bundle/reference;
- relevant data object aliases.

Never use job title, visible navigation or a guessed role name as proof of authority.

## 6. Execution order

Execute in five waves. Checkpoint 12 adds functional personas and four targeted scenarios but does not create extra waves.

### Wave A — Shell, global behavior and authority administration
`RV-001` through `RV-005`, then `RV-023`, `RV-024`, `RV-026`, `RV-027`, `RV-033`.

Purpose: login, Home, navigation, global search, shared tables, accessibility landmarks,
Tenant administration, Platform/Tenant authority-boundary UX, and persistent reference-persona administration.

A blocked sub-target does **not** automatically block unrelated scenarios. Record it explicitly
and continue only where security, evidence integrity and environment reliability remain sound.

### Wave B — Form intelligence and operational selection
`RV-006`, `RV-008`, `RV-010`, `RV-012`, `RV-014`, `RV-019`.

Purpose: cascade filtering, context defaults, known-data reuse, source selection,
Jalali input and technical-field exposure.

### Wave C — Core business workspaces and specialist lifecycles
`RV-007`, `RV-009`, `RV-011`, `RV-013`, `RV-015`, `RV-017`, `RV-018`,
`RV-028`, `RV-029`, `RV-030`, `RV-031`, `RV-032`.

Purpose: Procurement, Inventory, Finance, HR, Timekeeping, Payroll, document control,
employment records, contracts/commercial, project controls and external supplier-portal journeys.

### Wave D — State-driven and knowledge/workflow experiences
`RV-016`, `RV-020`, `RV-021`, `RV-022`.

Purpose: ESS, separate HSE/Safety and Quality/QA-QC perspectives, Knowledge traceability
and Workflow administration.

### Wave E — Cross-role responsive sweep
`RV-025`.

Wave E uses representative surfaces, not every persona on every page. It must include evidence
across ordinary operational, managerial, tenant-admin, platform-admin, document-control,
Payroll, Inventory, Contract/Commercial, Project Controls, Quality and external-portal perspectives
where applicable and reachable.

Run Wave E only after representative target surfaces are stable enough to compare across
desktop/tablet/mobile viewports.

## 7. Viewports

Default evidence viewports:

- Desktop: `1440 × 900`
- Narrow desktop/tablet: `1024 × 768`
- Mobile: `390 × 844`

A scenario may add another viewport when the defect is breakpoint-specific, but do not
turn the audit into an arbitrary device zoo.

## 8. Evidence requirements

For each executed scenario create one or more `RV-EV-###` records using
`UIUX_RUNTIME_EVIDENCE_RECORD_TEMPLATE.yaml`.

Minimum evidence:

- exact runtime SHA;
- browser/version and viewport;
- persona and effective context;
- preconditions;
- steps;
- expected result;
- actual result;
- screenshots where visual/responsive state matters;
- keyboard/focus notes for accessibility scenarios;
- server authorization result when a protected operation is exercised;
- linked `UIUX-F-###` findings;
- explicit result.

Do not store passwords, session tokens, CSRF secrets, personal secrets or unnecessary
sensitive data in screenshots/evidence.

## 9. Result semantics

Use only:

- `PASS`
- `FAIL_UIUX`
- `FAIL_ACCESSIBILITY`
- `FAIL_RESPONSIVE`
- `FAIL_PERMISSION_OR_SCOPE`
- `NEEDS_DOMAIN_REVIEW`
- `NEEDS_PRODUCT_REVIEW`
- `BLOCKED_ENVIRONMENT`
- `BLOCKED_TEST_DATA`
- `BLOCKED_AUTHORIZATION_FIXTURE`
- `UTV`

A scenario is not `PASS` merely because the page renders.

For example, a cascade scenario is `PASS` only when:

- parent selection filters child choices;
- stale child selections are invalidated;
- empty/loading/error states make sense;
- manipulated unauthorized/mismatched IDs are still rejected server-side where applicable.

## 10. Finding discipline

If runtime confirms an existing finding, link evidence to it.

If runtime appears to disprove a finding, mark it `REVIEW_FOR_RECLASSIFICATION`.
Do not delete historical findings.

If runtime discovers a new product UI/UX defect, create the next `UIUX-F-###`.

If the observed problem could be a business/workflow/domain-rule defect, use
`NEEDS_DOMAIN_REVIEW` and stop short of redesigning the rule.

If a security/tenant/object-scope failure is observed, stop the affected scenario and
retain the minimum safe evidence. Treat it separately from cosmetic UI debt.

## 11. No-remediation rule

During runtime validation:

- do not edit templates;
- do not edit CSS;
- do not change forms;
- do not alter permissions;
- do not modify workflow rules;
- do not patch data merely to make a result pass.

Required repair becomes a later bounded remediation package.

## 12. Runtime closure

Runtime audit may be closed only when every scenario is one of:

- `PASS`
- evidence-backed failure
- explicit blocker
- explicit `UTV`

There must be no silently skipped scenario.

Runtime closure produces:

- updated `UIUX_FINDINGS_REGISTER.yaml`;
- updated `UIUX_ROOT_PATTERN_IMPACT_MAP.yaml`;
- `UIUX_RUNTIME_VALIDATION_RESULTS.yaml`;
- `UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md`.

Even then, `UX_READY_FOR_UAT` is a separate checkpoint and must not be inferred
automatically.

## 13. Persona and coverage reconciliation

After Wave E, produce a coverage reconciliation across:

`UI dimension × Persona × Module × State`

Each material coverage cell must be classified as one of:

- `DIRECT_RUNTIME_EVIDENCE`
- `REPRESENTATIVE_EQUIVALENCE`
- `STATIC_EVIDENCE`
- `BLOCKED`
- `UTV`
- `NOT_APPLICABLE`

If a material area remains unsupported, add only the minimum targeted delta scenario.
Do not inflate the suite merely to make every route unique.

The additions through `P-26`, `RV-032`, and the persistent reference-persona governance scenario `RV-033` are pre-runtime coverage corrections. They do not invalidate frozen static findings or reopen historical checkpoints.
It does not invalidate the frozen static findings and does not reopen historical checkpoints.

## 14. Reference persona retention

Reference personas are persistent governed validation identities.

After a scenario/wave completes:

- do not delete the persona account merely because testing completed;
- do not automatically deactivate the persona;
- retain a stable persona/account identifier; a Persian display title is not required;
- retain traceable membership/role/scope mapping;
- reset/reconcile credentials out-of-band if required;
- re-verify effective permissions/scope before future reuse.

Scenario-specific disposable records may still follow their owning-domain cleanup rules.

The reference-persona catalogue must eventually be visible through a governed administrative UI
with stable persona/account identifiers. The governance catalogue file alone does not satisfy that UI requirement.

No impersonation / `Login as` capability is authorized by this rule.


## 15. Historical evidence cleanup instructions

Historical preparation evidence may contain cleanup guidance that predates the persistent-reference-persona policy.

Do not rewrite historical evidence to make it appear that the later policy existed earlier.

Instead, Checkpoint 15 supersedes those instructions prospectively.

For reference persona accounts:

`RETAIN → RECONCILE → RESET SECRETS IF NEEDED → REVERIFY BEFORE REUSE`

Scenario-specific disposable domain records remain governed by their owning-domain cleanup rules.
