# CEP-073 bounded Development verification — 2026-10-26

Current direct Human instruction authorizes advancement and removal of locally
resolvable verification prerequisites. The canonical prompt hash is verified.
This is preparation until GATE-06 and the entry record are PASS; no verification
is attributed to this CEP before those conditions are recorded.

Target: local PostgreSQL 18.6, Development settings, a uniquely named disposable
`test_bonira_cep073_*` database, synthetic records only. Database credentials come
from the configured environment; secrets and configured business data are not
captured. Application identity is existing main HEAD
`961e3fd942c668337012c22d42f59545c5e9fc0a` plus the exact current source-file hash
manifest, including pre-existing uncommitted changes. A SHA alone is not claimed
to identify those changes. Before/after manifest equality is required.

EXT-0023 qualification is technical: current PostgreSQL configuration/version,
exact SHA/build, representative scenario setup, data safety, and evidence capture.
It contains no independent Human sign-off requirement. This target follows the
current explicit Development instruction and canonical source-specific scenarios.
The historical P10 capacity workload remains bound to its historical candidate;
its user counts, duration, throughput and certification claims are not rebound.

Scenarios, using existing implementations and assertions:

1. Actual Audit 0016 / Billing 0008 preservation operations on dependency-complete
   historical schemas in a separate disposable database: reconciliation, source
   identifiers, finalized/returned/reversed history, tenant/actor/financial fields,
   explicit exceptions, rollback/reapply and retry. Run the shared CEP-012 proof
   again after entry as this CEP's required runtime migration scenario.
2. Current GL and Audit lists: 61 records across pages; GL 1,830 lines; asserted
   source query limits and tenant/authorization preservation. Capture actual
   PostgreSQL EXPLAIN ANALYZE/BUFFERS and application query execution time.
3. Current Inventory: non-zero receipts/transfers/reversals and tenant-filtered
   aggregate; UUID lock ordering; two opposing concurrent transfers preserve
   quantity and post exactly once. Retain actual query plan and measured timing.
4. Current Reporting: native synthetic valuation source, 1 then 17 source pools,
   foreign-tenant decoy, unchanged three-query source aggregation, exact values
   and source IDs, idempotent refresh and no Inventory/Stock/GL writeback.

Pass means these concrete runtime invariants and measurements are evidenced.
There is no invented latency/throughput target, production workload/capacity
acceptance, new financial policy, statutory activation, or production action.

Dependencies: mandatory CEP-006/009 and requalified CEP-012. GATE-06 contributor
evidence from completed CEP-028/029/057/058/064 is retained. This run does not
select Legacy Payment conversion, Employee conversion, Leave opening import or
Payroll YTD import as conditional migration scenarios. Their synthetic/real-data
boundaries remain intact. CEP-077..079 are excluded and are not rerun.

Actual touch set: `tests/test_cep073_runtime.py`,
`scripts/cep073_capture.py`, the output-directory parameter of the shared proof,
this manifest, CEP-073 report/CSV/evidence and narrow Registry records. Product
implementation remains the separately repaired CEP-012 migrations; CEP-073 adds
only verification fixtures/observation. All test-only role grants occur inside
the disposable test environment through existing models and registered codes.

Any failed behavioral verification is retained and attributed; ordinary harness
or fixture defects are corrected under the current Human instruction. Product
remediation beyond the CEP-012 repair is not silently absorbed into verification.
