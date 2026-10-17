# CEP-025 Execution Manifest

## Resumption at main dd8cf032 — 2026-10-17

- Repository grounding: `main` and `origin/main` at `dd8cf032b85873dcdfb730a20c747b0431d6f4d2`. The dirty working tree consists solely of separately scoped, closed CEP-020 product/evidence changes and Registry metadata; `apps/payroll` is untouched, so CEP-025 has no file collision.
- Prompt SHA-256 `07e2f8e8744148e83d6cacd0e7eb3f904c97dbd85b6ebf1be091634d58b480bb` matches the canonical manifest. CEP-010 COMPLETE; GATE-01 PASS; GATE-02 PASS. Standing non-production authority applies.
- Recovered frozen PD-028/031 and SPEC-013 establish finalized source/version and correction history; consolidated Human Decision-05 approves operational EARNING/ALLOWANCE/DEDUCTION/REIMBURSEMENT/EMPLOYER signed buckets, excludes INFORMATIONAL from money, and requires explicit versioned tenant Payroll-year start/end. Decision-07 grants bounded non-production persistence migration despite historical `NONE` migration classification. No statutory classification/rate/formula is authorized.
- Existing Payroll period/run/result line and reversal/replacement services are authoritative. No cumulative/YTD persistence exists. Intended product touch set: `apps/payroll` model, cumulative service, finalization/reversal hooks only if safe, migration and focused tests; existing organization authorization/audit conventions reused without new permissions. Intended evidence touch set: this manifest, acceptance/change/evidence manifests, Completion Report and Registry.
- The historical `CEP-025-FINDING-001` section below is retained as prior blocked evidence; its authority and migration causes are resolved. Test/database results will determine final disposition.

## Current execution closeout — 2026-10-18

- Added a versioned tenant Payroll-year model whose explicit start/end dates must be approved; the approved intervals cannot overlap. A replacement approval supersedes the prior version while leaving its cumulative history addressable.
- Added append-only per-component signed balance history keyed by approved year, Employee, source line and source digest. Explicit WorkRelationship links are retained when present; no identity is inferred from name or employee number. INFORMATIONAL lines are omitted from monetary buckets.
- Finalization and reversal call the cumulative service inside the existing Payroll transaction when a matching approved year exists. Without one, core Payroll retains its prior behavior and explicit YTD recording/read fails closed. Existing finalized/reversed runs can be ingested explicitly into an approved year without source mutation.
- Focused PostgreSQL evidence: four domain/service/transaction tests and one migration rollback/reapply test PASS. Ruff, Django system check, migration drift and diff checks PASS. Existing core Payroll and financial-handoff suites fail in their authorization fixtures before the CEP-025 behavior; baseline failure was reproduced before product mutation and remains separately attributed.
- Payroll migration `0006` is an expand-only, bounded non-production schema change; only the test database ran it. No operational historical dataset, statutory formula, production migration, Git write, Human Sign-off or certification was executed.

- Baseline: `main` / `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matches Registry reconciliation.
- Standing authority is active; CEP-010 is COMPLETE and GATE-01/GATE-02 are PASS. CEP-025 does not depend on current blocked CEPs.
- Prompt SHA-256 `07e2f8e8744148e83d6cacd0e7eb3f904c97dbd85b6ebf1be091634d58b480bb` matches `CEP_PROMPT_MANIFEST.yaml`.
- Migration Impact is `NONE`.

## CEP-025-FINDING-001 — BLOCKER-SPEC-REPOSITORY-MIGRATION

Approved recovery found only prompt references to `PD-028`, `PD-031`, `SPEC-013`, and `PDM-012`; no governing cumulative classification, reset-policy, source-version, or compatibility semantics are available. `apps.payroll` has period/run/component/result/statutory models but no cumulative/YTD state model or history/read contract. The statutory service explicitly keeps cumulative calculation unavailable until authoritative opening/cumulative treatment exists.

Creating the requested state, identity constraints, history, reset hook, or compatibility path would require schema/migration work despite `Migration Impact = NONE`, and selecting reset/statutory behavior would invent policy. Product touch set: **NONE**. Resolution requires authoritative, versioned PDM-012/PD-028/PD-031/SPEC-013 definitions plus an approved existing persistence contract or bounded schema/migration authorization. No product mutation, test, production, Human Sign-off or Git action occurred.
