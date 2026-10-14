# CEP-005 — approved SPEC-008 / INT-B11 supplement

Document identity: `CEP-005-SPEC008-INTB11-SUPPLEMENT`

Version: `1.0`

Status: **CANONICAL SUPPLEMENT / PRODUCT OWNER APPROVED**

Approval authority: Human/Product Owner

Approval date: 2026-10-14 (session date; no precise approval timestamp supplied).

Scope: supplementary root semantics for CEP-005 / IMB-0030 only.

## Approval and precedence

The Human/Product Owner explicitly approved corrected P01–P07 and the reviewed resolution/readiness documents in the canonicalization handoff at `C:/Users/azera/.codex/attachments/1739e803-4142-4fe3-8105-82786d99ea77/Pasted text.txt`. This version records that approval and adds no new semantics. It does not modify frozen PD-010 or sealed canonical archives, activate a producer, or authorize product implementation in this run.

Sources: [corrected resolution](CEP-005_SPEC_008_INT_B11_RESOLUTION.md) and [PD verification/readiness](CEP-005_PD_010_APPROVAL_READINESS.md). Historical proposal labels in those documents remain review provenance; this version is the current approved supplement. Original frozen PD-010 and recovered canonical SPEC-008/INT-B11 remain governing constraints. Drafting words such as “proposed” in the verbatim approved body below identify the reviewed text and do not leave P01–P07 unapproved. Alternative options in the review sources are not selected or normative.

AUTH-BATCH-001 and CEP-005 scope, AC, DoD and DAG are unchanged. No Human Sign-off, Production Acceptance, Go-Live, new freeze or GATE-05 passage is recorded. Product implementation requires a separate CEP-005 implementation-resume instruction and fresh actual-touch-set confirmation.

## Approved decisions

| Decision | State | Approved recommended resolution |
| --- | --- | --- |
| P01 | APPROVED | Use the six root dispositions; child determines exact eligibility; cancellation always maps to approved remaining-commitment release |
| P02 | APPROVED | Retain exact contract revision, tenant/domain/project, correlation and relevant event/line lineage; reject changed semantic payload under the exact canonical key |
| P03 | APPROVED | Child-proven predecessor/successor relationship; no inferred timestamp/lexical ordering |
| P04 | APPROVED | Revalidated committed replay returns historical result; unseen stale input and payload conflict reject |
| P05 | APPROVED | Immutable delta/offset effect set using child-approved values; cancellation RELEASE, bounded correction REVERSE |
| P06 | APPROVED | Persist attempts before effect; commit target/linkage/success audit atomically; persist failures outside target rollback; unresolved evidence cannot claim success |
| P07 | APPROVED | Read-only bounded comparison and discrepancy/coverage report; no automatic repair |

## Canonical source provenance

Original archive directory: `E:/ERP_Construction_Documents/New Version/BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013/Consolidated_Packages`. All sealed archives remain unchanged.

- PD-010: `BONIRA_PRODUCT_DECISION_FREEZE_CONSOLIDATED_LATEST.zip` :: `BONIRA_FINAL_PRODUCT_DECISION_REGISTER.md`, lines 263–279; FROZEN under `BONIRA-PD-FREEZE-20261012T002549+0330` / `BONIRA-PD-FREEZE-v1.0`; companion freeze completion record. Archive SHA-256: `1c11429f2e0cc16c61b585832537e5035d19d008bccefc4e94f6d18839047599`.
- SPEC-008: `BONIRA_REQUIRED_SPECIFICATION_COMPLETION_CONSOLIDATED_LATEST.zip` :: `BONIRA_REQUIRED_SPECIFICATION_COMPLETION_REGISTER.csv`, row 9; artifact `BONIRA_PROJECT_COST_PRODUCER_CONTRACT_SPECIFICATION.md`. Structure COMPLETE; source-specific mapping/cutoff before activation. Specification member SHA-256: `fd461c762a1dab5a6e5b2dd1e847927dee179d0a62360e749c065d23d9dc4610`.
- INT-B11: same specification archive :: `BONIRA_INTEGRATION_REGISTRY.csv`, row 22; official ROOT / L2, Approved PO / Approved Subcontract to ProjectCostFact COMMITMENT, governed by PD-010. Registry member SHA-256: `6d2944e120e3ff836c330177e3d0ecc2f1056407959f693542034da13f060944`.
- IMB-0030: `BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG_CONSOLIDATED_LATEST.zip` :: `BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG.csv`, row 31; unchanged root AC/DoD. Member SHA-256: `98681aba0ac4a66a77ea58543f802fe3e51d3b5bdd98748f8bc24b89dd2d717a`.

Full source/version verification and clause classifications are in the readiness source. Input hashes, this supplement's hash and approval provenance are recorded in [the canonicalization record](CEP-005_CANONICALIZATION_RECORD.md), avoiding a self-referential hash.

## Approved specification and contract body — verbatim reviewed text

Copied exactly from the corrected resolution's SPEC-008 section through its root/downstream responsibility section. No source-specific implementation or unselected alternative is added.

## SPEC-008 — proposed definition

### Purpose, eligibility and authority

SPEC-008 would govern the Project Cost commitment root and shared identity/retry/lineage conventions required by its known child producer family. INT-B11 would carry approved Procurement/Contracts commitment evidence into Project Controls-owned effects. The root cannot approve source business state, select unapproved mappings, register arbitrary source families or infer posting. Source and target authority remain separate (D01–D04, D08–D10).

The categories below are root validation dispositions, **not new stored business lifecycle states**. Source-specific state names, approval/issuance tests, cancellation authority, effective dating and eligible event mappings remain child-contract responsibilities (P01, D04).

| Category | Meaning and permitted root treatment |
| --- | --- |
| Eligible | Child contract validates the exact authoritative occurrence/version, permitted action, approval evidence and complete scope/mapping. Root may apply only that approved mapped effect. |
| Ineligible | A known source occurrence fails its approved child eligibility rule. Reject creation/adjustment; no inferred substitute action. |
| Pending/unapproved | Required source approval/issuance evidence is absent. No new commitment effect. Root does not advance source approval. |
| Cancelled | Not eligible for fresh creation. S7 dictates release of remaining commitment for PO cancellation and subcontract cancellation/termination. Child validates that instruction and remaining mapped amount; cancellation is not an interchangeable reversal action. |
| Superseded | Not eligible for a new current effect. An exact previously accepted replay can return historical evidence under P04. A valid successor instruction can correct the linked predecessor under P03/P05. |
| Invalid/unmapped | Identity/version, approved project/cost mapping or required scope is missing/inconsistent. Reject; do not invent defaults or repair source data. |

### Minimum identity and context

The proposed envelope uses conceptual requirements, not new database columns, API syntax or permission grants (P02). References may carry existing authoritative information without copying it into a new master.

| Concept | Proposed meaning |
| --- | --- |
| Source Domain | Owning source authority, selected by the approved child contract; not an arbitrary caller-provided authority claim |
| Source Type | Source aggregate/evidence type registered in that child contract |
| Source ID | Stable source-owned identity scoped by tenant/domain/type |
| Source Version | Exact immutable source revision identity; opaque to the root unless approved ordering evidence is supplied |
| Producer Contract | Exact approved child contract identifier and immutable revision governing source eligibility, permitted action and effect mapping |
| Recognition Type | Required component of S7's common key, resolved by the approved source-specific contract. The root does not invent recognition types. |
| Occurrence Identity | Supplementary source-owned event/line lineage where applicable. It does not extend or replace the canonical deduplication key or permit independent effects per line under the same key. |
| Organization | Validated tenant context resolved through existing authorized access; supplied evidence must match it |
| Project and cost target | Explicit approved project and cost mapping/reference. Required site/object context comes from the child contract; project changes are not a way to obtain a new deduplication key. |
| Effective time | Source occurrence/effective timestamp or date when required by its approved mapping; never inferred from receipt time |
| Correlation identity | Links invocation, source occurrence, target result and retries. It is diagnostic linkage, not an alternative deduplication key. |
| Requested effect and value evidence | Child-authorized action plus explicit source-backed monetary amount/currency or an immutable mapping reference that resolves them. No root valuation, FX, tax, rounding or accrual inference. |
| Prior linkage | Required predecessor/source-version and target-effect references for adjustment, supersession, release or reversal; absent for an initial occurrence where the child contract permits it |

S7's common idempotency key is exactly `ProducerContractID + SourceType + SourceID + SourceVersion + RecognitionType`. It governs logical occurrence deduplication. Validate tenant context separately (D09); neither correlation, project, domain nor line/event identifiers replace or extend this key to permit another effect. Line-level allocation may contribute only to the single approved mapped result/effect set under the common key; no independent line/event recognition granularity is invented. Source stream/version lineage retains source domain/type/ID, validated organization and producer/recognition identity; ordering remains a P03 proposal, not a new canonical key.

Retain exact approved producer-contract revision as provenance. S7 does not specify whether a revision changes ProducerContractID; do not infer that mapping or cross-contract migration behavior. A different ID does not authorize duplicate recognition of the same economic occurrence: an explicit approved source/contract transition and prior-effect linkage are required, otherwise fail closed. Normalize payload only under approved contract rules. A changed project, mapping, value, action, effective time or predecessor under an accepted common key is proposed to be a conflict; correlation and attempt IDs may change without changing semantic payload (P02/P04).

### Fail-closed and version rules

Missing/unapproved producer contract; missing/invalid mapping; invalid/unprovable source version; absent required tenant/project/object context; or an action outside the child's approved authority all produce a durable rejection and no target effect. PD-010 requires explicit source-specific cutoffs: where a child instruction requires cutoff evidence, missing/unvalidated cutoff evidence also fails closed; no global cutoff is invented. The root cannot resolve these by guessing. Source no longer eligible blocks new creation; a mapped cancellation/correction is evaluated as its own authorized instruction. A previously accepted exact replay never restores eligibility or changes prior effects (P01–P04, P06; S6/S7).

| Input situation | Proposed outcome and retained evidence |
| --- | --- |
| Same source occurrence + same version + same semantic payload | Revalidate authority/contract and identity. If previously committed, return the recorded effect/result as an idempotent replay; add attempt linkage only. If the earlier attempt failed, retry normal validation and application. |
| Same key + different semantic payload | Reject conflict; preserve accepted effect and both attempts' linkage. Require a genuine approved source correction/version. |
| Newer source version | Require child-validated successor/predecessor evidence and approved effect mapping. Apply linked correction atomically; only after commit select it as the accepted target current version. |
| Unseen older/stale version | Reject without new effects; retain mismatch evidence. No lexical comparison or timestamp-only ordering. |
| Already committed older version replay | Return historical result only after authority/contract and original occurrence validation; identify it as superseded where applicable. Do not reactivate it. If required validation now fails, reject the attempt while preserving prior history. |
| Cancellation | Child validates cancellation instruction/version and mapped remaining commitment; root applies RELEASE as dictated by S7. Original source and target history remain. |
| Source correction / superseding version | Require approved successor relationship and explicit mapping to prior effect(s); immutable additive linkage. Failed correction leaves previously committed effects intact and reconciliation exposes the source/target version mismatch. |
| Competing successors / missing predecessor / unknown ordering | Reject until authoritative source relationship and target predecessor are unambiguous; do not select by arrival order. |

Active **source** version comes from source authority. Active **accepted target** version comes from the most recent valid successor committed for that stream. They may differ after failure; the root must report that difference rather than relabel the target to match the source. Superseded versions and their producer, attempt and effect links remain inspectable (P03/P07).

## INT-B11 — proposed root contract

### Interface and effects

Conceptual input is the SPEC-008 envelope above. An approved child producer supplies and proves it; the root validates it, delegates source rules to that producer and invokes Project Controls-owned effect application. No generic endpoint accepting an arbitrary source type, model label or caller-selected mapping is permitted (D01–D04, P02). Whether application code uses a callable adapter or another internal form is an implementation choice, not a new business authority or external API.

Conceptual output: attempt/correlation identity; outcome; exact source/contract/version identity; linked committed effect references where present; prior/superseded/correcting/reversed references; and rejection/failure reason where applicable. The root returns no success before the effect boundary commits (P02/P06).

| Effect | Proposed root meaning (P05 unless noted) |
| --- | --- |
| CREATE | Initial child-approved commitment evidence creates the mapped commitment effect once. Does not recognize actual cost, accrual, payable, cash or GL. |
| ADJUST / SUPERSEDE | Append mapped difference/offset to linked prior commitment effect(s). Preserve original facts; record accepted successor and correction linkage atomically. Supersession is an evidence/version relationship, not permission to overwrite history. |
| RELEASE | Append the child-authorized reduction/discharge of outstanding commitment, with exact source and prior-effect linkage. Does not imply payment, expense, accrual or source cancellation. Child owns the release trigger and amount rules. |
| REVERSE | Append an explicit offset of identified prior commitment effect(s), only where the approved child mapping authorizes it. Original effects remain; already offset portions cannot be offset twice. Reversal is not a GL reversal or source-state mutation. |
| NO-OP / IDEMPOTENT REPLAY | Return the previously committed logical occurrence result without another economic effect (D05/P04). This is not a silent success for an invalid new instruction. |
| REJECT / FAIL-CLOSED | No committed target effect for this attempt. Record exact reason and source/contract/attempt linkage (D06/P06). Previously valid effects remain unchanged. |

The approved child supplies the economic amount and permissible prior-effect set for corrections. Root checks consistency and prevents applying the same logical correction/release/reversal twice; it does not invent cancellation amounts, negative-commitment policies or source valuation rules. Unavailable child-specific rules keep that action unavailable. An approved child instruction whose target economic effect is explicitly zero can return a linked no-effect result; zero cannot be inferred from missing data (P05).

### Retry, failure, audit and atomicity

Proposed minimum observable contract (P06, D05–D07):

1. Record a durable attempt containing exact source identity/version, requested effect, producer-contract identity/revision, correlation identity, attempt identity and retry-of relationship where applicable. No target mutation begins if required attempt evidence cannot be retained.
2. Validate current authority, source occurrence, approved contract, mapping, predecessor and replay/conflict status on every attempt. A retry token never grants approval or bypasses validation.
3. Serialize competing applications of the same occurrence/stream sufficiently to prevent duplicate/lost/colliding effects. Claim of concurrency correctness requires later applicable evidence, not this proposal.
4. Commit all target effects for that instruction, their source/correction links and success audit/result atomically. No partial linked effect set or success result may survive a failed target operation. The integration never modifies source business state, on success or failure.
5. On validation or mutation failure, retain the failure result and reason against the attempt outside the rolled-back target unit. A retry links to the failed attempt, revalidates and either commits once, returns a previously committed result, or fails closed again. Duplicate retries cannot mint new target effects.
6. If evidence persistence itself fails, report evidence failure and no claimed successful application. An unresolved attempt is not a success; it must remain distinguishable from a validated rejection or committed result. Recovery must determine actual committed outcome before another effect is allowed. No memory-only failure is sufficient final evidence.

Durable attempts/results are evidence categories, not new source approval states or workflow states. This proposal does not select storage schema, exception taxonomy, queue, outbox, job scheduler, remote API or production observability architecture. A caller transaction must not invalidate the promised durability/atomicity boundary; implementation feasibility must be checked after semantic approval. If schema or other excluded scope proves unavoidable, record a finding before proceeding; semantic approval alone does not authorize a migration. Crash recovery/performance claims remain unverified until applicable execution evidence exists.

### Correction, reversal and reconciliation

Corrections and releases reference the source instruction/version and the prior target effect(s) they change. Supersession links source predecessor to successor and prior to correcting target results. Reversal offsets explicitly identified effects; none are erased. Reconciliation derives the effective commitment from accepted initial effects plus their approved adjustments/releases/offsets without counting predecessor and successor as independent full commitments (P05/P07).

Read-only reconciliation compares authoritative source evidence with retained target lineage for an explicitly bounded organization/project, source family and as-of context supplied by the approved child contract. It reports source current version, accepted target version, effect references and discrepancies. It must not claim complete coverage where a producer, mapping, source snapshot or comparison scope is unavailable (P07).

| Detection | Proposed discrepancy |
| --- | --- |
| Eligible source instruction has no expected committed result | Missing target effect, distinguished from pending/rejected/failed attempt |
| Logical occurrence or correction contributes more than its authorized mapped effect once | Duplicate target effect |
| Prior effect remains economically active beyond its approved successor/release/reversal mapping | Stale/superseded target effect |
| Target lineage references a different version/contract than authoritative evidence | Source-version or contract mismatch |
| Correction/reversal/predecessor link cannot be resolved, or coverage is unknown | Lineage gap / incomplete comparison |

Reconciliation identifies issues, including source changes that have no successful target correction. It does not backfill, reverse, approve, repair mappings or mutate source/target records. Repair requires the appropriate separately validated child instruction; operational reconciliation and production activation are not performed by this drafting run (D10/P07).

## Root versus downstream responsibility

| Owner | Responsibility retained |
| --- | --- |
| CEP-005 / IMB-0030 | Proposed shared root evidence interface, contract gating, identity/version handling, idempotency, target transaction/audit linkage, failure/retry evidence and bounded reconciliation semantics |
| IMB-0031 — PCP-PO-COMMITMENT | Exact eligible approved/issued PO states/events, project/cost mapping, source version rules, authorized commitment amounts and release/cancellation mappings; implementation and tests remain downstream |
| IMB-0032 — PCP-SUBCONTRACT-COMMITMENT | Exact subcontract eligibility, amendments, cancellation/release and amount/mapping rules with lineage; implementation and tests remain downstream |
| IMB-0033 — PCP-GR-ACCRUAL / PCP-SERVICE-ACCRUAL | Source-specific Goods Receipt/Service Acceptance eligibility/mapping, accrual/relief, delta/reversal and reconciliation. Root identity/lineage conventions may be reused through its approved contracts; INT-B11 commitment scope does not authorize generic accrual or actual producers. |

No downstream producer is registered, activated or implemented by this proposal. Root readiness does not complete a child IMB or reverse the dependency edges (D04/D10).
