# CEP-019 Execution Manifest

## Grounding and entry checks — 2026-10-17

- Branch/baseline: `main` at `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matches.
- Existing working tree contains preserved CEP-015 blocker closeout and CEP-018 implementation/closeout artifacts. CEP-019 has no dependency on CEP-015 and no overlapping configuration-profile mutation.
- Canonical prompt SHA-256: `985904a4ffe2892eb844d34d4c19373cbc3ef2c323569dd6ae85cbc24e02dd66`, matching the immutable Prompt Manifest.
- Standing non-production execution authority applies. The prompt's historical generic per-package authorization wording is superseded by current governance.
- Prerequisites: CEP-001 and CEP-002 are COMPLETE. Entry `GATE-01 = PASS`; applicable exit `GATE-02 = PASS`. External dependencies: none.
- Migration impact: `NONE`.

## Repository reality and bounded touch set

No global-search endpoint or shell exists. Existing Project and Material services already enforce active-organization tenant scope, effective permission/scope checks, and direct-detail authorization. The global search adapter will use only these existing read services and will enumerate no financial, document, workforce, payroll, support, or other sensitive families.

Intended touch set:

- `core/search.py`, `core/views.py`, `config/urls.py`: bounded read-only search orchestration and active-organization GET endpoint.
- `templates/core/global_search.html`, `templates/base.html`: Persian/RTL responsive search shell and authenticated entry form.
- `core/test_cep019_search.py`: focused tenant/permission/deep-link/no-leakage/UI tests.
- CEP-019 evidence, completion, and Registry artifacts.

No model, schema, migration, permission catalogue/default grant, source-domain mutation, document/content search, financial search, configuration-profile semantics, workflow state, or production surface is in scope.

## Execution and closeout — 2026-10-17

- Implemented a read-only GET-only global search shell using an explicit allowlist of existing Project and Material source services. No unregistered family can be searched.
- Project results retain existing tenant/project scope enforcement. Material results retain existing active-organization permission enforcement. Both deep-link only to existing direct routes that independently enforce their source authorization.
- Empty, too-short and no-access searches return no result rows or source URLs. Search does not create, mutate, post, audit, or become a source-domain authority.
- Focused tests: **4 passed**. Affected Home/shared-shell regression: **19 passed**. Django check, Ruff, compilation, migration-drift and diff hygiene pass.
- Acceptance Criteria: **6/6 PASS**. Scoped DoD: **PASS**. Migration impact: **NONE**. Blockers: **NONE**.
- Remaining UTV: browser/accessibility runtime and performance/concurrency runtime evidence. No UTV is represented as PASS.
