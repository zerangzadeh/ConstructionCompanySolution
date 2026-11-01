# Contract Detail — State-Aware UX Remediation, 2026-11-01

User authority: targeted state-aware UX on the existing Contract Detail, preserving current visual direction and all business/permission/tenant/workflow/product-surface boundaries. This is an ordinary bounded request, not serial CEP execution. Branch `main`; observed HEAD and origin/main: `5b760e853b329e2b03415da7b046641359db6a62`. Initial dirty tree recorded in `initial-status.txt`, `initial-diff.txt`, `initial-stat.txt`. No Git writes, new branch/worktree, production action or deployment.

## Delivered behavior

- Draft uses preparation cards (amount, item count, applicable term configuration and descriptive review readiness), a real information/items/terms/review journey and authorized primary CTA `ویرایش قرارداد`. No operational claim/baseline/chart placeholders are rendered. The readiness wording does not grant approval, assert an execution gate or change lifecycle state.
- The existing Contract Detail POST endpoint is an adapter to registered services: `update_draft_contract` for authorized base edits, `add_contract_item` for draft item additions, and `create_contract_term_version` for new draft term versions. Existing draft insurance-classification editing is retained. Service-supported fields only are exposed; project, number, dates and status are not silently made editable.
- **Editability scope is explicit:** the current domain has no item-update/delete service or general in-place term-update service. This task does not infer `contract_items.add` as item-change/delete permission. Existing rows remain readable; draft rows can be added. General term changes use a new draft version; draft insurance classification uses its existing selection service. No new generic item/term mutation authority was invented.
- Active/Completed/Terminated have no direct base/item editors. Applicable active receivable baseline/progress/claim paths and payable subcontract certificate/measurement projections remain. Completed/terminated preserve history; no activation/approval action was invented. Active/completed terms may use an authorized new draft version, preserving approved history; terminated displays historical terms without a new term CTA.
- Supplier and other unsupported payable types show contract facts/items/available estimates and record-backed history, without subcontract/receivable charts, claims, progress or term preparation. Supplier has one explanatory note, aligned with the confirmed current rule, rather than multiple generic unavailable widgets.
- Source-specific permissions still gate every projection. Denied-source charts/tables are hidden, not represented as zero. Existing meaningful zero-data displays remain for supported authorized operational states. Unavailable physical rollups do not become fabricated percentages.
- Existing permissioned commercial review remains available, including read-only review from a draft. An initial regression caught accidental hiding of this link and it was restored with its original surface/permission conditions.

## Mutation safety

HTTP mutation forms require the existing individual permissions (`contracts.change`, `contract_items.add`, `contract_terms.manage`), active organization and scoped contract resolution. Service permissions remain authoritative. Before mutation, the already-resolved tenant contract row is locked; the unchanged authenticated selector is re-run inside the transaction and current state/type is rechecked. This avoids PostgreSQL's prohibition on `FOR UPDATE` with a DISTINCT scoped selector and preserves fail-closed object scope. Tenant-scoped party and active-unit form querysets reject foreign references; domain validation is retained. CSRF and POST method controls are tested. No domain services were edited.

## Touch set

- `apps/contracts/views.py`: Contract Detail integration only, plus method decorator import. Other pre-existing view changes are preserved.
- New `apps/contracts/detail_workspace.py` and `detail_forms.py`: presentation state and existing-service form adapters.
- `apps/contracts/detail_dashboard.py`: missing currency labels no longer render Python None; existing calculations and source contracts are preserved.
- `templates/contracts/detail.html` plus `detail_readiness.html`, `detail_base_editor.html`, `detail_item_editor.html`, `detail_terms.html` and appended state-specific rules in `apps/contracts/static/contracts/detail.css`.
- New `apps/contracts/test_state_workspace.py`; prior detail tests updated only for intentional state-aware projections/labels.
- This evidence directory. No models/migrations, domain service semantics, permission catalogs/default grants, tenant/project scope definitions, workflow or centralized Product Surface changes. No application seed/business records were changed; mutation fixtures are isolated in the dedicated PostgreSQL test DB.

## Supplier investigation

See [SUPPLIER_TERMS_INVESTIGATION.md](SUPPLIER_TERMS_INVESTIGATION.md). Current ContractTermVersion payable-subcontract-only scope is explicit in accepted architecture/closeout evidence and enforced by service/model; it is a **CONFIRMED RULE**, not a newly inferred permanent supplier prohibition. A future supplier-domain extension needs separate Product Owner decision and bounded implementation authority.

## Validation attribution

- Initial new fixture failed due to a helper method name colliding with a fixture's `self.url` string; renamed. Another fixture lacked authoritative OrganizationSettings; explicit test settings were supplied. These were test setup failures, not removed safety checks.
- The retained regression run had 32 PASS and one genuine regression: hiding the existing permitted draft commercial-review link. The link was restored; the full 4-test review-navigation module then passed on targeted recheck.
- An independent project-scoped write test exposed the real `FOR UPDATE`/DISTINCT adapter defect. It was corrected with row locking followed by the unchanged scoped selector check, not by widening scope.
- Final state functional suite: **9 PASS + 10 subtests PASS** (`final-functional-tests.txt`), covering state matrix, service-backed draft writes, immutable prior/approved term history, draft classification edit, individual permissions, finalized denied mutations, tenant-unit tamper, invalid money, CSRF, unknown activation action, and state recheck after form validation.
- Retained detail/payable/MVP journey regression: 32 PASS in `regression-tests.txt`; the corrected review module adds the originally failing case to the supported final result (`final-state-tests.txt`: 13 PASS including all 4 review tests; its sole failure was the subsequently corrected project-scoped lock case). No unrelated full suite claimed.
- Final installed Chrome: **1 browser test PASS, 22/22 scenarios PASS** in `final-browser-tests.txt` and `browser-summary.json`: 16 state/resolution checks (draft/active receivable, draft/active payable subcontract, draft/active supplier, completed subcontract, terminated receivable, each at 1440/390), 3 real form submissions (base, item, term), 2 restricted read-only checks, and a project-scoped base editor saving from 390px without gaining item/term write controls. Screenshots were directly inspected. Page status 200, no JS exceptions, no business-page or asset HTTP errors, and no document horizontal overflow. The existing shared-shell favicon 404 is filtered by the inherited browser harness; it is unrelated baseline shell behavior, not a business-page 404/500.
- All 22 screenshots/results reflect the final product implementation. Screenshot test fixture names are synthetic; no production claims or amounts are inferred.
- Ruff checks/format on new helpers, affected dashboard/tests and changed view imports: PASS. Django system check: PASS. Scoped Git whitespace: PASS. No schema/migration changes require a new migration.

## Visual and functional evidence

Screenshots preserve the current card, header, typography, spacing and RTL language. Draft replaces operational density with preparation information; active financial areas retain the established two-chart direction. Mobile forms stack within the current cards. Supplier and restricted views contain only relevant authorized content.

- [Draft receivable desktop](browser/f61-owner-draft-receivable-1440.png)
- [Draft subcontract mobile](browser/f61-owner-draft-subcontract-390.png)
- [Active receivable desktop](browser/f61-owner-active-receivable-1440.png)
- [Active supplier desktop](browser/f61-owner-active-supplier-1440.png)
- [Completed subcontract](browser/f61-owner-completed-subcontract-1440.png)
- [Terminated receivable](browser/f61-owner-terminated-receivable-1440.png)
- [Base form saved in Chrome](browser/f61-owner-draft-edit-submit-desktop.png)
- [Draft term saved in Chrome](browser/f61-owner-draft-term-submit-mobile.png)
- [Restricted mobile](browser/contract-reader-restricted-390.png)

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

## Final outcome

STATE-AWARE UX: PASS
DRAFT EDITABILITY: PASS (within the existing service operations documented above)
FINALIZED CONTRACT PROTECTION: PASS
SUPPLIER CONTRACT TERMS: CONFIRMED RULE
BROWSER VALIDATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

Git add/commit/push/merge: NOT EXECUTED. No Human visual acceptance, production sign-off or certification is inferred.
