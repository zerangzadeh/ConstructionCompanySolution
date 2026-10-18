# CEP-037 governing Variation Billing eligibility policy

Status: APPROVED Human Product Decision, 2026-10-18. Decision ID HUMAN-CEP037-ELIGIBILITY-20261018. Canonical supplement to PD013 / SPEC031 for CEP037 only; the recovered upstream archives remain unchanged.

1. Billing eligibility is source-availability only.
2. For a Variation lineage, the latest approved effective Original or Correction with entitlement_approved=True creates active Billing eligibility.
3. Eligibility is independent of approved_amount. An absent or zero approved_amount does not by itself deactivate eligibility.
4. An approved Cancellation, or an approved effective Correction with entitlement_approved=False, deactivates prior eligibility for that lineage.
5. Prior approved states and source lineage remain retained and auditable; historical eligibility evidence is not overwritten.
6. Latest means the latest approved effective state within the same governed Variation lineage/revision chain, not merely the newest record by timestamp.
7. CEP037 authorizes only determination of whether an eligible approved source exists for Billing consumption.
8. No pricing/valuation calculation, derivation of billable amount, Billing/invoice approval, accounting recognition/posting or inferred financial amount from entitlement is authorized.
9. Zero/absent approved_amount may affect downstream valuation or billing execution under other governed rules; CEP037 must not interpret it as absence of entitlement eligibility.

Human explicitly authorizes recording this Product Decision/canonical policy, updating applicable canonical source and prompt/hash provenance, and resuming under the already approved bounded migration authorization. No unrelated Scope/AC/DoD/dependency/production authority change. No Git writes. Finding002 is resolved by this decision.
