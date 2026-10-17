# CEP-015 Execution Manifest

## Grounding and authority — 2026-10-17

- Branch and baseline: `main` at `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matched and the working tree was clean before Registry reconciliation.
- Standing authority: active for eligible current-governed non-production CEPs. The prompt's older generic per-CEP authorization convention is superseded by current governance; package-specific scope and stop rules remain authoritative.
- Canonical prompt: SHA-256 `f8b50d828578735f4ec4ea60a87252e06d84a20fe6e4a6db388d95a2e78fa031`, matching `CEP_PROMPT_MANIFEST.yaml`.
- Prerequisites: none. `EXT-0001` and `GATE-03` are activation-only and do not block build.
- Migration impact: `NONE`.

## Repository grounding

The active organization settings boundary is `apps.organizations.OrganizationSettings`, updated atomically and audited through `update_organization_settings`; the existing Persian/RTL settings form is the natural implementation seam. No configuration-profile implementation or standalone `BONIRA_CONFIGURATION_PROFILE_MATRIX` exists in the current tree.

Approved recovery checks inspected the canonical CEP-015 prompt, current repository, retained historical checkpoint `a4a18a1`, and reachable Git history. They found the matrix name and outcome constraints, but no approved Small/Standard/Enterprise configuration keys and values.

## Actual execution touch set before product mutation

Product touch set: **NONE**. A safe implementation would otherwise require the existing organization settings form/view/service/template and focused tests, but selecting any profile key/value suggestions without the canonical matrix would invent configuration semantics prohibited by the prompt and project governance.

Governance/evidence touch set: this manifest, CEP-015 acceptance/evidence/change manifests, completion report, and `CEP_EXECUTION_REGISTRY.yaml`.

## CEP-015-FINDING-001 — BLOCKER-SPEC

CEP-015 AC-1 and the package regulatory/configuration requirement say Small/Standard/Enterprise suggestions must derive only from `BONIRA_CONFIGURATION_PROFILE_MATRIX`. The canonical prompt does not enumerate that matrix, and approved repository/history recovery did not locate it. Existing `OrganizationSettings` defaults do not establish profile-specific values. Defining or differentiating those suggestions would therefore be an unsupported Product/configuration decision.

Resolution requires an authoritative, versioned `BONIRA_CONFIGURATION_PROFILE_MATRIX` that identifies the allowed keys and exact suggested values for each profile, including any source/version identity required by AC-4. CEP-015 must then be re-grounded and resumed under the standing authority.

Final lifecycle: **BLOCKED BEFORE PRODUCT MUTATION**. No schema, migration, product code, test, production, Human Sign-off, or Git-write action was executed.

## Resumed execution grounding — 2026-10-17

The prior blocked finding is historical. Consolidated Human Decision-01 now approves the three exact key suggestions for each profile, with explicit key application and versioned audit; Decision-02 approves the Project Controls value contract. The recovered `SPEC-001` matrix was read from the approved consolidated archive. The canonical prompt hash remains `f8b50d828578735f4ec4ea60a87252e06d84a20fe6e4a6db388d95a2e78fa031` and matches the manifest. Branch `main`, HEAD and local `origin/main` are `fb6a1feaa78168748741c3c3253e2dea0871cda8`; existing CEP-021/028 work is dirty and preserved. Registry shows no prerequisite and CEP-015 ELIGIBLE; `GATE-03` is activation-only.

Actual touch set: `apps/organizations/policy_specs.py`, a focused configuration-profile service, `apps/organizations/policy_services.py`, `apps/organizations/views.py`, `apps/organizations/urls.py`, a focused profile template, and focused tests; then this manifest, CEP-015 evidence/change/acceptance/report artifacts and Registry. No schema or migration. Existing tenant policy selection is the authoritative per-key versioned application boundary. The Leave key remains fail-closed until an approved Leave Policy version can be verified; no Leave Policy version is present in repository reality.
