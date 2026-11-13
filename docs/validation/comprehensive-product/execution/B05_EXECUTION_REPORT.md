# B05 execution report

**12 November 2026 · MVP · Estimates, Contracts, Billing and Claims**

B05 is **not ready for Product Owner acceptance**. The current matrix records **20 PASS, 1 FAIL, 52 BLOCKED and 0 NOT_RUN** across 73 planned rows. Chrome and PostgreSQL verified working journeys and surfaced four product defects. All four have bounded fixes. The estimate input recovery passed a Chrome retest. Three fixes passed independent HTTP checks and still need final Chrome verification, including the P1 successor detail defect.

| Stage | Planned | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|
| Original execution | 73 | 20 | 7 | 46 | 0 |
| Current outcomes | 73 | 20 | 1 | 52 | 0 |

| Scenario | Planned | PASS | FAIL | BLOCKED |
|---|---:|---:|---:|---:|
| UAT-07 · Estimates and contracts | 8 | 3 | 0 | 5 |
| UAT-08 · Measurement and claim pricing | 13 | 9 | 1 | 3 |
| UAT-09 · Claim review and correction | 4 | 2 | 0 | 2 |
| CV-BIL-01 · Conditional billing controls | 48 | 6 | 0 | 42 |

The route inventory contains 25 active and 48 conditional rows. All 73 resolve within the MVP contracts capability. Conditional operations still require entitlement, eligible source state and applicable policy. The anonymous, restricted and foreign HTTP probes sampled all 73 rows. Real source foreign-tenant probes for scoped routes were denied. The browser observations cover maker and reviewer interactions. The restricted and foreign personas were exercised through separate authenticated HTTP sessions. [Current MVP matrix](../TEST_EXECUTION_MATRIX_MVP.csv) · [Original outcomes](B05_ORIGINAL_RESULTS.csv) · [Product Surface reconciliation](evidence/b05-24ad220f/mvp-surface-reconciliation.json) · [Scope probes](evidence/b05-24ad220f/boundary-probes.json)

## Baseline and migration gate

Local `main`, `HEAD` and `origin/main` were `24ad220f0376cb0b6232b745938b35433843a32d`. B05 used a private loopback PostgreSQL 18.6 cluster and a schema clone from earlier synthetic validation. The restored clone began without business tenants or users. All five pending B03 migrations applied, including `daily_reports.0009_revision_guards`. The B05 runtime verified **462 applied and zero pending**. Django system check and migration drift passed.

The B03/B04 integration gate passed on its frozen integrated source. The from-zero migration exited `0`, with **462 applied and zero pending**. The same source passed 68 focused tests, 31 subtests and four Chrome journeys. The earlier mutable-source attempt ended with exit `-1`. All migration file hashes match the current checkout. The four source differences are the B05 fixes listed below. Full B05 integrated acceptance remains pending. [B03/B04 integration gate](B03_B04_INTEGRATION_GATE_REPORT.md) · [Entry fingerprints](evidence/b05-24ad220f/entry-baseline.json) · [Migration comparison](evidence/b05-24ad220f/migration-and-preservation.json) · [B05 migration log](evidence/b05-24ad220f/migrate-original.log)

## Business and billing integrity

- **Estimates.** Chrome created a scoped draft and saved a unit-backed line. PostgreSQL confirmed `1.2345 × 123.45 = 152.399025`, rounded half up to **152.40 IRR**. Zero quantity and negative price wrote no line. The independently approved estimate rejected a subsequent item POST. Authorized estimate XLSX delivery passed through HTTP. The catalog expects creation from an approved unlinked estimate, while the implemented contextual route opens an existing association or explains that conversion is unavailable. Standalone contract creation, project/party association and the draft insurance classification POST passed through HTTP.
- **Receivable claims.** The synthetic baseline is 1 unit at 120 IRR. Verified period and cumulative work are 0.5000 units. Persisted claim gross and net were **60 IRR** each under the configured zero-adjustment fixture. Separate focused tests passed with pinned nonzero contractual deductions and synthetic tax and insurance parameters, including rounding, and refused a claim without an eligible rule version. The historical MVP08 50,000,000 gross and 36,700,000 net specimen was not rerun because its exact approved source configuration was unavailable in the isolated fixture. No rates were inferred from that specimen.
- **Claim review and history.** Chrome recalculated, submitted and returned a replacement claim. It showed the preserved approved source and linked successor. HTTP verified independent approval, missing-reason and self-approval refusals, and a linked correction. PostgreSQL races on a second claim recorded one workflow, one submission audit and one approval audit. Print and XLSX responses were validated at the HTTP boundary. The remaining Chrome approval, correction, creation and export actions are blocked by browser availability.
- **Payable and commercial controls.** The approved measurement contributed `5 × 100 = 500 IRR` gross. Approved contractual terms applied **50 IRR** retention and the documented draft deduction applied **25 IRR**, giving **425 IRR** net. A later approved replacement had **450 IRR** net and resolved to that exact source version. Concurrent submission reused the workflow and recorded one audit event. Concurrent approval recorded one approved decision. HTTP verified the configured guarantee, clearance evidence and retention release chains, their approved predecessors, and their linked successors. The selected evidence was scoped to the synthetic contract.
- **Handoff and statutory boundaries.** AR and AP source resolvers reproduced the same approved source identity, version, contract and amount on replay and rejected wrong versions and foreign organizations. The approval and correction journeys left GL journals, Treasury movements and subledger obligations at zero. Positive downstream recognition needs an applicable approved control-account mapping. Both statutory creation forms rendered and rejected the authorized POST without an effective published policy, leaving zero statutory records. The remaining positive statutory rows require that policy and a valid source record. Accounting, Treasury and subledger surfaces remained hidden.

[HTTP and persistence evidence](evidence/b05-24ad220f/http-and-persistence.json) · [Final HTTP and source evidence](evidence/b05-24ad220f/final-http-and-source-witness.json) · [Payable concurrency, print and XLSX](evidence/b05-24ad220f/supplement-and-concurrency.json) · [Receivable concurrency](evidence/b05-24ad220f/receivable-concurrency.json) · [Pinned rates and rounding tests](evidence/b05-24ad220f/final-focused-clean.log)

## Chrome and remediation

Chrome recorded 122 observations over 38 distinct paths. The 33-page sweep sampled each route at 1440, 1024 and 390 CSS px and reproduced the two successor errors at all three widths. The review used the approved Contracts List, Contract Create and compact form references and the shared list, detail, context, transactional form, dashboard and feedback archetypes. Two early Contract Detail width readings were taken during viewport changes. A settled retest at 1024 and 390 px showed that the document fit and the tab strip retained its own horizontal scroll. The accepted Contract page source was preserved. Page-specific Product Owner acceptance remains pending where the registry only defines a shared archetype. [Design registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md) · [Chrome observations](evidence/b05-24ad220f/browser-observations.json) · [Contract at 390 px](evidence/b05-24ad220f/contract-detail-390.png)

| Defect | Severity | Fix | Independent retest |
|---|---|---|---|
| BON-DEF-0029 | P2 | Keep estimate validation errors on the bound form and reopen the line editor. | Chrome at all three widths and focused PostgreSQL tests passed. The invalid attempt kept the description, quantity, unit and price and wrote no line. |
| BON-DEF-0030 | P2 | Show the measurement unit in place of the payable item UUID. | Final HTTP verified the unit and absence of the raw UUID. Final Chrome retest is blocked. |
| BON-DEF-0031 | P3 | Prevent a second currency formatting pass on the already formatted estimate line amounts. | Final HTTP verified the two formatted cells use the existing guard. Final Chrome retest is blocked. |
| BON-DEF-0032 | P1 | Select the history reason appropriate to the commercial record type. | Two focused PostgreSQL regressions and final HTTP returned 200 for guarantee and compliance successors and preserved their predecessors. The release correction also rendered. Final Chrome retest is blocked. |

[Defect register](../DEFECT_REGISTER.md) · [Estimate recovery retest](evidence/b05-24ad220f/estimate-zero-retest-1440.png) · [Original successor 500](evidence/b05-24ad220f/guarantee-successor-500-original-1440.png) · [Six focused defect regressions](evidence/b05-24ad220f/final-defect-regressions.log)

The initial 72-test selection had 39 errors. Most stopped during legacy fixture setup before the billing assertions. The browser fixture expected a fixed session cookie name, and mixed transactional teardown hit the retained-table flush constraint. With native roles added only to the affected test fixtures, 45 of 48 selected tests passed. The remaining errors involved a missing control-account mapping, an incomplete foreign-tenant fixture and a guarantee already expired on the execution date. Separate clean focused selections and independent PostgreSQL writers verified the affected behavior listed above. No full regression pass is claimed.

## Decisions and next wave

- **BON-DEF-0033, `NEEDS_PO_REVIEW`.** Decide whether UAT-07 should use the existing linked-contract journey or require separate authority for converting an approved unlinked estimate. The current contract creation form and linked navigation are usable independently.
- **BON-DEF-0034, `NEEDS_PO_REVIEW`.** The entitled maker verified their own receivable measurement under the existing compatibility starter. The independent reviewer path also worked. Decide whether the receivable starter must require separate actors for B05. The payable rule already requires maker-checker separation.
- Statutory policy and downstream financial mapping are prerequisites for the remaining positive branches. Browser use was disabled in Work settings during closeout. Resume the pending Chrome actions and retest BON-DEF-0030 through BON-DEF-0032 before accepting B05.

The next planned wave is **B06 · UAT-11–14 and CV-INV-01**, after B05 closeout. B06 and Product Owner acceptance remain unstarted. Product changes are limited to the estimate detail view/template and the two billing detail templates, with focused regressions in `tests/test_b05_validation.py`. The B05 Django and PostgreSQL listeners were stopped and the synthetic fixtures retained for resumption. There were no B05 schema changes, Git commits or pushes, or operations on existing Development, demo or Production data.
