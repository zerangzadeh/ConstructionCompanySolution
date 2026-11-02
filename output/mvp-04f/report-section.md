
## MVP-04F — End-to-End Verification (2026-11-02)

### Authority, start state and final touch set

Executed only the Human-authorized MVP-04F attached request. The entry gate read
this report and found MVP-04A, the Commercial Scope producer, MVP-04B1, MVP-04B2,
MVP-04C, MVP-04D and MVP-04E successfully completed without an unresolved in-scope
blocker. The request explicitly stops continuation after F. No MVP-05 work began.

[Exact start state](../../../output/mvp-04f/start-state.json): current dirty `main`,
HEAD and cached `origin/main` both
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, cached divergence 0/0.
The pre-existing tracked/untracked A–E work was retained; no clean-tree assumption,
reset, staging, commit, push, branch or worktree creation occurred.
[Request, governance and domain-boundary hashes](../../../output/mvp-04f/authority-and-boundary-manifest.json)
identify the authority and implementation inspected. This is bounded MVP
verification, not a CEP lifecycle transition or a production authorization.

The only F product correction is read-only forward history navigation, discovered
when auditing the complete journey: approved PR → existing RFQ, finalized Award →
existing supplier PO, and PO → existing GRNs. Each uses business labels and
requires the downstream read permission and existing organization/project scope.
Existing domain services, write paths and lifecycle rules remain authoritative.

Final F touch set:

- `apps/procurement/request_ui.py`, `apps/procurement/order_ui.py`:
  permission-scoped history query context.
- `templates/procurement/request_detail.html`,
  `templates/procurement/rfq_buyer_workspace.html`,
  `templates/procurement/order_detail.html`: the corresponding business links.
- `apps/procurement/test_mvp04f.py`, `apps/procurement/test_mvp04f_browser.py`:
  connected HTTP secondary journeys and principal installed-Chrome journey.
- This report and `output/mvp-04f/`: isolated validation harness, logs, screenshots,
  source proofs and closeout evidence.

No F model, migration, business permission, Product Surface, domain/posting policy,
financial integration or dependency change.
[Source hashes](../../../output/mvp-04f/final-source-manifest.json) cover the seven
implementation/test files. [Preservation](../../../output/mvp-04f/preservation-check.json)
qualifies the 572 pre-existing snapshotted files: before report append, 567 were
byte-identical and exactly the five declared UI overlaps changed; after append the
report is the sixth declared overlap. No unexpected changed or missing file.

### Connected canonical and secondary journeys

**Primary full PR → Inventory journey: PASS.**
The fixture starts with tenant masters, memberships, explicit role assignments,
project, material/unit, suppliers and warehouse only. It asserts no PR, RFQ,
quote revision or stock transaction exists. It does not seed upstream commercial
documents, an Award, PO, GRN or stock result.

The final Chrome run executes all business transitions through rendered forms and
contextual links: create PR and material row → submit → separate approval → create
RFQ from approved PR → select PR row → explicit Commercial Scope → select supplier
and issue → actual source-byte upload/capture → submit → corrected second quote
revision/submit → close → custody attachment → protected opening request and
independent approval → exact-revision access → admissibility preparation and
independent approval → comparison preparation/evaluator appointment/evaluation and
independent finalization → partial award preparation/independent finalization →
supplier PO/Issue → first partial GRN/Post → Inventory draft/explicit Post → later
GRN/Post → second Inventory draft/explicit Post → completed PO → explicit reversals.

The test clock satisfies existing close/opening timing rules; processing assessment
and versioned separation policies are explicit isolated test fixtures. Custody and
quote capture use actual uploaded synthetic bytes. This does not certify a real
scanner, arbitrary document rendering or deployment processing infrastructure.

| Scenario | Exact result |
| --- | --- |
| Primary partial procurement | PR 10; RFQ scope 10; award 6; unawarded 4; PO 6; posted GRNs 2 + 4; posted Inventory receipts 2 + 4; balance 0 → 2 → 6; PO completed |
| Split award | One newly created PR/RFQ, two effective supplier quotes, allocations 4 + 6, separate supplier-specific POs and independent GRNs/Inventory receipts; total balance 10; no supplier crossover |
| No Award | Complete upstream process through finalized comparison, explicit finalized No Award, retained history, no allocation/PO continuation and zero PO/GRN/stock rows |
| Reversal | Two explicit Inventory reversals, originals retained with reversal links, four stock records total, balance 6 → 0; both source GRNs remain posted |

[Canonical lineage](../../../output/mvp-04f/canonical-lineage.json),
[split lineage](../../../output/mvp-04f/split-lineage.json),
[No Award](../../../output/mvp-04f/no-award.json) and
[reversal proof](../../../output/mvp-04f/canonical-reversal.json) retain exact
source FKs and Decimal quantities. Technical identifiers in these restricted
engineering artifacts are not business-user inputs or visible UI labels.

### Source, quantities, finance and lifecycle integrity

**Source lineage and quantity conservation: PASS.** Assertions verify PR row,
RFQ row/version, effective quote revision (including corrected/superseded history),
comparison input, Award allocation, supplier-specific PO and issued version,
pinned GRN source row, stock source, material, unit, project and warehouse.
Primary conservation is `10 = 6 awarded + 4 unawarded` and
`6 ordered = 2 + 4 received = 2 + 4 stock posted`.
Split conservation is `10 = 4 + 6` independently through each supplier's order,
receipt and stock lineage. No quantity semantics were changed: PO creation consumes
whole selected approved allocations; Inventory receipt uses the existing complete
posted-GRN-line contract. The primary partial flow uses partial award and partial
GRNs, not an invented arbitrary partial-allocation PO or stock-acceptance policy.

Business-readable forward navigation is clicked in Chrome from PR through RFQ,
buyer workspace, existing PO, existing GRN and Inventory transaction. Backward
links agree with the retained source chain. Posted/completed records expose their
history and existing frozen-state behavior. Parent-only readers cannot see RFQ or
GRN history links without the corresponding downstream read permission.

**Financial boundary: PASS.** The connected tests hash both row contents and counts
before and after the journey checkpoints. Supplier Invoice, AP Obligation,
Accounting Journal Entry, Treasury Movement, Payment Request, retained payment
evidence and Project Cost Fact remain byte-equivalent at the row projection level
(tenant baseline counts zero). All retained tenant-owned tables with `payment` in
their name are included by database introspection, including legacy
`payments_payment`, `payments_paymentallocation`, `payments_paymentdocumentlink`
and Treasury payment transition/request tables. No financial fact, settlement,
recognition or posting is generated by any operational stage or reversal.
The complete hashes/checkpoints are in the canonical/split/No-Award/reversal proofs.

### Browser, technical leakage and security

[Final installed-Chrome run](../../../output/mvp-04f/browser-attempt-2.log):
**1/1 test method PASS, 425.745 seconds**, comprising
[83 distinct scenarios](../../../output/mvp-04f/browser-summary.json).
The full business journey runs at 1440. Representative PR List/Detail, RFQ
Create/Detail, Buyer Workspace, Award, PO List/Detail, GRN List/Detail and Inventory
List/Detail run at 1440, 1024 and 390. Document widths account for the browser
scrollbar. No horizontal overflow, JavaScript exception, unexpected HTTP error,
visible technical-label match or non-Persian/RTL document state was detected.
Expected repeated-transition 400s and explicit isolation 403/404s are recorded
separately; they are not valid-route failures. Favicon requests are not business
route evidence.

Screenshots are retained in [the browser evidence directory](../../../output/mvp-04f/browser/).
Visual inspection included mobile PR history, completed-PO receipt history,
buyer workspace and reversed Inventory history/balance, plus desktop Award
workspace. Contextual selectors, primary actions and retained history remain
readable; existing list/filter/menu and form-retention behavior is also exercised
by the affected A–E coverage. No broad visual redesign occurred.

Visible-content assertions cover UUIDs, hashes/fingerprints, managed retry and
idempotency keys, raw model/object labels, internal source/allocation/revision
references, backend enum values and permission/service terminology. Source values
are server-derived or managed form state; none must be manually reconstructed.

| Boundary | Executed evidence |
| --- | --- |
| Unauthorized, other tenant and wrong project | Final Chrome receipt-create 403, stock-detail cross-tenant 404 and GRN project-scope 404; affected A–E and receipt-contract tests enforce reads and direct mutations |
| Forged parent/source, supplier and project | A/B1 contextual PR/RFQ denials, B2 cross-context quote/award denial, C forged supplier/project/allocation/direct bypass and excess consumption, D source/version/context denial |
| Warehouse and source-derived stock values | E forged material/unit/quantity/value/source and incompatible warehouse denial, unposted/void source denial and scope/CSRF coverage |
| Stale and excessive quantities | Commercial Scope optimism/source drift/freeze tests, protected opening/admissibility/comparison freshness tests, Award excess/split/tie rules, PO consumption and GRN excess/version tests |
| History-link authorization | F parent-only reader test suppresses RFQ/GRN history links while authorized parent detail remains readable |
| Concurrency | Existing scoped Commercial Scope, custody, opening, admissibility, comparison/Award, GRN and Inventory receipt concurrency tests in the affected run |

**Retry / idempotency: PASS.** Final Chrome captures each actual rendered form's
managed state, submits it and replays the identical POST after success for RFQ
Issue, Award finalization, Award→PO, PO→GRN (both receipts), and GRN→Inventory draft
(both receipts). Final rows remain one RFQ version, one Award, one PO, two GRNs
and two original stock transactions. Refresh/back/forward preserve that state.
Repeating finalized Issue/GRN Post/Inventory Post is rejected by the existing
contract with 400, without duplication. A–E regression covers conflicting retries,
equivalent source retries, reversal retries and concurrent identical acceptance.
Existing deny/reuse semantics were preserved rather than changed to force success.

### Regression, failed attempts and limitations

[Affected regression](../../../output/mvp-04f/affected-regression-attempt-1.log):
**123/123 PASS, 555.113 seconds**, after the forward-link correction. Scope:
`test_mvp04f`, `test_mvp04a`, `test_mvp04b_scope`, `test_mvp04b1`,
`test_mvp04b2`, `test_mvp04c`, `test_mvp04d`, Inventory `test_mvp04e`,
`test_p5_s08_sealed_custody`, `test_p5_s09_protected_opening`,
`test_p5_s10_admissibility`, `test_p5_s11_comparison_award`, and Inventory
`test_cep034_receipt_contract`. This covers PR, RFQ and scope, quote/custody/opening,
admissibility, comparison/Award, PO, GRN, Inventory draft/Post/reversal, source and
financial boundaries, permissions/tenant/project isolation and concurrency.
The two new HTTP secondary methods, including the downstream-history denial
assertions, pass in this final run. No in-scope product failure, unrelated failure,
skip or expected failure remains in this 123-test command.
The isolated wrapper supplies explicit historical actor role assignments and the
existing guarded CASCADE/serialized fixture teardown; these are test-fixture
adaptations, not runtime authorization changes.

[Initial HTTP attempt 1](../../../output/mvp-04f/connected-http-attempt-1.log) failed
because the new harness posted to the detail URL rather than the rendered form
action. [Attempt 2](../../../output/mvp-04f/connected-http-attempt-2.log) failed on
an incorrect fixture ORM relation. Both are harness failures, retained as failed;
no Domain correction was needed. [Attempt 3](../../../output/mvp-04f/connected-http-attempt-3.log)
passed both connected HTTP scenarios (2/2, 59.316 seconds).
[Initial Chrome](../../../output/mvp-04f/browser-attempt-1.log) passed the complete
primary journey (1/1, 346.866 seconds). After the objective forward-navigation gap
was corrected, final Chrome reran the whole journey and affected tests re-exercised
the links and denial assertions. No failed command is relabelled as PASS.

The [initial closeout checker](../../../output/mvp-04f/closeout-evidence-attempt-1.log)
failed because it compared CRLF evidence bytes to the normalized LF report append.
Only the checker normalization was corrected; the
[final closeout](../../../output/mvp-04f/closeout-check.json) proves all previous
report bytes are preserved, every new report link resolves and no unexpected
file changed.

Lint, formatting, Django system check, template parse/UTF-8 and model/migration
drift checks pass; logs are retained in `output/mvp-04f/`.
[Isolated migration qualification](../../../output/mvp-04f/isolated-migration-plan.json)
shows 447 applied migration records and zero pending migrations in each of the
two separate PostgreSQL validation clones. The initial
[database qualification](../../../output/mvp-04f/database-qualification.json)
identifies the already-migrated E template. Development still has the unrelated
`payroll.0010_cep069_reviewed_statutory_context` pending; it was not applied.
No production migration, development business-data mutation or production action.

Known external supplier-portal fixture debt remains historical:
`SupplierPortalUiTests.test_external_context_is_exact_scope_and_submission_is_idempotent`
sends a fingerprint instead of the upload required by the existing capture contract.
That previously identified command is not represented as passing and was not
silently expanded into buyer/Inventory product scope. Synthetic policy, actors,
clock, source bytes and processing assessments qualify functional tests; they do
not prove real supplier participation, deployed scanning, Human UAT or statutory
or production readiness. Full-repository regression was not run.

**MVP-04 FUNCTIONAL IMPLEMENTATION COMPLETE.** No unresolved in-scope functional
blocker remains. Product Owner visual acceptance: PENDING. Human Sign-off,
real-user UAT, Production Certification and Production Cutover: NOT EXECUTED.
All work remains uncommitted on `main`; no commit or push. Stop after MVP-04F;
MVP-05 and later work: NOT STARTED.

```text
MVP-04F FUNCTIONAL: PASS
FULL PR → INVENTORY JOURNEY: PASS
SOURCE LINEAGE: PASS
QUANTITY CONSERVATION: PASS
PARTIAL / SPLIT JOURNEYS: PASS
NO-AWARD JOURNEY: PASS
INVENTORY POST / REVERSAL: PASS
FINANCIAL BOUNDARY: PASS
TECHNICAL LEAKAGE: PASS
TENANT/PERMISSION ISOLATION: PASS
RETRY / IDEMPOTENCY: PASS
RESPONSIVE BROWSER VALIDATION: PASS
MVP-04 FUNCTIONAL PACKAGE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```
