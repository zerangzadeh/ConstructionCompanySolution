# CEP-078 re-entry 02 completion report — 2026-10-23

**EXECUTION PARTIAL. Lifecycle: BLOCKED_AFTER_PARTIAL_VERIFICATION.**

Entry and EXT-0024 readiness passed under the approved Chrome + Edge scope. Actual
runtime verification then failed the required login landmark check. The defect is
the existing **UIUX-F-107**, recorded here as **CEP-078-FINDING-006**. Product
remediation is outside this verification authority. CEP-078 is not COMPLETE.

Environment: Development / Non-Production. Primary IMB: IMB-0108. Branch/start/end
HEAD: `main` / `43ac319c6e73e48ca9626461b73987922c498ec3`, with accepted dirty product
sources. Local `origin/main` is the same SHA; remote freshness not queried.

## Authority, readiness and exact identities

The [direct Human decision](../../supporting/CEP-078_V1_BROWSER_SCOPE_HUMAN_DECISION_20261023.md)
sets Google Chrome + Microsoft Edge as the V1/CEP-078 supported browsers. Safari is
excluded from entry, acceptance, DoD and remaining UTV; no compatibility,
certification or future Safari support is claimed. Historical source/blocked files
and the immutable prompt remain unchanged. The explicit decision governs this scope.

The Human subsequently installed the Edge extension. Provider inventory then exposed
Chrome **3** and Edge **4**, and both actual blank tabs were controlled and measured
at **1440×900, 1024×768 and 390×844** CSS viewports. The initial connector/native
helper failures remain in [RUNTIME_READINESS.json](RUNTIME_READINESS.json); resumed
proof is [READINESS_RESUMED.json](READINESS_RESUMED.json).

| Runtime | Full observed running build | Observation method |
| --- | --- | --- |
| Google Chrome | 155.0.8059.82 | Read-only OS executable and loaded runtime-module metadata; all 46 visible local candidate processes report this build. |
| Microsoft Edge | 155.0.4283.62 | Read-only OS executable and loaded runtime-module metadata; all 16 visible local candidate processes report this build. |
| OS/device | Windows NT 10.0.26200.0, x64 desktop host | Actual host observation; viewport classes are CSS emulation, not physical-device certification. |

[RUNNING_BROWSER_IDENTITIES.json](RUNNING_BROWSER_IDENTITIES.json) retains timestamped
process/module evidence. The connected providers do not expose PIDs: the provider
family-to-version binding is an explicit inference from uniform current builds
across every visible local candidate and the local provider identity. Installed-only
metadata is not substituted for running-module evidence.

The earlier `chrome://version/` navigation was rejected by browser protocol policy
(HTTP(S) only). That action was not retried or bypassed. The later identity method
reads local OS process metadata and does not load an internal page, drive UI outside
the browser API, use raw CDP, or transmit browser/private state.

All 1497 accepted product source hashes matched at entry. The pinned dirty application
and non-secret configuration identity from re-entry 01 remains valid (Django 5.2.17).
The 19/19 contribution, 42-case scoped GATE-07 proof was reused without duplicate
tests. Global activation readiness and GATE-08 remain unchanged/not passed.
Development DEBUG/loopback PostgreSQL and current schema were checked read-only.

[ENTRY_REVIEW.json](ENTRY_REVIEW.json) records **PASS**, and the Registry recorded
STARTED before application verification. [EXT0024_MATRIX.json](EXT0024_MATRIX.json)
retains both browsers, all 33 journey inputs, exact canonical persona/route/state
requirements, all three viewport classes and accessibility dimensions. No scope was
deleted after a failure.

## Actual required runtime outcome

The approved login scenario was entered directly in both browsers. Edge showed the
anonymous login surface. Chrome's existing authenticated session redirected login
to Home; its anonymous-login precondition was not met. That session was preserved;
no logout, identity change or forced session injection was used to obtain a result.

| Scenario / browser | Actual result |
| --- | --- |
| CEP-078-SC-001 / Edge, desktop 1440×900 | **FAIL**: two nested main landmarks. |
| Same / Edge, tablet 1024×768 | **FAIL**: same two nested main landmarks. |
| Same / Edge, mobile 390×844 | **FAIL**: same two nested main landmarks. |
| Same / Chrome, all three viewport observations | **UTV** for anonymous login: authenticated redirect; actual geometry observed, no anonymous-login PASS inferred. |

Expected: one document main landmark. Actual: outer `main#main-content` contains
inner `main[aria-labelledby=login-title]`. The actual DOM/AX tree and current source
agree: `templates/accounts/login.html:422` extends the shell whose main is at
`templates/base.html:715`. The existing finding register already records the same
failure as UIUX-F-107 / RV-EV-001 on 2026-10-21. This is a **pre-existing product
accessibility defect**, with a valid failed expectation; it is not a newly introduced
CEP regression or permission to waive a required result.

[RUNTIME_RESULTS.json](RUNTIME_RESULTS.json), [actual measurements](RUNTIME_OBSERVATIONS.json)
and native AX/captures retain the failure. Supporting Edge checks at all three sizes
passed: exact viewport, no page overflow, Persian/RTL, one H1, associated required
labels, skip-link Tab reachability, visible focus, and natural keyboard order.
Final corrected assertion totals: **24 PASS / 3 landmark FAIL** across three viewport
cases; the scenario's overall result is FAIL.

An initial harness expectation incorrectly skipped the visible forgot-password link
when expecting password immediately after username. Original observations are retained.
[KEYBOARD_CORRECTION.json](KEYBOARD_CORRECTION.json) proves the actual
username → forgot-password link → password sequence at all three sizes. Only the
harness expectation was corrected; no product or test source changed.

Observed page console errors: **0**, limited to the captured pages.
Desktop/tablet/mobile native images were inspected. Retained screenshots show empty
credential controls. Preliminary browser-autofill captures were replaced with native
empty-control captures after local UI clearing; no values were inspected/serialized,
no image was edited and no stored credential changed. [CAPTURE_PRIVACY.json](CAPTURE_PRIVACY.json).
Native captures are JPEG: desktop/tablet pixels match their measured CSS viewports;
the mobile image is 390×843 pixels while the independent DOM measurement is
390×844 CSS pixels. The native image is preserved verbatim; no pixel-height
equivalence or full-page capture is claimed. [CAPTURE_FORMAT.json](CAPTURE_FORMAT.json).

Jalali date interaction, tables, modals, other role/workspace scenarios and full
cross-browser anonymous behavior remain **UTV**, not N/A or PASS. The required-test
failure stops affected verification under the canonical fix-or-block rule. The other
32 journey inputs remain planned/UTV; they were not silently removed or certified.

## All six ACs and scoped DoD

| Criterion | Evidence / outcome |
| --- | --- |
| AC1: approved browser/accessibility/responsive target outcome | **FAIL** — required semantic login check fails; full cross-browser outcome unavailable. |
| AC2: exact scenario/environment/version | **PASS** — approved Human scope, full matrix, source/configuration identity, actual runtime binding and timestamps retained with limitations. |
| AC3: actual execution, not static inference | **PARTIAL** — real Edge scenario executed; Chrome precondition and remaining matrix remain UTV. |
| AC4: measured artifacts/timestamps/explicit results | **PASS** — actual DOM/AX, keyboard results, screenshots, logs and explicit FAIL/UTV retained. |
| AC5: failed scenario remains an open gap | **PASS** — Finding 006 remains OPEN; no feature completion or silent repair. |
| AC6: UTV remains until executed | **PASS** — Chrome anonymous login and unexecuted matrix remain UTV. |

**Acceptance: 4/6 PASS, 1 FAIL, 1 PARTIAL.** These are criterion results, not a claim
that most runtime coverage passed. [CEP-078_ACCEPTANCE_MAPPING.csv](CEP-078_ACCEPTANCE_MAPPING.csv)
maps each criterion and DoD to exact existing/new evidence and remaining gaps.

| Scoped DoD obligation | Result |
| --- | --- |
| Target outcome within approved scope | **FAIL** — required accessibility result failed. |
| Target environment/scenario documented | **PASS**. |
| Execution procedure prepared | **PASS** — exact observed steps, no-mutation boundary and failure stop retained. |
| Evidence/pass-fail format defined | **PASS**. |
| Actual required verification evidence produced | **PARTIAL** — actual bounded runtime evidence exists; required result and remaining coverage incomplete. |

Overall DoD: **NOT_MET_REQUIRED_ACCESSIBILITY_FAILURE_AND_REMAINING_UTV**.

## Findings, preservation and final reconciliation

- Finding 001: scoped GATE-07 convergence supported; reused source-valid proof.
- Finding 002 Safari component: resolved by explicit Human V1/CEP-078 decision.
- Findings 004/005 readiness: resolved after Edge connection and permitted running
  process/module identity evidence. Earlier failures/security rejection remain history.
- **Finding 006 / BLOCKER-TEST: OPEN** — existing UIUX-F-107 nested login main landmark.
  Separately authorized bounded product remediation and affected revalidation are
  required before retrying the failed scenario and remaining runtime coverage.

Accepted Wave D/E/RV-025/F-110/F-134/F-135 and positive portal results remain unchanged.
Original 18 baseline failures and separate statutory/Projects assertion debt remain
explicit. Prior successful RV results retain their identities; none was relabeled as
CEP runtime execution. The existing defect's baseline provenance does not authorize
closing this required failed verification as COMPLETE.

No application suite was rerun: no product source changed, source hashes preserve
prior regression applicability, and the actual required runtime result already fails.
Only affected evidence/preservation checks apply. [DATA_INTEGRITY.json](DATA_INTEGRITY.json)
compares **518 model aggregates: zero changes**, excluding normal sessions/last_login
as in the accepted helper. No business form was submitted. Temporary viewport
overrides were reset and created tabs closed; the user's authenticated session and
tabs were preserved. [BROWSER_CLEANUP.json](BROWSER_CLEANUP.json).

[CLOSEOUT_CHECK.json](CLOSEOUT_CHECK.json), [evidence manifest](CEP-078_EVIDENCE_MANIFEST.csv)
and [change manifest](CEP-078_CHANGE_MANIFEST.csv) retain exact integrity, 340 accepted
artifact / 1497 source preservation, other CEP/history, count/state, reference and
whitespace checks. Registry: PARTIAL / BLOCKED_AFTER_PARTIAL_VERIFICATION; valid entry
and Human scope retained; AC and DoD results synchronized; Finding 006 and remaining
UTV explicit. GATE-08 remains NOT_PASSED; no downstream readiness is issued.

Product/template/style/permission/business-rule/schema/configured business-data
changes: NONE. CEP-079, Production deployment/certification/cutover, Human Sign-off
and prohibited Git operations: NOT EXECUTED. New artifacts remain uncommitted.

The [computer-use skill](C:/Users/azera/.codex/plugins/cache/openai-bundled/computer-use/26.1016.62342/skills/computer-use/SKILL.md)
was used only for the initial native Edge readiness fallback; actual browser scenarios
used the connected browser API. No messages to other people were sent.

**STOP after this PARTIAL CEP-078 reconciliation.** No separate remediation, scope
waiver, Human Sign-off or Production acceptance is inferred.
