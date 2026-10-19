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

## Current bounded follow-up — 2026-10-20

Entry: clean existing main `4a292332809431b89c060f4ac778d76377fb436a`.
The [latest Human decision](../supporting/LEGACY_PAYMENT_RETIREMENT_DECISION_20261020.md)
confirms Development-only demo disposition, grants the separate Demo Safety
approval, and permits valid non-CEP registry attribution. No canonical package
scope, dependency, Product Decision or Production authority changed.

**Registry blocker closed by valid baseline attribution.** The original four
architecture failure sets reproduce exactly at pre-retirement `784a5e6`:
duplicated Payroll model registration, 17 absent Support codes, enforcement
reference gaps and 77 namespace mismatches. The expanded required registry suite
is **2 PASS / 6 baseline FAIL, 11 subtests PASS**. Its two additional database/flush
failures reproduce the same existing Support registration defect using the
baseline registry. Baseline/current registry code sets are identical and catalogue
bootstrap source bytes are unchanged. The changed retirement namespaces have no
new registration/enforcement defects. No permission or test was weakened; no
full-registry PASS is claimed. See CEP-064-EV-006.

**Demo Safety blocker closed.** The seed calls the existing record submit and
approve services before closure. Existing permission checks, review revisions,
audit and closure guard remain unchanged. **6 Safety tests PASS**: the actual
seed method's review/closure/idempotency case plus five existing source review
regressions. An initial reused-test-DB catalogue absence was repaired by restoring
canonical code-owned fixtures in the test database only. Human disposition is
corroborated by all80 source records belonging to the four known demo seed tenants
and all80 archived dispositions being `excluded_demo_test`.

**Fresh recovery checkpoint PASS.** Native custom dump restored to a unique local
DB; all **523 table counts and row digests match**, source stable during capture.
The private dump/manifest and restored DB remain available. Original checkpoint
was520 tables before reference preparation; the new checkpoint covers its523-table
result. Source/evidence verification again proves80 snapshots,32 typed links,
32 generic links and160 audit IDs. No source row was deleted and no Treasury/GL
history was fabricated.

**Rehearsal preflight FAIL; destructive graph remains UNVERIFIED.** Dependency
search found the active Reporting `claim_settlement` adapter still querying
`billing.ClaimSettlementAllocation`, which depends on Legacy PaymentAllocation.
It is registered in ADAPTERS and called by execute/replay reconciliation. Runtime
reads were verified for all four demo tenants. Zero active allocation rows do not
eliminate the schema dependency. The previous zero-reader inventory was incomplete
and has been corrected. No Reporting product mutation was made under the request
to close only the three named blockers.

The required full demo seed now passes Safety and **FAILS Quality closure**:
`_seed_quality_issue` never submits/approves the separately reviewed Quality record.
That method's AST is unchanged from entry; the Quality guard is preserved. This
new failure is recorded without absorbing unrelated Quality work or inferring a
Human Quality decision. No full-demo PASS is claimed.

Prior preparation proof remains **428/428 migrations from zero,523 tables**;
it is explicitly not full destructive-graph proof. Existing focused/affected
validation remains65 PASS/28 subtests PASS (with the separately failing seed),
16 transition checks, and successful current UI/DMS/precision reruns. Current
Django checks:0 issues; migration drift:no changes; touched-Python lint and diff
whitespace:PASS. Private JUnit results are retained under the ignored output root.

## Current exact gate and blockers

[Exact gate evidence](../evidence/CEP-064_RETIREMENT_READINESS.json):
**9 PASS / 2 FAIL / 1 UNVERIFIED**. Condition2 FAIL is the active Reporting reader;
condition11 FAIL is the required full seed's Quality review prerequisite;
condition10 remains UNVERIFIED. The other retained evidence is unchanged except
for refreshed condition12 recovery proof. Valid registry attribution is supported
by the latest explicit Human instruction, not a blanket regression waiver.

- **CEP-064-FINDING-004 / BLOCKER-TEST:** required full seed fails Quality closure
  because its separate record review is absent.
- **CEP-064-FINDING-005 / BLOCKER-RUNTIME-REFERENCE:** registered Reporting
  reconciliation still reads the obsolete Billing settlement model.
- **CEP-064-FINDING-003 / BLOCKER-MIGRATION:** full destructive candidate graph
  from zero remains UNVERIFIED; rehearsal preflight exposed the required consumer.

Findings001 (registry) and002 (Safety) are closed with evidence. The Human STOP
rule applies. No destructive migration/rehearsal, model/table/app removal,
Production action, unrelated CEP, Sign-off or Certification was performed.

`LEGACY_PAYMENT_RETIREMENT_READINESS = FAIL`

`LEGACY_PAYMENT_RETIREMENT_COMPLETE = NO`

Canonical acceptance remains12/14 PASS and2 PARTIAL; scoped DoD NOT_MET_BLOCKED.
GATE04/GATE06 and dependency semantics are unchanged. Full post-removal validation
is NOT_EXECUTED. See [bounded closure evidence](../evidence/CEP-064_BLOCKER_CLOSURE_20261020.json).

Bounded follow-up checkpoint `e150cf5838a49d4a62f9a6897c740ac0d978f7bf` was committed directly
on existing main, pushed to origin/main and independently verified with a clean
tree. A governance-only follow-up records these Git facts; tested product code
is unchanged by that follow-up.
