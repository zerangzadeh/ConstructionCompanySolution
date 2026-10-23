# BATCH-09 — Site-aware operational selectors

Date: 2026-10-22, Asia/Tehran. **UIUX-F-115, UIUX-F-126 and UIUX-F-127 =
RUNTIME_VERIFIED_RESOLVED / RESOLVED.** Decision:
**BATCH_09_RUNTIME_VERIFIED_RESOLVED**.
Authority: the Human's attached end-to-end request, including minimum synthetic
Development fixtures and existing canonical authority, and the
[BATCH-09 contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-09).

## Baseline and Actual Execution Touch Set

`main`; HEAD and local `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`; upstream `origin/main`;
local-reference divergence 0/0; no fetch. Sixteen dirty product files, existing
untracked tests, UIUX evidence, Graphify and protected documents are the effective
entry baseline. All three findings entered OPEN / STATIC_CONFIRMED / NOT_EXECUTED.
[Entry Git state, 5,566 hashes and intended boundary](f111_batch_09_evidence/ENTRY_BASELINE.json).

| Finding | Form constructor | View form construction |
| --- | --- | --- |
| F-115 | `apps/equipment/forms.py:MaintenanceRecordForm` | `apps/equipment/views.py:maintenance_create` |
| F-126 | `apps/quality/forms.py:QualityIssueForm` | `apps/quality/views.py:issue_create` |
| F-127 | `apps/safety/forms.py:SafetyIncidentForm` | `apps/safety/views.py:incident_create` |

Only these six product seams and necessary imports changed. Added
`tests/test_uiux_f111_pattern_operational_scope.py`, this report and
`f111_batch_09_evidence/`; updated only the three named findings in the register.
No services, models, schema, migrations, templates, settings, shared helpers,
permission catalogs, Registry or Roadmap changes. Migration: **NO**.
[Final preservation/boundary verification](f111_batch_09_evidence/VERIFICATION.json)
compares all entry hashes, all other finding blocks byte-for-byte, and source AST
outside the three constructors and three view form assignments. Prior F-111
Equipment Assignment changes in the same files remain intact. BATCH-01..08 code,
tests and historical evidence are preserved. No graph rebuild or broader sweep.

## Implementation and existing domain behavior

Each view obtains `get_active_membership` server-side. Constructors fail closed
for missing, invalid or wrong-tenant membership. Quality/Safety explicitly empty
all five ModelForm-generated querysets before any early return. Canonical helpers
evaluate membership/user/tenant status and effective grants. GET, bound validation
and error redisplay use the same scoped constructors.

- **F-115:** Project uses `scoped_projects_for_form`; Site uses `scope_queryset`
  with `project_id` / `pk`. Existing Equipment/provider tenant masters, lifecycle
  filters, ordering, optional blanks and Site-to-Project validation remain.
  Limited actors retain the existing unassigned-record service denial;
  organization authority can still create with blank Project/Site.
- **F-126:** Project uses the site-parent-aware helper. Site uses `project_id` /
  `pk`; Phase uses `site__project_id` / `site_id`; Activity and DailyReport each
  use `project_id` / `site_id`. Existing optional children, lifecycle predicates,
  model/service structure checks, state machine and workflow remain unchanged.
- **F-127:** independently applies the same five local field mappings while
  retaining Safety-specific fields, exceptions, validation and lifecycle.

Project-only A/B grants expose their qualifying children. A Site-only grant may
show its parent Project as context and its exact Site/Phase/Activity/DailyReport
children; sibling objects and project-only Activities remain excluded. Parent
context does not create a general Project grant. Existing explicit service
`allow_site_parent=True` handling remains unchanged. No cascade, automatic parent
selection, new reader permission or global helper semantic change was introduced.

**Existing stricter workflow gate:** Quality/Safety `load_*_subject` require their
VIEW permission at organization scope without Project/Site arguments. Therefore
limited Project/Site actors can select valid authorized combinations but their
public create service can still deny during workflow startup and roll back.
This unchanged behavior is proved with actual services and HTTP, including safe
redisplay and zero business/success-audit changes. Organization-scoped creation
succeeds in disposable tests. Altering that workflow gate is outside this batch;
no authority was broadened to manufacture limited-actor success.

## Automated validation and regression attribution

[Focused](f111_batch_09_evidence/focused.txt): **48 tests + 221 subtests PASS**,
16 concrete test methods independently executed for each finding. Coverage includes
all protected fields; A/B, C/D and X; organization and exact Site-only visibility;
project-only Activity; sibling and mixed Project/Site/Phase/Activity/DailyReport
rejection; missing/invalid/wrong-tenant membership; absent, revoked, expired and
future Project and Site grants; inactive member/user/tenant; missing role and
capability; mixed grant unions; forced/malformed IDs; missing-required and actual
service-error redisplay; original lifecycle/master predicates; no denied business
or success-audit mutation; and actual authorized organization creation.
Maintenance additionally proves Project- and Site-scoped successful creation.

[Regression](f111_batch_09_evidence/regression.txt): **69 tests + 73 subtests
PASS; 22 failures**. Ran full Equipment, Quality, Safety and Daily Report
`tests.py`, all three workflow TestCase classes, and original F-111 controls.
Unchanged concurrency suites and unrelated domain suites were not run.
The [exact dirty-entry replay](f111_batch_09_evidence/baseline_regression.txt)
uses an import loader for all six byte-captured form/view files without replacing
working source. [Per-test attribution](f111_batch_09_evidence/REGRESSION_ATTRIBUTION.json)
proves identical outcomes/messages: ten Equipment and twelve Daily Report legacy
authorization failures, before the remediated selectors. **Zero new failures.**
Quality/Safety service, view and complete workflow lifecycle controls pass.
No full regression PASS or unrelated debt repair is claimed.

[Django](f111_batch_09_evidence/django_check.txt),
[Ruff](f111_batch_09_evidence/ruff.txt),
[test formatting](f111_batch_09_evidence/ruff_format.txt),
[migration drift](f111_batch_09_evidence/migration_check.txt), YAML, source
boundary, links and whitespace: PASS. Development has zero pending migrations.
Focused/regression tests use dedicated disposable PostgreSQL
`test_bonira_uiux_batch09`, all 434 canonical migrations, temporary protected
document storage and test-only password hashing.
[Commands](f111_batch_09_evidence/VALIDATION_COMMANDS.json) and
[fixture/harness corrections](f111_batch_09_evidence/HARNESS_CORRECTIONS.json)
retain initial failures. The initially reused prior disposable DB lacked workflow
template rows; a fresh database restored canonical seed state. No new migration,
dependency or product workflow workaround was added.

## Runtime fixture and authority preparation

[Preflight](f111_batch_09_evidence/PREFLIGHT.json) confirmed existing qualifying
A/B/C/D in `demo-construction-01`, X in `demo-construction-02`, Equipment,
Sites, Phases, site-aware and project-only Activities, and Daily Reports.
All required capabilities already existed on three nonstaff/nonsuperuser actors:

- `uiux.persona.project-manager`: explicit A/B Project grants only.
- `uiux.persona.tenant-admin`: organization scope.
- `uiux.reference.batch03.site-only`: existing operations-manager role and A Site
  grant only, with no parent Project grant.

A lacked an ungranted sibling Site and its operational children. Under explicit
fixture authority, created exactly four synthetic Development records through
`create_project_site`, `create_project_phase`, `create_activity` and
`create_daily_report`, atomically, using the existing tenant owner. The Phase is
active for the canonical Daily Report validator. Four creation audit events are
retained. Existing Project-only Activities and all other fixtures were reused.
[Fixture ledger](f111_batch_09_evidence/FIXTURES.json).
No user, role, permission, role assignment or scope grant was created or changed.
Temporary authority: **NONE**; no revocation is necessary. Fixtures and audit
history remain retained. No canonical service or business/security control bypass.

## Independent HTTP, service and browser evidence

Fresh Development processes on `localhost:8012`, PostgreSQL `construction_erp`,
zero pending migrations. [Initial process identity](f111_batch_09_evidence/initial_SERVER_IDENTITY.json)
and [second process identity](f111_batch_09_evidence/SERVER_IDENTITY.json) prove
the same checkout, HEAD and identical product hashes predating both starts.
The second process adds four real valid-form workflow-gate controls. Browser
and full HTTP matrices used the first fresh process. Authentication used existing
credentials and actual form CSRF; evidence contains no passwords, cookies, tokens
or raw token-bearing HTML.

| Finding | Own HTTP observations | Own direct source denials | Own browser evidence | Final status |
| --- | --- | --- | --- | --- |
| F-115 | 30 PASS | 8 PASS | Limited GET, mixed Project/Site server POST rejection, Site-only GET; one extra date-normalization click | RUNTIME_VERIFIED_RESOLVED |
| F-126 | 58 PASS | 8 PASS | Limited five-field GET, mixed Site/Phase server POST rejection, Site-only five-field GET | RUNTIME_VERIFIED_RESOLVED |
| F-127 | 58 PASS | 8 PASS | Independent limited and Site-only five-field GETs; own complete HTTP mixed-child/forced-ID matrix | RUNTIME_VERIFIED_RESOLVED |

[HTTP ledger](f111_batch_09_evidence/RUNTIME_HTTP.json): **146 observations
PASS**. Every route independently has Project-only, organization and Site-only
GET and required-field redisplay. All local fields reject C/D/X; Site-only actors
also reject B and A siblings. Forced query IDs leave choices unchanged. Mixed
authorized parent/child combinations fail existing relationship checks. Quality
and Safety each reject a site-only attempt to choose a project-only Activity.
Maintenance's blank unassigned submission retains its service denial.
Quality/Safety each have independent valid-form limited and Site-only workflow
reader denial controls. All retain scoped options with no protected metadata
leakage, unauthorized business write or success audit.

[Direct services](f111_batch_09_evidence/DIRECT_SERVICE.json): **24 denials
PASS**, eight independently per finding: same-tenant and cross-tenant targets,
Site-only unrelated Project targets and an internally consistent ungranted
sibling subtree. These prove existing target/service checks; they do not assert
new independent service enforcement of every child enumeration policy.

[Browser ledger](f111_batch_09_evidence/RUNTIME_BROWSER.json): nine observations
and screenshots, independently compared with each finding/actor's HTTP GET
options. Two are real server POST rejections. The first Maintenance click only
normalized its Jalali date and is explicitly not counted as a server rejection.
The [raw browser ledger](f111_batch_09_evidence/initial_RUNTIME_BROWSER.json) is
preserved: three Site-only actor metadata values were corrected after a logging
closure retained the previous actor name. Explicit login actions, screenshot
account headers and exact option sets support the correction. Daily Report labels
undergo existing browser Jalali localization; the
[label comparison](f111_batch_09_evidence/BROWSER_LABEL_NORMALIZATION.json) uses
the unchanged canonical date converter and digit normalization while still
comparing every UUID, option order, full label and parent context.
[Maintenance error](f111_batch_09_evidence/browser_maintenance_rejected_post.png),
[Quality error](f111_batch_09_evidence/browser_quality_mixed_post.png),
[Maintenance Site-only](f111_batch_09_evidence/browser_maintenance_site_only.png),
[Quality Site-only](f111_batch_09_evidence/browser_quality_site_only.png),
[Safety Site-only](f111_batch_09_evidence/browser_safety_site_only.png).
Safety has its own full HTTP matrix; Quality evidence does not substitute for it.
Shared demo labels are disambiguated by UUID and parent context; disposable tests
also use distinctive codes/names. Caller-supplied navigation query echoes are
excluded from fetched-metadata assertions.

## Integrity, cleanup and boundary

[Before preparation](f111_batch_09_evidence/PREPARATION_BEFORE.json),
[before runtime](f111_batch_09_evidence/RUNTIME_BEFORE.json),
[after](f111_batch_09_evidence/RUNTIME_AFTER.json) and
[integrity](f111_batch_09_evidence/RUNTIME_INTEGRITY.json): **519 model tables**;
all pre-existing business rows preserved; only sessions change during runtime,
with authentication `User.last_login` explicitly excluded. The only preparation
additions are the four documented synthetic objects and their four audit events.
Zero unauthorized mutations, zero runtime success-audit changes, zero financial
changes. Authority fingerprints match before preparation and after verification.
[Final cleanup](f111_batch_09_evidence/SERVER_CLEANUP.json) and
[initial cleanup](f111_batch_09_evidence/initial_SERVER_CLEANUP.json) record own
process identity verification, termination and no remaining listener. Browser
actors logged out; the successful browser tab closed. Temporary grants: NONE.

Only the three finding entries advance. **BATCH-01..08 preserved; Wave C remains
NOT_STARTED; SP-031 remains NOT_EXECUTED and untouched.** No broader remediation,
global authorization change, role/permission definition, schema/domain redesign,
production action, CEP-078/079 execution, posting, payment, Human Sign-off or
Production Certification. No Git add/commit/push, branch or worktree creation.
BATCH-09 complete; STOP.
