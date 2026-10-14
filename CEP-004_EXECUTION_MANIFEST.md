# CEP-004 Execution Manifest

## Authorization and baseline — 2026-10-15

- Authorization: AUTH-BATCH-002, bounded Development/non-production execution.
- Branch: `cep/CEP-004-metric-governance`; HEAD: `17dff5f48eb34b6de3a22e0597861b0581146f33`.
- Baseline `git status --short`, `git diff --name-status`, and `git diff --stat`: empty.
- Prerequisite CEPs and blocking external dependencies: none.
- Canonical prompt SHA-256: `efdead9fec23489162abef34fe5984b22b9d66bf75a99ae4d26791f4b09ee8ee`.

## Repository grounding

The existing Reporting app already owns six code-defined metric contracts, published definition versions, source manifests, scoped refresh results, freshness, reconciliation evidence, and reporting tests. The canonical PD-020 project-controls matrix in the approved consolidated package supplies no authority to invent further formulas. `dashboard_results` currently selects incomplete results and does not recheck the source-domain permission for each displayed result. The dashboard template presents every selected result as a card. This is the bounded gap for CEP-004.

## Actual execution touch set before product mutation

| Surface | Intended change | Migration |
| --- | --- | --- |
| `apps/reporting/services.py` | Restrict displayed results to governed complete/current source evidence and enforce source permission before display; retain existing tenant/project scope. | None |
| `templates/reporting/dashboard.html` | Continue to render only selector-approved cards with version/as-of/freshness and source drillthrough. | None expected |
| `apps/reporting/test_p10_s02_s06.py` | Extend the existing focused Reporting acceptance module with selector, authorization, and freshness tests. | None |
| CEP-004 manifests and `ROADMAP.md` | Evidence and status closeout. | None |

Existing source-domain models, metric formulas, data migrations, source facts, and reporting write paths are outside the touch set.

## Validation-closure correction

Executable regression reached test bodies after the existing test database completed its pending migrations. Existing export test 14 then exposed a CEP-004 interaction: suppressing incomplete KPI cards left the governed export empty, violating its nonempty manifest contract. The selector now retains incomplete results only for the explicitly freshness-labeled audit export. Display cards remain fail-closed. This was the only product-code correction in validation closure.
