# CEP-032 authenticated browser verification — 2026-10-18

Evidence: **CEP-032-EV-007** (this record), **CEP-032-EV-008** (actual screenshots).
Current verdict: **EXECUTION COMPLETE / 12 AC PASS**. The initial verification below is historical; the buyer-action remediation closeout at the end resolves Finding 003.

## Grounding and bounded scope

Branch/main HEAD, origin/main and live remote main: `1a9e8c334d24b22be9688058a79378972b89377b` at entry and closeout. `git status --short --branch`, `git diff --name-status`, `git diff --stat`, `git rev-parse HEAD origin/main`, `git ls-remote origin refs/heads/main` and `git log e35847f..HEAD` ground the repository. The sole intervening commit since prior Registry reconciliation is CEP-031 integration-evidence documentation. Existing CEP-032 implementation is retained; this resumption modifies evidence/governance only. Prompt SHA-256 `a2f789dd2dc8821ed2e8a71914f9d95ea53ca7d52321d7b19635f560ce82db8a` matches the canonical manifest. No direct prerequisite; EXT-0004/GATE-03 activation remains closed and does not block the permitted build.

The current browser inventory exposes Chrome and the in-app browser. Existing authenticated development sessions at `http://127.0.0.1:8000` were used. No credential, permission, membership, policy activation or production changes were made. Prior focused 6/6 PASS, checks, migrations and 21-error BASELINE TEST DEBT attribution remain as recorded in `CEP-032_VALIDATION.txt`; they were not repeated.

## Observed verification

| Check | Actual result | Screenshot |
| --- | --- | --- |
| Authorized entry | Refreshed authenticated navigation exposes RFQ and Commercial workspace links | RFQ empty and Commercial desktop |
| Buyer empty state | Explicit Persian RFQ empty state and new-RFQ entry | `rfq-empty-desktop.jpg` |
| RFQ form | Required fields and Jalali-facing date controls render | `rfq-create-desktop.jpg` |
| Invalid input | Opening before closing returns explicit Persian form alert; corrected input creates a draft | `rfq-validation-error.jpg` |
| Real buyer detail | Draft identity, project, Jalali closing/opening times, source link, RFQ line/submit/cancel controls and quote/comparison/award sections render | `rfq-detail-desktop.jpg` |
| Source deep link | Opens the existing approved source request in the same tenant/project | `rfq-source-deeplink.jpg` |
| Commercial policy absence | Explicit warning states policy is not active and creation/transitions are stopped; empty register remains visible | `commercial-policy-closed-desktop.jpg` |
| RFQ mobile | At 390 × 844 the RTL content stacks; document width equals viewport width 390 | `rfq-detail-mobile.jpg` |
| Commercial mobile | At 390 × 844 the warning and empty state remain readable; document width equals viewport width 390 | `commercial-policy-closed-mobile.jpg` |
| Cross-tenant actual-object denial | Existing in-app-browser account selected another authorized tenant; the real RFQ URL returned 404 with generic Persian denial and no RFQ title, project, source or commercial data | `rfq-cross-tenant-denied.jpg` |

The 404 screenshot is the local Django DEBUG presentation, with route diagnostics, not a claimed production error-page review. Original in-app-browser tenant selection was restored and its temporary tab closed. Chrome viewport override was reset. Full cross-browser, formal accessibility and performance/concurrency remain UTV; the sampled responsive/browser checks above are verified only to their stated extent.

Local verification data: browser-created draft `CEP032-BROWSER-20261018`, RFQ public ID `fede8194-2a22-43c6-a047-0131347d04ef`, project `PRJ-01-01`, existing approved source `PRQ-01-01-01`. It remains a draft with no lines, issue, award, contract or financial effect. It is intentionally retained as reproducible evidence rather than deleted or finalized. Commercial activation was not enabled to create active-policy data; established isolated tests remain the lifecycle/history evidence.

## Finding 003 — missing buyer lifecycle actions

**Classification: BLOCKER-REPOSITORY. Affected: AC-01, AC-02, IMB-0022 target-outcome/workspace DoD.**

The authenticated detail shows quote/comparison/award sections but no buyer action forms or links for quote capture/submission, comparison preparation/evaluation/finalization or award preparation/finalization. These controls are absent from the implementation, rather than merely unavailable for the new empty draft:

- `apps/procurement/rfq_workspace.py` orchestrates RFQ create/line/submit/issue/close/cancel only; `_context` reads quote/comparison/award records.
- `apps/procurement/rfq_forms.py` defines RFQ create/line/issue/close/cancel inputs only.
- `apps/procurement/urls.py` exposes no buyer quote/comparison/award action routes. Existing portal/sealed-custody endpoints do not provide those buyer operations.
- `templates/procurement/rfq_detail.html` displays comparison/award metadata without action links or forms in any state.
- Existing domain commands include `quote_services.capture_quote_revision` / `submit_quote_revision` and `comparison_services.prepare_comparison` / `evaluate_comparison` / `finalize_comparison` / `prepare_sourcing_award` / `finalize_sourcing_award`.

Thus the canonical “Backend lifecycle is fully discoverable” target cannot be satisfied by the current read sections. No product fix was made because the current Human instruction limits this resumption to remaining verification. Safe follow-up is to expose the existing scoped operations with their current tenant, permission, workflow and separation controls, without introducing scoring/ranking/automatic award or expanding financial authority, then validate and capture the missing lifecycle states.

## AC and scoped DoD reassessment

Acceptance Mapping: **10 PASS, 2 PARTIAL / 12**. AC-01/02 retain the explicit implementation gap. AC-04/05 gain actual tenant-denial and empty/error screenshots alongside established permission tests; AC-06 gains Persian/RTL/Jalali observation; AC-07 is supported for the bounded non-production build, with activation still closed.

IMB-0022: target outcome and complete lifecycle surface **PARTIAL**; observed empty/error/denied states, independent backend authorization evidence, Persian/RTL/Jalali, sampled mobile layout and existing UI/security tests supported. Missing buyer-operation/SoD runtime checks remain unverified because those actions are unavailable.

IMB-0028: bounded build, persistence/history, exact governed transitions, invalid/policy-absent failure and negative-path tests retain established evidence. Browser confirms the required policy-absent failure presentation. No active-policy runtime, Human Sign-off or production activation is claimed.

Completion is not authorized by screenshots alone. Registry remains PARTIAL/BLOCKED with Finding 003; no conditional Git checkpoint or next CEP execution occurred. No canonical prompt, product code, fixture, schema or dependency-graph change was made in this verification resumption.

## Screenshot integrity

Files under `CEP-032_SCREENSHOTS/` are browser-produced JPEGs, not mockups. SHA-256 values follow.
- `commercial-policy-closed-desktop.jpg` — `a1bbd73f7c16b5b74e9d4903ebc75151bf6b1976cecae56d4931b57dbe8bdff9`
- `commercial-policy-closed-mobile.jpg` — `0330288f1b07acf1d84bed483df2039c09c01a0d527e6b37313ffd399853b2e8`
- `rfq-create-desktop.jpg` — `f047f8b70d48d3c844556b983f7327b7839573cff62128107591b27374a5c63a`
- `rfq-cross-tenant-denied.jpg` — `90201750337741d20a9d9d084794cca109644025654527af1aa2783623cc5abc`
- `rfq-detail-desktop.jpg` — `bdf1ed0a69e282d4e00d58fac8c559d8307ace4687889b3e50c0c866ab8f1db4`
- `rfq-detail-mobile.jpg` — `2a6fd4aabaa1208c1f8978f9ccf9ffb75a33267823e1853d667984aab7b15045`
- `rfq-empty-desktop.jpg` — `9205c49c1f7c0d849bb6e50ddfc2d64d41b70724ce34fb3ae945774b35b2d49a`
- `rfq-source-deeplink.jpg` — `3e746f774cff4f0d078427aa8e23bff927d592cc4afa89354ce6c87374bd9ed2`
- `rfq-validation-error.jpg` — `54936e2faca60093e98d1dc3c31d8917b946d692c0305d68e34908257c268bc2`


## Buyer-action remediation closeout — current result

The Human authorized in-scope implementation after the historical verification-only pass. Finding 003 is now resolved by the new buyer action controller/forms/templates over existing domain commands. Relevant Commercial ownership, seven-state lifecycle, submitted-history and migration contract remain unchanged.

Authenticated Chrome verification used normal login as two synthetic test actors on `localhost:8001`, backed by the existing disposable Django test database. The fixture prepared only defined RFQ/custody/opening/admissibility and current grants/policies for test data; it did not activate Commercial or change development policies. Comparison preparation, explicit evaluator assignment, recorded review, self-finalization denial and independent finalization succeeded through the UI. Award preparation allocated 5 of 10 units explicitly; self-finalization was denied and a separate actor finalized it. Both prepared predecessors and final records remained visible. A second issued RFQ demonstrated quote capture and submission. Final outcome selectors require an explicit choice. The action form and populated result workspace at 390 × 844 had document width 390. Temporary viewport overrides were reset.

`CEP-032_BUYER_BROWSER_RESULT.json` reconciles actual browser-created records and confirms zero downstream purchase orders, contracts, obligations, journals, cash movements and Project Cost facts. The fixture-only disposable test database was verified to contain only the two synthetic fixture tenants/six actors, then cleaned through Django after stopping the temporary server. The temporary browser tab was closed; existing development sessions/data/policies were preserved.

Validation: buyer-action and affected RFQ UI tests 10/10 PASS; final award-history projection recheck 1/1 PASS. The earlier 21 legacy Procurement failures remain BASELINE TEST DEBT and were not rerun or repaired. The final choice-placeholder/button-label presentation was verified after reloading the final server code. Existing Commercial/migration evidence remains applicable without repetition.

All 12 AC and both scoped IMB DoD are supported. No remaining in-scope blocker; full cross-browser/formal accessibility and performance/concurrency remain UTV under the canonical non-required applicability. Activation, Human Sign-off, Production Certification and Cutover remain absent.

### Additional screenshot integrity (11 new JPEGs)
- `buyer-action-form-mobile.jpg` — `cc573e2deac0333896feb50ca4130022e9ccdf7fa25ea508386509e0c9ff3d7c`
- `buyer-actions-desktop.jpg` — `3b5eba09334fe09fdfe43bd513701d2eb383bf026e6b1c6fc03c059458484a84`
- `buyer-award-final-history.jpg` — `0c5fe214fc0faf237185e7b6229ce4474bb54302572ebb0735821667e6ce03af`
- `buyer-award-final-mobile.jpg` — `b9bc7bf3ca1fcab4e87f73cb5079b72376e61c0eb42b1becfe3699c902ffa162`
- `buyer-award-preparation.jpg` — `6e9c952a19a1f4fc0ca2bc1cef45f38b01ef99da8b7dfc5b9c1a74d45fecc588`
- `buyer-award-sod-denied.jpg` — `eaf7ffd501ca55dab08cebbaf973ab1fc1d88d72b7151eed8bbb730204ab7775`
- `buyer-comparison-final-history.jpg` — `53f6d8cc5f673b01c4197a9285bfd27123c6aad241b6d173b3b70239350756b7`
- `buyer-comparison-input.jpg` — `0e8530f7aef5e2979624b77d14172b17661453c6600ecc79e873d1a656cf434c`
- `buyer-comparison-sod-denied.jpg` — `4ba9657da9368a0c30f1f25a416eba939112b4a294ef40138957b74c0ad49119`
- `buyer-explicit-outcome.jpg` — `e333e85cc11821c1222d6606bbe435ad63011fca1cbf870c8bad3ba511cbec2e`
- `buyer-quote-submitted.jpg` — `02903336eb1d001154fea52b31095a3d66547bdda6cf49021e89cdd08e429246`
