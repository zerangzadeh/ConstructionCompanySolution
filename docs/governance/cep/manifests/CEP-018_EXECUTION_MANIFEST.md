# CEP-018 Execution Manifest

## Grounding and entry checks — 2026-10-17

- Branch/baseline: `main` at `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matches.
- Existing working tree: only the preserved CEP-015 blocker Registry/evidence closeout. CEP-018 does not modify those artifacts or configuration-profile semantics.
- Canonical prompt SHA-256: `bbefae22557ca49b82e22424a99ac2caa766c00928a45d3b2c5890680d19f0b4`, matching the immutable manifest.
- Standing non-production execution authority: applicable. The prompt's older generic per-package authorization wording is superseded by current governance.
- Prerequisites: CEP-001 and CEP-002 are COMPLETE. Entry `GATE-01 = PASS`. External dependencies: none.
- Migration impact: `NONE`.

## Repository reality and bounded touch set

The existing shared Workbench already provides permission/candidate-scoped My Tasks with source deep links, filters, actions, tenant isolation, and assignment evidence. The existing Support `Notification` model/service already provides recipient authorization, source validation, deduplication, read state, and audit evidence, but its UI does not expose the validated source link. Canonical navigation retains My Requests as unavailable. No bounded Manager Workspace exists.

Intended product touch set:

- `apps/workflows/personal_workspaces.py`: read-only own-request and explicit-team-lead Manager projections over source-owned Timekeeping records.
- `apps/workflows/views.py`, `apps/workflows/urls.py`: guarded GET-only workspace routes.
- `templates/workflows/my_requests.html`, `templates/workflows/manager_workspace.html`, `templates/components/navigation_links.html`, `templates/timekeeping/workbench.html`: Persian/RTL states, navigation and source anchors.
- `apps/organizations/context_processors.py`: permission plus explicit identity/team-assignment availability flags; no authorization grant.
- `apps/support/services.py`, `apps/support/templates/support/workbench.html`: validated notification source deep link only.
- `apps/workflows/test_cep018_workspaces.py`, `core/test_cep017_navigation.py`: focused and affected regression.
- CEP-018 evidence, completion and Registry closeout artifacts.

No model, migration, permission catalogue/default grant, workflow state, source-domain mutation, notification channel, financial behavior, configuration profile, or production surface is in scope.

## Execution and closeout — 2026-10-17

- Implemented read-only My Requests and Manager Workspace projections over existing Timekeeping authorities. Own requests require explicit workforce identity; Manager access requires an active explicit `WorkTeam.lead` assignment plus existing review/view permissions. A title string grants nothing.
- Preserved the existing My Tasks Workbench and all source workflow states. Added only stable source anchors and guarded deep links.
- Extended the existing in-app notification read projection with a source URL only after recipient permission and source availability are rechecked. Existing enrollment authorization, deduplication, read state and append-only audit behavior were verified; no channel or approval behavior was added.
- Focused and affected combined regression: **22 passed**. Django check, Ruff, compilation, migration drift and diff hygiene pass.
- Two broader legacy suites were attempted and failed before CEP-018 behavior because their old fixtures omit the explicit authorization scopes now required by shared services. The affected Home/Timekeeping UI path and focused CEP-018 behavior pass; this attributed baseline fixture debt is not an in-scope failure.
- Acceptance Criteria: **18/18 PASS**. Scoped DoD: **PASS**. Migration impact: **NONE**. Blockers: **NONE**.
- Remaining UTV: browser/accessibility runtime and performance/concurrency runtime evidence. No UTV is represented as PASS.
