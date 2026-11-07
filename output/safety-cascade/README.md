# Safety create cascading choices — 2026-11-05

Authorization: explicit user request for cascading filtering on `/safety/create/`.
This is a bounded UI task, not CEP execution or production authorization.

Repository grounding: local `main`, HEAD `59f2fde6` (`inventory`), tracking
`origin/main`, ahead/behind `0/0`. The tree already contained substantial unrelated
work, including the sectioned safety template; that work was preserved. No Git
branch/worktree, staging, commit, push, or merge was performed.

Actual product touch set:

- `apps/safety/forms.py`: metadata on already tenant/object-scoped options,
  Persian dependency hints, and eager loading of phase parent data.
- `apps/safety/static/safety/context_choices.js`: synchronous local filtering,
  disabled/empty states, incompatible-selection and descendant-error clearing,
  compatible-selection retention and accessible result announcements.
- `templates/safety/create.html`: bounded form hook and script inclusion,
  preserving the pre-existing sectioned form work.
- `apps/safety/test_context_choices.py`: 11 focused form/view/isolation tests.
- This directory: validation runner, results, screenshot and completion evidence.

Relationships follow `SafetyIncident.clean()` unchanged: site belongs to project;
phase belongs to site; activity matches project and its non-null site/phase;
daily report matches project, site and phase exactly, including empty phase.
Project-wide activities and project-only incidents remain supported. Existing
server authorization, relationship validation and services remain authoritative.
No new endpoint, dependency, permission, model, schema or migration was introduced.

## Validation

- `.venv/Scripts/python.exe output/safety-cascade/validate.py`:
  **25 passed; 12 subtests passed**, including the 11 focused tests, existing safety
  tests and HSE object-scope regression. See `validation.txt`.
- The raw run found four existing service/model tests failing because the reused
  test database lacked `safety_incident_legacy_compatibility`. Their stack traces
  enter workflow template loading without reaching the changed form/template/JS.
  See `raw-validation.txt`. The runner restores only that exact code-owned seed,
  following the existing HSE fixture pattern, after verifying a `test_` database.
  No development or production business data was changed by testing.
- `manage.py check`: no issues.
- Ruff lint and formatting: PASS for the changed Python files and runner.
- `node --check apps/safety/static/safety/context_choices.js`: PASS.
- Targeted `git diff --check`: PASS.
- Chrome, real local page: initial descendants disabled; project restricts sites;
  site restricts phases; selecting a phase reveals matching activities/reports;
  changing phase clears incompatible activity/report; changing project clears
  site/phase/activity/report. Latest reload verifies helper text and empty states.
  Selected test context yielded 1 site, 2 phases, 5 compatible activities and 9
  compatible reports, with no horizontal overflow. See `desktop.png`.
- Browser console messages observed were from an unrelated Chrome extension's
  content script; no application-script error was observed.
- Mobile viewport and successful incident submission were not exercised in the
  browser. Server validation, compatible bound selections and create permission
  denial were covered by focused tests. No full repository suite was run.

Human sign-off, production certification and production cutover: NOT EXECUTED.
