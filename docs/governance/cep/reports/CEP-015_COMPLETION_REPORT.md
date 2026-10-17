# CEP-015 Completion Report

**Current status: EXECUTION COMPLETE (non-production).** Consolidated Human Decision-01 resolved the historical matrix-value blocker. The scoped build implements the three exact versioned profile suggestions with an inert preview and explicit application of each Project Controls key through the existing published policy-version and tenant-selection authorities. Leave application fails closed until an approved Leave Policy version exists. `GATE-03` remains activation-only and unpassed; this closeout does not activate profile-specific runtime policy.

| Resumed checkpoint | Result |
| --- | --- |
| Baseline / branch | `main` at `fb6a1feaa78168748741c3c3253e2dea0871cda8`; local `origin/main` matched before mutation; pre-existing CEP-021/028 changes preserved |
| Canonical contract | Prompt SHA-256 `f8b50d828578735f4ec4ea60a87252e06d84a20fe6e4a6db388d95a2e78fa031` matched manifest; no prerequisites; `GATE-03` activation-only |
| Source and authority | Recovered `SPEC-001` matrix and Human Decision-01/02 supply exact suggestions and Project Controls value contract; matrix archive SHA-256 and decision identity recorded in `MATRIX_VERSION` |
| Product change | Profile preview/selection form; explicit per-key Project Controls policy application; versioned tenant selection and audit with matrix version, old/new value, actor, effective time, reason and prior selection; no label-driven grant or behavior |
| Leave boundary | `POLICY_DEFINED` suggestion is previewable, but no approved Leave Policy version exists in the repository and application fails closed |
| Migrations / data | None. `makemigrations --check --dry-run` found no changes. No development or production database mutation |
| Acceptance / DoD | 6/6 AC PASS; scoped build DoD PASS. Activation and browser/accessibility remain UTV |
| Verification | 4 focused tests PASS; 15 affected policy/settings regression tests PASS; Django check and Ruff PASS |
| Broader regression attribution | Broader organizations run: 70 PASS, one `OrganizationTenantIsolationTests.test_invalid_session_organization_is_cleared_by_middleware` failure, reproduced in isolation. It expects the invalid session key to contain a fallback organization, but the unchanged middleware clears the key; the test, middleware, context and select view were not changed by CEP-015. Recorded as baseline debt, outside this package |
| Evidence | `CEP-015_ACCEPTANCE_MAPPING.csv` and `CEP-015_EVIDENCE_MANIFEST.csv`, EV-005 through EV-010 |
| Git / production | No add, commit, push, merge, Human Sign-off or production action |

## Historical blocked attempt before Human Decision-01

**Execution status: EXECUTION FAILED / BLOCKED BEFORE PRODUCT MUTATION.** `CEP-015-FINDING-001 / BLOCKER-SPEC` prevents implementation because the authoritative `BONIRA_CONFIGURATION_PROFILE_MATRIX` key-value definitions are unavailable.

| Checkpoint | Result |
| --- | --- |
| CEP / Primary IMB | CEP-015 / IMB-0017 — Guided explicit configuration profiles |
| Repository baseline | `main` at `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matched |
| Authority / canonical identity | Standing non-production authority applies; prompt SHA-256 matches the immutable manifest |
| Dependencies / gates | No prerequisite CEP; EXT-0001 and GATE-03 are activation-only and do not block build |
| Product files changed | None |
| Migrations / data changes | None; Migration Impact = NONE |
| Acceptance Criteria | 0/6 PASS; 6/6 BLOCKED |
| Scoped DoD | BLOCKED / NOT MET |
| Tests / lint / runtime | Product checks not run because the stop occurred before product mutation; required coverage remains UTV |
| Blocker | Exact approved keys/values and source/version semantics for Small/Standard/Enterprise profiles are absent from the canonical prompt, repository, retained checkpoint, and reachable Git history |
| Required resolution | Supply and version the authoritative `BONIRA_CONFIGURATION_PROFILE_MATRIX`; then re-ground and resume CEP-015 |
| Human Sign-off / production | NOT EXECUTED / NOT EXECUTED |
| Git add/commit/push/merge | NOT EXECUTED |

No profile values, role/permission/workflow/capability effects, financial rules, or hidden defaults were invented. The Registry records the blocker and removes CEP-015 from the dependency-ready frontier while preserving the remaining independent candidates. The serial queue stops at this blocked boundary.
