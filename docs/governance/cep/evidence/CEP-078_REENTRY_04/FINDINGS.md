# CEP-078 resumed technical findings

Prior findings/results remain byte-preserved in REENTRY_03. Finding018 is resolved
by actual Chrome and Edge control in BROWSER_CONTROL.json; no product FAIL attaches
to that tooling interruption. Finding017 final table runtime now passes both
browsers at all three approved sizes in RUNTIME_RESULTS.json.

- **019 / existing UIUX-F-055 and UIUX-F-057**: selecting a Daily Reports project
  leaves sites for other projects available; Equipment Assignment renders the same
  independent Project/Site choices. Existing recommendations explicitly require
  presentation cascade while retaining server validation. Bounded touch set before
  repair: core/forms.py adds option parent metadata to already scoped choices;
  DailyReportForm and EquipmentAssignmentForm opt in; erp_context.js filters only
  those rendered choices. No queryset, clean(), endpoint, permission or grant change.
  Test existing selector/isolation contracts and actual both-browser dependent,
  empty and stale-child states. No domain form submission in browser.
- **020 / Jalali month navigation**: actual Chrome and Edge Enter on month-next
  changes the month, then closes the picker and loses focus. Re-render detaches
  the event target before the outside-click handler tests its ancestors. Bounded
  touch set: erp_jalali.js uses the original composed event path for inside clicks
  and restores the corresponding month navigation control after re-render. No
  date conversion, validation, calendar arithmetic or submitted value changes.
  Actual required keyboard checks rerun at all three sizes in both browsers.

Technical remediation authority is the explicit continuing Human request and prior
bounded authority recorded in REENTRY_03/AUTHORITY_AND_FIXTURE_DISPOSITION.md.
Billing Finding016 remains a source/regulatory decision gap outside this repair.

- **021 / stale CEP003 test assertion**: focused run 41 PASS / 1 FAIL. The failed
  assertion explicitly requires the nested login main removed by accepted F107
  remediation. Change only that presentation expectation to the approved inner div,
  add absence of inner main and presence of shared main assertions. Original output
  retained in FOCUSED_TESTS.txt; final rerun recorded separately. No product rollback
  or weakened accessibility requirement.

- **022 / SC033 residual variant precondition**: both actual browser sessions,
  signed in as the existing explicit Platform Admin, redirect the planned Django
  user-list route to staff login and state that this account lacks access. Platform
  Admin is not Django staff. The planning claim of existing staff authority was
  incorrect. This is BLOCKER-DATA / authorization-fixture precondition UTV, not a
  failed persona catalogue or permission bypass. No new staff grant, impersonation
  or product UI is authorized/invented. Existing members/effective-role evidence
  remains valid for its actual scope; a governed all-persona catalogue is not proved.
  The admin login's observed nested landmarks are an adjacent observation outside
  the qualified scenario; no unrelated Admin redesign is absorbed.
- **023 / transient DOM diagnostic**: one Edge employee/tablet snapshot contains
  duplicate PING_CONTENT_PUSH_NOTIFICATION, the same identifier in two historical
  Edge denial-page diagnostics. No product source contains that identifier. Direct
  re-observation and the affected cell recheck show no such nodes and PASS without
  product changes. Probable browser injection is an inference; exact injecting
  component is not proved. Preserve the original FAIL and classify the intermittent
  diagnostic separately from attributable product defects. Captured Chrome console
  errors explicitly originate in chrome-extension URLs (two); Edge has none.

The old portal receipt in row067 belongs to an unavailable historical fixture; its
original 404/FAIL records and Edge unexecuted cells remain historical UTV. The new
canonical positive grant/receipt was actually verified separately in rows068/069;
those distinct IDs and timestamps are retained, never relabeled as row067 PASS.

REENTRY03/DATA_INTEGRITY.json retains unresolved aggregate attribution for audit
events and a document-number sequence from prior fixture preparation. This session
does not retrospectively resolve that evidence. Its exact before/after comparison
independently proves only one synthetic role, two synthetic scopes and three new
audits changed. The prior attribution limitation remains explicit.
