# Local receivable sample — 2026-11-01

User request: a new receivable/client sample with multiple claim states in the same project. The user explicitly selected بازسازی کارخانه نوآوران / PRJ-02-03 in demo-construction-02. The bounded reuse of the existing published tax/insurance configuration was separately and explicitly approved for THIS NEW LOCAL SAMPLE ONLY; see HUMAN_AUTHORIZATION.md.

Contract: UAT-REC-02-03. Active receivable/client. Amount 196,200,000,000 IRR, copied from the existing same-project sample contract line quantities/rates, with the existing employer party and identity snapshot. All new records are marked as local UAT/demo evidence. No production or legal/statutory claim.

Created through the normal domain services inside one transaction: one contract and its two items; one independently approved contract term version; one independently approved two-line baseline; eight independently verified progress records; four claim numbers, including a returned claim whose normal workflow creates a linked draft revision. Preparation and approvals use separate existing tenant actors. No role/permission grants, models, migrations, services, UI or workflow definitions were edited by this task.

| Claim | Revision | Status | Gross IRR | Net IRR |
| --- | --- | --- | --- | --- |
| 1 | 1 | approved | 19620000000.0000 | 20287080000.0000 |
| 2 | 1 | submitted | 29430000000.0000 | 30430620000.0000 |
| 3 | 1 | returned | 49050000000.0000 | 50717700000.0000 |
| 3 | 2 | draft | 49050000000.0000 | 50717700000.0000 |
| 4 | 1 | draft | 68670000000.0000 | 71004780000.0000 |

Periods are explicit, disjoint 2026-10-24/25, 26/27, 28/29 and 30/31, all within the effective published configuration. Measurement fractions are synthetic demo inputs. The service computes each claim against prior APPROVED cumulative quantities only: therefore a pending, returned or draft amount is not independently certified incremental work. Returned revision 1 and its editable revision 2 are both retained; they must not be summed as separate certified work.

Only the existing Platform configuration was consumed (tax 10%, gross basis; insurance deduction 6.6%, gross basis). Its publication, sources and review evidence were not changed. Contractual rates/caps use existing service defaults and the organization billing configuration is initialized through the existing get-or-create service defaults (explicit periods, contract numbering, zero currency decimal places); no existing tenant configuration was overridden.

## Verification

- Six authenticated Django render checks: contract plus all five claim revisions, HTTP 200.
- Seven installed Chrome read-only scenarios: contract desktop 1440/mobile 390 plus all five revision pages. All PASS, no page JS/HTTP errors and no horizontal document overflow. Existing harness excludes only the shared favicon 404.
- Persisted amounts reconcile to source claim items and signed adjustments. Approved/returned/submitted/draft states and returned-to-draft lineage are verified. Approved baseline ceiling equals the contract amount; eight measurements are verified.
- Dashboard approved 19,620,000,000; submitted 29,430,000,000; remaining 147,150,000,000 IRR; approved ratio 10%. Returned and draft amounts are excluded. Physical percentage remains unasserted since measurement existence alone is not a governed contract-wide physical rollup.
- Protected fingerprints of existing project contracts, their existing receivable/payable records and the existing published policy match before/after seed.
- Accounting JournalEntry, subledger Obligation, TreasuryMovement and PaymentRequest counts match before/after. No actual AR recognition, journal, receipt, payment or settlement was created.
- A separate read-only browser verification fingerprint also matches before/after.

Contract path: /contracts/ac494a22-bf60-4249-8cee-3cd828206861/

Evidence: dry-run.json, result.json, verification.json, execution-log.txt, browser-log.txt and browser/*.png. Reproducible seed helper defaults to dry-run; application requires explicit policy-reuse flag backed by the recorded user answer. No git add/commit/push/merge, production migration, deployment or certification.
