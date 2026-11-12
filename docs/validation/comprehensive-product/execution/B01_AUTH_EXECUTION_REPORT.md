# B01 authentication and user context

**Baseline** · main at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`, matching local origin/main. MVP, real Google Chrome 156.0.8078.80, disposable PostgreSQL 18. Wave run dated 2026-11-10 Asia/Tehran.

| Planned | Rows with evidence | PASS | FAIL | BLOCKED | NOT_RUN | NEEDS_PO_REVIEW | PO_ACCEPTED |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 41 | 29 | 21 | 0 | 3 | 12 | 5 | 0 |

[Derived matrix](../TEST_EXECUTION_MATRIX_MVP.csv) gives the exact row dispositions. The one technical Django Admin row is a protection-only check. The browser sent one restricted request, observed 403, and did not open or capture a hidden page.

## Results

| Scenario | Current evidence and limit |
|---|---|
| UAT-01 | Chrome exercised valid, invalid and inactive login, unsafe return handling, actual tenant selection, scoped search and navigation to the matching project, and POST logout with a protected bookmark redirect. The same synthetic project code in the other company did not appear. Configured image handlers have focused automated coverage. Login design reference remains open. |
| CV-AUTH-01 | Public recovery gave the same message for known, unknown and inactive accounts. The file sink captured one eligible recipient. Chrome followed the valid link, saved a new credential, rejected used and expired tokens, and verified first-login confinement and private profile image delivery after actual upload. The focused suite independently exercised throttle, blocked accounts and profile scope. Four public recovery pages retain a page-specific reference gap. |
| UAT-15 | Restricted menu and keyboard drawer checked at 1440, 1024 and 390. Same-company project 200, foreign project 403, foreign site 404, and forged switch/context POSTs 403. Workbench, report and timekeeping XLSX probes also denied the restricted user. Foreign Project contextual document selector denied. Three absent-record probes produced 403 but could not prove foreign-document, stock or claim isolation with a valid domain fixture. Twelve remaining variants were unattempted. |

No authorization or business-rule failure was confirmed in the executed scope. The read-only witness retained the same project and site counts. Per-row authorization PASS for a blocked row records the observed guard result only. It leaves the required valid foreign-record assertion blocked.

## Design and navigation

| Rendered page or state | Archetype | Current disposition |
|---|---|---|
| Login and invalid credentials | DC-01/DC-09 | RTL responsive composition, labeled inputs, recovery affordance and one main landmark verified at 1440, 1024 and 390. `REFERENCE_MISSING` for approved page-specific visual conformance. |
| Public reset request, neutral response, confirm, complete and expired/used states | DC-01/DC-09 | Recovery path, safe state feedback and real terminal behavior checked. `REFERENCE_MISSING` for dedicated visual authority. |
| Required personal password | DC-06/DC-09 | Scoped compact form, credential sequence and context matched the existing pattern for the tested state. |
| Tenant selector, Home and restricted menu | DC-02/DC-03/DC-08 | Explicit tenant selection and permission-aware destinations verified. Menu showed five accessible links at all three widths for the restricted fixture. |
| Search and contextual Project Detail | DC-02/DC-03/DC-05 | Positive link led to the correct record; empty copy and contextual heading checked. Projects retains its independent layout exception. |
| Personal settings | DC-03/DC-06 | Labeled profile and security groups, save feedback and authenticated image delivery checked on the actual page. |

**Historical retests.** F-107 single main confirmed at all three widths. F-015 wording absent on the current empty search. F-016 one RFQ link per populated navigation region and F-017 no unconditional disabled placeholders in the inspected owner shell. These are scoped observations. The historical Home hierarchy decisions F-065/F-066 require a richer populated Home fixture for a separate reassessment.

**PO review.** Identify the authoritative login and public recovery visual reference. The registry retains the shared objective requirements and the historical reference without inferring approval. The [page conformance index](evidence/wave-01-865fa3f3/PAGE_CONFORMANCE.md) distinguishes completed design judgments from partial observations.

Evidence · [Initial browser observations](evidence/wave-01-865fa3f3/browser-all.json) · [Keyboard menu and profile retry](evidence/wave-01-865fa3f3/browser-retry-auth.json) · [Expired link check](evidence/wave-01-865fa3f3/browser-expired-auth.json) · [Focused tests](evidence/wave-01-865fa3f3/test.log) · [Final read-only witness](evidence/wave-01-865fa3f3/state-final.json)
