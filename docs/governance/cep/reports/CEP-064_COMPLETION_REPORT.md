# CEP-064 — Legacy Payment Development retirement

**EXECUTION COMPLETE — 14/14 AC PASS; scoped DoD MET.**

`LEGACY_PAYMENT_RETIREMENT_READINESS = PASS` (12/12)

`LEGACY_PAYMENT_RETIREMENT_COMPLETE = YES`

Baseline: clean existing `main @ d2f9abdd53b4995dbd377dde8aec965970ac5d0d`, equal
origin/main. [Latest bounded Human continuation](../supporting/LEGACY_PAYMENT_RETIREMENT_CONTINUATION_20261020.md)
closed only Reporting, Quality demo approval and retirement rehearsal. Canonical
prompt SHA256 remains `302e4475f2369a2322c7cb4e1498138878ab21ae361e3232de89d5cd0d506312`.
Prerequisites and dependency semantics are unchanged. Earlier checkpoints remain
in Git and the cited historical evidence; no architecture/history decision reopened.

Reporting reads exact-version/context AR Subledger allocations with allocation
and reversal cutoffs. It never adds cash to settlement allocations. The demo seed
uses existing source-owned Quality submit/decide services before closure, retaining
snapshot, actor, reason and audit. Quality policy, permissions, evidence rules and
closure guards are unchanged. The obsolete64 document-link expectation now asserts
32 project links, zero Payment links and4 separately approved closed Quality records.

After all12 readiness conditions passed, Development billing0018/payments0007
removed obsolete Billing settlements and Payment/link/allocation tables. The runtime
app, services, forms, UI/templates/admin and4 obsolete business permissions/default
consumers are removed. `core.retired_payments` retains the original `payments`
migration label and unchanged historical migrations with zero runtime business
models. Treasury PaymentRequest remains. Forensic inventory reads Documents snapshots.

All80 original source snapshots,32 typed/32 generic links and160 audit identifiers
remain interpretable. Treasury, Accounting, Subledger, Documents, Audit and Quality
counts/digests are unchanged. Public tables523→519. No cash, GL, opening balance or
authoritative financial history was fabricated.

| Required proof | Result |
| --- | --- |
| Populated destructive contract clone | PASS;4 tables removed;original fingerprints stable |
| Native recovery after rehearsal | PASS;all523 table counts/digests match;pre-contract code checks PASS |
| Candidate graph from zero + seed/retry | PASS;430 migrations;4 tenants;64 pending requests |
| Configured Development contract + seed/system/drift | PASS |
| Post-removal focused/affected regression |107 tests +40 subtests PASS;0 failures/errors |
| Repeated post-removal graph from zero + seed/retry | PASS;430 migrations;stable counts and financial/document/Quality/audit digests |
| Runtime reference scan and touched-Python lint | PASS |
| Retained source/document/audit interpretation | PASS |

The registry suite retains2 PASS/6 baseline failures and11 subtests PASS. Complete
registry defect sets match the accepted original baseline; there is no new defect.
Three ancillary Estimate/Budget/Timekeeping fixtures reproduce the same permission
failures on the restored original schema before changed assertions;3 affected
authorization tests PASS. Set ordering was normalized. An initial candidate test
catalog included4 obsolete codes recreated by a pre-contract characterization
attempt; final configured/post catalogs contain zero. Independent diagnostic sets
match the baseline. Tests and product authorization were not weakened. This is
valid non-CEP attribution under the preserved Human decision and Execution Policy
section16, not a global registry PASS. See [attribution](../evidence/CEP-064_FINAL_REGRESSION_ATTRIBUTION.json).

Evidence: [readiness](../evidence/CEP-064_RETIREMENT_READINESS.json),
[rehearsal/recovery](../evidence/CEP-064_DESTRUCTIVE_REHEARSAL.json),
[Development result](../evidence/CEP-064_DEVELOPMENT_RETIREMENT.json),
[final validation](../evidence/CEP-064_FINAL_VALIDATION.json),
[reference scan](../evidence/CEP-064_POST_REFERENCE_SCAN.json).
Private native dumps, JUnit and diagnostics remain ignored. The verified checkpoint
manifest identifies the dump/hash and tested native restoration. Recovery uses the
full checkpoint and pre-contract code; an empty reverse schema cannot reconstruct
deleted rows and is intentionally unavailable. Local file storage used a short
private path during rehearsal to avoid Windows path-length limits.

Remaining UTV: performance/load and browser/accessibility runtime certification,
which are not required for this bounded retirement. Human Sign-off, Production
Certification/Cutover, Production action and unrelated CEP execution: NOT_EXECUTED.
GATE04/GATE06 and wider program activation are unchanged. Registry lifecycle is
CLOSED_VERIFIED. Stop at the Human-bounded clean boundary; no next CEP is started.
Git integration is recorded separately in CEP-064_GIT_CHECKPOINT.json.
