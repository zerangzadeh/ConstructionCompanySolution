# Contract Create — Reference Form verification

Date: 2026-11-01. Authorization: the user's bounded UI request in this chat.
This is ordinary presentation work, not CEP execution or production action.

## Grounding and scope

- Branch: `main`; starting HEAD and local `origin/main`:
  `5b760e853b329e2b03415da7b046641359db6a62`.
- The working tree already contained uncommitted List, Contract Detail, Project
  and supporting changes. Those are pre-existing work, not this task's output.
- Product touch set: `templates/contracts/create.html`, presentation attributes
  in `apps/contracts/forms.py`; new shared Create header, section header, footer
  and icon templates; opt-in shared token/Create CSS and summary-only JS.
- Documentation: additions to existing `docs/ui-guidelines.md` and
  `templates/components/README.md`, preserving their prior modifications.
- Verification: `apps/contracts/test_create_reference.py`, isolated test runner
  `scripts/verification/contract_create_validate.py`, this directory's evidence;
  optional viewport/bottom screenshot flags added to the existing CDP driver,
  preserving its pre-existing changes and default behavior.
- No models, migrations, domain/services, views, permission/scope/workflow,
  Product Surface or validation rules changed. All 12 existing fields retained.
- Existing qualified Tom Select, Jalali and Rial helpers are reused unchanged.
- Draft remains available through the existing status field. There is no new
  separate draft-save command or button.
- The reference pattern is documented for reuse after Product Owner visual
  acceptance. This task adopts it only on Contract Create.

## Reference

`reference.png` is an exact copy of the supplied image, not generated content.
SHA-256: `82727CA28D3DC97DC6403A62F648D41720F57DBFC915621375D56EBE8555A995`.
The image guides presentation; its depicted data and controls do not define
business behavior, fields or authorization.

## Verification environment

Python/Django and the configured PostgreSQL backend; all mutations/fixtures and
automated browser journeys use `test_bonira_contract_create_reference_20261101` exclusively.
Additional read-only layout/keyboard checks use the existing local development
page in the user's visible Chrome. No development business records or fixtures
are created/updated by these checks. The test
database is migrated through Django before tests; no schema files are authored.
Browser: installed Google Chrome via the existing repository CDP verification
driver, in an isolated temporary profile. Synthetic tenant/project/party only.

## Results

| Check | Result |
| --- | --- |
| Contract Create functional / affected scope regression | PASS — 20 tests and 6 subtests |
| Real Chrome | PASS — 1 browser test, 10 complete scenarios |
| Reference visual conformance | PASS — direct review of reference and three widths |
| Product Owner visual acceptance | PENDING |
| Django system check | PASS — no issues |
| Ruff lint / format | PASS — all 3 changed Python files |
| JavaScript syntax | PASS — Create enhancement and CDP driver |
| Changed tracked file whitespace | PASS |

Functional coverage includes valid creation/Detail redirect and persisted values
for all existing business inputs; required-field errors and accessible field
associations; invalid precision, dates, ordering and status; field retention;
both cancel contexts; foreign project/party POST rejection; canonical contextual
Create regressions including forged/foreign/ambiguous parents, explicit project
scope, active membership, permission revocation and lifecycle re-checks.

Chrome coverage: 1440×1086, 1024×900 and 390×900; required errors with real
default values retained; remote party search/keyboard selection; formatted
decimal Rial input; Jalali calendar open/selection/close; visible focus;
invalid amount/date order with retained values; real Create/Detail transition;
contextual cancel and general project-summary selection/cancel. ORM assertions
verify the browser-created contract's tenant, project, party, Decimal amount,
Gregorian stored date, direction, type, status and notes. All 10 recorded
responses are 200, with zero JS exceptions, zero HTTP asset errors (the existing
favicon is excluded by the driver), and no horizontal overflow.

Commands / evidence:

```text
.venv/Scripts/python.exe -u scripts/verification/contract_create_validate.py
  20 passed, 6 subtests passed; one browser assertion corrected below
.venv/Scripts/python.exe -u scripts/verification/contract_create_validate.py apps/contracts/test_create_reference.py::ContractCreateReferenceBrowserTests --reuse-db -q
  1 passed in 51.31s (final focused rerun)
.venv/Scripts/python.exe manage.py check
.venv/Scripts/ruff.exe check apps/contracts/forms.py apps/contracts/test_create_reference.py scripts/verification/contract_create_validate.py
.venv/Scripts/ruff.exe format --check apps/contracts/forms.py apps/contracts/test_create_reference.py scripts/verification/contract_create_validate.py
node --check apps/accounts/static/js/erp_create_form.js
node --check scripts/verification/mvp02_browser.mjs
git diff --check -- apps/contracts/forms.py templates/contracts/create.html docs/ui-guidelines.md templates/components/README.md scripts/verification/mvp02_browser.mjs
```

See [functional run](validation.log), [final browser run](browser-validation-final.log)
and `browser/batch-*.json`. The 20 functional tests passed in the combined run;
subsequent changes corrected only browser-test expectations/driver usage. No
business behavior changed after that functional PASS. The later presentation-only
wording correction is recorded below. A whole-repository regression
suite was not run for this bounded presentation change.

Verification iteration findings (test infrastructure issues, resolved): the
initial process loaded pre-polish test source while the new database migrated
for 31 minutes (18 PASS, 2 failed assertions/fixture). The fresh combined run
passed 20 tests; its browser expectation incorrectly counted prefilled draft/zero
defaults as missing. The actual required-error count is four, with those defaults
retained. The next browser iteration opened the calendar successfully but used
the driver's navigation-waiting click action for an in-page action; existing
non-navigation click support resolved this. The final focused browser run passes
every scenario. No business validation was changed to satisfy tests.

## Direct visual comparison

The exact supplied 1448×1086 reference and the saved 1440×1086 Chrome screenshot
were opened and compared directly, followed by the tablet and both mobile
viewport screenshots. No material unresolved layout, hierarchy, spacing or
field-composition difference remains within this form's authorized surface.

| Reference element | Implementation/evidence |
| --- | --- |
| Header on right, selected company/project summary on left | Same desktop composition; context moves below the title at tablet/mobile widths |
| Basic section: project + number, full-width title | Same placement and preserved contextual parent contract |
| Party section: party + direction, type + status | Same two-row grouping; qualified Tom Select retained |
| Inline amount section | Same heading/control composition and existing Rial helper |
| Three dates and a separate notes section | Same hierarchy; existing Jalali picker and unconstrained notes retained |
| Footer with clear primary/secondary actions | Existing Create and Cancel; no invented draft operation |
| Responsive composition | Two/three columns at 1440/1024; one column at 390; sticky actions visible without horizontal overflow |

Intentional adaptations preserve real BONIRA behavior: contextual project is
read-only instead of reselectable; existing empty dates remain empty; no fake
note-length limit/counter or unsupported draft action is added. Controls are
38px on desktop and 44px on mobile. Existing application shell, approved color
tokens, authenticated context and actual data replace the image's sample data
and decorative treatment. The form is not rolled out to other pages.

Screenshots:

- [Desktop 1440](browser/f61-owner-create-1440.png)
- [Tablet 1024 top](browser/f61-owner-create-1024.png) /
  [bottom](browser/f61-owner-create-1024-bottom.png)
- [Mobile 390 top](browser/f61-owner-create-390-viewport.png) /
  [bottom](browser/f61-owner-create-390-bottom.png) /
  [full-page composite](browser/f61-owner-create-390.png)

The full-page mobile composite captures the sticky footer at its initial
viewport position. Separate top/bottom screenshots show its actual accessible
position at each scroll boundary. Native Tab navigation from contract number
to title, the visible primary focus ring, and focus visibility above the footer
were also verified in the user's visible Chrome without changing form values.

CONTRACT CREATE FUNCTIONAL: PASS  
CONTRACT CREATE BROWSER: PASS  
REFERENCE VISUAL CONFORMANCE: PASS  
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

End HEAD remains `5b760e853b329e2b03415da7b046641359db6a62` on `main`.
Unrelated work, including changes made concurrently elsewhere in the working
tree, is preserved. The query-only Graphify timestamp generated by this session
was restored to its previously clean value. The existing local development
page is available for review; the temporary browser viewport was reset.

No Git staging, commit, push, branch/worktree creation or production action.

## Product Owner wording correction — 2026-11-01

Contract Create's `direction` dropdown now displays `سمت قرارداد`, with
`با کارفرما` for `receivable` and `با پیمانکار / تأمین‌کننده` for `payable`,
matching the existing Contracts List terminology. The section description also
uses `سمت`. Choice keys, requiredness, validation and business semantics remain
unchanged. Focused form-field verification (both labels and canonical clean
values), Django check, Ruff lint/format and whitespace checks PASS. Existing
screenshots above predate this wording-only correction; layout is unchanged.
