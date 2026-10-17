# CEP-020 Execution Manifest

## Grounding and authority — 2026-10-17

- Branch and baseline: `main` at `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matched the Registry reconciliation baseline.
- Standing authority: active for eligible current-governed non-production CEPs. The prompt's older generic authorization wording is superseded only for generic mechanics; its package-specific scope and source requirements remain authoritative.
- Canonical prompt: SHA-256 `d79ae3dc72ea9c06be2c4106bfe8bbbd47ce5f5a3dbcc648c619234d3001f5a2`, matching `CEP_PROMPT_MANIFEST.yaml`.
- Prerequisites: none. `GATE-01` is PASS. `EXT-0011` and `GATE-03` are activation-only and do not block Build.
- Migration impact: `NONE`.

## Repository grounding

`apps.projects` already contains an immutable `ProjectCostForecast` draft and `ProjectBudgetControl` pointer; `create_project_cost_forecast_draft` creates the bounded draft snapshot. Those implementation facts do not establish the required approval/rejection/supersession/reforecast lifecycle, governed business-event enforcement points, approved configuration keys, override reasons, or source/version semantics.

Approved recovery checked the canonical CEP-020 prompt, non-prompt repository documentation and code, retained governance materials, and canonical-source references. It located only references to `PD-020`, `PD-024`, `SPEC-001`, and `SPEC-004`; no authoritative content defining the required lifecycle or budget-control semantics is available. `BONIRA_CONFIGURATION_PROFILE_MATRIX` is also absent as an authoritative source. Existing draft behavior may not be elevated into a lifecycle or control policy by inference.

## Actual execution touch set before product mutation

Product touch set: **NONE**. A safe implementation would need the forecast/budget-control domain model and service surfaces plus required workflow and regression tests, but choosing transition paths, authorized decision roles, source preconditions, approved business events, control-key values, override requirements, or version semantics would create unsupported Product Decisions.

Governance/evidence touch set: this manifest, CEP-020 acceptance/evidence/change manifests, completion report, and `CEP_EXECUTION_REGISTRY.yaml`.

## CEP-020-FINDING-001 — BLOCKER-SPEC

CEP-020 AC-1 requires the forecast lifecycle defined by `PD-020`; AC-5 requires rejection, cancellation and correction only where governing policy permits; AC-7 through AC-12 require approved configuration keys, authoritative control behavior, override reason/audit, policy-absent fail-closed behavior, source identity/version preservation, and no profile-label behavior. The prompt names `PD-020`, `PD-024`, `SPEC-001`, `SPEC-004`, and `BONIRA_CONFIGURATION_PROFILE_MATRIX`, but the approved repository/recovery materials supply none of their operative definitions.

Resolution requires authoritative, versioned copies of those governing sources that define at least lifecycle transitions/actors/preconditions, the approved business-event control points, allowed key/value and override/audit semantics, and source/version identity. CEP-020 must then be re-grounded and resumed under standing authority.

Final lifecycle: **BLOCKED BEFORE PRODUCT MUTATION**. No schema, migration, product code, test, production, Human Sign-off, or Git-write action was executed.
