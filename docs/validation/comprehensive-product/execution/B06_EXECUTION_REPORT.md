# B06 execution report

**12 November 2026 · MVP · Procurement, Materials and Inventory**

| Execution | Planned | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|
| Original | 88 | 33 | 4 | 21 | 30 |
| Current | 88 | 88 | 0 | 0 | 0 |

The original outcomes record the first Chrome and PostgreSQL attempts. The current matrix records the qualified reruns and the independent remediation checks. All 88 execution IDs resolve in the current MVP Product Surface. Material master checks and the inventory export are supplemental. The B06 update preserved all 1,043 other matrix rows. [Original outcomes](B06_ORIGINAL_RESULTS.csv) · [Current matrix](../TEST_EXECUTION_MATRIX_MVP.csv) · [Evidence by execution ID](evidence/b06-24ad220f/row-witnesses.json) · [Reconciliation](evidence/b06-24ad220f/surface.json)

## Procurement and inventory

| Scenario | Evidence |
|---|---|
| UAT-11 | A requester created and submitted a PR with an authorized material and unit. Independent approval exposed explicit RFQ continuation. Rejection and cancellation used separate copies. Scope, positive quantity, retained input, and absence of an automatically created RFQ were checked. |
| UAT-12 | Explicit RFQ scope froze at issue. The addendum preserved the earlier version. Separate buyers, suppliers, opening approvers, evaluators and award reviewers exercised sealed access, exact-version grants, conflict decisions, comparison, award and revocation. An authenticated supplier's repeated PDF submission retained one receipt. |
| UAT-13 | Chrome followed a new PR through explicit RFQ scope, protected award, PO issue and partial receipts on the same source chain. A separate receipt run posted 2 of 5, rejected 4 with 3 remaining, then posted the exact 3. Wrong source and duplicate lines were rejected. Competing final receipts conserved the remaining quantity, and void preserved source history. The existing authorized direct PO path also passed. |
| UAT-14 | GRN posting and draft stock intake left stock unchanged. Explicit posting increased it once. The connected run reconciled 6 units back to zero with two linked reversals, two retained originals and both GRNs still posted. Separate assignment requests retained two workflow instances and one opposite movement. Scoped transaction search, source navigation and XLSX download passed. |
| CV-INV-01 | Over-reservation at 6 against 5 left no draft or audit. The corrected request reserved 2, then released the allocation and retained the cancelled reservation. Two count lines started at 5 and finished at 6 after independent approval, with one adjustment per line. Transfer dispatch debited 3 from 5, destination stayed at zero in transit, and independent acceptance credited 3 once. The finalized valuation showed 10 units at 10 IRR/unit and 100 IRR total. |

The separate PostgreSQL witness reconciled the transfer to **2 source + 3 destination**, with one debit, one credit and distinct dispatch/acceptance actors. Count, reservation and transfer witnesses recorded zero journal entries. The connected Chrome run checked six financial checkpoints with no changes to downstream financial counts. Qualified tests covered duplicate receipt-to-stock acceptance, receipt and award contention, and moving weighted-average conservation. The connected HTTP fixture independently verified source lineage through separate supplier orders and receipts. [Persisted witness](evidence/b06-24ad220f/persisted-postgres.json) · [Connected stock evidence](evidence/b06-24ad220f/connected-stock-reversal.json) · [Browser case index](evidence/b06-24ad220f/browser-case-index.json) · [Test outcomes](evidence/b06-24ad220f/test-outcomes.json)

The material master checks created a category, unit and material in Chrome, edited the material, and checked its list entry. Focused services covered tenant-scoped normalization, duplicate prevention, inactive/archive behavior, unit precision and references. Warehouse Chrome checks covered creation, location filtering, «همه محل‌ها», foreign record denial and archive. [Material witness](evidence/b06-24ad220f/chrome/materials-state.json) · [Warehouse witness](evidence/b06-24ad220f/chrome/warehouse-state.json)

## Defects and design

| Defect | Severity | Current outcome |
|---|---|---|
| BON-DEF-0035 | P1 | Fixed and retested. Rejection rolls back the reservation, allocation and audit together. The same number can be retried. |
| BON-DEF-0036 | P1 | Fixed and retested. Count submission holds the parent lock, rolls back every line on failure, retains valid input, and shows the freeze timestamp in Jalali format. |
| BON-DEF-0037 | P1 | Fixed and retested. The destination-scoped receiver can open and accept in-transit custody. Source actions retain source scope. The detail identifies both warehouses and returns the receiver to the scoped warehouse list. |
| BON-DEF-0038 | P2 | Fixed and retested. Reservation, count and transfer forms search the existing authorized warehouse and material options. |
| BON-DEF-0039 | P2 | Fixed and retested. RFQ issue filters its eligible supplier checkboxes while keeping prior selections visible. Chrome issued the version with exactly the two selected suppliers. |

The Chrome review used DC-03 context and navigation, DC-04 reference lists, DC-05 details, DC-06 compact forms, DC-07 sectioned forms, DC-08 workbenches and DC-09 feedback at 1440, 1024 and 390 CSS px. It covered contextual return, scoped selectors, status, Persian RTL and Jalali presentation, invalid-input recovery, and protected controls. The explicit portal receipt identifier follows the supplier-portal exception in the UI guidelines. [Design registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md) · [Warehouse list at 390 px](evidence/b06-24ad220f/chrome/warehouse-list-390.png) · [Count feedback at 390 px](evidence/b06-24ad220f/chrome/count-invalid-390.png) · [Inbound transfer at 390 px](evidence/b06-24ad220f/chrome/transfer-inbound-390.png) · [Supplier search at 390 px](evidence/b06-24ad220f/chrome/supplier-search-390.png)

## Baseline and integration

Local main and origin/main both resolved to 24ad220f0376cb0b6232b745938b35433843a32d at entry. The live working tree included B03 Return, B04 and B05 changes. B06 used the existing working tree and a new loopback PostgreSQL 18.6 cluster. The base database applied **462 migrations from zero**, including the B03 Return guards and the Equipment handoff constraint. It had zero users and tenants before fixtures. Django migration check, system check and schema drift check passed. Test databases cloned that base. [Entry status](evidence/b06-24ad220f/entry-status.txt) · [Entry diff summary](evidence/b06-24ad220f/entry-stat.txt) · [Migration log](evidence/b06-24ad220f/migrate.log) · [Catalog witness](evidence/b06-24ad220f/persisted-postgres.json)

The separate B03/B04 integration report records its own PASS against a frozen source export. B05's current summary still requires separate Chrome work. B06 verified local source contracts and protected document processing with a synthetic clean assessment for the exact file version. A deployed document scanner and external integrations remain unverified by this wave. [B03/B04 integration gate](B03_B04_INTEGRATION_GATE_REPORT.md) · [B05 status](WAVE_05_SUMMARY.md)

Original browser failures included confirmation dialogs the harness did not advance and inherited test actors missing object-scope grants. Qualified reruns supplied explicit synthetic grants, clicked confirmation, and selected the PR line through the current RFQ form. One parallel teardown exceeded PostgreSQL's shared lock budget during test-table truncation after the Chrome assertions succeeded. A separate read-only connection verified the retained rows. The final focused custody run passed 9/9, and the RFQ search regression, count-post race and transfer-dispatch race passed. The supplemental XLSX run used a configured tenant timezone and resolved the link against the movements page. [Test outcomes](evidence/b06-24ad220f/test-outcomes.json) · [Test qualification](evidence/b06-24ad220f/b06_qualification.py)

## Acceptance and Product Owner review

**B06 is ready for Product Owner acceptance review.** All 88 rows passed and no attributable P0/P1 defect remains open. Formal Product Owner acceptance remains unrecorded. On 12 November 2026, the Product Owner approved a bounded inbound transfers view in the existing Inventory Custody Workbench for destination-authorized receivers. [Separate enhancement record](B06_INBOUND_TRANSFERS_ENHANCEMENT.md)

The next planned wave is **B07 — CV-TEN-01, CV-WF-01 and CV-PAR-01**. B07 remains unstarted. All writes ran on isolated PostgreSQL databases. Existing Development, demo and Production databases were untouched. No Git commit or push.
