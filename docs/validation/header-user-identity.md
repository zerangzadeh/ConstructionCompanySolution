# Header user identity — 2026-11-03

Direct Human authorization: implement the reviewed profile preview, showing name,
current company role(s), current primary position and the personal-settings link
with proportional avatar/text sizing. This is an ordinary bounded presentation
task, not CEP execution or production authorization.

Repository grounding: local `main`; HEAD and `origin/main` both
`560bc3c9f136a3b76c6816dc127a80d74bcb7a1d`. Existing global-loading changes in
`templates/base.html` and untracked loading assets, verification and evidence are
unrelated and preserved. No branch/worktree or Git writes authorized/performed.

Touch set: own-data label selector in `apps/accounts/header_identity.py`, the
existing organizations context processor, shared profile/avatar/label components,
the header in `templates/base.html`, generated Tailwind CSS, focused identity and
browser validation, this evidence and scoped output in `output/header-identity/`.
No models, migrations, permissions, routes, dependencies, business workflows,
Product Surface or Registry/CEP state changes.

The context processor calls the projection only after canonical active membership
resolution. Roles use effective assignments, with the existing unmigrated legacy
compatibility boundary. Positions use explicit Person/User + current
WorkRelationship/legacy Employee links; direct Employee/User compatibility is
allowed only before a workforce relationship exists. Missing, ended or ambiguous
links never infer identity. Only an active, started primary position in the same
tenant on an active, unarchived employee is displayed; role/status/title labels
confer no permissions. Missing position is shown as «سمت ثبت نشده».

Desktop keeps the personal-settings link and shows all labels beside a 56px
avatar. Below 768px the 60px compact header exposes labels and settings via the
avatar's native disclosure. This preserves the existing mobile working-context
panel's 60px offset. Desktop header height is 88px. Long labels are bounded in
the desktop header and wrap in the mobile disclosure. A subsequent direct Human
request authorizes Persian built-in role labels in this header only. The selector
maps system-role codes to Persian display titles for both effective assignments
and the governed legacy fallback. The Human-requested company terminology uses
«مالک شرکت» for the Tenant Owner header label. Registered role titles, role codes, catalog
screens and custom-role names remain unchanged; the display map is not an
authorization source. Custom roles sharing a built-in code are not translated.

## Validation

`manage.py test tests.test_header_identity core.test_home
apps.accounts.tests.PersonalSettingsTests
tests.test_f3_module_selector.ModuleSelectorPresentationTests
tests.test_global_loading --keepdb --noinput --verbosity 0`: **37 tests PASS**
(configured PostgreSQL test database, preserved by the existing keepdb workflow).
After the final responsive breakpoint adjustment, the header browser test was
rerun successfully against rebuilt Tailwind CSS.

After header-only Persian localization, `manage.py test
tests.test_header_identity.HeaderIdentityTests --keepdb --noinput --verbosity 0`:
**12 tests PASS**. This includes preserving registered catalog titles and custom
role names even when a custom role uses a built-in code. Focused Ruff lint/format,
Django system checks and whitespace validation also pass. No layout or CSS change
was needed for this localization follow-up.

Coverage includes effective multi-role assignments (revoked/expired/future/
inactive exclusions), governed legacy role fallback, explicit legacy and canonical
workforce identity, expired/ambiguous canonical relationships, no name matching,
current primary-position dates/state, inactive/archived employees and positions,
foreign-tenant position rejection, switching active companies, denied/anonymous
membership and superuser non-bypass, escaped labels, protected avatar and settings
routes. Existing home, personal settings, module selector and loading checks pass.

The real Django-rendered shared shell and contracts-list header were exercised in
installed headless Chrome at 1440, 1024, 768, 640, 390 and 320px. Verified no page
overflow, proportional avatars, image/fallback handling, native keyboard-operated
disclosure, settings URLs, wrapped long labels and working-context/profile
separation. Screenshots were visually inspected at desktop/tablet and mobile
sizes. Evidence: `output/header-identity/browser-results.json` and adjacent PNGs.
Browser fixtures are synthetic and perform no database writes; this is not Human
UAT or production verification. Initial own-test expectations used legacy role
titles; they were corrected to assert the effective role-assignment authority.

`manage.py check`, focused Ruff lint/format and `git diff --check`: **PASS**.
`npm run build:css`: **PASS**; existing Browserslist data-age notice remains,
without dependency updates. No models or migrations changed. No unrelated
implementation changes, commit, push, production deployment or Human sign-off.
