# Billing Journey navigation — current working tree, 2026-11-01

## Outcome and reproduction limits

The reported Claims List → Baseline-tab → Claim Detail transition was **not
reproduced**, including the real Chrome check performed before product edits.
Its root cause remains unconfirmed; this report does not claim to have fixed an
unobserved redirect. Current local templates, URLconf, claim list/detail contexts,
baseline contextual resolver, shared filter JavaScript and baseline views were
inspected, including uncommitted/untracked local work.

Before-edit observed click:
- Before: http://localhost:64008/billing/claims/?contract=91248f23-db6c-4273-9700-11936c71455e
- Clicked/hit-tested href: http://localhost:64008/billing/baselines/?contract=91248f23-db6c-4273-9700-11936c71455e
- After: http://localhost:64008/billing/baselines/ddaed0ab-1451-47a1-b13b-842ac5c5c711/

Evidence: browser-before/batch-before-single-baseline.json; before-validation.txt
(1 test PASS). This reached Baseline Detail, not Claim Detail.

A separate confirmed navigation defect was fixed: Baseline Versions and Baseline
Empty pages omitted the journey navigation entirely, preventing the return
journey. They now include the shared tabs using resolved selected_contract.pk.
The third tab is labelled کارکرد و پیشرفت as requested. Stable data-journey-tab
markers identify all three links for destination and active-tab regression tests.

## Product changes and preserved behavior

Only two product templates changed in this request:
- apps/billing/templates/billing/journey_nav.html: tab identity markers and third
  tab label. Existing named routes and business-permission checks retained.
- apps/billing/templates/billing/baseline_list.html: shared journey navigation
  added for global, versions and empty states, with resolved contract context.

No new product navigation helper or client-side interception was introduced.
Claim List/Detail URLs already use the proper named collection routes. Baseline
Detail derives journey contract context from baseline.contract_id; Claim Detail
uses claim.contract_id. The baseline list resolver already selects only the
existing authorized queryset and directs a single approved baseline to its own
Detail; multiple versions remain in the scoped list, zero versions display its
scoped empty state. This logic was retained and tested. Billing views are
byte-identical to this request's initial views-before.py snapshot.

No Domain, Model, Migration, calculations, workflows, permissions, tenant/project
scope, Product Surface or financial-authority changes. Development data untouched.
Existing unrelated local work preserved. Branch main; HEAD 5b760e85; upstream 0/0.
No staging, commit, push, merge or branch/worktree creation.

## Validation and actual URLs

[Actual URLs for every click](ACTUAL_URLS.md) lists all 48 observed before/href/after
URLs. Underlying JSON is in browser/batch-*.json and per-scenario *-clicks.json.
All 48 hit-tested anchors matched their intended tab href. No click entered a
Claim Detail. All 16 scenarios had zero page/asset HTTP errors and JS exceptions
(legacy favicon excluded by the existing driver).

Coverage:
- Global and contract-scoped three-tab cycles, desktop and mobile.
- Zero baselines: scoped Baseline empty page, same contract retained.
- One approved baseline: Baseline Detail; all return tabs use that baseline's
  contract despite the Detail URL not needing a contract query parameter.
- Multiple versions: scoped Baseline Versions page; same contract retained.
- Entry from Claim Detail in both single/multiple baseline cases.
- Restricted project reader in scoped desktop and global mobile modes.
- Server tests verify independent tab permissions, denied direct routes and a
  baseline-only reader without contracts.view using the existing authorized-row
  fallback.

Commands:
- .venv/Scripts/python.exe scripts/verification/claim_list_validate.py apps/billing/test_journey_navigation.py apps/billing/test_baseline_list.py::BaselineListTests apps/billing/test_mvp03.py --reuse-db -q
  → 22 server tests PASS; browser test initially failed on an offscreen mobile
  third tab. See validation.txt.
- The existing Chrome driver was corrected to scroll horizontally clipped
  controls into view before physical clicks, and gained opt-in exact URL/hit
  tracing. Existing local driver changes were preserved.
- .venv/Scripts/python.exe scripts/verification/claim_list_validate.py apps/billing/test_journey_navigation.py::BillingJourneyNavigationBrowserTests --reuse-db -q
  → 1 browser test PASS, 16 scenarios / 48 real mouse clicks. See
  browser-validation.txt. Real installed Chrome executable, headless CDP;
  isolated PostgreSQL test_bonira_claim_list_clone_20261101 only.
- Ruff check/format for new test, node --check for driver, Django system check and
  git diff --check for touched tracked files: PASS.

JOURNEY NAVIGATION: PASS
CONTRACT CONTEXT: PASS
BROWSER VALIDATION: PASS
REPORTED CLAIM-DETAIL TRANSITION: NOT REPRODUCED (root cause unconfirmed)
