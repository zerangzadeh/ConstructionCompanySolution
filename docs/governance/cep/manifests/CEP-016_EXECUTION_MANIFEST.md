# CEP-016 Execution Manifest

## Authority and package

- CEP: `CEP-016 — Context UX and scoped form filtering`
- Authorization: `AUTH-BATCH-003` (Human Decision Authority, Development / Non-Production)
- Entry gate: `GATE-01 = PASS` (explicitly recorded in `ROADMAP.md`)
- Prerequisites: `CEP-001 = EXECUTION COMPLETE`; `CEP-002 = EXECUTION COMPLETE`
- Canonical IMB sequence: `IMB-0004 → IMB-0012`
- Migration impact: `NONE`

## Repository grounding before mutation

- Branch: `main`
- HEAD: `89ca8f28da8828a6ac4226baceb18d27c5d98f09`
- Existing working-tree changes: CEP-017 shell/navigation closeout changes in
  `ROADMAP.md`, `templates/base.html`, `templates/components/navigation_links.html`,
  `templates/components/page_header.html`,
  `apps/organizations/test_p1_1_authorization.py`, plus untracked CEP-017 evidence
  and `core/test_cep017_navigation.py`. These are Human-owned/unrelated changes and
  must be preserved.
- Current Company context: validated active membership and Organization lifecycle,
  stored in session, resolved by `OrganizationMiddleware`, and visible in the shell.
- Current Project/Site context: no persistent shared session contract or shell
  controls.
- Current form filtering: tenant-filtered in sampled Expense/Estimate forms, with
  relation consistency validation, but choices are not intersected with current
  membership object scope and are not narrowed by parent selection.
- Current backend authorization: services and direct routes already enforce
  business permission, Tenant, and Project/Site scope through
  `apps.organizations.authorization`; this remains authoritative.
- Canonical source result: UIA-002, UIA-018 and UIA-019 require visible persistent
  Company/Project/bounded-Site context, scope-filtered dependent choices and explicit
  no-context/error states. PD-016 preserves role/person separation; context never
  grants authority. The configuration-profile matrix defines no applicable profile
  behavior and therefore no profile semantics are introduced.

## Actual Execution Touch Set

Planned product mutation surface:

- Context contract/services: `apps/organizations/context.py`,
  `apps/organizations/services.py`, `apps/organizations/middleware.py`
- Context HTTP/template exposure: `apps/organizations/context_processors.py`,
  `apps/organizations/views.py`, `apps/organizations/urls.py`,
  `templates/components/context_selector.html`, `templates/base.html`
- Shared cascade behavior: `apps/organizations/form_scoping.py`,
  `apps/accounts/static/js/erp_context.js`
- Approved representative project-scoped mutations:
  `apps/expenses/forms.py`, `apps/expenses/views.py`,
  `templates/expenses/create.html`, `apps/estimates/forms.py`,
  `apps/estimates/views.py`, `templates/estimates/create.html`
- Focused tests: `apps/organizations/test_cep016_context.py`
- Required evidence/closeout: `CEP-016_ACCEPTANCE_MAPPING.csv`,
  `CEP-016_EVIDENCE_MANIFEST.csv`, `CEP-016_CHANGE_MANIFEST.csv`,
  `CEP-016_COMPLETION_REPORT.md`, `ROADMAP.md`

No models, schema, migrations, permission catalogue, role grants, workflow state,
financial behavior, background jobs, external integrations or production settings
are in the touch set.

