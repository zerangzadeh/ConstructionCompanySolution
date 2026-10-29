# Construction ERP — Persistent Agent Rules

## 1. Purpose and responsibility

BONIRA (بنیرا) is a multi-tenant SaaS platform for construction contractors with
a Full Construction ERP vision and a capability-level MVP commercial surface.
Each `Organization` is a tenant. Correctness, tenant isolation,
financial integrity, security, auditability, and domain-authority integrity are
non-negotiable.

This file is the concise persistent entrypoint for architecture, invariants,
authority boundaries, and repository rules that must always be true. Detailed
repository execution, Git, queue, validation, evidence, efficiency, and
communication controls are defined in
`docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md`. The procedure for one
or more serial CEPs is defined in `docs/ROADMAP_EXECUTION_PLAYBOOK.md`.

Development is incremental. Implement only authorized scope. Current-governed
non-production CEPs have standing bounded execution authority when their
canonical dependencies and gates are satisfied. A roadmap item, historical
phase, passing test, or completed CEP does not expand package scope or authorize
production action.

## 2. Authority map

- `docs/governance/CEP_PROGRAM_AUTHORITY.md` defines the source hierarchy and
  Human decision boundary.
- `Agents.md` defines persistent architecture, invariants, and entry rules.
- `docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md` defines detailed
  generic repository execution policy.
- `docs/ROADMAP_EXECUTION_PLAYBOOK.md` defines the procedural workflow for serial
  CEP execution and closeout.
- `docs/governance/cep/PROMPTS/CEP-xxx_EXECUTION_PROMPT.md`, verified through
  `docs/governance/cep/CEP_PROMPT_MANIFEST.yaml`, defines package-specific Scope,
  Acceptance Criteria, Definition of Done, migration impact, evidence, and stop
  conditions.
- `CEP_EXECUTION_REGISTRY.yaml` is the sole live CEP lifecycle, authorization,
  blocker, completion, UTV, Git-integration, Gate, and execution-frontier
  authority.
- `ROADMAP.md` defines delivery direction, dependency-ordered planning, program
  structure, and residual/future target scope; it does not authorize execution.
- CEP Completion Reports and cited evidence prove individual execution results;
  they do not define live program state.
- Product code, migrations, tests, and configured environment behavior define
  implementation reality.
- `docs/PROJECT_STATUS.md` contains dated snapshots and historical validation;
  never use it instead of current implementation evidence, the Registry, or the
  Roadmap.

Relevant architecture authorities include:

- `docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md` — frozen D1–D7
  positioning, capability exposure and release direction; not implementation authority.
- `docs/architecture/DOMAIN_MODEL.md`
- `docs/architecture/DATA_MODEL.md`
- `docs/architecture/BUSINESS_MODEL.md`
- `docs/architecture/USER_CAPABILITY_MAP.md`
- `docs/architecture/WORKFLOW_AND_PERMISSION_MATRIX.md`
- `docs/architecture/DOMAIN_AND_DATA_MODEL.md`
- `docs/architecture/TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md`
- `docs/architecture/BILLING_AND_PROGRESS_CLAIMS.md`
- `docs/architecture/WORKFLOW_OPERATIONS.md`
- `docs/architecture/web_stack_specification.md`
- `docs/ui-guidelines.md`

The earlier capability/readiness audit is retained at
`docs/architecture/history/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md` as historical
evidence, not current exposure or live readiness authority.

Read references progressively and only to the depth required by the task and its
material risks.

## 3. Product and repository architecture

- Apply the canonical D1–D7 strategy at capability level. MVP UI-hidden domains
  remain backend-active within existing contracts; do not remove apps, models,
  FKs, migrations, relationships, handoffs, workflows, resolvers or services for
  UI hiding. Additive MVP-gap design requires separate bounded implementation authority.
- Future UI exposure must follow one centralized Product Surface Exposure
  authority, including direct user-facing URLs and shared entry points. Its
  mechanism is not frozen. Gating never replaces authentication, authorization,
  tenant isolation, business permissions or object/project/site scope.
- Use a Python/Django modular monolith with lightweight Clean Architecture,
  PostgreSQL through Django's PostgreSQL backend and Psycopg 3, Django templates,
  Tailwind CSS, and HTMX only for useful small interactions.
- Django apps live in `apps/`, shared code in `core/`, project configuration in
  `config/`, and environment settings in
  `config/settings/{base,development,production}.py`.
- Keep app templates with their app and shared components in
  `templates/components/`.
- Use English for code, files, classes, variables, URL names, and database fields.
- Keep views thin. Put business workflows and multi-step operations in focused,
  type-hinted application services or use cases.
- Domain rules must not depend on HTTP, templates, or external services. Keep
  calculations and complex business logic out of templates.
- Prefer the Django ORM. Add repository abstractions only for a demonstrated
  need. Do not hide critical business behavior in Django signals.
- Keep cross-domain dependencies explicit and avoid circular imports. Introduce
  an app only with approved ownership, scope, lifecycle, and permissions.
- Reuse shared masters such as `BusinessParty`, materials, units, equipment, and
  expense categories rather than creating uncontrolled duplicates.
- Support small and large contractors through one model. Departments, positions,
  employees, teams, and enterprise structures remain optional.
- CRM, general-purpose BPM/BPMN, tenant-authored executable workflow code,
  microservices, and event sourcing remain out of scope unless explicitly
  approved.
- Accounting and Payroll have historical non-production baselines. Remediation,
  extension, downstream activation, production enablement, certification, or new
  behavior requires the applicable authorized CEP or other bounded Human
  Authorization.

## 4. Tenant isolation and lifecycle

- `Organization` is the tenant. Almost every business entity belongs to one
  organization, and tenant isolation fails closed.
- Never trust an organization identifier from a user, form, URL, request body,
  integration payload, or client state. Resolve the active organization through
  authenticated membership and governed session state.
- Scope every queryset, form, view, service, API, relationship validation,
  uniqueness rule, export, background operation, and integration to the active
  organization where applicable.
- Validate that related records share tenant and, where required, project/site
  context. Prevent and test cross-tenant reads and writes.
- Check active membership, tenant status, business permission, and object scope
  before reads and mutations. Re-check critical authorization inside the
  transaction.
- Organization creation and its initial owner membership must be atomic.
- Tenant lifecycle is controlled: `active` permits normal access; `suspended`
  blocks business mutations; `cancelled` blocks normal access while retention and
  export policies continue to apply.
- Enforce tenant status, plan limits, feature flags, and quotas server-side.
  Organization deletion, export, suspension, and other lifecycle actions must be
  audited and transactional.
- Tenant timezone, currency, fiscal settings, and numbering schemes come from the
  organization after configuration, not from ungoverned global defaults.

## 5. Authorization architecture

- Authorization denies by default. UI visibility is never authorization.
- Superuser and Platform Admin are distinct platform authorities. Tenant Owner,
  Tenant Admin / Local Admin, Tenant Manager, and other registered business roles
  are separate tenant authorities.
- Roles require explicit assignment and never imply one another. Effective tenant
  role assignments are membership-scoped and may be multiple where governed and
  implemented.
- Union active applicable role permissions, then intersect them with active tenant
  membership, business permission, object scope, tenant state, workflow authority,
  and protected-operation/separation policy.
- Project or site roles may restrict access but never expand tenant authority.
  Positions route responsibility; they never grant permission.
- Preserve legacy role fields only for governed compatibility. Do not restore an
  obsolete fixed single-role model or create a second permission system.
- Enforce object-level permission for sensitive view, edit, approval, archive,
  export, delete, posting, payment, and protected operations.
- Every new access-controlled capability requires a `BusinessPermissionCode`,
  registry entry, authorized catalog/default-grant migration where applicable,
  enforcement in services and views, and authorization/tenant-isolation tests.
- Audit privilege escalation, role changes, invitation acceptance, membership
  removal, and protected-operation decisions.

## 6. Workforce identity boundary

- MVP field-worker UI reuses `workforce` and `timekeeping`; no parallel `Worker`
  model/domain. MVP-02 delivers non-login field-worker `national_id` additively on
  tenant-owned `Person`, preserving explicit identity links and legacy Employee
  compatibility. Attendance, Timesheet and Overtime remain distinct.
- `User` is authentication identity.
- `Person` is tenant-owned human identity.
- `WorkRelationship` is the tenant-scoped, effective-dated work relationship.
- `Employee` and optional `Employee.user` are legacy/compatibility data where
  still used; do not assume cutover is complete.
- ESS and workforce access require explicit governed identity links. Never infer
  workforce identity from username, email, display name, or employee number.
- Position and team assignments are routing/filter evidence, not identities or
  implicit permissions. Retain effective assignment evidence when it qualifies an
  action.

## 7. Domain and financial authority

Preserve explicit source-of-truth ownership:

- Treasury = cash authority.
- Accounting = general-ledger authority.
- AP = payables authority.
- AR = receivables authority.
- Payroll = payroll authority.
- Inventory = stock and inventory-value authority.
- Project Controls = project-cost authority.

Reporting, reconciliation, dashboards, and other read models are projection
authorities only. They must identify source records, versions, tenant scope, and
cutoffs and must never become transaction, posting, settlement, inventory, or
payroll authorities.

Do not introduce parallel financial authority, silent posting paths, implicit
model-save-to-journal behavior, generic financial corrections, or competing
sources of truth. Separate budget, committed cost, actual cost, forecast, and
variance. Preserve organization/project/site/phase/contract/cost-center context
where required.

## 8. Data integrity and schema evolution

- Use `Decimal`, never `float`, for money. Use explicit units for material,
  labor, and equipment quantities and timezone-aware datetimes.
- Important records should use UUID public identifiers, timestamps, actor fields
  where applicable, archival/soft deletion where retention is required, and audit
  evidence for important actions.
- Enforce atomic invariants with database constraints and transactions. Use
  organization-scoped uniqueness and explicit concurrency control where needed.
- Store document and estimate revisions. Do not overwrite approved history.
- Preserve approved, posted, paid, completed, and other finalized history through
  revision, reversal, adjustment, void, or supersession—not silent edit or delete.
- Preserve working behavior unless an approved product change replaces it. For
  schema replacement, prefer expand → migrate/backfill → switch → validate →
  explicitly approved contract.
- Keep legacy compatibility fields until replacement deployment, migration or
  retention, dependency removal, invariant/tenant revalidation, and passing tests
  are complete. Removal still requires explicit approval.
- Every environment must run migrations against its configured database; never
  assume database currency. Migration preparation or development execution never
  implies production migration or cutover authority.

## 9. Workflow and approval invariants

- Every lifecycle defines states, valid transitions, authorized permissions,
  required fields, reversibility, and audit evidence: actor, time, prior/new state,
  and reason.
- Approval services use transactions, lock and re-read relevant state, and
  re-check authorization inside the transaction to prevent races.
- Domain models/services remain authoritative for business invariants. Workflow
  coordination calls registered domain services; it must not mutate domain state
  generically or synchronize critical state through signals.
- The platform owns registered step, condition, routing, and domain-command
  catalogs. Tenants own versioned declarative configurations assembled from that
  catalog.
- Definitions, versions, instances, steps, work items, candidates, delegations,
  and assignment history are tenant-scoped. Published definitions and completed
  runtime history are immutable.
- Acting requires active membership, required business permission, current
  assignment/candidacy, and configured separation rules.
- One active membership has one workbench per active organization. Multiple
  positions are routing/filter evidence, not separate identities.
- Starter workflows must work without workforce structures; position and project
  routing remain optional.
- Domain transition, work-item completion, next-step activation, and audit
  evidence commit atomically.
- Workflow behavior is bounded and declarative: no arbitrary tenant Python, SQL,
  templates, network callbacks, or unregistered expressions. Consuming domains
  must not create a second workflow/work-item mechanism.

## 10. Security, privacy, reliability, and audit

- Never hardcode secrets, credentials, tokens, or database connection strings.
  Read environment-specific values from environment variables.
- Production settings must reject insecure database or TLS configuration.
- Require authentication, authorization, tenant scope, and CSRF protection on
  every endpoint, including HTMX endpoints. Validate all input server-side.
- Treat uploads as untrusted. Validate type and size and retain tenant, uploader,
  type, size, and version metadata.
- Never expose internal identifiers or tenant data across boundaries. Keep logs,
  fixtures, screenshots, errors, and evidence free of secrets and unnecessary
  personal or sensitive data.
- Security and financial audit records are append-only at the application layer.
  Define retention/archival before hard deletion and support organization-scoped
  export where required.
- Wrap multi-step and externally visible workflows in `transaction.atomic()`.
  Make retryable operations idempotent, use unique business keys, handle
  concurrency explicitly, and prevent lost updates.
- External integrations fail safely and never bypass tenant or authorization
  checks. Structured logs must exclude secrets and use correlation/request
  identifiers when integrations or background work are introduced.
- Queues and scheduled jobs remain deferred until approved, but services must not
  assume every operation will always remain synchronous.

## 11. Frontend invariants

- MVP screens retain enterprise quality and zero critical technical leakage.
  The strategy's navigation/output targets and `MVP` / `FULL_ERP` verification
  profiles are requirements, not claims of runtime implementation. Preserve
  hidden-capability regression/UAT evidence; future exposure requires maturity,
  browser verification, isolation, applicable outputs and Human UAT.
- Follow `docs/ui-guidelines.md`. The product is Persian-first and RTL, with the
  approved design system shared by ERP UI and Django Admin.
- Use Tailwind utilities, reusable components, responsive mobile-first layouts,
  and HTMX only for small interactions that benefit from partial refreshes.
- HTMX endpoints enforce the same authentication, CSRF, permission, tenant, and
  object-scope controls as normal views.
- Keep presentation logic out of services and business logic out of templates.
  Avoid scattered custom CSS and inline styles.
- Hiding a control is never authorization; every operation is enforced server-side.

## 12. No-inference and scope controls

- Autonomy is the default. For current-governed non-production CEPs, the standing
  Human authorization applies when canonical identity, dependencies, gates,
  blockers, repository safety, and package Scope/AC/DoD permit execution.
- Escalate only for the material Human-decision triggers defined in the Execution
  Policy. Do not request a Human choice between technically equivalent safe
  options or create a separate decision audit for ordinary engineering choices.
- Codex may evaluate and record objectively defined technical, dependency,
  evidence, and readiness Gate PASS when all canonical requirements are proved
  and no material Human-decision trigger applies. Gate PASS never expands scope,
  activates Post-V1 work, or authorizes production.
- Only the Human Decision Authority may change Product Decisions, CEP Scope/AC/DoD
  or the dependency graph; accept material legal/business/financial/security or
  residual risk; authorize irreversible production action; issue Human Sign-off;
  or issue final Production Certification.
- Do not infer Product Decisions, business behavior, financial/posting rules,
  domain ownership, migration semantics, CEP Scope/AC/DoD, or dependency changes.
- Repository-local absence of a canonical source does not prove nonexistence;
  follow approved canonical recovery rules in the Execution Policy.
- Preserve fail-closed behavior: no approved policy means no invented business
  behavior; no approved producer contract means no Project Cost fact; no approved
  accounting-recognition owner means no inferred posting; no statutory evidence
  means no current statutory activation.
- A finding outside authorized scope is recorded with evidence, not silently
  absorbed into the task.
- Canonical prompts are immutable by default. Package-specific contract semantics
  remain authoritative. Current `Agents.md`, Execution Policy, and CEP Playbook
  govern generic mechanics. Unsafe classification stops with
  `BLOCKER-PROMPT-GOVERNANCE-CONFLICT` before product mutation.

## 13. Session bootstrap

Before product mutation:

1. For CEP-related work, read `CEP_EXECUTION_REGISTRY.yaml` and the relevant
   Roadmap section.
2. Ground the current branch, HEAD, upstream state, and dirty working tree.
3. Load and verify the applicable canonical contract and referenced sources.
4. Verify the standing or other applicable Human Authorization.
5. Verify applicable dependencies and gates without inference.
6. Follow `docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md`.
7. For CEP execution, follow `docs/ROADMAP_EXECUTION_PLAYBOOK.md`.

A single session may execute multiple eligible CEPs serially, with no fixed CEP
count. Do not stop merely because one CEP completes: close it out, synchronize the
Registry, evaluate objective gates, recalculate the frontier, and continue when
safe. Stop automatic continuation on a partial, failed, or blocked CEP, a material
Human-decision trigger, or a clean operational boundary. Detailed continuation
rules belong to the Execution Policy and CEP Playbook.

Preserve unrelated Human changes. Stop before mutation when authorization,
canonical identity, repository safety, tenant/security/financial integrity, or
required package semantics cannot be established.

## 14. Persistent engineering priorities

- Correctness and quality, data/financial integrity, security/tenant isolation,
  domain authority, auditability, and regulatory safety take precedence over
  speed, cost, token reduction, or convenience.
- Subject to those controls, minimize latency, compute/token cost, governance
  overhead, operational complexity, change blast radius, and unnecessary churn.
- Use the smallest sufficient evidence; never weaken a required PASS or material
  safety control for efficiency.
- Prefer mature existing capability for commodity infrastructure and focused,
  license-compatible libraries for commodity UI when they materially improve
  usability or maintainability. Avoid unnecessary dependencies; preserve Django
  Templates + Tailwind + HTMX and BONIRA-owned strategic ERP business logic.
  `docs/ui-guidelines.md` owns the practical frontend selection policy.
- Do not add a dependency without clear purpose and appropriate authorization.
  Never custom-build cryptographic, password, OAuth/OIDC/SAML, or similar security
  primitives when trusted implementations exist.
- Preserve performance, scalability, concurrency safety, maintainability,
  testability, backward compatibility, reversibility, and recoverability.

## 15. Codex communication discipline

- Use strict token discipline in every Codex session.
- Do not narrate routine reasoning, file reads, searches, commands, or ordinary
  implementation steps.
- Intermediate working updates are event-driven, delta-only, and normally no
  more than 3 lines.
- Emit an intermediate update only for a material finding, blocker, failed test,
  scope/dependency issue, governance conflict, Human-required decision, or other
  material exception.
- Do not repeat repository context, governance already loaded from canonical
  sources, prior findings, or completed work.
- Prefer compact status summaries such as `Focused tests: 12/12 PASS`.
- Keep required detail in repository evidence and the final compact completion
  report; token reduction must never weaken required evidence, safety controls,
  or truthful status reporting.

Principle: silent on routine work; explicit on material exceptions.

Detailed execution mechanics, Git permissions, CEP queues, validation and
regression attribution, evidence requirements, completion-state semantics,
blocked-work handling, resource efficiency, build-vs-reuse evaluation, and
detailed communication mechanics belong to the Execution Policy and CEP Playbook.
