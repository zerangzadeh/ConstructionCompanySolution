# CEP-064 — Treasury authority cutover and read-model convergence

**Execution state: EXECUTION PARTIAL. Lifecycle: BLOCKED_REQUIRED_VALIDATION.**
Primary IMBs: IMB-0049 / IMB-0051. Baseline: existing `main` at
`784a5e6290a250dcdd4fa1a0fafc2225c64e5215`, verified equal to remote main before
this checkpoint. CEP-007 and CEP-028 prerequisites are COMPLETE. The bounded
[Human authorization](../supporting/LEGACY_PAYMENT_RETIREMENT_AUTHORIZATION_20261019.md)
and both amended canonical prompt hashes were verified. No dependency, Product
Decision, production authority or exit-Gate semantics were changed.

## Implemented preparation

Legacy create/void/allocation/read services now deny before database access.
Root Payment routes are removed and old admin module/view/mutation access is
disabled. Treasury has thin Persian/RTL receipt/disbursement forms and
create/submit/post/reverse endpoints calling its existing approved services,
with CSRF, tenant/object scope and existing permission checks. Posting and
reversal preserve existing independent-actor, policy and GL controls.

Billing settlement adapters require an explicitly recognized exact-version AR
obligation and delegate allocation/reversal to Subledger. They retain tenant,
claim, project, contract, party, capacity and idempotency checks. Corrections see
active Subledger allocations. They never implicitly recognize AR or create cash.
Financial projections read posted, unreversed Treasury cash movements and retain
source UUID/version/journal references and the query cutoff. Cash totals retain
the approved source Decimal precision. They require the
Treasury source permission as well as the financial projection permission.

DMS current-operation uploads use a Treasury-owned typed movement link. The
Development reference migration retains all 80 excluded Payment sources and
their dependent values as immutable Documents-owned evidence using the original
Payment UUIDs. Generic references now target that evidence; 32 copied typed
links preserve original link/document/actor/time identities. All 160 captured
audit identifiers still exist. These are excluded demo/test interpretation
records, not financial history or cash authority. No Treasury/GL/opening data
was fabricated or backfilled.

Current financial demo generation creates pending Treasury PaymentRequests.
Requests are idempotent and create no Payment, posted cash or GL history.
Billing demo claims are omitted when approved commercial terms do not exist;
measurements remain. Other claim prerequisites continue through normal Billing
services. Treasury `PaymentRequest` remains a product model.

## Schema, recovery and validation

Applied **only** `documents.0012_legacy_payment_reference_preparation` and
`treasury.0010_legacy_payment_reference_preparation` to configured Development.
They add retained evidence/current Treasury document links and repoint DMS
references. Original source rows, old Billing settlement rows, old tables/models
and the legacy app remain. The source-retention migration rejects execution
outside Development. No destructive contract migration is installed.

Before preparation, a native custom-format Development dump was restored into a
separate local database. All **520** table counts and row digests matched; the
source was stable during capture. Dump SHA-256 and private recovery-manifest
location are recorded in CEP-064-EV-002. The ignored dump and restored database
remain available. Recovery uses an isolated restore, compatible preparation code
and verified migration replay; it must not reactivate obsolete financial writers.
Refresh/recheck checkpoint coverage before any future destructive contract.

A fresh isolated test database applied **428/428 migrations**, producing **523
tables**. This proves the preparation graph. The complete destructive candidate
graph is **UNVERIFIED**; its required order is documented in the
[contract plan](../supporting/CEP-064_RETIREMENT_CONTRACT_PLAN.md).
Reference preparation replayed twice under rollback with **zero duplicates**.
Source/dependent-value and audit/document identity verification PASS.

Main focused/affected run: **65 passed, 28 subtests passed, 1 failed**. All **16
new transition cases PASS**, covering approved cash UI, CSRF, valid cross-tenant
membership denial, source permissions, explicit AR, partial caps/retry, reversal,
correction guard, concurrent allocations, DMS, retained evidence and no double
counting. Existing Treasury/Subledger, financial, document and identifier checks
are included. Current-form UI rerun: **1 PASS**. DMS temporary protected-storage
rerun: **1 PASS**. Final precision/current-cash projection rerun: **2 PASS**.
Private JUnit artifacts are ignored and retained.

The main run's demo failure first exposed absent approved Billing terms. The
bounded seed guard now leaves such claims uncreated. An intermediate reused test
database had lost its migration-seeded Expense groups after transactional flush;
the seed test now restores the exact canonical six-group fixture. The latest
full seed run reaches Safety closure and **FAILS** its unchanged separate-record
approval requirement. Full demo generation is **not** claimed PASS.

Required registry architecture regression: **2 passed / 4 failed**. The same
four failures were independently reproduced against baseline registry source at
`784a5e6`: duplicated Payroll model ownership, unregistered Support codes,
missing enforcement declarations, and resource/permission namespace mismatches.
Safety services/workflow bytes and the seed Safety method AST match baseline.
These findings were recorded without changing unrelated domain authority.

An introduced missing required `message` argument on three Billing permission
checks was fixed; subsequent Billing transition tests PASS. No introduced
focused failure remains open. System checks, migration drift, applicable prompt
hashes, touched-Python Ruff lint and diff whitespace checks PASS at closeout.

## Exact Human retirement gate

The original twelve-condition gate is evaluated separately from both remediation
areas and canonical Acceptance Criteria. See
[readiness evidence](../evidence/CEP-064_RETIREMENT_READINESS.json) and
[transitional-surface inventory](../evidence/CEP-064_RUNTIME_REFERENCE_INVENTORY.json).

| Condition | Result |
| --- | --- |
| 1. No active legacy runtime writer | PASS |
| 2. No active legacy business/reporting reader | PASS |
| 3. Required references have approved disposition/replacement | PASS |
| 4. Approved Treasury/Subledger settlement flows | PASS |
| 5. No Payment/Treasury double counting | PASS |
| 6. No required active consumer of legacy compatibility surfaces | PASS |
| 7. Current financial seed paths use approved Treasury flows | PASS |
| 8. Transition coverage retained/replaced | PASS |
| 9. Retained audit/document interpretation | PASS |
| 10. Complete retirement graph from zero | **UNVERIFIED** |
| 11. All required validation passes | **FAIL** |
| 12. Verified Development database recovery checkpoint | PASS |

`LEGACY_PAYMENT_RETIREMENT_READINESS = FAIL`

`LEGACY_PAYMENT_RETIREMENT_COMPLETE = NO`

## Blockers and closeout

- **CEP-064-FINDING-001 / BLOCKER-TEST:** resolve the four required registry
  architecture failures with approved resource/enforcement ownership, then rerun
  the affected regression. Baseline attribution is not a waiver of gate 11.
- **CEP-064-FINDING-002 / BLOCKER-TEST:** repair full-demo Safety seeding through
  its approved independent record-approval flow. Do not bypass separation of
  duties or invent an approver/policy to make this regression pass.
- **CEP-064-FINDING-003 / BLOCKER-MIGRATION:** prepare and rehearse the complete
  candidate contract/migration-only history arrangement from zero, bound to its
  actual code/migration digest; preparation-graph success is not that evidence.

Canonical AC: **12/14 PASS, 2 PARTIAL**; full target outcomes remain partial while
the required gate/validation blocks closeout. Scoped DoD: **NOT_MET_BLOCKED**.
The Acceptance/Evidence/Change manifests retain the individual proofs. Legacy
positive service/UI/allocation/void cases were replaced by negative compatibility
checks and current Treasury/Subledger behavior. Identifier/tenant source-model
checks remain interpretive transition evidence; current operation seeds have no
legacy writer. Old void-race coverage is superseded by denied legacy entry
points and the approved settlement concurrency test.

Remaining UTV: complete destructive candidate graph, gated Development contract
execution and every required post-removal check. No downstream cutover readiness
is inferred. GATE-04/GATE-06 remain unchanged. Registry records PARTIAL and stops
automatic continuation. The historical Payment population decision is resolved;
no historical financial dataset is requested.

Git checkpoint is separately authorized; exact committed/pushed implementation
facts are recorded in the Registry after verification. No source data deletion,
Legacy Payment model/table/app removal, Production migration/deployment/cutover,
CEP-069..079 execution, Human Sign-off or Production Certification occurred.
