# BONIRA Wave C — Domain decisions and bounded execution

Recorded 2026-10-23 (Asia/Tehran). Authority: [approved Product Decisions](PRODUCT_DECISIONS.md).
Entry HEAD: `43ac319c6e73e48ca9626461b73987922c498ec3`; accepted dirty baseline retained.

The five domain/source gates are addressed under PD-WC-D01–D05. No further
Human Product Decision is needed for this scope. Full Wave C remains open:
the final Tender browser confirmation is blocked by Work settings, and the
other required Wave C journeys have not all been revalidated here.

## 1. CURRENT_STATE_BY_SCENARIO

| Scenario | Current result and exact remaining limit |
|---|---|
| RV-011 | Effective Development monetary versions selected/applied canonically; populated posted Treasury/ledger statement exercised in HTTP and desktop/mobile. The two future published versions are byte-for-byte unchanged as serialized model snapshots. No remaining domain gate. |
| RV-013 | Approved invoice match → AP obligation → posted Treasury disbursement → settlement exercised. Browser settlement consumes the remaining balance; over-allocation, unauthorized and malformed-source submissions fail closed. No remaining domain gate. |
| RV-018 | Fixed Payroll calculated, independently reviewed/finalized; payslip and handoff preparation displayed. Approved Timesheet selector records server-derived provenance; variable run locked, calculated and submitted for review. Four absent statutory prerequisites are visible and calculation fails closed. Official successful statutory outputs remain explicitly unvalidated under D03. |
| RV-030 | Existing activation contract enabled using the approved bounded lifecycle. Service and real HTTP submission → review → lost retain revisions; missing reference and terminal transitions reject. Project selection and creation were checked in desktop/mobile. Final browser confirmation of corrected form IDs/evidence selector and transitions remains pending because local browser use is disabled in Work settings. |
| RV-032 | Actual multipart PDF/DOCX bytes reach the server, protected DMS storage and immutable revision evidence. Server-derived and retained-content digests match. Comparison mismatch, changed-content replay, invalid type/size, multiple files and unauthorized principal reject. Desktop/mobile upload and receipt were exercised before browser access became unavailable. No external Tenant membership. |

## 2. ALREADY_DETERMINED_BY_CURRENT_CONTRACT

- Monetary precision: IRR money scale 0, intermediate scale 6, preserved unrounded intermediates and final-line `ROUND_HALF_UP`; existing policy services enforce effective dates and Tenant selection/application.
- AP: approved Purchase Order/accepted Goods Receipt and independently approved exact invoice match provide the eligible source through `handoff_supplier_invoice_match()`. `Obligation`, `SettlementAllocation`, `TreasuryMovement`, `MatchTolerancePolicy`, `ControlAccountMappingVersion` and Treasury account mappings remain authoritative. Posted compatible source, party/project scope, available balance and independent approval remain mandatory.
- Payroll: existing run/configuration/rule/input/snapshot/review/finalization and financial-handoff services own calculations and transitions. `Approved Timesheet Revision` is the D02 producer; explicit mapping consumes approved minutes as minutes or exact hours. Rule/configuration selects the existing rate. Inexact eight-decimal conversion rejects; no payable-time/premium interpretation is inferred.
- Statutory calculation uses effective regulatory policy plus reviewed `StatutorySourcePackage`; official output also requires effective schema and identifier/calendar semantics. Readiness uses the same resolvers as execution.
- Tender: `TenderBidActivation` requires the Tenant, active flag, approved policy reference and activating actor. Existing `create_tender_bid()`, `revise_tender_bid()`, `transition_tender_bid()` and evidence-link services govern required fields, transition references and immutable history. A won status does not create a contract or financial transaction.
- Portal: external principal/grant/invitation/deadline controls remain authoritative. DMS staging validates bytes/type/size; protected storage verifies the write. `DocumentVersion.sha256`, sealed custody and `QuoteRevisionEvidence` associate the retained original with the receipt/revision. Client digest is comparison metadata only.

## 3. SAFE_DEVELOPMENT_CONFIGURATION

All added fixtures/configuration are labeled `UIUX_TEST_ONLY_NON_AUTHORITATIVE`.
The monetary bridge runs from execution date **2026-10-22 until 2026-12-22
(exclusive)**. Future policy publication dates and values were preserved.

Matching tolerance is **0 bps quantity / 0 bps unit price**; Treasury
self-approval is **false**. Preparation and approval use distinct existing
authorized actors. Synthetic `WCD-AP-CONTROL`, `WCD-CASH` and `WCD-CLEARING`
accounts and effective source/account mappings support the bounded runtime.
Existing domain sources were reused; no domain reset was performed.

Tender activation references PD-WC-D05 and the existing CEP-032 bounded
lifecycle. Payroll uses the pre-existing effective hourly rate with explicit
hour mapping, plus a synthetic approved 60-minute Timesheet. No Production
rates, tolerances, chart accounts, legal policy or statutory sources were inferred.

Exact configuration and retained record IDs: [CONFIGURATION.json](CONFIGURATION.json),
[FINANCIAL_FLOW.json](FINANCIAL_FLOW.json), [PAYROLL_FLOW.json](PAYROLL_FLOW.json).

## 4. TRUE_PRODUCT_DECISIONS_REQUIRED

**None outstanding for these five domain gates.** D01–D04 were approved by the
Human; D05 reuses the existing contract. Browser access and test-debt attribution
are execution/evidence matters, not additional business-policy choices.

## 5. OUT_OF_WAVE_C_CERTIFICATION_ITEMS

Production chart-account selections, tolerances/self-approval policies,
live banking/payment release, genuine Iranian tax/insurance rate and legal
certification, official output/filing acceptance, provider/calendar/identifier
certification, Production Tender legal/scoring/award policy, multi-file package
digests, Production deployment and certification remain outside this work.

There are **zero statutory calculations and zero statutory outputs** in the
verified Development database. Payroll Accounting handoff correctly reports
`ACCOUNT_MAPPING_NOT_CONFIGURED`; preparation and the prerequisite state are
validated, with no fabricated posting or automatic mapping.

## 6. IMPLEMENTATION_REQUIRED

Implemented the bounded changes below; RV-011 and Tender activation themselves
needed configuration rather than new accounting or Tender policy engines.

- Payroll: authorized Timesheet/rule selectors, explicit quantity mapping,
  server-derived source snapshot/digest and lock-time source revalidation.
  Structured prerequisite visibility and secondary technical metadata presentation.
- Portal: one required original file, server SHA-256, protected retained-byte
  verification, receipt/revision provenance, replay integrity, comparison mismatch
  rejection, cleanup/audit and preserved quarantine/confidentiality controls.
- Schema: approved minimum additive `external_portal_upload` choice and replacement
  channel CHECK in procurement migration **0016**, applied to Development. No new
  payload columns/storage subsystem were needed. No Production migration ran.
- Reachable runtime corrections: compatible posted settlement selector;
  scoped Tender project selector; authorized clean DMS-version selector;
  unique Tender form IDs. Existing assignment, posting and approval contracts remain authoritative.

Validation:

- Focused: **59 tests + 10 subtests PASS**; after the final Commercial error-handler
  correction, **6 Commercial tests PASS** again (overlapping tests, not 65 distinct tests).
- Real cookie/CSRF HTTP: **28/28 PASS**, plus final Tender extension **6/6 PASS**.
- Ruff, Django system check and migration drift check: **PASS**.
- Retained portal originals rehashed at closeout; all match revision, evidence
  and `DocumentVersion.sha256`. External submitters have no Tenant membership.
- Existing desktop/mobile captures cover the populated financial, settlement,
  Payroll, statutory unavailable and portal journeys. Final states captured for
  those journeys have one main landmark and no horizontal page overflow.
- Broad regression is **not green**: earlier runs report **73 pass / 9 fail**
  and **35 pass / 1 fail**. The 10 failures concern registry expectations,
  pre-existing role fixtures/default-grant expectations and duplicate role
  assignment setup. Existing failing service/test definitions checked against
  HEAD are unchanged; prior registry debt is linked. They are retained as
  unresolved out-of-package debt, not reported as passing or repaired through
  Authorization changes. See [BASELINE_DEBT.json](BASELINE_DEBT.json).

Evidence: [final verification](FINAL_VERIFICATION.json), [focused results](focused_final.xml),
[post-correction tests](commercial_final.xml), [HTTP](HTTP.json),
[final Tender HTTP](TENDER_HTTP_FINAL.json), [browser observations](BROWSER.json),
[remaining validation gates](RESIDUAL_BLOCKERS.json).

## 7. PRODUCT_OWNER_DECISION_TABLE

These are resolved questions; no new Human approval is requested.

| Exact question | Options | Recommended / approved option | Consequences | Scenarios |
|---|---|---|---|---|
| May Development exercise existing monetary semantics before December 22, with which tolerance and Treasury policy? | Wait; approve bounded bridge; alter future publication | **D01: bounded bridge**, 0/0 bps, self-approval false, synthetic mappings | Enables real Development flows; future versions preserved; no Production authority | 011, 013, 018 |
| Which authoritative source and mapping may produce bounded variable Payroll inputs? | Manual technical payload; governed source producer | **D02: Approved Timesheet Revision**, explicit unit/rule mapping | Server owns provenance; unsupported or inexact quantities reject; existing rates only | 018 / F-059 |
| Must Wave C produce successful official statutory calculation/export? | Require statutory certification now; validate ordinary runtime and fail-closed prerequisites | **D03: ordinary runtime and prerequisite boundary** | Official populated statutory success stays unvalidated until genuine source-backed certification | 018 |
| What is the authoritative submitted payload and digest? | Client digest only; one retained original; undefined multi-file aggregation | **D04: one immutable PDF/DOCX**, server SHA-256 of actual retained bytes, minimum additive channel migration | Enables authoritative integrity/replay checks; comparison mismatch rejects; quarantine preserved; multi-file semantics deferred | 032 / F-060 |
| Does bounded Tender activation require new scoring/legal/award choices? | Existing approved lifecycle; introduce new policies | **D05: existing lifecycle**; no new Product Decision | Development activation sufficient; no inferred award/accounting consequence | 030 |

## 8. RECOMMENDED_EXECUTION_ORDER

1. Completed: D01 effective configuration; AP/Treasury/source activation; financial runtime.
2. Completed: D02 Payroll producer and ordinary lifecycle; D03 prerequisite/fail-closed validation.
3. Completed: D04 ingestion/migration/integrity; D05 activation and service/HTTP lifecycle.
4. Remaining: enable local browser use in Work settings; confirm final Tender forms,
   transition history and desktop/mobile presentation. Retain existing captures.
5. Separately resume the remaining Wave C matrix, including RV-007's canonical
   scheduled lifecycle and RV-029's populated own-history journey, before full
   Wave C closure. Route recorded regression debt through separately authorized work.

Authorization was not reopened. CEP-078/079, Production, Human Sign-off,
Production Certification and Git writes: **NOT_EXECUTED**.

Wave C execution status: **WAVE_C_BLOCKED** (evidence limits above).

DOMAIN_DECISION_PACK_READY
