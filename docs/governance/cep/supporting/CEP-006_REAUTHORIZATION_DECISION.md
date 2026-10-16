# CEP-006 reauthorization decision

**State:** Decision closure and reauthorization preparation only, 2026-10-15. This document records evidence-backed recommended Human decisions. It does not itself approve D02–D07, amend CEP-006, authorize a migration, or resume the stopped queue.

## 1. Approved baseline: D01 and D08

`CEP006-D01` is approved and recorded in [PD-033](../../../architecture/BONIRA_PD_033_RECONCILIATION_CURRENT_STATE.md): native-run current selection applies only to Reporting adapters that consume a retained native reconciliation run. Direct-source pairs use their source domain's lifecycle/version/currentness contract and never receive an artificial native run.

`CEP006-D08` is approved and recorded in PD-033: `contractor_compliance` remains `gated_not_activated` until an authorized right-side consumer persists its declared contract, assessment, policy-version and currency dimensions. No placeholder consumer or two-sided current-state claim is allowed.

## 2. Recommended D02: direct-source contracts

| Pair / gap | Repository fact | Recommended Human decision | Owner and target path | Historical policy |
| --- | --- | --- | --- | --- |
| `estimate_budget` | `ProjectBudgetControl.governing_budget` points to one accepted `BudgetVersion`; the budget's source manifest pins estimate/revision. The pointer is mutable. | Select the governing budget only for a current read. Historical currentness must use a Reporting run's retained source manifest; where no exact historical selection was retained, return `unverifiable`, never reapply today's pointer. | Projects: existing `ProjectBudgetControl → BudgetVersion → BudgetSourceManifest`; no schema. | Existing run snapshots: derivable only when they carry the exact selected IDs; otherwise unbackfillable. |
| `po_receipt_invoice`, `claim_settlement`, `payroll_financial_handoffs`, `fixed_asset_handoffs` | Each has existing immutable version/correction/predecessor/reversal lineage. | Use its existing approved/current lifecycle relation, version and exact source IDs; retain current result as `unverifiable` if a historical current head is absent. Do not add a native run. | Subledgers, Billing, Payroll, Fixed Assets; existing relationships; no schema. | Derivable only from exact retained lineage; no inferred historical heads. |
| `commitment_projection` | PO source-award and cost source-contract are distinct; PO line has no persisted currency. | Leave the pair `uncomparable` until its source owner authorizes an exact source-contract and currency contract. Do not place its source-model remediation in CEP-006. | Procurement/Projects; later source-domain package. | Unbackfillable on current evidence. |
| `inventory_quantity_value` | Valuation pool has no warehouse/unit and no immutable historical cutoff snapshot. | Leave the pair `uncomparable` at the declared grain until Inventory owns a warehouse/unit/currency/cutoff valuation snapshot contract. Do not add a Reporting projection as an authority substitute. | Inventory; later source-domain package. | Unbackfillable without inference. |
| `project_cost_sources` | Cost fact has project/source IDs, but producer contract has no project and source-event correspondence is ambiguous. | Leave the pair `uncomparable` until Project Controls owns an exact project/event source-contract relation. | Projects; later source-domain package. | Unbackfillable without inference. |
| `contractor_compliance` | D08 governs. | Keep `gated_not_activated`. | Billing/consumer domain; no CEP-006 change. | Not applicable before consumer activation. |

**Repository facts:** [Budget control/source manifest](../../../../apps/projects/models.py), [invoice match lineage](../../../../apps/subledgers/models.py), [claim correction/allocation](../../../../apps/billing/models.py), [Payroll handoff lineage](../../../../apps/payroll/models.py), and [fixed-asset envelope supersession](../../../../apps/fixed_assets/models.py) already contain source-domain currentness concepts. [The Reporting adapters](../../../../apps/reporting/reconciliation.py) currently aggregate broad querysets and do not safely reconstruct a historical source head.

**Canonical requirement:** D01 preserves each declared grain and source-version traceability; it does not authorize a fallback aggregation. **Engineering consequence:** CEP-006 may make a pair explicitly `uncomparable` or `unverifiable` where existing evidence cannot support the declared grain. **Recommended Human decision:** approve the table above and keep U01–U06/U10–U11 source-model remediation out of reauthorized CEP-006. This keeps the package bounded and prevents a false financial projection.

## 3. Recommended D03: `subledger_gl` control-account contract

**Repository fact:** Accounting owns `Account`; `JournalLine.account` is the posted ledger-account relationship. Subledgers owns `Obligation` and `SubledgerReconciliationRun`. The current run has `direction`, `as_of_date`, aggregate totals, ID arrays and a hash, but no control account or per-account evidence. The native service explicitly emits `CONTROL_MAPPING_NOT_APPROVED` and keeps `linked_gl_total` at zero. [Account and journal fields](../../../../apps/accounting/models.py), [obligation/run fields](../../../../apps/subledgers/models.py), and [the service](../../../../apps/subledgers/services.py) establish this boundary.

**Canonical requirement:** the declared grain is `direction/as_of/control_account`; a current read needs one exact native run/slice for every grain and cannot map history through a current chart-of-accounts configuration.

**Engineering consequence:** one parent run may cover multiple accounts. A single account FK on `SubledgerReconciliationRun` would misrepresent mixed account evidence. Old aggregate runs cannot be given per-account identity or amounts safely.

**Recommended Human decision:**

1. `accounting.Account.pk` is the authoritative control-account identity; the associated posted `JournalLine.account_id` is the authoritative Accounting-side evidence.
2. A Subledger native run may contain multiple control accounts. Add an immutable `SubledgerReconciliationAccountSlice` for each `(organization, direction, as_of_date, control_account)` within a parent `SubledgerReconciliationRun`.
3. Each slice pins its account, totals/difference, evidence hash, grain-local revision and predecessor, and exact immutable source membership: an obligation identity/source-version snapshot and the matching journal/journal-line identity/source-version snapshot.
4. Each slice is created atomically with its parent run after the approved account mapping validates every included source. Parent totals must equal the sum of slices. An unmapped source prevents that slice from becoming a complete native reconciliation result; it does not receive a fabricated GL amount.
5. Historical run account values, amounts, source-membership and revisions receive **no inferred backfill**. Existing rows remain history with a `legacy_unverified` provenance record.

## 4. Recommended D04: `treasury_gl` currency and source-membership contract

**Repository fact:** `TreasuryMovement` persists currency, version, occurrence ID, treasury account legs and the linked journal. `JournalEntry` persists currency, source UUID/version and journal lines. `TreasuryGLReconciliationRun` only persists cutoff, aggregate totals/counts, exceptions and an evidence hash. The current service's movement and journal ID lists are transient payload input, not typed persisted membership. [Treasury models](../../../../apps/treasury/models.py), [Accounting journals](../../../../apps/accounting/models.py), and [the native service](../../../../apps/treasury/services.py) establish this.

**Canonical requirement:** the declared grain is `cutoff/currency/source_identity`; source identity/version and membership need immutable native evidence. A hash is evidence integrity, not a recoverable source set.

**Engineering consequence:** Reporting cannot infer currency or replay membership from present Treasury/Accounting records. The source scope must be stable across repeats; a hash of each changing input set cannot be the source identity.

**Recommended Human decision:**

1. Define `source_identity` as the persisted `TreasuryAccount.pk` of the included `TreasuryMovementLeg`, because it is the existing Treasury cash-source scope used by the native service's account mapping. It is distinct from a movement occurrence and a journal source UUID.
2. Add an immutable `TreasuryGLReconciliationSlice` for each `(organization, cutoff_date, currency, treasury_account)` under one parent `TreasuryGLReconciliationRun`.
3. Each slice pins per-slice Treasury/GL totals, evidence hash, grain-local revision/predecessor, and immutable membership evidence: movement ID, occurrence ID, version, currency, status; leg ID/direction/amount/account; journal ID, currency, source UUID/version/status; and included journal-line ID/account/debit/credit.
4. Parent totals must equal all slices. A movement without a valid posted journal or a source-version mismatch is recorded as an exception and cannot create a fabricated Accounting-side source identity. Mixed currency/account sources create distinct slices; they must never be aggregated into one declared grain.
5. Existing runs are **UNBACKFILLABLE-WITHOUT-INFERENCE** for currency, source identity, membership and source versions. Retain them with `legacy_unverified` provenance only.

## 5. Recommended D05: native-run eligibility

| Pair | Completed proof | Current-state eligibility | Failure / invalidation / review |
| --- | --- | --- | --- |
| `subledger_gl` | Parent run and every required account slice plus source evidence commit atomically. | A completed, non-invalidated slice is eligible even if its difference is nonzero. | A failed transaction leaves no completed candidate. An append-only invalidation record, with actor/reason/evidence, makes a completed slice ineligible. Existing independent review remains evidence; it does not change financial facts. |
| `treasury_bank` | Immutable native run commits after an accepted statement import and exact retained bank evidence. | A completed, non-invalidated run is eligible even if unmatched/uncleared exceptions remain. | A failed transaction is not a candidate. Add append-only invalidation only if a later approved source defect invalidates the run. Review remains independent evidence, not an automatic currentness gate. |
| `treasury_gl` | Parent run and every required currency/account slice plus source evidence commit atomically. | A completed, non-invalidated slice is eligible even with a mismatch/exception. | Same failed/invalidation/review treatment as Subledger. |
| `payroll_insurance` | Immutable statutory reconciliation exists for its immutable output, whose calculation originates from a finalized Payroll run. | A reconciliation is eligible if its output is not cancelled and it has no later correction/cancellation in the same output series. `matched`/`exception` is an outcome, not execution success. | Reversed/cancelled payroll/output lineage or a successor statutory output removes current eligibility but preserves historical evidence. Existing revision/correction chain supplies ordering; no new native-run lifecycle field is proposed. |

**Recommended Human decision:** approve this eligibility distinction. A mismatch may be a valid completed control result; current selection means the latest valid evidence, never an assertion that the pair matched. Independent review remains visible and may be required by any separately configured material-disposition rule, but it does not silently replace completion as the candidate fact.

## 6. Recommended D06: ordering and supersession

**Repository fact:** existing native run models have timestamps and UUID identifiers, but neither is an approved business sequence. Payroll statutory outputs already have `(series_id, revision)` uniqueness and explicit `corrects` lineage.

**Recommended Human decision:**

- For prospective Subledger and Treasury–GL slices, allocate a positive `grain_revision` under `transaction.atomic()` while locking the exact grain scope. Link every revision after the first to one `supersedes` predecessor. Enforce unique `(organization, full declared grain, grain_revision)` and at most one successor for a predecessor.
- For prospective Treasury-bank runs, add `grain_revision` and `supersedes` to the existing run because account/import/as-of already make its complete grain.
- For Payroll insurance, use the existing statutory output `series_id`, `revision` and `corrects` relation. There is no repeat execution for an identical output because its reconciliation is one-to-one; a successor output is ordered by its existing revision.
- A newer completed eligible revision supersedes the predecessor only for current-state reads. A later failed or invalidated candidate does not displace the last eligible result. If a prospective row lacks a unique revision/predecessor chain, fail closed. Legacy unsequenced rows are history only and never selected as current.

## 7. Recommended D07: immutable traceability

| Pair | Native run/slice ID and revision | Source identity/version/occurrence | Snapshot, as-of and lineage |
| --- | --- | --- | --- |
| `subledger_gl` | Parent run ID; account-slice ID and grain revision. | Account FK; obligation ID plus `source_kind`, `source_uuid`, `source_version`, `source_line_key`, source hash; journal/journal-line IDs and journal source UUID/version. | Slice hash, direction/as-of, predecessor, invalidation/review evidence. |
| `treasury_bank` | Run ID and grain revision. | Treasury account, accepted statement import/line IDs, clearing/proposal/reversal IDs, linked movement ID/version/occurrence. | Statement payload/acceptance hash, as-of, predecessor, invalidation/review evidence. |
| `treasury_gl` | Parent run ID; currency/account-slice ID and grain revision. | Treasury account, movement/leg IDs, occurrence/version, linked journal/journal-line IDs, journal source UUID/version. | Slice hash, cutoff, predecessor, invalidation/review evidence. |
| `payroll_insurance` | Reconciliation ID; statutory output series/revision. | Finalized payroll run, calculation/output IDs, policy/schema versions and output content digest. | Calculation source/policy snapshot, series correction chain, output generation time. |

**Recommended Human decision:** approve these as distinct evidence values. A run ID, run revision, source version, business occurrence and snapshot hash must remain separate fields/concepts. Reporting copies only the approved native references into its read snapshot; it creates no competing financial identity.

## 8. Exact target model and migration design

> **Successor decision record (2026-10-15):** The Human Decision Maker approved
> the required AP/AR control-account contract as
> [PD-034](../../../architecture/BONIRA_PD_034_CONTROL_ACCOUNT_MAPPING.md). The
> implementation uses that bounded Accounting-owned mapping/pin contract; this
> reauthorization remains the authority for the nonfinancial legacy-provenance
> migration and native evidence scope.

| Owner / target | New field or relation | Nullability and immutability | Constraint/index | Historical and forward behavior |
| --- | --- | --- | --- | --- |
| Subledgers / `SubledgerReconciliationAccountSlice` | New immutable child: parent run, organization, direction, as-of date, control-account FK, totals/difference, evidence hash, `grain_revision`, `supersedes`. | Required for new slices; immutable after insert. | Unique `(run, control_account)`; unique `(organization, direction, as_of_date, control_account, grain_revision)`; one successor per predecessor; current lookup index over grain/revision. | No old slices. New runs create every required slice atomically. |
| Subledgers / `SubledgerReconciliationObligationEvidence`, `SubledgerReconciliationJournalLineEvidence` | New immutable links to account slice with persisted source-version snapshots and contribution values. | Required for new complete slice evidence; immutable. | Unique slice/source identity; FK `PROTECT`; indexes on source and slice. | No historical inferred membership. |
| Subledgers / `SubledgerReconciliationSliceInvalidation`, `SubledgerReconciliationRunProvenance` | Append-only invalidation record; one-to-one provenance record. | Invalidation optional; provenance required for newly classified legacy rows. Immutable. | One invalidation per slice; one provenance record per parent run; reason/actor/time/hash required. | Data migration writes `legacy_unverified` provenance for existing runs only. |
| Treasury / `TreasuryGLReconciliationSlice` | New immutable child: parent run, organization, cutoff, currency, Treasury-account source identity, totals/hash, `grain_revision`, `supersedes`. | Required for new slices; immutable. | Unique `(run, currency, treasury_account)`; unique `(organization, cutoff, currency, treasury_account, grain_revision)`; one successor per predecessor; current lookup index. | No old slices; prospective writer captures all evidence atomically. |
| Treasury / movement and journal-line evidence, slice invalidation, run provenance | New immutable membership rows and append-only invalidation/provenance records. | Membership required for new complete slice; invalidation optional. | Unique slice/movement-leg and slice/journal-line; FK `PROTECT`; source/slice indexes. | Data migration writes `legacy_unverified` provenance only; never recomputes membership. |
| Treasury / `BankReconciliationRun` | Add nullable legacy-compatible `grain_revision` and `supersedes`; add immutable run invalidation/provenance child if not shared. | Nullable for history; required by prospective service validation, not immediately DB non-null. | Unique prospective full grain/revision via conditional unique constraint; predecessor one-to-one; current lookup index. | Historical rows retain null revision and legacy provenance. |
| Payroll | No schema change proposed. | Existing immutable statutory output/reconciliation and correction chain remain authoritative. | Existing one-to-one reconciliation/output and series/revision constraints. | Existing links are derivable; no invented lifecycle history. |
| Reporting | No missing financial-identity model or data migration. | Read snapshots remain immutable. | Existing tenant/scope protections apply. | Read query consumes only source-owned evidence or returns uncomparable/unverifiable. |

**Final migration impact: `SCHEMA + DATA-MIGRATION`.** The schema expansion is necessary for prospective source-owned evidence and deterministic ordering. The only allowed data migration creates a nonfinancial `legacy_unverified` provenance record for existing Subledger, Treasury–GL and bank native runs. It must not populate account identity, currency, source membership, revision, amounts or source versions. New evidence remains nullable for existing history; prospective service validation enforces completeness. A reverse code deployment can cease using new projections, but migrations must not automatically drop immutable evidence or erase history. Rehearsals must cover forward, reverse-code, reapply, interrupted data migration, checksum, concurrent same-grain allocation, cross-tenant denial and lock duration.

## 9. AC/DoD and package decision

All 16 CEP-006 Acceptance Criteria are **UNCHANGED**. The remediation provides evidence needed to meet IMB-0044's existing current-state, as-of/freshness, source/version, no-write and repeated-snapshot requirements; it adds no financial formula, accounting posting, ledger correction or source authority.

The scoped DoD is **UNCHANGED in outcome** and supplemented in implementation evidence: source-domain model/service/migration tests, native source membership/version tests, legacy-unverified behavior, same-grain concurrency/order, source authority/no-write, tenant scope, migration forward/reverse/reapply rehearsal, focused Reporting tests, and existing IMB-0048/IMB-0066 regression. No AC or DoD is weakened.

**Recommended packaging decision: CEP-006 — reauthorized with bounded migration impact.** The objective, 16 AC, DoD outcome, financial authority and DAG meaning remain unchanged. The target work is the smallest source-owned evidence foundation required to make the existing `subledger_gl`, `treasury_bank` and `treasury_gl` read correction truthful. Direct-source source-model remediation is explicitly excluded and retains its future source-domain governance. A separate remediation CEP is therefore **not recommended**. The existing CEP-006 package must receive a specific canonical amendment; AUTH-BATCH-002 alone does not supply it.

## 10. Proposed bounded Human Authorization

> **Authorize a bounded reauthorization of CEP-006 / IMB-0044 in Development/non-production on local `main`. Replace CEP-006 Migration Impact `NONE` with `SCHEMA + DATA-MIGRATION` solely to persist prospective, source-owned reconciliation evidence and nonfinancial legacy provenance for `subledger_gl`, `treasury_bank`, and `treasury_gl`. Authorize the exact source-domain models, relations, constraints and indexes described in `CEP-006_REAUTHORIZATION_DECISION.md`: Subledger account slices and membership evidence; Treasury–GL currency/Treasury-account slices and membership evidence; Treasury-bank grain revision/predecessor and native provenance/invalidation evidence; and the limited data migration that creates `legacy_unverified` provenance records without inferring historical account, currency, source membership, source version, amount or business sequence. Authorize corresponding source services, Reporting read queries, source/version lineage, tenant-scope and no-write tests, same-grain concurrency tests, focused regression, Ruff, Django checks, migration-drift verification, and forward/reverse-code/reapply migration rehearsal.**
>
> **This authorization preserves the 16 CEP-006 Acceptance Criteria, DoD outcome, financial authority and current CEP DAG. It excludes production migration, production deployment, production cutover, irreversible production change, unrelated source-domain remediation, new accounting or Reporting authority, financial posting or journal correction, any inferred historical backfill, new consumer activation, CEP-009/CEP-011/CEP-013 implementation, Human Sign-off, UAT certification, and production certification. CEP-006 must reach EXECUTION COMPLETE before the already-authorized serial queue may continue.**

## 11. Implementation and queue resume conditions

1. The Human Decision Maker approves D02–D07 recommendations and the exact bounded authorization above, including its `SCHEMA + DATA-MIGRATION` classification.
2. The canonical CEP-006 execution package/manifest is amended with the migration scope, target models, exclusions and evidence plan; its original immutable source package remains historical.
3. Repository grounding, actual touch set and migration plan are repeated against the then-current local `main` before mutation.
4. CEP-006 reaches **EXECUTION COMPLETE** only after the authorized implementation, focused tests, representative regression, lint/system/drift checks and migration rehearsal evidence pass or have valid evidence-backed classification.
5. Only then may the serial queue continue in order: CEP-009, CEP-011, CEP-013. A partial, failed or blocked CEP-006 keeps the queue stopped.
