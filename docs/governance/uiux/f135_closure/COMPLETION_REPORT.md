# F-135 / RV-025 closure — 2026-10-23

**F-135 PASS / RESOLVED. RV-025 PASS.**

**WAVE_E_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT** and **TARGETED_RUNTIME_VALIDATION_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT** remain unchanged. **UX_READY_FOR_UAT = NOT_ISSUED**. This closes the sole remaining RV-025 interaction failure using a targeted delta; it is not full WCAG certification, Human Sign-off or Production authority.

## Minimum repair

One guarded `keydown` listener in the existing Jalali script handles Escape only while its active picker is open. It hides the picker; focus on the date input or trigger stays there. If focus is inside calendar content, it moves to that field's existing calendar trigger, so it cannot remain hidden or reopen the picker through input-focus behavior. Existing trigger Enter behavior still reopens normally. Focus outside the picker is preserved. Escape on a closed picker is a no-op and non-Escape keys retain existing behavior.

The existing script reference changes only its cache-version query so the browser loads this repair. No CSS, calendar redesign, date conversion, parsing, masking, filter, submit/change/input handler, workflow, authorization, service, model or schema change. [Exact session delta](SOURCE_DELTA.diff) and [source proof](SOURCE_INTEGRITY.json) demonstrate that all existing script content outside the new listener is identical to entry, including prior F-110 names.

## Validation

**18/18 focused/affected tests PASS, with 3 additional date-field subtests PASS**: seven Jalali form/format cases plus eleven existing date/filter/name/localization cases. [JUnit](focused_affected.xml), [test output](focused_affected.txt). JavaScript syntax check, Django system check and changed-file whitespace check PASS. No full-suite PASS is claimed.

**22/22 authenticated keyboard cases PASS**, Projects and Quality at **1440×900** and **390×844** CSS viewports. Empty desktop and populated mobile date fields are observed. Escape closes from the input, trigger, month navigation and day buttons. Focus stays visible, returns from hidden picker content to the correct trigger, and Tab continues to the next boundary. Escape outside the picker does not steal focus; repeated Escape on a closed picker does not alter state; non-Escape caret input keeps the picker open. Populated `1404/01/01` values and query URLs are identical before/after. Persian RTL, LTR dates and viewport containment remain intact. [Keyboard assertions](KEYBOARD_TESTS.json), [captures](CAPTURES.json), [RV-EV-065](EVIDENCE_RECORDS.json).

Browser/runtime errors: **0**. Development Tailwind warnings remain explicit in [logs](BROWSER_LOGS.json). The full browser build is unavailable; the prior same-provider metadata limitation remains. Native provider JPEG dimensions may differ from the directly measured CSS viewport; original native images are retained without resizing. Temporary viewport overrides were reset and the temporary tab closed. No dates were selected or saved and no business form was submitted.

## Accepted evidence and debt

Accepted Wave D and completed Wave E evidence is preserved without replay. F-110, F-134 and positive authenticated external portal coverage retain PASS. RV-025 combines those accepted records (RV-EV-060's completed cells and RV-EV-061/062/063) with current RV-EV-065. The former F-135 failure RV-EV-064 remains historical. Tablet layout evidence is retained; the new shared handler has no breakpoint/CSS branch, with desktop/mobile direct interaction evidence supplying representative equivalence. [Coverage delta](COVERAGE_DELTA.json).

The **18 accepted baseline failures** remain unchanged debt. The separately evidenced inherited statutory-copy and Projects navigation assertions also remain explicit, unrepaired and not rerun. Other unrelated open findings remain outside this bounded repair. **Zero unresolved attributable or indeterminate regressions.** [Attribution](REGRESSION_ATTRIBUTION.json). One draft browser assertion compared animation-progress shadow values; the stable focus identity, picker visibility, date values and URL were unchanged, and the corrected assertion verifies those behavior contracts. JUnit includes the three successful subtests in its total of 21; this is 18 parent cases plus 3 subtests, not additional failures.

## Integrity and stop

[Entry](ENTRY.json), [source integrity](SOURCE_INTEGRITY.json) and [data integrity](DATA_INTEGRITY.json) prove preservation of unrelated dirty changes, all business/financial/authorization records, prior fixtures and expiry. **No business rows added, changed or deleted**; only normal sessions/last-login bookkeeping is excluded. Existing accounts use normal login with existing DPAPI credentials held only in memory. No credential, permission, membership or scope changes.

HEAD, Git index, CEP Registry and Roadmap remain unchanged. CEP-078/079, Production actions/certification/cutover/migration, Human Sign-off and Git writes: **NOT EXECUTED**. No Product Decision was required or inferred. **STOP after this F-135 / RV-025 reconciliation.**
