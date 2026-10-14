# CEP-005 — SPEC-008 / INT-B11 specification resolution proposal

**Status: PROPOSED / PENDING PRODUCT OWNER APPROVAL — READY FOR APPROVAL.** Existing frozen PD-010 and canonical SPEC-008/INT-B11 records were independently located during the subsequent verification run. This document proposes supplementary root details; it does not replace those records. No proposal in this document is approved, frozen or canonical.

Date: 2026-10-14. Scope: CEP-005 / IMB-0030 only. Existing AUTH-BATCH-001 is unchanged. CEP-005-FINDING-001 remains BLOCKED pending explicit Product Owner approval of the resolved semantics. GATE-05 is an EXIT GATE / UNCHANGED. No implementation, producer activation, migration, data change, Human Sign-off or next CEP is performed.

## Grounding and source authority

Branch `main`; HEAD `0b0cfcdabb93e4e6215d6f2805e763dd82f99cf4`. Pre-draft worktree: existing ROADMAP.md modification and five untracked CEP-005 execution/evidence files. All are preserved. This run's sole new artifact is this resolution document; it does not replace sealed history or alter AC, DoD, DAG, authorization or existing execution evidence.

| Source | Exact location and relevant record | Use / provenance limit |
| --- | --- | --- |
| S1 — Human resolution instruction | `C:/Users/azera/.codex/attachments/6202c535-3519-4583-9ddb-ad713500acae/Pasted text.txt`, sections 1–9 | Explicit authority constraints and authorization to draft proposals. PD-010 and IMB-0030 availability are already established. No permission to approve this draft. |
| S2 — Final Implementation Master Backlog | `C:/Users/azera/Desktop/New folder/BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG_MICRO_CORRECTION_PACKAGE_20261012 (1)/BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG.csv`, rows 31–34, IMB-0030–IMB-0033 | Canonical outcome/scope/AC/DoD and downstream ownership records, inspected directly. Not a complete SPEC-008 or INT-B11 definition. |
| S3 — Dependency Edge Register | `C:/Users/azera/Desktop/New folder/BONIRA_UAT_DEPENDENCY_TARGETED_CORRECTION_PACKAGE_20261012/BONIRA_IMPLEMENTATION_DEPENDENCY_EDGE_REGISTER.csv`, rows 25–27, DEP-0024–DEP-0026 | Root-to-child contract dependencies; Project Controls authority and approved-producer-only effects. No dependency change proposed. |
| S4 — Final corrected package | `C:/Users/azera/Desktop/New folder/BONIRA_CODEX_EXECUTION_PACKAGE_DESIGN_FINAL_POSTV1_READINESS_CORRECTED_PACKAGE_20261013/packages/CEP-005.md`, Scope, Out of Scope, Prerequisites | IMB-0030-only root, no generic producer, GATE-05 exit classification. Historical authorization label superseded by AUTH-BATCH-001. |
| S5 — Recovery evidence | `E:/Construction_Company_Solution/CEP-005_EXECUTION_MANIFEST.md`, Canonical source recovery and subsequent PD verification | Earlier limited search did not recover sources; subsequent verification found them in the exact consolidated directory named by PD-032. Historical absence is superseded. |
| S6 — Frozen PD-010 | `E:/ERP_Construction_Documents/New Version/BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013/Consolidated_Packages/BONIRA_PRODUCT_DECISION_FREEZE_CONSOLIDATED_LATEST.zip` :: `BONIRA_FINAL_PRODUCT_DECISION_REGISTER.md`, lines 263–279; companion freeze completion record | Independently verified frozen decision and freeze provenance; see CEP-005_PD_010_APPROVAL_READINESS.md. |
| S7 — Canonical SPEC-008 / INT-B11 | Same consolidated directory, `BONIRA_REQUIRED_SPECIFICATION_COMPLETION_CONSOLIDATED_LATEST.zip` :: `BONIRA_PROJECT_COST_PRODUCER_CONTRACT_SPECIFICATION.md`, lines 3–33 and 42; `BONIRA_INTEGRATION_REGISTRY.csv`, row 22; specification completion register, row 9 | Existing specification structure COMPLETE; INT-B11 official L2 ROOT / NOT IMPLEMENTED. Source-specific mappings/cutoffs remain activation gates. Not a freeze or approval of this proposal. |

PD-010 consistency now uses the independently verified original frozen register (S6). Consolidated canonical IMB-0030 row 31 has the same member hash as S2. S7 dictates the common idempotency key and child cancellation/revision rules; conflicting proposal text was corrected, with history recorded in the readiness report. DTR-GAP/UGR references supply no inferred additional semantics. Current product models/fields do not determine business behavior.

## Semantic decision register

Every normative point below maps to a register entry. `D` means DERIVED FROM EXISTING AUTHORITY; `P` means PRODUCT OWNER DECISION REQUIRED. Derived constraints remain authoritative through their sources; the proposed specification as a whole requires approval.

| ID | Classification | Semantic point | Authority / disposition |
| --- | --- | --- | --- |
| D01 | DERIVED FROM EXISTING AUTHORITY | Source domain owns source state; Project Controls owns ProjectCostFact; no authority transfer | S1; S2 IMB-0030; S3 |
| D02 | DERIVED FROM EXISTING AUTHORITY | No approved producer contract means no ProjectCostFact; no generic Procurement/Contracts producer | S1; S2 IMB-0030 exclusions; S3 |
| D03 | DERIVED FROM EXISTING AUTHORITY | Root governs approved PO/Subcontract commitment evidence at L2 | S2 IMB-0030; S4 |
| D04 | DERIVED FROM EXISTING AUTHORITY | Child producers own source-specific eligibility, mapping and lifecycle | S2 IMB-0031–0033; S3 |
| D05 | DERIVED FROM EXISTING AUTHORITY | Source identity/version retained; same occurrence/version cannot duplicate an effect | S2 IMB-0030 AC2–3 |
| D06 | DERIVED FROM EXISTING AUTHORITY | Failed target mutation preserves source authority; retry retains validation and error/retry evidence | S2 IMB-0030 AC4 |
| D07 | DERIVED FROM EXISTING AUTHORITY | Correction/reversal linkage and source/target reconciliation identify active source version and effect | S2 IMB-0030 AC6 and DoD |
| D08 | DERIVED FROM EXISTING AUTHORITY | Explicit project/cost mapping; no inferred fact or automatic accrual | S2 IMB-0031 exclusions and IMB-0033 integration impact |
| D09 | DERIVED FROM EXISTING AUTHORITY | Authorized tenant and explicit object scope remain mandatory; UI context grants no authority | S2 IMB-0030–0033 required scope |
| D10 | DERIVED FROM EXISTING AUTHORITY | CEP-005 does not implement child producers, alter DAG/AC/DoD, or pass GATE-05 by drafting | S1; S3; S4 |
| P01 | PRODUCT OWNER DECISION REQUIRED | Root eligibility categories and bounded cancellation/correction instructions | Proposed eligibility table below |
| P02 | PRODUCT OWNER DECISION REQUIRED | Supplementary envelope/lineage and payload-conflict rules under the existing canonical key; no replacement key | Canonical key dictated by S7; additional provenance proposed below |
| P03 | PRODUCT OWNER DECISION REQUIRED | Explicit predecessor/successor ordering and current-version selection | Proposed version table below |
| P04 | PRODUCT OWNER DECISION REQUIRED | Exact replay, stale replay and changed-payload conflict dispositions | Proposed replay rules below |
| P05 | PRODUCT OWNER DECISION REQUIRED | Additive delta corrections; bounded release/reversal meanings and effect lineage | Proposed effect table below |
| P06 | PRODUCT OWNER DECISION REQUIRED | Durable attempts/results and atomic target/audit boundary with failure evidence outside rollback | Proposed retry/failure rules below |
| P07 | PRODUCT OWNER DECISION REQUIRED | Read-only reconciliation scope, mismatch categories and active-target derivation | Proposed reconciliation rules below |

### Product Owner choices

Recommendations form one coherent proposal. No recommendation is effective before approval. Where only one option is supportable within existing authority, no artificial alternative is supplied.

| Decision | Question | Option A | Option B | Recommended / reason | Impact if unresolved |
| --- | --- | --- | --- | --- | --- |
| P01 | How does the root distinguish eligibility without owning source lifecycle? | Derived eligibility categories plus separately validated cancellation/correction instructions; delegate actual source states to children | No compliant alternative identified within delegated ownership | A: supports cancellation without permitting cancelled sources to create fresh commitments | Cannot distinguish valid lifecycle corrections from invalid creation |
| P02 | Which supplementary context and conflict evidence must accompany the existing common key? | Retain validated tenant/domain/project, exact contract revision, correlation and relevant line/event lineage; reject changed semantic payload under the canonical key | No alternative replacing the canonical key is permitted | A: makes lineage inspectable while preserving S7's required key; extra context never mints another effect | Supplementary envelope/conflict handling remains undefined; the canonical key itself is already dictated |
| P03 | How are newer/current versions established? | Source-validated successor/predecessor relationship; one accepted current chain per source occurrence stream, no inferred lexical/time ordering | Source-specific approved monotonic revision comparator; root uses that comparator and records predecessor evidence | A: avoids inferring order from opaque IDs or timestamps; child may later specify a comparator under its contract | Cannot validate supersession or distinguish stale input |
| P04 | What happens to stale and repeated input? | Valid exact accepted replay returns historical result without effects; unseen stale input or changed payload under an existing occurrence key is rejected | Unseen stale input receives a durable no-effect stale disposition; payload conflicts still reject | A: makes missing/out-of-order effects explicit; replay never silently reactivates superseded evidence | Retry/replay acceptance is undefined |
| P05 | How is corrected target history represented? | Immutable linked delta/offset effects; source producer supplies approved correction/release/reversal mapping | Linked full offset plus replacement, atomically, instead of a delta; same source-specific authority rules | A: minimum additive root contract without inventing replacement business amounts | Correction algebra and active-target interpretation remain undefined |
| P06 | What is the minimum durable failure contract? | Persist attempt evidence before target effects; atomically commit target effects, linkage and success audit/result; retain failure outcome independently of failed target rollback | No compliant evidence-free alternative: memory-only errors violate AC4 | A: preserves inspectable attempt/error/retry evidence without selecting an outbox, queue or observability platform | Cannot prove failure/retry or atomicity obligations |
| P07 | What does root reconciliation do? | Read-only comparison of authoritative active source evidence to committed linked target effects; report discrepancies without repair | No compliant automatic-repair alternative within this resolution's authority boundary | A: detects lineage problems without silently exercising domain authority | Cannot verify AC6 or safely identify active target effects |

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

## Consistency and review result

| Check | Result and basis |
| --- | --- |
| PD-010 | PASS against independently verified S6; explicit source-specific contracts/mappings/cutoffs preserved |
| IMB-0030 | PASS: preserves six AC/DoD; proposals make missing semantics explicit and approval-dependent rather than weakening the criteria |
| IMB-0031 / IMB-0032 / IMB-0033 | PASS: child eligibility/mapping/lifecycle remains delegated; no child implementation absorbed |
| Dependency Edge Register | PASS: DEP-0024–0026 retained; no new prerequisite, edge or phase change |
| No-Inference rule | PASS: no unsupported semantics asserted as existing authority; P01–P07 explicitly require decisions; no implementation from this draft |
| Authority boundaries | PASS: source authority retained; Project Controls owns ProjectCostFact; approved producer contract required |

Current conflicts: **0**, after correcting the common-key and cancellation-action contradictions proven by S7. Historical conflict details and clause-level classification are in CEP-005_PD_010_APPROVAL_READINESS.md. New authority introduced: **NO**. New business KPI: **NO**. New generic producer: **NO**. Scope expansion: **NO**. These are proposal-level consistency results, not runtime verification or certification.

Proposal coverage: SPEC-008 **COMPLETE FOR REVIEW**; INT-B11 **COMPLETE FOR REVIEW**. Existing-authority-derived decision groups: **10**. Product Owner decision groups: **7**. Unresolved semantic decisions: **P01–P07** until explicitly approved or revised. No source-specific child eligibility/valuation/lifecycle rule is supplied or requested as a root decision.

The Product Owner must explicitly approve or revise P01–P07 and the resulting proposed SPEC-008/INT-B11 text. Only then can a separately recorded approval resolve CEP-005-FINDING-001 and permit resumption under the existing bounded authorization. Approval is not a freeze, Human Sign-off, gate passage, migration authorization or authorization for CEP-007.

## Documentation closeout and validation

Only this specification-resolution artifact is created. Existing CEP evidence, ROADMAP.md changes, sealed decisions and product files are preserved. ROADMAP.md's CEP-005 entry was checked: delivery remains blocked. Its older source-availability wording is superseded by the current execution manifest's recovery record (PD-010 available; GATE-05 exit gate); it is not treated as a new entry blocker. This run's artifact-only boundary leaves that prior roadmap text untouched. Validation passed for source-row comparison, decision/section coverage, artifact whitespace and touch set. Application tests and migrations are not applicable to this documentation-only proposal.
