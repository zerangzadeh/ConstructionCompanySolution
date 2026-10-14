# CEP-005 — implementation-resume grounding and migration conflict

**Resolution checkpoint — 2026-10-14:** CEP-005-FINDING-002 **RESOLVED** by explicit bounded audit migration authorization and successful forward/reverse/reapply verification. Finding 001 remains RESOLVED. The following pre-product stop is preserved historical evidence; current execution is COMPLETE within the bounded root scope, as recorded in [the completion report](CEP-005_COMPLETION_REPORT.md).

Date: 2026-10-14. **EXECUTION PARTIAL — STOPPED BEFORE PRODUCT MUTATION.** Primary IMB: IMB-0030. AUTH-BATCH-001 remains valid; the separate resume instruction was received. No CEP-007 or other CEP started.

## Fresh repository baseline

```text
branch: main
HEAD: 0b0cfcdabb93e4e6215d6f2805e763dd82f99cf4
git status --short:
 M ROADMAP.md
?? CEP-005_ACCEPTANCE_MAPPING.csv
?? CEP-005_CANONICALIZATION_RECORD.md
?? CEP-005_CHANGE_MANIFEST.csv
?? CEP-005_COMPLETION_REPORT.md
?? CEP-005_EVIDENCE_MANIFEST.csv
?? CEP-005_EXECUTION_MANIFEST.md
?? CEP-005_PD_010_APPROVAL_READINESS.md
?? CEP-005_SPEC_008_INT_B11_RESOLUTION.md
?? CEP-005_SPEC_008_INT_B11_SUPPLEMENT_v1.0.md
git diff --name-status:
M ROADMAP.md
git diff --stat:
 ROADMAP.md | 13 +++++++++++++
 1 file changed, 13 insertions(+)
```

These are actual pre-resume outputs; tracked diffs omit untracked artifacts. All preceding governance changes and historical touch sets are preserved.

## Source revalidation

The three governing consolidated archives were read-only hash checked against the verified values in CEP-005_CANONICALIZATION_RECORD.md. PD-010 frozen archive hash, required-specification archive (SPEC-008 and INT-B11), and canonical IMB-0030 archive all match. Approved supplement v1.0 SHA-256 remains `209295fb21a031d9776cd1d278866a15dd9fc3fe393ccfdf792f97e28921c64a`. P01–P07 approval and original authorities are unchanged. Governing semantic conflicts = 0; unsupported approved semantics = 0. CEP-005-FINDING-001 remains RESOLVED.

## Actual Execution Touch Set, before any product mutation

| Area | Inspected / planned surface | Actual effect |
| --- | --- | --- |
| Project models | `apps/projects/models.py`: ProjectCostSourceContract, ProjectCostFact, ProjectCostCoverage | Inspected; no model changes made |
| Existing services | `apps/projects/services.py`: source contract draft/approval, record_project_cost_fact, _require_budget_access, hashing and projection/reconciliation | Inspected; no changes made |
| Minimum root module | Planned new `apps/projects/commitment_integration.py` | Not created; would own registered child-adapter interface, canonical-key gating, immutable root outcome linkage and bounded read-only reconciliation |
| Source producers | Only minimum trusted adapter contract for future approved PO/Subcontract producers | No IMB-0031/0032/0033 adapters or source lifecycle implementation created |
| Shared audit contract | `apps/audit/models.py`, `apps/audit/services.py`, existing migrations 0047 and 0053 | Inspected; root attempt/result action-catalog addition identified as requiring explicit migration disposition |
| Tests | Inspected `apps/projects/test_p4_integrated_cost.py`, `apps/projects/test_p4_budget_preparation.py`, pytest.ini, conftest.py | No tests changed or run; planned new `apps/projects/test_cep005_commitment_integration.py` not created |
| Configuration | `config/settings/development.py`, relevant base-settings references, pyproject.toml | Inspected; no settings/packages/dependency changes |
| Schema/migration | Existing audit action field choices and catalog migration pattern | No migration/model alteration made; see finding below |
| Actual changed files | This findings document; current CEP-005 execution/completion/evidence/change/acceptance artifacts; existing CEP-005 ROADMAP.md entry | Governance-only; product touch set EMPTY |

Before a later implementation attempt, confirm the actual product touch set again. Planned filenames above are explicitly new-file proposals, not claims that those files currently exist.

## CEP-005-FINDING-002 — BLOCKER-MIGRATION

The approved P06 requires a durable attempt before any target effect, independent error evidence after target rollback, and atomic target/linkage/success evidence. See supplement lines 131–138. Existing ProjectCostFact is insufficient: an attempted or failed operation may have no fact at all; a failed transaction rolls back its fact and fact-recorded audit event. No attempted fact may be manufactured to represent failure.

The existing append-only AuditEvent store has JSON metadata/changes, correlation identity, tenant and actor, so it is a viable existing persistence mechanism without inventing a separate integration database or production logging architecture. However:

1. `apps/audit/services.py:60` rejects any action outside `AuditAction.values`.
2. The Project Cost action set at `apps/audit/models.py:641` through its reconciliation entries has source draft/approval, fact recorded, coverage changed, forecast drafted and reconciliation viewed/exported. It has no truthful root invocation/attempt/result event. A failed or pending integration cannot truthfully be logged as fact recorded, contract approved or reconciliation viewed.
3. `apps/audit/models.py:1591` defines the action as model field choices. Existing catalog extensions use `migrations.AlterField(... choices=AuditAction.choices ...)`, including `apps/audit/migrations/0047_p4_s14_s20_project_cost_actions.py:13` and `0053_password_recovery_actions.py:13`.

The minimum repository-conventional design therefore needs an audit action-catalog extension and its Django model-state migration. This is a migration-scope conflict even if it needs no physical table/column addition. No new attempt table is proposed as necessary at this checkpoint. Existing historical migrations import the live enum; relying on that to conceal a catalog change from autodetection would not be evidence that the change requires no migration or that it was authorized. Historical migrations must not be rewritten.

The resume handoff section 11 explicitly requires **STOP and report scope/specification conflict** if a migration is required contrary to the NONE expectation. P06 approval expressly does not authorize a migration. Accordingly no product code, audit enum, migration or test implementation was written. No bypass of the audit service, misleading reuse of an unrelated action, file-based business evidence store or new package is introduced.

**Exact resolution required:** explicitly authorize a bounded development-only audit action-catalog/model-state migration for CEP-005 root attempts/results, retaining the existing AuditEvent store and its immutability/security checks. A single root-integration action with append-only attempt/result metadata is sufficient for design review; exact event representation can be finalized within P06. No production migration execution, source-specific producer or new domain authority is requested. Alternatively, identify an existing approved audit action whose established semantics genuinely cover pre-effect root attempts/results; the inspected Project Cost catalog has none. Do not infer approval from the earlier supplementary specification approval.

The proposed model-state migration is not created or executed here. Any additional actual schema need discovered later remains a separate finding, not pre-authorized by this minimum resolution.

## Acceptance, tests and checks

All AC-1–AC-6: UTV / NOT VERIFIED. DoD: PARTIAL (governing contracts available; implementation obligations unverified). No required test failure was hidden or waived. Unit/domain/integration/regression tests executed: **0**; collected/passed/failed/skipped/xfailed and duration are **N/A**, not a zero-failure PASS. Ruff, Django system checks and migration dry run were not run after the explicit pre-product STOP condition; no executable changes exist to validate. Applied migration/database state is not claimed current.

Required future tests remain the complete resume list: approved occurrence, canonical-key duplicate/retry, successor and stale versions, missing contract/mapping, target rollback and durable failure evidence, successful retry with revalidation, correction/reversal/supersession, cancellation RELEASE, read-only reconciliation and authority preservation. No AC or DoD requirement is weakened to avoid the migration boundary.

CODE DIFF / TEST OUTPUT / LINT OUTPUT / INTEGRATION TRACE / TRANSACTION TRACE and runtime source/target evidence remain outstanding. Static code inspection above is not an executed transaction trace. Idempotency, reconciliation and authority enforcement are UTV for the new root. Performance/concurrency certification remains UTV; UI/browser evidence N/A. GATE-05 remains an unevaluated EXIT GATE, not the blocker.

## Documentation closeout

Current CEP-005 evidence and ROADMAP.md are reconciled with EXECUTION PARTIAL and the new migration-scope finding. The earlier specification finding stays RESOLVED; approved source documents, supplement/version/hash, frozen authorities and all historical evidence remain unchanged. Documentation checks cover CSV shape/count, unchanged canonical AC text, references, whitespace and documentation-only touch set. No application test result is inferred from these checks.

Product/migration/data changes NONE. AUTH-BATCH-001, PD-010, SPEC-008/INT-B11 semantics, P01–P07, AC, DoD, DAG and authority scope unchanged. Git add/commit/push/merge NOT EXECUTED. Human Sign-off NOT EXECUTED. CEP-007 NOT STARTED.
