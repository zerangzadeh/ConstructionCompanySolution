# Repository structure and retention

BONIRA keeps domain ownership in its Django modular monolith. This guide records
filesystem organization; it does not change product scope, CEP lifecycle,
authorization, business behavior, or production readiness.

## Directory ownership

| Path | Contents |
| --- | --- |
| `apps/<app>/` | Domain-owned models, services, views, forms, migrations, static assets, and tests. |
| `apps/<app>/templates/<app>/` | That app's templates. Keep Django logical names such as `projects/detail.html` stable. |
| `core/` | Shared infrastructure and support code. Avoid moving domain rules here. |
| `config/` | Django configuration, URLs, entrypoints, and environment settings. |
| `templates/` | Shared shell/components, shared print/widgets, Django/Admin overrides, and shared core pages. `core` itself is not an installed app. |
| `frontend/` | Frontend build sources; the existing app-static CSS output stays unchanged. |
| `tests/` | Cross-domain and repository-level tests. Existing app test modules remain valid and retained. |
| `scripts/` | Maintained operational and verification scripts; one-use experiments belong in `.scratch/`. |
| `docs/architecture/` | Architecture and domain/data-model references; diagrams belong in `diagrams/`. |
| `docs/design/` | Design system, handoff documents, and reference images. |
| `docs/governance/` | Execution policy, package contracts, live governed registers, and retained evidence. |
| `docs/governance/history/` | Historical agent rules and dated implementation closure reviews. |
| `docs/validation/`, `docs/assessments/` | Validation records and assessments. |
| `security/`, `certification/` | Existing supply-chain policies and qualification fixtures consumed by scripts/CI. These are not disposable output. |
| `output/<task-or-cep>/` | Task-specific generated artifacts and retained evidence. Existing governed paths remain valid. |
| `.scratch/` | Ignored, disposable local experiments; never the sole home of required evidence. |

Keep `Agents.md`, `ROADMAP.md`, `CEP_EXECUTION_REGISTRY.yaml`, `README.md`,
`manage.py`, and tool/dependency configuration at the root. Do not create empty
folders merely to match a diagram. Split large modules into packages only when
there is a concrete maintenance need and import/test compatibility is verified.

## Relocations on 2026-11-08–09 (Asia/Tehran)

The following directory-prefix substitutions apply to all descendants:

| Previous physical path | Current physical path |
| --- | --- |
| `templates/<app>/` | `apps/<app>/templates/<app>/` for the app list below. |
| `design/` | `docs/design/` |
| `AGENTSـold.md` | `docs/governance/history/AGENTS_legacy.md` |
| `ERD_Diagram.png` | `docs/architecture/diagrams/ERD_Diagram.png` |
| `V1_IMPLEMENTATION_CLOSURE_20261020.md` | `docs/governance/history/V1_IMPLEMENTATION_CLOSURE_20261020.md` |
| `docs/compact-form-reference.png` | `docs/design/references/compact-form-reference.png` |
| `docs/compact-form-specification.png` | `docs/design/references/compact-form-specification.png` |
| `docs/detail-page-reference.png` | `docs/design/references/detail-page-reference.png` |
| `docs/sectioned-form-reference.png` | `docs/design/references/sectioned-form-reference.png` |

App list: `accounts`, `audit`, `compliance`, `contracts`, `daily_reports`,
`documents`, `equipment`, `estimates`, `expenses`, `financials`, `inventory`,
`materials`, `organizations`, `parties`, `payroll`, `procurement`, `projects`,
`quality`, `reporting`, `safety`, `timekeeping`, `workflows`, `workforce`.

Current code, maintained verification scripts, live path metadata, and mutable
documentation references use the new locations. Django template names and
include/extends references remain unchanged because their namespace has not
changed. Shared `templates/core/global_search.html` stays in the shared root.

Restart a running Django development server after adding or moving an app
template directory. Django caches the list of app template directories for the
life of the process, so the old server can raise `TemplateDoesNotExist` even
when a fresh process loads the relocated template successfully.

Canonical CEP prompts/manifests, signed supporting packages, historical capture
JSON/hash inventories, archived scripts/diffs, and completion evidence retain
their historical bytes and paths. Those paths describe the captured revision;
use the table above to locate a relocated file in the current checkout. Do not
rewrite a historical capture to imply that a new location was verified then.
The Registry closure-review change is path metadata only.

## Retention and local files

- Preserve tests, migrations, canonical contracts, required screenshots, approved
  history, evidence manifests, and recovery/retention artifacts.
- `output/` is not blanket-ignored or blanket-deleted: it contains retained
  evidence as well as generated files. Remove a task artifact only after checking
  its consumers and applicable retention/contract requirements.
- `.venv/` is the local Python environment; `node_modules/` is the local frontend
  build installation. Recreate them from the existing dependency files when
  needed. Avoid additional numbered environments inside this checkout.
- Ignore caches, `.scratch/`, generated project-tree dumps, local environments,
  `graphify-out/`, `media/`, and `protected_documents/`. Ignore rules prevent new
  additions; they do not remove already tracked files or their history.
- Keep the persistent graph and its manifest when using graphify; its AST/stat
  caches and intermediate analysis are regenerable. Refresh the derived graph
  with the existing tooling before relying on source paths after relocations;
  retained graph data may describe the earlier checkout.
- Uploaded documents, media, private recovery captures, and backups are runtime
  data, not cleanup candidates. Keep deployment storage configured separately.
- Before moving a maintained file, inspect literal and dynamically composed paths,
  update consumers and relative links, and run validation appropriate to the
  affected boundary. Filesystem tests should use Django's template loader when
  they are asserting a logical template rather than a particular physical root.

## Maintenance verification

Starting point: `main`, HEAD/origin `9705b7656137cfe4cbcfc63652d1519ffee20228`.
The sole initial working-tree change was graphify's query-cache timestamp from
the preceding read-only investigation; it is disposable cache state.

Results:

- 275 files relocated, including 260 app templates across 23 apps. The moved
  template bytes and all 455 logical template resolutions match the baseline;
  all 455 templates compile with the existing Django settings.
- `python manage.py check`: PASS, zero issues.
- `npm run build:css`: PASS; generated CSS is byte-identical (SHA-256
  `c3f5d684c5c6f446a2d333ef6f0f7830f23a07107267e4f4f99a3f786ecc793f`).
- Ruff check and format check for the changed test module: PASS.
- Focused pytest run covering CEP-003 localization/accessibility, CEP-014
  administration template tests and CEP-017 navigation: 29 passed, 3 failed,
  54 subtests passed. The three failures are existing navigation-test debt:
  `DeferredUiPatternTests.test_ess_grouping_preserves_permission_gates`,
  `DeferredUiPatternTests.test_navigation_denies_ungranted_destinations_and_has_no_dead_placeholders`,
  and `DeferredUiReferenceTests.test_navigation_uses_existing_availability_flags_and_omits_empty_groups`.
  Replaying both referenced templates directly from starting HEAD through a
  locmem loader reproduced all three failures. No navigation behavior was changed
  to make historical expectations pass. Full application regression and browser
  UAT were not run for these byte-preserving template relocations.
- All 79 canonical prompts and the canonical identity manifest remain
  byte-identical. Historical captures and retained evidence were preserved.
- Local Markdown file-link audit: 677 checked; a pre-existing capability-audit
  link in the affected budget architecture document was repaired to its existing
  historical location. No missing local file links remain in the audited set.
- `git diff --check`: PASS. The only maintained Python consumer changes are a
  loader-based login-template assertion and the relocated workflow-template path
  in the existing stage-six probe.
- Removed redundant `.venv-1`/`.venv-2`, graph AST/stat caches and intermediate
  analysis, the empty ERD source, generated project-tree dump, accidental Git
  status dump, and an empty synthetic directory: 11,073 local files / 171.35 MiB.
  Python/test/lint caches and the one-use maintenance script are also removed
  after verification. The primary `.venv/`, frontend dependencies, persistent
  graph, existing task evidence, and runtime data are retained.

No Git staging, commit, push, branch creation, database migration, or production
operation was performed. The Registry change is exactly the relocated closure
review path. The cleanup does not claim full-suite PASS or new acceptance.
