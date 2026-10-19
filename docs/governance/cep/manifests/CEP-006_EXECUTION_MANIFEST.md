# CEP-006 execution manifest — AUTH-BATCH-002 serial queue

Date: 2026-10-15. Execution: Development / non-production. Status: **BLOCKED BEFORE MUTATION**.

## Repository grounding

- Branch: `main`; HEAD: `533fbd52e38dd448973ba4cc618e5faa44b01fec`.
- Initial `git status --short`: modified `Agents.md`; untracked `BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md`. `git diff --name-status` and `git diff --stat` showed only `Agents.md` (392 lines changed). Both unrelated user changes were preserved.
- The user supplied explicit serial authorization for CEP-006, CEP-009, CEP-011, CEP-013, overriding older prompt placeholders and the older one-CEP-per-session instruction. No branch or worktree was created.

## Canonical source recovery

- Recovered the full CEP-006 handoff and unmodified canonical prompt from `C:\Users\azera\Downloads\BONIRA_CEP_HANDOFF_PLUS_CANONICAL_PROMPTS_20261013.zip`.
- Checked `ROADMAP.md`, `docs/architecture/P10_S07_S13_RECONCILIATION_AND_EXCEPTION_DECISION_PACKET.md`, `apps/reporting/reconciliation_catalog.py`, `apps/reporting/reconciliation.py`, and the native run models in `apps/subledgers/models.py` and `apps/treasury/models.py`.
- The canonical prompt requires all 16 acceptance criteria across IMB-0044, IMB-0048, and IMB-0066, with Migration Impact `NONE`. Its IMB-0044 criteria require authoritative current-state aggregation and exclusion of superseded/repeated snapshots where policy defines current evidence. The P10 decision packet requires an exact native run/review/hash, source grain, cutoff, and replacement behavior; it does not define a fallback current-run selection rule.

## Repository finding: CEP-006-FINDING-001 / BLOCKER-PD

`_subledger_gl`, `_treasury_bank`, and `_treasury_gl` in `apps/reporting/reconciliation.py` sum all retained native runs through the cutoff. Those runs are immutable historical snapshots, so repeated runs are double-counted. The published pair catalogue declares `subledger_gl` grain `direction/as_of/control_account`, but `SubledgerReconciliationRun` has no control-account field. It declares `treasury_gl` grain `cutoff/currency/source_identity`, but `TreasuryGLReconciliationRun` contains aggregate totals, a cutoff date, and an evidence hash without currency or source-identity fields. `BankReconciliationRun` records account, statement import and as-of date, but has no supersession/current pointer. No recovered source defines which repeated or overlapping native runs constitute current evidence or how the missing declared dimensions are established without a schema change.

Choosing latest by timestamp, aggregating one run per partial key, or treating missing dimensions as equivalent would invent financial aggregation and source-mapping semantics. Adding the missing dimensions or a current pointer may require a migration, which this CEP forbids. Resolve the approved native-run selection/supersession and grain policy, including whether the existing schema can represent it, before product mutation. If a migration is required, issue bounded migration authorization separately.

## Actual execution touch set

Potential code surfaces identified: `apps/reporting/reconciliation.py`, `apps/reporting/services.py`, `apps/accounting/views.py`, `apps/accounting/reporting.py`, `apps/audit/views.py`, related templates and focused tests. **Actual product touch set: NONE.** No model, migration, service, view, template, test, or configuration was changed.

No focused tests, regression, Ruff, Django checks, or migration-drift checks were run because the material source-policy blocker arose before implementation. `ROADMAP.md` was checked and remains current: no CEP-006 delivery occurred. CEP-009, CEP-011, and CEP-013 were not started.

## 2026-10-15 decision resolution and resume check

The Human Decision Maker approved latest eligible successful complete native run per pair and native grain as the V1 current-state rule. This is recorded in [PD-033](../../../architecture/BONIRA_PD_033_RECONCILIATION_CURRENT_STATE.md). Re-grounding confirmed `main` at the same HEAD with the pre-existing dirty tree preserved. The approved instruction explicitly requires stopping before product mutation if the existing pair implementation cannot establish an unambiguous persisted native grain.

Applicability fails for `subledger_gl`: the catalogue tuple is `(direction, as_of, control_account)`, but `SubledgerReconciliationRun` persists only `direction` and `as_of_date` from that tuple. It also fails for `treasury_gl`: the catalogue tuple is `(cutoff, currency, source_identity)`, but `TreasuryGLReconciliationRun` persists only `cutoff_date` from that tuple. No model, migration, service, view, template, query, or test was mutated on resume. The actual product touch set remains **NONE**. This is `CEP-006-FINDING-002 / BLOCKER-SPEC` under the new decision's express stop rule. CEP-009, CEP-011, and CEP-013 remain not started.

## 2026-10-15 final reauthorization implementation grounding

The Human Decision Maker authorized the bounded `SCHEMA + DATA-MIGRATION` CEP-006 remediation recorded in [the reauthorization decision](../supporting/CEP-006_REAUTHORIZATION_DECISION.md). Repository grounding reconfirmed `main` at `533fbd52e38dd448973ba4cc618e5faa44b01fec`, with the pre-existing dirty tree preserved. The target models, native runs and reporting adapters still match the decision packet.

### CEP-006-FINDING-003 / BLOCKER-PD — no authoritative Subledger control-account mapping

The authorized prospective Subledger slice requires an approved control-account mapping to validate every included obligation before the service creates a `(organization, direction, as_of, control_account)` slice. The repository contains no `SubledgerControlAccountMapping`, no equivalent source-owned configuration, no obligation-to-`JournalLine.account` relation, and no deterministic allocation contract. `run_subledger_reconciliation` still records `CONTROL_MAPPING_NOT_APPROVED` for obligations with a recognition journal and sets `linked_gl_total` to zero. The only Accounting candidates are the potentially multiple `JournalLine.account` rows of the linked journal.

Selecting one journal line, every journal line, or a direction-wide account would invent the missing AP/AR-to-GL mapping and per-account allocation semantics. This is a material contradiction with the authorized contract's requirement that mapping validate every source and that CEP-006 not invent financial semantics. It must be resolved by an explicit source-owned mapping policy/model contract before model, migration or service mutation. Actual execution touch set remains **NONE**; no migration plan can be safely created. The serial queue remains stopped before CEP-009.

## 2026-10-15 control-account decision approval and execution resume

The Human Decision Maker approved `PD-006-CAM-02`, recorded as
[PD-034](../../../architecture/BONIRA_PD_034_CONTROL_ACCOUNT_MAPPING.md). This resolves
`CEP-006-FINDING-003 / BLOCKER-PD` without altering the preceding historical
grounding. The actual authorized mutation surface is:

- Accounting: `ControlAccountMappingVersion`, mapping service, audit action and
  `accounting.control_account_mappings.manage` catalog/default-role grant.
- Subledgers: nullable immutable historical mapping/account pins on `Obligation`,
  pin resolution for the posting seam, account-grain reconciliation slices and
  evidence/provenance models.
- Treasury: account/currency-grain GL slices, Bank-run revisions/supersession and
  immutable evidence/provenance models.
- Reporting: native-slice current-state reads and fail-closed `uncomparable`
  direct-source pairs that do not yet own a sufficient exact comparison contract.
- Migrations: Accounting `0012`, Organizations `0108`, Subledgers `0004`, and
  Treasury `0008`; their data operations add only `legacy_unverified` provenance
  and do not infer account identity.

No AP/AR journal producer was activated. The posting seam returns only the
Obligation's pinned account, preserving the approved future producer boundary.

## 2026-10-15 validation closure

An isolated PostgreSQL test database (`test_cep006_validation_20261015_b62e`) was
created through Django's existing test-database setting mechanism, never sharing or
resetting `test_construction_erp`. It applied the full migration graph, including
Accounting `0012`, Organizations `0108`, Subledgers `0004` and Treasury `0008`.
After validation completed and no session remained, that CEP-specific temporary
database was removed; the shared database was not touched.

The first focused run found two CEP-006 regressions: the predecessor lookup for
Treasury GL slices and Bank reconciliation runs used `SELECT ... FOR UPDATE` across
the nullable `invalidation` join. PostgreSQL rejected that query. The bounded fix
uses `select_for_update(of=("self",))` for the Subledger, Treasury GL and Treasury
Bank predecessor rows, preserving same-grain serialization while not locking the
nullable join. The final focused suite passed **54 tests**. The representative
CEP-005/CEP-008 regression passed **23 tests and 28 subtests**.

Ruff, scoped formatting, Django system checks, migration drift and migration plan
all passed. This completes the authorized CEP-006 scope. CEP-009 is ready for queue
resume; CEP-011 and CEP-013 are not started.

## 2026-10-19 IMB-0066 bounded remediation — pre-mutation entry

Human instruction explicitly authorizes Development/Non-Production IMB-0066 only,
including focused/affected regression, evidence reconciliation, commit/push and
CEP-073 entry re-review. No whole-package redesign or rerun. Migration NONE;
STOP before model/migration mutation if that changes. Historical evidence retained.

Grounding: clean local main and origin/main at
5bff28aa143e9048ca83461910d97b9cd30286c8; no branch/worktree creation.
Registry checkpoint c884bad is stale metadata: intervening 5bff28a contains only
adjudication/Registry changes. Canonical CEP-006 prompt SHA-256 verified as
DFE2B61A485320D0347EBC40CB45A30569936481A52F11F033A3ED2970E0EA2A.
No prerequisites/external dependencies; explicit remediation authority satisfies
entry; GATE-01 PASS. Current generic main/Git rules supersede old branch mechanics.
A3 is historical and is not erased by new remediation. Preserve 57 COMPLETE /
6 PARTIAL unless actual evidence changes those states.

Actual intended touch set:
- apps/accounting/views.py and journal_list.html: fixed 25-row shared pagination,
  existing date/time ordering plus UUID tie-break, first displayed line debit via
  tenant-correlated LIMIT 1 subquery rather than all-line prefetch.
- apps/audit/views.py and templates/audit/log.html: page the existing authorized,
  payroll-filtered service queryset, stable created_at/UUID ordering.
- templates/components/bounded_table_pagination.html: constant-size Persian RTL
  previous/next navigation; no all-page link loop.
- apps/accounting/test_imb0066.py and apps/audit/test_imb0066.py: bounded queries,
  stable traversal, invalid/empty pages, tenant/object permissions, payroll filters,
  unchanged source/linkage/read-only assertions.
- output/cep-006/imb0066/: isolated test runner/results/query evidence/checks.
- CEP-006 report/manifest, missing acceptance/evidence/change CSV mappings,
  remediation evidence JSON; Registry and CEP-073 entry-review evidence.
No models, schema, migration files, financial workflows, permission catalogs,
settings, shared pagination helper behavior or previously valid evidence changed.

UI finding CEP-006-FINDING-004: canonical UI NONE coexists with the explicitly
owned list-bounding outcome. Human scope expressly includes related templates;
only pagination navigation and existing displayed debit query are changed.
Runtime load/performance/concurrency/browser verification remains UTV under CEP-073.

### Touch-set adjustment after initial focused execution

The initial isolated run completed schema initialization and reported 6 PASS /
6 FAIL (12 tests). Two Accounting failures were new test-fixture assumptions:
auto_now_add overrode supplied tied timestamps, and Viewer already grants
accounting.view. Corrected with a frozen creation clock and explicit role revocation.
Four Audit tests were denied before pagination because AuditServiceTests.setUp
has legacy memberships without explicit organization scope. The unchanged view
decorator rejects these fixtures before the new read path is entered. Add only
explicit organization scope grants to apps/audit/tests.py's existing fixture;
this also supplies the new Audit tests' reused setup. Product authorization and
Audit service behavior remain unchanged. This bounded test-fixture correction is
within the authorized focused authorization/object-scope tests and affected
regression. Preserve initial outputs; rerun focused validation and affected
AccountingTenantUiTests/AuditServiceTests on the now-migrated isolated database.


### 2026-10-19 validation closure

13 focused and 11 affected regression tests PASS. Executed scoped SQL bounds,
source authority, no-write and authorization checks PASS. Ruff/format 6 files,
Django checks and drift PASS; no product migration. AC1-11 retained, AC12-16 newly
proved, scoped DoD PASS. See corrected completion-report addendum and evidence
CEP-006-EV-001..009. Runtime load/concurrency/browser UTV. Safe Git integration
and CEP073 entry re-review follow; neither is inferred from these test results.
