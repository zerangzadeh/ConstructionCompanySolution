# Local subcontract demo seed — 2026-11-01

User explicitly requested multiple estimates and certificates on one subcontract. A new, clearly labelled demo contract was created in the existing local development tenant `demo-construction-02`, project `PRJ-02-03`. This avoids modifying commercial conditions or finalized history on prior contracts.

Contract: `UAT-SUB-02-03`; payable subcontract; active; value 29,700,000,000 IRR. Existing party, identity snapshot, units and source example prices were reused. All writes used normal application services inside one transaction; separate existing tenant members prepared and approved records. No new roles, permissions, schema, domain behavior or exposure.

Commercial terms exist only on the NEW demo contract, labelled as synthetic. Existing service defaults were used: zero retention, recovery and insurance rates/caps and zero payment delay. No statutory rules were fabricated or activated.

## Created records

| Type | Number | Status | Amount (IRR) |
| --- | --- | --- | --- |
| Estimate | UAT-EST-SUB-02-03-01 | approved | 29700000000.00 |
| Estimate | UAT-EST-SUB-02-03-02 | draft | 14850000000.00 |
| Estimate | UAT-EST-SUB-02-03-03 | draft | 7425000000.00 |
| Payable certificate | 1 | approved | 2970000000.0000 |
| Payable certificate | 2 | approved | 5940000000.0000 |
| Payable certificate | 3 | submitted | 4455000000.0000 |

Six supporting measurements were created and independently verified. Certificates cover July, August and September 2026 and are calculated by existing services from those measurements, not assigned amounts directly. First two certificates were approved through the existing workflow; the third remains submitted for review. First estimate is approved; two remain editable drafts.

## Verification

- Eight authenticated render checks: HTTP 200 (contract, certificate list, 3 estimates, 3 certificate details).
- Post-commit verification: PASS for persisted record counts, statuses, exact amounts, item totals, gross/net reconciliation and independent approvals.
- Before/after fingerprints of CTR-02-03-04 and CTR-02-03-05, including their terms, items, estimates and certificates, match. The earlier two test estimates on CTR-02-03-04 remain. No certificate was added to that completed contract.
- Accounting JournalEntry, subledger Obligation, TreasuryMovement and PaymentRequest counts are unchanged. No recognition, posting, payment, settlement or cash history was created.
- No receivable ProgressClaim or ProjectBaseline created.
- Existing unrelated payroll migration remains unapplied; no migrations or application code changes made by this seed operation. No commit/push.

## Existing UI limitation

Contract Detail currently consumes receivable ProgressClaim data only. The seeded payable certificates are available through the existing `/billing/payable-certificates/` list and individual detail pages; seeding does not alter this UI behavior or add unrelated receivable links. Estimate links are available in the contract supplementary details.

Evidence: `dry-run.json`, `result.json`, `verification.json`. Reproducible bounded helper: `seed.py`; dry-run is the default, and an already-existing marked seed is inspected rather than duplicated or overwritten.

## Follow-up: payable source connection

The UI limitation above was resolved by the same-day follow-up in [payable-connection/REPORT.md](../payable-connection/REPORT.md). The original seed records remain unchanged.
