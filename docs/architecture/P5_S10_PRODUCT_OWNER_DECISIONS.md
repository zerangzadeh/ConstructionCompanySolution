# P5-S10 Product Owner Decisions

**Status:** P5-S10-D01 through D05, the implementation and focused PostgreSQL
verification were Product Owner accepted on 2026-10-02.

**Scope:** Revision-specific commercial admissibility only. This is not
comparison, scoring, ranking, evaluation, award, contractual/financial effect, or
a downstream handoff.

## Accepted decisions

| Decision | Accepted disposition | Runtime consequence |
| --- | --- | --- |
| D01 — lifecycle and outcome | `prepare -> approve`; only `ADMISSIBLE`, `INADMISSIBLE`, or `REVIEW_REQUIRED` may be prepared. | A preparation is immutable; approval creates an immutable decision for that exact quote revision. |
| D02 — controlled reasons and evidence | The v1 code-owned reason catalogue is `requirements_met`, `late_submission`, `required_evidence_missing`, `commercial_nonconformance`, and `exception_review_required`. | The service validates the state/reason pairing and retains the close manifest, opening event, package fingerprint, actor/time, confidential rationale and idempotency fingerprint. |
| D03 — confidentiality and prerequisites | Commercial admissibility may use only an opened effective revision with active revision-specific confidential access. | Every prepare, withdraw and approve transaction revalidates the active Tenant, membership, project scope, close-manifest entry, opened revision, explicit confidential grant and exact evidence fingerprint. No generic Documents/DMS route is added. |
| D04 — authority and SoD | `rfq_quotes.prepare_admissibility` and `rfq_quotes.approve_admissibility` are separate, default-ungranted permissions. The existing Platform/Tenant policy pattern controls self-approval for this non-Protected operation. | An active, configured `rfq-admissibility-self-approval` policy is required and pinned to the decision. Missing policy fails closed; when disabled, preparer and approver must differ. |
| D05 — withdrawal, correction and history | A pending preparation can be withdrawn before approval. Approved decisions never mutate; a correction is a new approved decision that explicitly supersedes the current decision. | Withdrawal, approval and correction are append-only, tenant/revision scoped, idempotent where applicable, locked and audited. |

P5-S10 does not classify admissibility approval as a Protected Operation and does
not weaken the already-Protected P5-S09 reveal control. The Tenant policy choice
does not supply a missing permission, membership, scope, confidential grant, close
custody, opening, or evidence prerequisite.

## P5-S11 dependency finding

The P5-S11 comparison, evaluator-governance, exception and sourcing-only award
boundaries are accepted in the authoritative
[P5-S11 Product Owner decision packet](P5_S11_PRODUCT_OWNER_DECISION_PACKET.md).
The detailed comparison, evaluator, exception, allocation, tie/no-award and
finalization rules are also accepted. P5-S11 narrowly supersedes P5-D01 only for
policy-enabled self-finalization of its immutable sourcing-only award operation;
every other P5-D01 Protected-operation control remains unchanged. Until separately
implemented, a `REVIEW_REQUIRED` S10 decision remains only admissibility evidence
and cannot be interpreted as comparison eligibility, evaluation clearance, award
authority, or an exception approval.

## Verification closeout

An isolated PostgreSQL database applied S10, rolled it back to Procurement 0008,
and reapplied it successfully. Focused S10 tests passed (9 tests), including
permission/catalog behavior, Tenant/revision isolation, confidential-access
revocation, policy-controlled self-approval, withdrawal, correction, idempotency,
concurrency and immutability. The minimum P5-S07–S09 prerequisite regression set
also passed (27 tests and 4 subtests). No full-suite or seed run was used.
