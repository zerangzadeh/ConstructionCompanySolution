# Wave E targeted closure — 2026-10-23

**WAVE_E_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT**. **TARGETED_RUNTIME_VALIDATION_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT**.

All three requested closures PASS: F-110 accessible names, F-134 static company label and positive authenticated external portal coverage. RV-025 is fully executed for its targeted representative coverage, but retains **FAIL_ACCESSIBILITY** for independently observed inherited **F-135**, calendar Escape dismissal. Completion means supported evidence and explicit debt, not an all-accessibility PASS or risk acceptance. **UX_READY_FOR_UAT = NOT_ISSUED**.

| Target | Result and evidence |
|---|---|
| F-110 | PASS — RV-EV-061; four Projects/two Quality Persian boundary labels with matching distinct calendar action names; unchanged names, values and filters |
| F-134 | PASS — RV-EV-062; static `Tenant` filter label becomes `شرکت`; stored names/codes/values and authorization unchanged |
| P-26 positive portal | PASS — RV-EV-063; same external identity, fresh service-created/accepted invitation, exact issued RFQ version; zero memberships |
| Inherited F-135 | FAIL_ACCESSIBILITY — RV-EV-064; Escape leaves the auto-open calendar visible; independently recorded without remediation |

## Scope and implementation

The shared filter row associates separate Persian labels with each from/to input. The Jalali trigger derives its accessible name from the associated field label. A version query on the existing script reference refreshes the previously cached script; live generic names persisted until that cache refresh. No date parsing, filtering, input values, events or picker lifecycle changed. The Platform catalogue changes only one literal presentation label. English stored role display names remain as observed and outside the static-label closure.

The invitation manager `uiux.wavec.portal` uses its existing effective permission; neither Buyer nor Owner was assumed to hold it. `create_supplier_portal_invitation` → `accept_supplier_portal_invitation` → `get_supplier_portal_rfq_context` creates and verifies the test context. The one-time token exists only in memory and is discarded. No delivery message is sent. The fresh invitation expires normally at **2026-10-23 18:58:32 Asia/Tehran**, before the unchanged RFQ deadline; capture-time evidence does not extend its validity. The old accepted invitation/grant remains unchanged and denied after expiry. No membership, account, privilege, RFQ, quote, financial or source record is modified.

## Validation and retained debt

Focused: **11/11 PASS**, with three date-field subtests. Affected regression: **14/15 PASS**, one inherited Projects assertion for the absent `/projects/sites/` link. [Entry-template probe](BASELINE_PROBE.json) reproduces the identical failure with immutable HEAD versions of all three changed templates supplied in memory; these files were clean at entry. Its preceding positive/negative tenant assertions pass. No repository files or Git state were restored. **Zero unresolved attributable or indeterminate regressions**. [Attribution](REGRESSION_ATTRIBUTION.json), [affected JUnit](affected.xml), [focused JUnit](focused_final.xml).

The original **18 accepted baseline failures** remain unchanged debt; no unrelated suite was rerun or reclassified. The prior separately recorded statutory-copy assertion remains separate. The newly exposed inherited Projects navigation assertion and baseline UI keyboard finding F-135 are also separate; none is hidden in the 18. No full-suite PASS is claimed. Ruff check/format of the new presentation test and Django system check PASS. Development migration guard PASS; no migration created or executed.

Authenticated HTTP: **16/16 PASS**, normal login/cookies/CSRF. Positive scoped context, old expiry, wrong internal principal, foreign opportunity identifier, manipulated unauthorized submission, tenant/Platform boundaries and actual Jalali inclusion/exclusion are verified. The denied POST creates no submission. [HTTP controls](HTTP_CONTROLS.json).

Browser: **1440×900, 1024×768, 390×844** for all four affected surfaces. Positive portal context, required upload/reference labels, keyboard-reachable submit action and visible focus are directly observed without uploading/posting a quote. Projects/Quality have distinct field/calendar names and keyboard focus; tables scroll inside their containers, with Persian RTL and LTR dates/identifiers. No horizontal page overflow or unexpected browser errors. Tailwind Development warnings remain explicit. The browser reports the requested CSS viewport sizes directly; native provider JPEGs have smaller bitmap dimensions on some captures (including scrollbar-bearing pages), recorded individually in CLOSEOUT_VALIDATION.json. No image is resized and no exact-bitmap-size claim is made. The full browser build is not exposed; prior same-provider reduced version metadata is retained with that limitation. [Browser captures](BROWSER_CAPTURES.json), [interactions](INTERACTIONS.json), [logs](BROWSER_LOGS.json).

F-135 is inherited: the entry script has no Escape-dismissal handler, and the only script behavior diff is the trigger name. The observed popover remains visible after Escape; no full WCAG or screen-reader certification is claimed. This item is recorded, not silently absorbed into the two presentation repairs. It prevents an RV-025 accessibility PASS, but creates no missing positive coverage cell or indeterminate regression. Runtime Playbook §12 permits evidence-backed failure dispositions at closure.

## Coverage and preservation

Accepted Wave D remains **WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT**, unchanged and not reexecuted. Accepted completed Wave E surfaces/interactions remain preserved; only Projects, Quality, Platform label and positive portal receive this delta. [Coverage reconciliation](COVERAGE_RECONCILIATION.json) combines the retained evidence with direct current evidence. The earlier expired portal denial is never promoted into positive evidence. Inventory/Quality reader perspectives still do not certify specialist write authority; current representative states do not certify all routes/lifecycles or all 26 personas on every surface. No material positive portal cell remains blocked.

[Entry](ENTRY.json), [source integrity](SOURCE_INTEGRITY.json) and [data integrity](DATA_INTEGRITY.json) preserve existing dirty changes and historical evidence. Database additions are exactly one invitation, one grant and two canonical audit events; existing rows, authorization, financial sources and the expired grant are unchanged. Session/last-login bookkeeping is excluded explicitly. All retained identities remain active as before. HEAD/index, CEP Registry and Roadmap remain unchanged.

CEP-078/079, Production actions/certification, Human Sign-off and Git writes: **NOT EXECUTED**. No Product Decision is requested or inferred. **STOP after this reconciliation.**
