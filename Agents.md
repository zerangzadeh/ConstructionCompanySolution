# Construction ERP — Agent Instructions

## 1. Scope and authoritative references

This repository is a complete-product, multi-tenant SaaS platform for construction
contractors. Each `Organization` is a tenant; strict tenant isolation is
non-negotiable. Development is incremental: implement only the requested and
approved scope. A planned roadmap item is not implementation authorization.

Use references progressively; read only those relevant to the task:

- `ROADMAP.md`: delivery order, implementation status, and approved next scope.
- `docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`: repository-wide
  current/target capability assessment, ownership gaps, pre-production correction
  register, and production-readiness gates.
- `docs/architecture/DOMAIN_MODEL.md`: target domain ownership and boundaries.
- `docs/architecture/DATA_MODEL.md`: target source-of-truth, history, relationship,
  lineage, and conceptual-data rules.
- `docs/architecture/BUSINESS_MODEL.md`: product positioning, customer value,
  packaging direction, operating model, success measures, and non-goals.
- `docs/architecture/USER_CAPABILITY_MAP.md`: user groups, goals, capability
  coverage, and access-layer expectations; not an authorization grant source.
- `docs/architecture/WORKFLOW_AND_PERMISSION_MATRIX.md`: cross-domain lifecycle,
  permission, object-scope, responsibility, and separation policy.
- `docs/architecture/DOMAIN_AND_DATA_MODEL.md`: domain ownership, relationships,
  invariants, lifecycle states, and approved future concepts. Models and migrations
  remain the schema source of truth.
- `docs/architecture/TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md`: workflow/work-item
  architecture, migration slices, and acceptance gates.
- `docs/architecture/BILLING_AND_PROGRESS_CLAIMS.md`: billing and progress-claim
  architecture and delivery decisions.
- `docs/architecture/WORKFLOW_OPERATIONS.md`: workflow operations, recovery, and
  deployment checks.
- `docs/ROADMAP_EXECUTION_PLAYBOOK.md`: rolling session decomposition and
  model/reasoning guidance for approved roadmap work; it is not a scope or status
  authority and must be recalibrated at phase boundaries.
- `docs/ui-guidelines.md`: Persian-first RTL UI and Django Admin rules.
- `docs/architecture/web_stack_specification.md`: detailed stack and layer
  responsibilities.
- `docs/PROJECT_STATUS.md`: dated snapshots and historical validation records;
  never use it instead of current code, migrations, tests, or `ROADMAP.md`.

## 2. Stack and repository conventions

- Python/Django modular monolith with lightweight Clean Architecture.
- PostgreSQL 18.6 via Django's PostgreSQL backend and Psycopg 3.
- Django templates, Tailwind CSS, and HTMX only for useful small interactions.
- `pytest`/`pytest-django` and Ruff.
- DRF, Celery, and Redis are future capabilities unless explicitly approved.
- Do not add packages without a clear purpose and explicit approval.
- Django apps live in `apps/`; shared code in `core/`; project configuration in
  `config/`; environment settings in `config/settings/{base,development,production}.py`.
- Keep app templates with their app and shared components in
  `templates/components/`.
- Use English for code, files, classes, variables, URL names, and database fields.

## 3. Architecture and domain boundaries

- Keep views thin. Put business workflows and multi-step operations in small,
  focused, type-hinted application services/use cases.
- Domain rules must not depend on HTTP, templates, or external services. Keep
  calculations and complex business logic out of templates.
- Prefer the Django ORM. Add repository abstractions only for a demonstrated need.
- Do not hide critical business logic in Django signals.
- Validate authorization and tenant scope at service boundaries and, where
  appropriate, at view boundaries.
- Keep cross-domain dependencies explicit and avoid circular imports. Introduce a
  new app only with approved ownership, scope, lifecycle, and permissions.
- Reuse shared masters (`BusinessParty`, materials, units, equipment, expense
  categories) instead of creating uncontrolled duplicates.
- `User` is authentication identity; `Employee` is workforce data and
  `Employee.user` may be null. Positions route responsibility but never grant
  permission.
- Support small and large contractors with one model; departments, positions,
  employees, teams, and other enterprise structures must remain optional.
- General-ledger accounting and payroll are approved target roadmap domains but
  are not implementation-authorized until their work packages are approved. CRM,
  general-purpose BPM/BPMN, tenant-authored executable workflow code,
  microservices, and event sourcing remain out of scope unless explicitly approved.

## 4. Tenant isolation, lifecycle, and authorization

- Almost every business entity must belong to an `Organization`.
- Never trust an organization identifier from a user, form, URL, or request body.
  Resolve the active organization through authenticated membership and session
  state.
- Scope every queryset, form, view, service, future API, relationship validation,
  and uniqueness constraint to the active organization where applicable.
- Check membership status, tenant status, role, and required business permission
  before reads and mutations. Prevent and test cross-tenant reads and writes.
- Organization creation and its initial owner membership must be atomic.
- Tenant lifecycle is controlled: `active` permits normal access; `suspended`
  blocks business mutations; `cancelled` blocks normal access while retention and
  export policies continue to apply.
- Enforce tenant status, plan limits, feature flags, and quotas server-side.
  Organization deletion/export/suspension must be audited and transactional.
- Tenant timezone, currency, fiscal settings, and numbering schemes come from the
  organization after configuration, not global defaults.
- Authorization denies by default. Organization roles include `OWNER`, `ADMIN`,
  `MANAGER`, `ACCOUNTANT`, `SUPERVISOR`, and `VIEWER`; project/site roles may only
  further restrict access.
- Enforce object-level permissions for sensitive view, edit, approval, archive,
  export, and delete actions. UI visibility is never authorization.
- For every new access-controlled capability, add a `BusinessPermissionCode`,
  register it in `permission_registry`, add a data migration for the catalog and
  default-role grants, enforce it in views and services, and test authorization
  and tenant isolation.
- Audit privilege escalation, role changes, invitation acceptance, and membership
  removal. Use existing membership and active-organization services; do not create
  a second permission model.

## 5. Data, finance, and schema evolution

- Important records should use UUID public identifiers, timestamps, actor fields
  where applicable, archival/soft deletion where retention is required, and audit
  logging for important actions.
- Use `Decimal`, never `float`, for money. Use explicit units for material, labor,
  and equipment quantities and timezone-aware datetimes.
- Enforce atomic invariants with database constraints and transactions. Use
  organization-scoped uniqueness and `select_related`/`prefetch_related` where
  needed.
- Separate budget, committed cost, actual cost, forecast, and variance. Aggregates
  must identify their source records and organization scope.
- Preserve organization/project/site/phase/contract/cost-center hierarchy where
  required. Validate that related records share both tenant and project context.
- Store document and estimate revisions; do not overwrite approved history.
- Preserve approved, posted, paid, and other finalized history through revision,
  reversal, adjustment, void, or supersession—not silent edits or deletion.
- Preserve working behavior unless an approved product change replaces it. For
  schema replacement, prefer expand → migrate/backfill → switch → validate →
  explicitly approved contract.
- Keep legacy compatibility fields until replacement deployment, data migration or
  retention, dependency removal, invariant/tenant revalidation, and passing tests
  are complete; removal still requires explicit approval.
- Every environment must run migrations against its configured database; never
  assume a database is current.

## 6. Workflow and approvals

- Every lifecycle defines states, valid transitions, authorized roles/permissions,
  required fields, reversibility, and audit evidence (actor, time, previous/new
  state, and reason).
- Approval services must use transactions, lock/re-read relevant state, and
  re-check authorization inside the transaction to avoid races.
- Domain models/services remain authoritative for business invariants. Workflow
  coordination calls registered domain services; it must not mutate domain status
  generically or synchronize critical state through signals.
- The platform owns registered step, condition, routing, and domain-command
  catalogs; tenants own versioned configurations assembled from that catalog.
- Workflow definitions, versions, instances, steps, work items, candidates,
  delegations, and assignment history are tenant-scoped. Published definitions and
  completed runtime history are immutable.
- Acting requires an active `OrganizationMembership`, the required
  `BusinessPermission`, current assignment/candidacy, and configured separation
  rules. Position-based actions must retain the qualifying effective assignment as
  historical evidence.
- One active membership has one workbench per active organization. Multiple
  positions are routing/filter evidence, not separate identities.
- Starter workflows must work without workforce structures. Position and project
  routing remain optional.
- Domain transition, work-item completion, next-step activation, and audit evidence
  must commit atomically. Publication validates graph, scope, permission, routing,
  fallback, and domain transitions deterministically.
- Workflow behavior is bounded and declarative: no arbitrary tenant Python, SQL,
  templates, network callbacks, or unregistered expressions. Consuming domains
  must not create a second workflow/work-item mechanism.
- For procurement compatibility and migration behavior, consult the current
  services/tests plus the workflow architecture and roadmap; preserve existing
  audit history and finalized records.

## 7. Security, privacy, and governance

- Never hardcode secrets, credentials, tokens, or database connection strings;
  read environment-specific values from environment variables.
- Production settings must reject insecure database or TLS configuration.
- Keep authentication, authorization, organization scope, and CSRF protection on
  every endpoint, including HTMX endpoints. Validate all input server-side.
- Treat uploads as untrusted. Validate file type and size and retain tenant,
  uploader, type, size, and version metadata.
- Do not expose internal identifiers or tenant data across boundaries.
- Audit records for security and financial actions are append-only at the
  application layer. Define retention/archival before hard deletion and support
  organization-scoped export when required.
- Keep logs, fixtures, screenshots, and errors free of secrets and unnecessary
  personal/sensitive data.

## 8. Reliability and integrations

- Wrap multi-step and externally visible workflows in `transaction.atomic()`.
- Make retryable operations idempotent, define unique business keys, handle
  concurrency explicitly, and prevent lost updates.
- External integrations must fail safely and never bypass tenant checks. Keep
  structured logs free of secrets; add correlation/request identifiers when
  introducing integrations or background jobs.
- Queues and scheduled jobs remain deferred until approved, but services should
  not assume every operation will always be synchronous.

## 9. Frontend

- Follow `docs/ui-guidelines.md` for UI/Admin work. Use Tailwind utilities,
  reusable template components, responsive mobile-first layouts, and the approved
  Persian-first RTL design system; avoid scattered custom CSS and inline styles.
- Use HTMX only for small interactions that benefit from partial refreshes and
  enforce the same auth, CSRF, permissions, and tenant isolation as normal views.
- Keep presentation logic out of Python services and business logic out of
  templates.

## 10. Working process and validation

Before implementing a feature:

1. Inspect the relevant project structure and code.
2. Briefly state the plan and files to create or modify.
3. Implement only the requested scope; do not combine unrelated roadmap work.
4. Add unit tests for business/service rules and integration tests for permissions,
   organization scope, and tenant isolation as applicable.
5. Run the smallest relevant checks, expanding when risk or failures require it:
   `python manage.py check` after Django/config changes, relevant
   `python -m pytest`, and Ruff check/format when available.
6. Complete documentation closeout: identify which authoritative active documents
   are affected by the task and update them in the same change. Reconcile current
   implementation status, target direction, roadmap disposition, lifecycle,
   permissions, data ownership, operations, and UI standards only where the task
   materially changes them. Do not create duplicate status/snapshot documents.
7. Report changed files, test results, documentation updates (or explicitly state
   that none were required), assumptions, and follow-up work.

Preserve unrelated user changes in a dirty worktree. Do not rewrite unrelated
files or create branches, commits, pushes, pull requests, or remote changes unless
explicitly requested.

## 11. Token, time, and execution efficiency

Treat the user's token allowance and elapsed time as finite project resources.
Accuracy and safety remain mandatory, but unnecessary work is not evidence of
thoroughness.

- Every read, search, tool call, test, status update, and generated document must
  have a concrete purpose tied to the requested outcome or a material risk. Skip
  actions whose expected information or assurance does not justify their token,
  time, or compute cost.
- Use progressive disclosure: start with `rg`, file lists, headings, diffs, and
  narrow line ranges. Do not dump large files, test collections, logs, or command
  output when a filtered summary answers the question.
- For roadmap execution sessions, follow the C0/C1/C2 minimum-sufficient-context
  policy in `docs/ROADMAP_EXECUTION_PLAYBOOK.md`: load the session contract and
  direct implementation evidence first, expand only for a recorded material-risk
  trigger, and never trade away an invariant or acceptance criterion to save tokens.
- Inspect only relevant code and references. Do not restate the full prompt,
  duplicate the same analysis across documents, or repeat evidence already
  established. Keep one authoritative explanation and link to it elsewhere.
- Choose the smallest validation proportional to the change. Documentation-only
  work normally needs link/reference checks, stale-claim searches, whitespace or
  formatting checks, and review of the changed documents. Do not run the full
  application test suite for documentation-only changes unless the user explicitly
  requests it or a concrete executable/configuration risk justifies it.
- For code changes, begin with targeted tests and expand only when affected
  boundaries, failures, or release risk require it. Do not run both broad and
  overlapping validations without a stated reason.
- Before a materially expensive action—such as broad web research, repository-wide
  analysis, full test suites, large rendering/generation jobs, or long-running seed
  tests—state its purpose and expected cost. If a lower-token or faster action can
  provide adequate confidence, inform the user and use/recommend that option.
- Whenever a meaningful token-saving approach is available, tell the user
  concisely, including any quality or coverage tradeoff. If it has no material
  downside, take the efficient approach without blocking for confirmation; if it
  reduces required quality or safety, request the user's decision.
- Avoid frequent polling and repetitive progress messages. Use the longest safe
  wait supported by the tool, report only meaningful state changes, and keep tool
  output capped. Waiting itself may be cheap, but repeated model/tool cycles are
  not.
- If a command takes materially longer than expected or stops producing useful
  signals, reassess once: identify the slow operation, decide whether it is still
  necessary, and either continue with justification or stop and report the exact
  incomplete validation. Do not keep polling merely to obtain a green result.
- Stop when the acceptance criteria are met. Do not broaden the audit, research,
  implementation, documentation, or validation scope for theoretical completeness.
- Keep final responses concise and link to repository artifacts instead of copying
  their contents. Report honestly what was and was not validated.

For large repository-wide requests, briefly establish a resource-aware execution
plan before acting: required deliverables, authoritative sources, minimum sufficient
inspection, proportionate validation, and explicit stop conditions. Revise that
plan if actual cost grows substantially beyond the initial expectation.

Documentation closeout is the final work step of every task, before the final
response. It does not authorize unrelated documentation rewrites: inspect and
update only affected authoritative documents, preserve current-vs-target labels,
and keep models/migrations/tests authoritative for implemented behavior.

## 12. Build-vs-Reuse and engineering Skills

- Reuse commodity technical capability; own strategic construction-ERP business
  logic. Before custom implementation, consider in order: Python standard library,
  Django/PostgreSQL built-ins, an existing repository dependency, a mature secure
  maintained third-party library, then custom code only with documented need.
- For a significant dependency, evaluate maintenance and security history,
  adoption/trust, documentation, version compatibility, commercial-SaaS license,
  transitive burden, architecture fit, operational ownership, and exit risk. A
  roadmap mention does not approve installation.
- Never custom-build cryptographic/password primitives or OAuth/OIDC/SAML and
  similar security protocols when trusted implementations exist. Do not replace
  good custom workflow, costing, posting, compliance-application, reconciliation,
  or other strategic domain logic merely because a generic package exists.
- Appropriate Skills may be used when they materially improve analysis, testing,
  security review, browser/UI/accessibility validation, documentation, or another
  repeatable engineering task. Skills are optional aids: they do not replace
  repository understanding, do not define product architecture, and do not create
  roadmap scope. Verify material Skill output against code, tests, sources, or
  actual behavior as appropriate.
