# Related Documents — Phase 1

**Status:** Implementation and focused automated validation complete; required
Chrome verification BLOCKED. Product Owner visual acceptance pending.

## Scope and result

The Project, Contract, Estimate, Expense and Daily Report Detail templates now
use one shared read-only «اسناد مرتبط» section and the same existing document
icon. Navigation follows each page's current structure:

| Page | Navigation placement | Section placement |
|---|---|---|
| Project | Existing project section navigation | After operational related records, before project information |
| Contract | Existing contract contextual navigation, including draft/quantities views | Full-width section following the contract workspace |
| Estimate | Compact contextual row beside the identity/related-record area | Between estimate information and items |
| Expense | Existing detail/action group | Before allocations |
| Daily Report | Existing report header/action area | After report details/observations, before supporting entries |

Project's photo entry is labelled «گالری تصاویر» separately. Each page has one
Related Documents navigation entry. The shared section displays title, type,
version, processing availability and authorized view/download actions. It shows
five rows initially and uses native disclosure for additional authorized rows.

The read adapter uses existing typed links and source-domain/DMS read services.
Legacy mirrors do not add rows. DMS Detail authorization is rechecked before a
document contributes metadata or a count. Download links resolve an exact clean
version through the existing secure service; rendering does not record a download.

Documents Detail now links back to the five supported persisted sources. Return
context is an allowlisted source type/UUID checked against actual authorized
links, never an arbitrary return URL. Estimate's project context is included only
when its Project read authority also permits it. Retired Payment evidence retains
a non-actionable Persian historical label.

No new upload/link/unlink controls, routes, domain relationships, schema,
permissions or financial/business transitions were introduced. Existing DMS
mutation forms remain unchanged. Hidden capabilities are not activated.

## Validation

- Django system checks: PASS.
- Affected templates: 10/10 compile.
- Ruff check and format validation: PASS.
- JavaScript syntax check: PASS.
- Focused authorization/read-only UI tests: 14/14 PASS. This includes actual
  Django responses for all five Detail pages, one navigation entry/section each,
  empty states, exact clean-version actions, all-context/project/site/tenant
  boundaries, compatibility parity, safe return context and no projection writes.
- Existing DMS service and form-scope regressions: 18/18 PASS.
- Combined final run: **32/32 PASS**, 39.293 seconds after isolated schema setup.
- Two additional existing processing tests fail in their unchanged `setUp` at
  `create_project`, before any changed presentation code or test body runs. The
  fixture creates only a legacy owner membership, without explicit role/scope
  grants. Classification: **BASELINE TEST DEBT**. The test, project/DMS services
  and authorization module were verified unchanged from HEAD; evidence is in
  `baseline-test-debt.json`. These tests were not edited or counted as PASS.
- Required Chrome screenshots and responsive/usability checks: blocked by the
  Work setting disabling local browser access. Re-enabling was requested; no
  browser-access bypass or substitute screenshot claim was made.

| Chrome page | 1440 px | 1024 px | 390 px |
|---|---|---|---|
| Project | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Contract | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Estimate | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Expense | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Daily Report | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |

The exact pre-change working-tree templates and SHA-256 baseline were saved in
`output/related-documents-phase1/baseline/` and `baseline.json`, with a source diff
in `implementation.diff`. These are **not screenshots**. The local preview helper
`serve_preview.py before` serves those original templates on port 8012; `after`
serves the current implementation on port 8011. This supports faithful before/after
Chrome capture once access is available, without reverting concurrent changes.
Neither preview server was started during the blocked browser verification.

Evidence: `output/related-documents-phase1/final-tests.txt`, `lint.txt` and
`baseline-test-debt.json`. `verification-tests.txt` retains the earlier run,
including test-helper/fixture errors corrected in the new tests before the final
run; no dependency was installed and no production authorization was weakened.
The tests use a dedicated test database, separate from the application's database.
No migrations were authored or run against the application database.

## Preservation and handoff

Baseline HEAD: `560bc3c9f136a3b76c6816dc127a80d74bcb7a1d`, branch `main`.
Existing uncommitted work was retained; the five business views and existing DMS
services/models were not edited. The pre-existing Project template changes were
extended only at the relevant navigation/section seams. No Tailwind rebuild,
dependency installation, migration files, commits or pushes.

The read projection deliberately retains canonical per-document authorization
calls. Large related-document sets therefore retain the existing DMS validator's
per-document query cost; no persistent authorization cache or weakened shortcut
was introduced. Existing unrelated DMS list/form technical labels are outside
this Phase 1 integration.

**Remaining:** Complete the 15 Chrome viewport checks, populated/empty and
permission-persona journeys, safe source roundtrips, exact-version downloads and
before/after screenshots; then obtain Product Owner visual acceptance. Visual
acceptance, Human Sign-off and production authorization have not been issued.
