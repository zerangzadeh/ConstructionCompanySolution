> Current Wave C disposition — 2026-10-23: **WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT**.
> **RV-007 PASS; 12/12 scenarios PASS; 18 pre-existing baseline failures retained.**
> [Final closure](rv007_mobile_closure/COMPLETION_REPORT.md) · [final matrix](rv007_mobile_closure/WAVE_C_MATRIX.json).
> Earlier sections below preserve historical attempts and their then-current blockers.

# Wave C targeted re-entry — 22 October 2026

**WAVE_C_BLOCKED.** Five canonical scenarios PASS; seven retain precisely bounded
authority, policy or source-contract blockers. All twelve have current dispositions
under `wave_c_targeted_reentry` in [the canonical results](UIUX_RUNTIME_VALIDATION_RESULTS.yaml).
This pass does not close Wave C or authorize another wave.

## Authority and preserved baseline

[The Human decision pack](wave_c_reentry/AUTHORIZATION.txt), PD-WC-01 through
PD-WC-08, authorizes this Development-only re-entry. Local `main`, HEAD and local
upstream remain `43ac319c6e73e48ca9626461b73987922c498ec3`; the accepted dirty
source is preserved. [Entry fingerprints](wave_c_reentry/FILES_BEFORE.json) and
[exact initial report copies](wave_c_reentry/entry_reports/) retain the effective
baseline. The CEP Registry, Roadmap, canonical CEP prompts, built-in role defaults
and permission definitions are unchanged. No remote freshness claim is made.

Seven separate specialist accounts, ten exact-tenant custom roles and seven
explicit scopes were provisioned through canonical services. Three roles remain
unassigned after canonical transfer denial; their account transactions rolled back.
The Buyer receiving/preparation subset omits unavailable protected opening powers.
HR/Controls dependent permissions were refined by revoke → update → independent
reassignment, with held-permission and dual-control checks preserved. Payroll uses
its own Payroll-only persona; the existing assurance Owner is only a canonical
delegator. [Role evidence](wave_c_reentry/ROLES.json),
[original denial](wave_c_reentry/DELEGATION_ATTEMPT.json),
[explicit linked identity](wave_c_reentry/EMPLOYMENT_IDENTITY.json).

## Current scenario results

| Scenario | Current result | Material coverage |
| --- | --- | --- |
| RV-007 | BLOCKED | Bounded Buyer receiving/preparation role provisioned at Project A. Genuine synthetic source fingerprint captured/submitted canonically; same-tenant C, foreign X, site-only and manipulated actions deny. Protected opening/confidential first-grant remains unavailable; F-008 stage/prerequisite/unique-empty-stage guidance is implemented without an invented later-stage priority. |
| RV-009 | PASS | Prior PASS retained; only necessary inherited isolation/valuation smoke coverage ran. No Inventory fixture or scope changes. |
| RV-011 | BLOCKED | Exact existing monetary defaults recovered, but both published policy dates are 2026-12-22. Current canonical selection rejects them and the attempt rolls back. No populated journal/statement is fabricated. |
| RV-013 | BLOCKED | Registered source adapters verified. No eligible AP/AR source, approved tolerance policy, Treasury approval-policy version or cash/clearing mapping exists. Accounting effective-date gate also persists. Workbench and negative controls observed; no fake obligation, cash movement or settlement. |
| RV-015 | PASS | Least-privilege HR specialist completes structure/foundation/create surfaces. Canonical department/position/team/employee fixtures plus real CSRF department creation and existing-account Employee reuse verified. Explicit Employee.user/Person/WorkRelationship links retained. Sensitive performance/rate controls deny. New employee-detail nested main fixed as F-131; desktop/mobile final capture has one main. |
| RV-017 | PASS | Least-privilege Timekeeping specialist completes calendar/setup/daily attendance journeys on isolated synthetic calendar. Canonical attendance and real CSRF holiday creation verified. Closed setup disclosure separates daily work; populated mobile overflow fixed. ISO weekday entry remains an observed existing form convention, not a change to calendar rules. |
| RV-018 | BLOCKED | Separate Payroll-only specialist with no Workforce-sensitive grants completes configuration, period/run preparation and draft/statutory/handoff surfaces. Canonical synthetic non-statutory example stops at active-monetary-policy input-lock gate. No statutory rules or downstream financial effects manufactured. Bounded presentation, project-site narrowing and generated retry-key changes validated; populated downstream journeys remain blocked. |
| RV-028 | PASS | Project-scoped Document Specialist creates one benign synthetic document, two immutable versions and canonical Project link. Both byte-identical hashes receive genuine Microsoft Defender no-threat verdicts through canonical processing assessment; both downloads pass. C/X/unauthorized controls deny. Temporary independently assigned Platform Operations duty revoked; no CLEAN evidence synthesized. |
| RV-029 | BLOCKED | Governed internal management form/list/append-only command UI implemented. Isolated authorized creation, duplicate/invalid redisplay, cross-tenant/other-person history, missing/mismatched Employee.user and sensitive-metadata controls pass. Live management/own custom roles remain unassignable through tenant delegation. Explicit linked identity fixture is present, with fail-closed live own-history denial; no identity inference. |
| RV-030 | BLOCKED | Project-scoped Commercial specialist provisioned; tender creation form and contract reads available. Canonical tender activation lacks an approved policy reference/activation contract. No threshold, scoring, approval, award rule or test-policy activation invented. |
| RV-031 | PASS | Project-scoped Controls Analyst reads WBS/activity and populated advanced comparison/reconciliation from the existing accepted budget (one coded line); exceptions remain a scoped read model. Same-tenant project C and foreign X controls deny. No Project Cost source fact added or source-authority inference. Canonical authorized reconciliation-view audit is preserved. |
| RV-032 | BLOCKED | Exact tenant custom Portal Manager role created but canonical tenant assignment rejects unavailable permission transfer. External invitation lifecycle remains blocked. F-060 also lacks an external original-payload custody/hash input contract; existing portal metadata hash is not substituted for file-integrity evidence. No external identity with tenant membership created. |

## Bounded remediation

RFQ guidance shows its real stage, receipt prerequisites and a primary capture link
only for the determinate empty-receipt state. Later concurrent choices retain an
explicit ambiguity rather than an invented purchasing priority. Timekeeping puts
setup in a closed disclosure and daily operations first. Payroll uses task terms,
one-run continuation, dependent Project/Site choices, hidden generated retry keys,
and closed digest/calculation details while preserving monetary results and hashes.
F-059's remaining caller-owned source snapshots are not silently manufactured.

The new Employment management surface binds relationships, safe linked DMS
versions and explicit supersession to the active organization, checks the existing
permissions, and calls `record_employment_version`. Own history additionally
requires the current relationship's explicit `Employee.user` link; existing
Person/relationship identity remains intact. The rehire test fixture now establishes
that explicit link, and historical same-Person records remain preserved. No schema
or identity model was introduced. The HR linked-detail nested main defect is
recorded separately as F-131 and runtime-resolved without reopening F-129.

F-005/F-006/F-040/F-058 have bounded runtime resolution records. F-008/F-059/
F-067/F-068/F-069 retain partial runtime verification where populated downstream
journeys are gated; F-060 remains blocked by the external payload contract. All
prior F111/BATCH-01–09, SP031/F-128, F-129 and F-130 closure records are preserved.

## Verification and integrity

- Final focused tests: **26 PASS + 6 subtests PASS**.
- Combined affected suite: **75 PASS + 44 subtests PASS; one BASELINE TEST DEBT**.
  The unchanged failing test checks `payroll.StatutorySourcePackage` against the
  model registry. Its function matches HEAD and all three dependencies match entry
  hashes; changed behavior is not reached by the failing assertion. The stale
  Payroll title assertion was updated for the authorized terminology and passes.
  This is affected-boundary coverage, not full-repository regression PASS.
- **100** real authenticated HTTP matrix observations, including **35**
  CSRF-bearing POSTs, have no unexpected statuses. Successful department/holiday
  writes are retained in the initial complete matrix; known-account reuse is
  separately verified. **19** genuine Edge observations / **38** desktop/mobile
  screenshots plus interaction captures show one main and no page-level overflow.
  Focus samples and invalid-form behavior are bounded checks, not accessibility
  certification. Initial diagnostic expectations/stale-process output are history.
- **21** direct-service controls have expected outcomes. Comparison and
  reconciliation read one existing accepted-budget line. No business row changes
  occurred during these controls; the canonical authorized reconciliation-view
  audit is expected and retained.
- Both synthetic document versions were genuinely scanned by Microsoft Defender
  4.18.26090.9 with `found no threats` output and matching pre/post byte hashes.
  Canonical assessment unlocked downloads. The temporary Platform Operations duty
  was independently assigned and revoked. No mocked scanner output is used.
- Django checks, focused Ruff lint/format and migration-drift checks PASS.
  **Migration: NO.** No schema, production configuration or dependency changed.
- All 519 model fingerprints were compared. The sole changed pre-existing business
  row is the expected DMS document-number sequence increment. Additions are
  bounded synthetic fixtures, exact role/account/scope and audit history; no
  journal, obligation, Treasury movement, settlement or Project Cost fact was
  added. Login timestamps are excluded; session credentials are never serialized.
  Credentials remain in current-user Windows DPAPI outside the repository.

[Focused output](wave_c_reentry/focused_final.txt),
[combined regression](wave_c_reentry/final_tests.txt),
[baseline attribution](wave_c_reentry/BASELINE_DEBT.json),
[HTTP summary](wave_c_reentry/HTTP_SUMMARY.json),
[direct services](wave_c_reentry/DIRECT_SERVICE.json),
[scanner evidence](wave_c_reentry/DOCUMENT_SCAN.json),
[integrity](wave_c_reentry/INTEGRITY.json).

## Residual blockers and minimum input

**RV-007 — A governed tenant first-grant/delegator for rfq_quotes.open and rfq_quotes.view_confidential (and the independently assigned opening duties required by the canonical closed-RFQ lifecycle).**

The full custom role was created, but assign_membership_role rejected transfer of permissions absent from the assigning tenant actor. No active tenant holder exists. The available receiving/preparation subset now captures and submits a genuine hashed synthetic source; it cannot open/confidentially compare it. F-008 does not invent precedence among concurrent permitted commands.

Minimum Human/external input: Provide a governed authorized tenant delegator, or approve a bounded first-grant mechanism preserving independent approval and exact project scope.

**RV-011 — Currently effective accounting-money-precision and accounting-rounding versions.**

Both existing published code-owned versions start on 2026-12-22. Canonical selection rejects them on 2026-10-22. Advancing an existing accounting effective date is not determined by PD-WC-06. The activation attempt rolled back; no journal was fabricated.

Minimum Human/external input: Approve a specific currently effective Development version/date for the existing closed values, or wait for the published effective date and apply it canonically.

**RV-013 — One eligible approved AP/AR source and a canonically postable Treasury source: approved source policy, treasury-self-approval.allow_self_approval, cash/clearing ledger mappings, and effective accounting policies.**

All four source adapters are registered, but no eligible source exists. The invoice route requires an approved MatchTolerancePolicy with explicit quantity_tolerance_bps and unit_price_tolerance_bps; none exists. Treasury has no policy version or account mapping. Neither allowed boolean alternatives, account-code guesses nor test tolerance values select a business policy.

Minimum Human/external input: Supply one governed eligible source/policy configuration and the explicit Treasury approval/mapping decisions; also resolve RV-011's accounting effective-date gate.

**RV-018 — Effective monetary policies for the prepared non-statutory run; reviewed official tax/insurance rules and output schemas for statutory journeys; a governed source-payload selection contract for the remaining F-059 input derivation.**

A separate Payroll-only specialist, synthetic configuration/rule/period/run are provisioned. Input lock reaches the canonical missing active policy gate. No published statutory rule/source was supplied. Current source snapshot inputs are caller-supplied; hiding them or inventing their content cannot establish source integrity. Run/statutory/handoff presentation is improved, but their populated downstream runtime remains unverified.

Minimum Human/external input: Resolve RV-011, provide reviewed canonical statutory source/schema evidence, and specify the authoritative input producer/selection contract for source snapshots.

**RV-029 — A governed tenant first-grant/delegator for employment_records.manage and employment_records.view_own.**

Both custom roles exist, but canonical assignment rejects permissions held by no tenant delegator. The management UI and explicit Employee.user plus existing Person/WorkRelationship linkage are implemented and tested; there is no permitted live specialist to complete the management/own-history positive journey. Platform privilege cannot supply that tenant authority.

Minimum Human/external input: Provide an authorized tenant delegator or approve a bounded first-grant path with independent approval. No new identity model is needed.

**RV-030 — An approved canonical Development Tender policy reference and its governed activation contract.**

The Commercial specialist is provisioned. There is no TenderBidActivation row, approved policy_reference or code-owned default activation. The placeholder approved-test-policy in isolated tests is not a Product Decision; writing it would fabricate activation evidence.

Minimum Human/external input: Supply the approved policy/version reference and bounded canonical activation instructions; define any required tender values rather than deriving them from test fixtures.

**RV-032 — A governed tenant first-grant/delegator for supplier_portal.invitations_manage; an external submitted/uploaded-payload custody/hash contract for F-060.**

The tenant custom role exists but canonical assignment rejects the unavailable permission transfer. The portal accepts only a precomputed integrity fingerprint and metadata, not original bytes. Its metadata fingerprint includes that supplied hash. Existing sealed-file custody requires tenant authority and a closed RFQ, so it cannot be reused as an external pre-submission upload path without an approved contract change. Hashing a reference string would weaken integrity.

Minimum Human/external input: Provide the governed first-grant authority and approve/identify the external payload-custody interface from which the server can compute the canonical hash. External users must remain outside tenant membership.

The [machine-readable blockers](wave_c_reentry/RESIDUAL_BLOCKERS.json) and
[source-gate inventory](wave_c_reentry/SOURCE_GATES.json) retain exact boundaries.
No scanner blocker remains. Specialist definitions and ordinary fixtures are prepared; the exact first-grant authority boundaries remain blocked above.

Production, deployment, cutover, Human Sign-off, Production Certification and
CEP-078/079: **NOT_EXECUTED**. Git add/commit/push/merge and branch/worktree creation:
**NOT_EXECUTED**. The session's Development server is stopped at closeout.

**WAVE_C_BLOCKED — STOP.**


## Authorization reconciliation addendum — 2026-10-22

The Human Product Decision authorizes the bounded Platform Initial Grant and
Role-Permission Matrix correction. The former first-grant authority gaps for
RV-007, RV-029 and RV-032 are resolved through six audited scenario grants using
existing role/scope/audit records. Owner/Admin default permissions match HEAD
exactly. No new bootstrap subsystem, second Platform approver or tenant-business
bypass was introduced.

18 final Initial Grant/matrix tests and 9 protected-opening retests PASS. The
affected selection has 110 passing main tests after fixture retests and 68 passing
subtests, with four HEAD-attributed registry failures retained. Real runtime:
18 expected HTTP observations, including six POSTs; one concurrent grant and one
duplicate denial. All pre-existing rows remain; financial/Payroll/Inventory model
fingerprints are unchanged. No schema migration or domain reset occurred.

The newly reachable Portal management page exposed an existing missing required
permission-message argument. UIUX-F-132 is runtime-verified resolved by the bounded
call correction and regression. One real synthetic external invitation was
created; its plaintext token was not persisted and no external membership was
created. Existing own-history identity/source-document checks remain authoritative.

RFQ opening still requires the scheduled October 24 close and valid source/scan
evidence. Populated own Employment history was not rerun. Accounting, statutory,
Tender and external payload-custody gates remain as previously recorded. This
authorization revalidation does not close Wave C or CEP-078/079.

[Completion report](authorization_reconciliation/COMPLETION_REPORT.md),
[current matrix](authorization_reconciliation/ROLE_PERMISSION_MATRIX.csv),
[verification](authorization_reconciliation/FINAL_VERIFICATION.json).

**WAVE_C_BLOCKED. Production, Human Sign-off and Git writes: NOT_EXECUTED.**

## Domain decisions and bounded execution addendum — 2026-10-23

[PD-WC-D01–D05](wave_c_domain_resolution/PRODUCT_DECISIONS.md) resolve the
remaining financial, Payroll producer, statutory-coverage, Tender activation
and external-original integrity decisions. Development bridge configuration
preserves the published future monetary policies. Approved source/Treasury
and Payroll lifecycles now have populated runtime evidence. Portal integrity
comes from the actual retained original, with the approved minimum additive
channel/CHECK migration applied only to Development.

Focused checks: **59 tests + 10 subtests PASS**; **6 overlapping Commercial
tests PASS** again after the last correction. Real CSRF-bearing HTTP:
**28/28**, plus **6/6** final Tender controls. Static/system/migration-drift
checks PASS. Broad regression remains **not green** with 10 recorded failures
across the earlier runs; unchanged failing paths and prior registry debt are
documented without reopening Authorization.

Desktop/mobile evidence covers populated statement/settlement, Payroll,
statutory unavailable states and actual portal upload/receipt. Final Tender
browser confirmation remains pending: local browser use is disabled in Work
settings. HTTP confirms corrected unique IDs, required references, transitions
and terminal rejection. This package does not close the full Wave C matrix,
RV-007's scheduled opening lifecycle or RV-029's populated own-history retest.
Successful official statutory output is explicitly outside Wave C under D03.

The [completion report](wave_c_domain_resolution/COMPLETION_REPORT.md),
[verification](wave_c_domain_resolution/FINAL_VERIFICATION.json) and
[current remaining gates](wave_c_domain_resolution/RESIDUAL_BLOCKERS.json)
supersede the five historical domain-decision blockers above. Historical
evidence and prior closed findings are retained.

**Domain decision pack: DOMAIN_DECISION_PACK_READY. Wave C: WAVE_C_BLOCKED.**
Production, Human Sign-off, CEP-078/079 and Git writes: **NOT_EXECUTED**.

## Final closure reconciliation — 2026-10-23

Current result: **WAVE_C_PENDING_REAL_TIME_CONDITION**. [Final report](wave_c_final_closure/COMPLETION_REPORT.md) and [matrix](wave_c_final_closure/WAVE_C_FINAL_MATRIX.json) supersede only current Wave C dispositions; previous evidence remains historical.

RV-029 populated explicit-identity Employment history and RV-030 authenticated desktop/mobile Tender verification **PASS**. The raw Person/UUID management labels are corrected as UIUX-F-133. Of ten recorded failures, **7 attributable failure conditions are fixed, 3 baseline cases retained, 0 indeterminate**. Final focused selection: **6 PASS / 4 baseline FAIL**, including one separately unmasked HEAD schema mismatch. Final affected selection: **45 tests + 10 subtests PASS / 2 baseline fixture FAIL**. Full regression is not claimed green.

**11 scenarios PASS; RV-007 remains pending the real close/opening lifecycle.** Its unchanged Tehran close is October 24 at 14:46:11 and earliest opening October 25 at 14:46:11. No early close/opening or fabricated source/scan evidence occurred. Official statutory success remains **OUT_OF_WAVE_C_CERTIFICATION** under D03.

All existing business rows/identity links and unrelated dirty source are preserved; no new migration was introduced. The bounded scanner duty has a recorded October 23 02:03:51 Tehran expiry; independent early revocation was denied and not bypassed. Production, Human Sign-off, Wave D, CEP-078/079 and Git writes: **NOT_EXECUTED**.

**WAVE_C_PENDING_REAL_TIME_CONDITION — STOP.**


## RV-007 final closure attempt — 2026-10-23

**WAVE_C_BLOCKED — RV-007 BLOCKED_CANONICAL_TEMPORAL_PREREQUISITE.** The real-clock canonical rollback probe proves a newly created past-close RFQ receives a late quote, cannot submit it, and has no opening-eligible manifest entry. No canonical retrospective quote-import path exists in the inspected Procurement services. No new RFQ is retained. The existing RFQ, all Procurement model fingerprints, product source and Git HEAD/index remain unchanged. Early close/opening denial is retained; the manifest guard precedes the separate opening-time guard.

Focused: **9 passed in 71.12s (0:01:11)**. Affected: **27 failed, 25 passed, 4 subtests passed in 158.81s (0:02:38)**. [Report](rv007_final_closure/COMPLETION_REPORT.md), [proof](rv007_final_closure/FEASIBILITY.json), [matrix](rv007_final_closure/RV007_MATRIX.json), [validation](rv007_final_closure/VALIDATION.json). Positive live opening/comparison/source-scan and authenticated desktop/mobile verification remain unexecuted. No completion status is issued. Prior baseline debt and 11 prior scenario results are preserved. The additional 27 fixture failures have historical attribution UTV; they are not accepted as baseline debt and the earlier zero-unresolved-regression claim is not extended to this broader selection. Production, Wave D, CEP-078/079, Human Sign-off and Git writes: **NOT_EXECUTED**. **STOP.**


## RV-007 controlled-time reconciliation — 2026-10-23

**WAVE_C_BLOCKED_ENVIRONMENT.** The explicitly authorized application-only clock completes the canonical positive opening, independent approval/admissibility, exact confidential comparison, real source/hash/custody/scan and authorization controls. OS clock, normal server, retained RFQ, business rules/default roles and Production remain unchanged. All 27 original regression failures are attributed: **9 attributable, fixed; 18 baseline, retained; 0 indeterminate; 0 unresolved attributable**. Focused **9 PASS**; affected **34 PASS / 18 baseline FAIL + 21 subtests PASS**. Twelve real authenticated HTTP controls PASS. Desktop opened workspace and desktop/mobile comparison form pass; final mobile opened-workspace capture remains blocked because local browser use is disabled in Work settings. No full RV-007/Wave C PASS or completion status is issued. [Report](rv007_controlled_time/COMPLETION_REPORT.md), [matrix](rv007_controlled_time/WAVE_C_MATRIX.json), [attribution](rv007_controlled_time/REGRESSION_ATTRIBUTION.json), [integrity](rv007_controlled_time/INTEGRITY.json). Prior findings and baseline debt preserved. Wave D, CEP-078/079, Production, Human Sign-off and Git writes: **NOT_EXECUTED**. **STOP.**


## Final mobile browser reconciliation — 2026-10-23

**WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT. RV-007 = PASS.**
The retained opened-quote workspace passes authenticated mobile verification in
Google Chrome 155.0.8059.82 at 390 × 844 as `uiux.wavec.buyer`. Correct closed RFQ
stage, populated authorized comparison, reachable permitted operations, one main,
no overflow/duplicate IDs and no console error are evidenced. All 12 current
scenario dispositions PASS. **18 BASELINE_PREEXISTING failures remain debt**;
9 attributable failures are fixed, 0 indeterminate and 0 unresolved attributable.
Prior focused 9 PASS and affected 34 PASS / 18 baseline FAIL / 21 subtests PASS
are retained, without an unnecessary browser-only regression rerun. Original RFQ,
business data/rules, authorization/default roles, source, migrations and Production
are unchanged. Earlier evidence and earlier baseline debt are preserved.
[Final report](rv007_mobile_closure/COMPLETION_REPORT.md),
[matrix](rv007_mobile_closure/WAVE_C_MATRIX.json),
[browser evidence](rv007_mobile_closure/BROWSER.json),
[integrity](rv007_mobile_closure/INTEGRITY.json).
Wave D/E, CEP-078/079, Production actions, Human Sign-off, Git writes and
branch/worktree creation: **NOT EXECUTED**. **STOP.**
