# CEP-037-FINDING-002 — BLOCKER-SPEC / eligibility predicate

2026-10-18. Finding001's persistence/migration restriction is resolved by HUMAN-CEP037-PERSISTENCE-20261018. Canonical migration amendment and SHA verification are complete. This is a separate business-semantic gap discovered before any CEP037 product/schema/data mutation. The Human decision's point 7 explicitly requires stopping for such a gap.

## Concrete source distinction

`apps/contracts/contractual_services.py::_approve_contractual_record_domain` accepts an explicit Boolean `entitlement_approved`, including False, and optional `approved_amount`. It persists status APPROVED for that decision. Thus APPROVED is not equivalent to positive entitlement or a positive amount. Approved cancellations also use this path; `create_contractual_revision` gives them a CANCELLATION action and source predecessor. Source rules and decision authority remain valid and unchanged.

`BONIRA_VARIATION_BILLING_HANDOFF_SPECIFICATION.md` says: "Eligible approved Variation may create/update only Billing Eligibility or Billing Draft." It requires source version and correction/reversal lineage but defines no eligibility predicate over the source's distinct approval/entitlement decisions. PD013 and IMB0029 repeat the ownership/boundary/eligible-source requirement without defining whether a false-entitlement approved original/correction should create an active eligibility, a review candidate, or only invalidate an earlier eligibility. SPEC031's completion register marks it Complete; that metadata does not supply the missing predicate. No source was declared absent: the canonical artifacts were recovered previously and their archive/member hashes reverified against EV001.

The canonical journey register describes historical automatic final effects as deferred-by-design; it does not resolve the V1 L2 eligibility predicate. The integration registry establishes L2 and Contracts-to-Billing ownership only. Financial source-contract completion covers INTB01/INTB07, not an additional INTC02 eligibility policy. Repository-wide Billing/Contracts and architecture searches found no existing predicate or consumer contract for these cases.

The earlier Finding001 statement that no source business rule was missing was too broad. The source Variation lifecycle is defined; its mapping to Billing eligibility is not fully defined for these concrete cases. That statement is corrected here without rewriting its historical evidence or treating the migration authorization as a business-rule decision.

## Specific Human decision requested

Confirm or replace this proposed predicate:

- An original or correction source must be the latest approved Variation in its source series and have `entitlement_approved=True` to create active Billing eligibility.
- Missing or zero `approved_amount` does not create an inferred financial value or disqualify source availability; eligibility alone has no claim/valuation/approval effect.
- An approved cancellation or a latest approved correction with `entitlement_approved=False` deactivates an earlier eligibility by retained source/target predecessor lineage; it creates no new active eligibility.
- An approved original with `entitlement_approved=False` creates no active eligibility. Source occurrence/error/inactive evidence may be retained for idempotency and reconciliation, without treating it as billable.

The above is a proposal, not an approved contract or current product behavior. Alternative authoritative eligibility policy/evidence is also sufficient. Technical table layout, uniqueness, locks, immutable event storage and retry mechanics remain ordinary engineering choices once the business predicate is established; no further decision packet is needed for equivalent safe storage choices.

## Impact and boundaries

AC01-06 remain UNVERIFIED, scoped DoD BLOCKED, execution FAILED at pre-implementation entry. No CEP037 models/migrations/services/permissions/tests/data were changed and no new verification PASS is claimed. Bounded persistence authority remains approved and available; this does not reopen Finding001. Do not amend Scope/AC/DoD or unrelated canonical semantics, create product persistence, implement a guessed filter, or claim GATE05 PASS. Preserve completed CEP035 and all existing UTV. Queue stops on this specific unresolved business decision.

## Resolution — 2026-10-18

RESOLVED by explicit HUMAN-CEP037-ELIGIBILITY-20261018. The governing canonical supplement in docs/governance/cep/supporting/CEP-037_VARIATION_BILLING_ELIGIBILITY_POLICY.md supplies the exact latest-approved-effective-chain predicate, amount independence and false-entitlement/cancellation deactivation. No further business-rule decision is pending for this finding. Historical discovery/proposal retained.
