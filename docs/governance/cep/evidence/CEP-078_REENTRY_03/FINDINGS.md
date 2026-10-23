# Current CEP-078 remediation findings

- **006 / UIUX-F-107**: pre-existing redundant login main landmark. Explicit Human
  bounded technical remediation authority applies. Replace inner main with div only;
  retain outer main, layout, form and login behavior. Existing 9 authentication tests
  PASS. Actual Chrome and Edge landmark checks PASS at all three required viewports.
  Original failure history remains untouched. Full login result includes separately
  retained focus-probe correction (actual visible blue border/ring, not outline-only).
- **007 / mobile navigation logout parity**: actual Chrome mobile drawer and source
  show desktop POST logout form has no mobile equivalent. Responsive navigation parity
  is already required by SC-004 and UI guidelines. Minimal shared-shell addition:
  duplicate the existing POST logout action with CSRF inside mobile navigation panel,
  using existing button classes. No auth endpoint, permission, state or business change.
  Direct affected authentication/navigation tests and browser revalidation required.
  Initial screenshot/DOM observation retained through current browser evidence; role
  switch harness timeouts were caused by assuming desktop-only logout was visible.

Probe diagnostics remain distinct from product defects. Initial clientWidth/viewport
assertion ignored normal vertical scrollbar width; corrected probe uses actual
window.innerWidth and keeps clientWidth for overflow. Original diagnostics retained.

- **008 / portal long terms overflow**: new synthetic positive grant reproduces page
  overflow in both browsers at390px (document456/client375). Add existing Tailwind
  break-words utility to the terms paragraph only. Required values/terms unchanged.
  Both browsers then PASS all three sizes; receipt also PASS. Portal payload9 tests
  PASS; initial incorrect presentation-test selector retained, corrected suite passes.
- **009 / stale planning route**: /expenses/new/ returns404; current named
  expenses:create is /expenses/create/. Resolve actual route from repository URL
  authority; no product route/redirect change. Original404 observations retained.
- **010 / Subledger rendered form semantics**: positive accountant workbench has
  two unlabelled reversal date controls and duplicate amount-currency-unit ID from
  repeated amount fields with no IDs. Add stable unique presentation IDs to the two
  amount controls and label/id to each reversal date. No posted names, amounts,
  monetary parser, validation or settlement services change.8 focused/affected tests
  PASS; actual Chrome/Edge all-three-size workbench checks PASS.
- **011 / existing UIUX-F-109 effective-role presentation**: current SC056 AX repeats
  legacy Reporting Test label as primary role despite ACTOR_READINESS showing no
  effective role/scope. This is the existing confirmed no-business-logic finding,
  directly relevant to SC033 persona readiness. Intended bounded touch set before
  mutation: organizations member-list view/template only, using existing public
  membership_has_role/scope selectors with prefetched data for presentation; explicitly
  label compatibility value. No authorization rule, role definition, stored value,
  sorting key or enforcement change. Focused view/isolation checks plus both browsers
  at required sizes before closure.
- **012 / mobile navigation Escape focus return**: both browsers actually close
  the drawer but move focus to BODY after Escape from its close button. SC004 and
  UI guidelines49 require predictable focus recovery. Add summary.focus() to the
  existing close handler only; same close state/links/actions, no navigation redesign.
  Direct both-browser keyboard revalidation is required before resolution.
- **013 / existing UIUX-F-085 sort-state semantics**: actual Projects DOM has
  aria-sort on each anchor and none on column headers, reproducing the known
  accessibility defect. Scoped touch set: shared table_sort_header component removes
  unsupported link aria-sort; existing shell enhances active sort column header from
  the existing data-sort-state value. Same URL/whitelist/order/query unchanged.
  Existing focused state/query tests apply unchanged; no assertion suppression.
  Actual both-browser sorted-column/keyboard checks must prove final header
  semantics. No sorting/business/permission logic changes.

- **014 / case-detail nested main**: actual new canonical case reveals nested main in
  both browsers at all sizes. Minimal reporting/project_closeout_detail.html main
  wrapper becomes section; shared main/layout/commands unchanged. Both browsers
  revalidated single main at all3 sizes PASS. Template compilation and Django checks
  supplement actual runtime; no artifact-writing legacy reporting suite rerun.
- **015 / static Projects sorting footer**: actual code-sorted page2 falsely says
  sorted by project name. Remove the incorrect static phrase and clarify the number
  is the current page count. Existing header now carries actual sort semantics; no
  query, ordering, pagination or stored project change. Browser sort/page2 tests prove
  resulting state.
- **016 / populated Billing claim material source gap**: no ProgressClaim, no approved
  ContractTermVersion and no receivable-claim-regulatory version. Existing4 approved
  baselines do not supply commercial/regulatory authority. Required populated detail
  remains UTV; no invented statutory values/approvals, financial records or risk waiver.
  Human source/decision request is pending while independent verification continues.
- **017 / external associated filter events**: actual select changes to planning,
  URL remains unfiltered. Controls live in a table outside their associated form;
  input/change events do not bubble through that form. Existing automatic apply
  requirement is explicit in shared script/pattern. Minimal erp_table.js remediation:
  document-delegated listeners resolve event.target.form for already-bound GET forms.
  Preserve the same controls, debounce, query whitelist, clear and sorting contracts;
  no POST/business form auto-submission. Focused shared tests and real both-browser
  filtering/sorting/pagination/clear proof required.
