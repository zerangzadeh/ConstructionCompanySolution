# PD-033 — V1 reconciliation current-state selection

**Decision authority:** Human Decision Maker, “BONIRA — CEP-006 PRODUCT DECISION RESOLUTION AND QUEUE RESUME,” 2026-10-15.

**Decision status:** APPROVED for the bounded CEP-006 implementation semantics; not part of the sealed `BONIRA-PD-FREEZE-v1.0` register or the separate PD-032 freeze.

**Register identity:** The consolidated frozen register ends at PD-031. The separately frozen [PD-032 addendum](BONIRA_PD_032_CANONICAL_HOME.md) is the next governing ID. A search of the available local decision records found no PD-033, making this the next verified available ID. This record does not rewrite either prior freeze.

**Scope:** CEP-006 / IMB-0044, IMB-0048 and IMB-0066, reconciliation and financial read-model behavior only. Scope, the 16 Acceptance Criteria, Definition of Done, CEP dependency graph, and AUTH-BATCH-002 authorization remain unchanged. Accounting remains GL authority; source domains own native facts; Reporting/Reconciliation has read/projection authority only.

## Approved rule

For each reconciliation pair and its existing native comparison grain, current state is the latest eligible, successful, complete native run. Exactly one selected run per grain contributes to current-state aggregation. A newer qualifying run supersedes older qualifying runs for current reads only; historical runs remain immutable and queryable. Failed, incomplete, cancelled, or invalid runs cannot replace a valid current run or contribute to current aggregation unless existing canonical semantics explicitly require it.

The native grain is the tuple of persisted fields already used by that pair's implemented grouping, identity and matching contract. No universal grain or new identity is authorized. “Latest” must follow existing persisted deterministic business/run ordering; arbitrary row order and primary-key ordering without explicit authority are prohibited. Preserve native source-version and immutable source-identity evidence; a run ID is not a source version without an existing canonical equivalence. Fail closed if the grain, ordering, eligibility, or required provenance cannot be established from persisted authoritative data.

No source fact, journal, ledger entry, source lifecycle state, or historical run may be rewritten by this read-model rule. CEP-006 has **Migration Impact: NONE**. It does not authorize a current pointer, supersession field, reconciliation identity field, schema constraint, schema migration, or data migration. A required schema change stops execution before model or migration mutation.

## CEP-006 applicability finding

The decision resolves the selection policy but does not supply missing pair-specific fields. The current [pair catalogue](../../apps/reporting/reconciliation_catalog.py) declares `subledger_gl` grain `direction/as_of/control_account`, while `SubledgerReconciliationRun` persists `direction` and `as_of_date` but no control account. It declares `treasury_gl` grain `cutoff/currency/source_identity`, while `TreasuryGLReconciliationRun` persists `cutoff_date` but neither currency nor source identity at run grain. Their native services retain aggregate runs, and the Reporting adapter currently sums all runs through the cutoff. No existing persisted tuple unambiguously implements either declared grain. The Human decision requires **STOP BEFORE PRODUCT MUTATION** for these pairs; dropping a declared dimension or deriving one from aggregate contents would invent a comparison contract. Resolve the exact native grain and its representation under the no-migration boundary before CEP-006 can resume.

## Approved applicability and gated-consumer addendum — 2026-10-15

The Human Decision Maker subsequently approved `CEP006-D01`: the native-run latest-current rule applies only where the Reporting reconciliation adapter consumes a retained native reconciliation run. Direct-source pairs must use their authoritative source domain's existing lifecycle, version and currentness contract; no native run is invented for them. This does not waive any declared comparison grain, source-version traceability, current-state correctness or CEP-006 Acceptance Criterion. A direct-source pair without sufficient persisted evidence remains blocked.

The Human Decision Maker also approved `CEP006-D08`: `contractor_compliance` stays `gated_not_activated` until an authorized consumer with all declared right-side dimensions exists. No placeholder consumer or two-sided current-state claim is allowed. `CEP006-D02` through `CEP006-D07` remain unresolved. The [schema remediation and reauthorization packet](../governance/cep/supporting/CEP-006_SCHEMA_REMEDIATION_REAUTHORIZATION_PACKET.md) is design evidence only; it does not authorize schema/model changes, migrations, implementation, production action or queue resumption.

## Successor decision record — 2026-10-15

The preceding unresolved-state statement is historical. The Human Decision Maker
subsequently authorized the bounded CEP-006 schema/data-migration remediation and
approved the AP/AR control-account decision as
[PD-034](BONIRA_PD_034_CONTROL_ACCOUNT_MAPPING.md). PD-034 resolves only
`CEP-006-FINDING-003 / BLOCKER-PD`; it does not reopen the sealed register or
authorize downstream CEPs or production activity.
