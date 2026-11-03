# BONIRA Excel / Print button unification

Date: 2026-11-03 (Asia/Tehran).

Implementation complete; requested browser validation is PARTIAL because the
browser tool became unavailable. Product Owner visual acceptance remains pending.

## Scope and result

All 20 existing template placements now use one shared output-action component:
14 Excel placements and 6 print placements, including the standalone print toolbar.
The complete placement inventory is in [template-results.json](template-results.json).

- Excel: `#168446`, `file-spreadsheet`, `خروجی اکسل`.
- Print: `#1764D8`, `printer`, `چاپ`.
- Both: height 36px, radius 8px, icon/text gap 8px, intrinsic content width.
- Icons reuse `components/form_icon.html`; no icon dependency was added.
- Shared CSS defines hover and keyboard focus. Disabled rendering removes the
  action URL/event hook and exposes `aria-disabled`; no disabled controls or new
  capabilities were added to product pages.
- Existing wrapping layouts and intrinsic button widths support small screens.
- Query parameters, pagination removal rules, help associations, return links and
  `data-*` action hooks are retained. `erp_print.js` is unchanged.
- No routes, views, services, permissions, business rules, migrations or schema
  were changed. The print document body and print-media rules are unchanged.

## Changed product/design files (11)

1. `templates/components/output_action.html` — new shared control.
2. `apps/accounts/static/css/erp_output_actions.css` — new shared, scoped action
   tokens and styles; no global brand-token changes.
3. `templates/components/form_icon.html` — two named icons in the existing SVG
   include, preserving all existing icons.
4. `templates/components/xlsx_action.html` — delegates to the shared control;
   retains existing scope description and URL filtering.
5. `templates/components/print_action.html` — delegates to the shared control;
   retains existing preview URL.
6. `templates/base.html` — loads the shared output stylesheet.
7. `templates/print/document.html` — uses the shared print button and stylesheet.
8. `apps/accounts/static/css/erp_print.css` — removes conflicting legacy print
   button styles; preserves return-link and document styles.
9. `apps/billing/templates/billing/claim_list.html` — replaces only its existing
   Excel link, preserving the scope-help association.
10. `apps/billing/templates/billing/claim_detail.html` — replaces only its existing
    Excel link, preserving detail pagination semantics and help association.
11. `design/BONIRA_UI_COLOR_SYSTEM.md` — documents the requested action-specific
    colors and sizes without changing the brand/status palette.

The two Billing templates already contained unrelated local edits. Those edits
were retained. Other pre-existing changes, including generated Tailwind CSS,
were not changed by this task. No Tailwind rebuild was needed.

## Validation

- `manage.py check`: PASS, no issues.
- `manage.py test tests.test_mvp05_xlsx.FoundationTests
  tests.test_mvp06_print.PrintFoundationTests --noinput --verbosity 1`:
  3/3 PASS; SimpleTestCase only, no database setup or migrations.
- `output/output-actions-ui/validate_templates.py`: 8/8 PASS, with database cursor
  access explicitly forbidden. Checks cover exact preserved query parameters,
  both Billing URL/help contracts, non-actionable disabled rendering, print
  button/return-link contract, and compilation of all 20 placements.
- Ruff check and format check of the evidence script: PASS after correction.
- `git diff --check` on changed tracked files: PASS.
- Changed templates/shared stylesheet checked for corrupted Persian text: PASS.

## Actual browser evidence and outstanding checks

The existing authenticated local Chrome session was used at
`http://127.0.0.1:8000`. The initial implementation was visually inspected on
Billing claim detail and the claim list was opened successfully with its new
Persian Excel label. On detail, DOM/computed-style inspection measured:

| Action | Background | Text | Height | Radius | Gap | Width |
| --- | --- | --- | --- | --- | --- | --- |
| Print | rgb(23,100,216) | white | 36px | 8px | 8px | 81.36px |
| Excel | rgb(22,132,70) | white | 36px | 8px | 8px | 130.26px |

Both SVG icons rendered; existing URLs and Excel help association were present.
The page screenshot was inspected in the tool output; no screenshot file was
saved before connectivity was lost.

Browser calls then began returning `Local browser use is disabled in Work
settings`. The user reported re-enabling browser use, but another attempt and a
fresh tool session still returned the same disabled status. No alternative
browser-control mechanism was used to bypass the setting.

Outstanding: final browser recheck after the icon-grid/scoped-token refinement;
mobile/tablet geometry and screenshots; keyboard focus/hover/disabled visual
states; actual Excel download and native print-dialog interaction; representative
browser checks of other domains. These are UTV, not PASS. No full browser or
end-to-end regression claim is made.

## Repository and execution boundary

- Explicit bounded authority: user's Excel/Print UI request; not CEP execution.
- Branch: `main`; HEAD `28a9896086faa50064bf6f8d53a66a4628657b22`, unchanged.
- At start, local HEAD and `origin/main` had zero ahead/behind divergence; existing
  dirty/untracked work was preserved.
- Git branch/worktree creation: NO.
- Migration creation/execution: NOT EXECUTED.
- `git add`, `git commit`, `git push`, `git merge`: NOT EXECUTED.
- No Registry, Roadmap, authorization or production state changes.

Evidence files: this report, `validate_templates.py`, `template-results.json`.
