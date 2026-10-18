# CEP-054 Execution Manifest

## Before product mutation — 2026-10-18

`main` / `origin/main` / remote match at
`4f37c118f920f99f1ec01940343fe83b18c8e84d`; clean tree. CEP-069 intake is
checkpointed PARTIAL/BLOCKER-EXTERNAL; the Human's subsequent `continue` resumes
independent non-production work, not statutory activation or certification.
Standing authority applies to CEP-054; CEP-025/026 COMPLETE and GATE-02 PASS.
Canonical hash `78e210b460e214c766eec2e439f4e12f11b744e4865ce41462a7f50d6170bc84`
matches the manifest. Twelve AC and both scoped DoDs apply. Conditional schema
expansion is necessary for the approved inquiry/category/response/evidence history;
no speculative backfill or production migration.

Recovered PD-029/031, SPEC-035 Payroll Inquiry Handling, and ESS-CAP-007/008/020
govern. Payslips use existing immutable source artifacts and source financial
values only; no new payslip template, formula, statutory activation or YTD total.
Inquiry is communication, never a Payroll correction. Categories are explicitly
configured/versioned, with no seeded category names. Shared Workflow owns status,
routing, assignment, separation, work items and completion. No invented inquiry
state vocabulary, review depth, priority, due/SLA timer, escalation or reopen.
Missing category/published workflow/eligible handler fails atomically without an
orphan request. Employee-visible responses are explicit source records; internal
Workflow notes are never exposed. Optional evidence uses DMS-owned versioned typed
links, retention and download authorization, plus the inquiry's own-data/assigned
handler boundary on every direct DMS path.

Actual intended touch set:

- `apps/payroll/models.py`: append-only inquiry category, inquiry, response and
  typed evidence records. `apps/payroll/migrations/0008_*`: expand-only schema.
- `apps/payroll/ess_services.py`, `ess_forms.py`, `ess_views.py`, `inquiry_workflow.py`:
  own finalized history/artifact selection, episode/source lineage, scoped inquiry
  submit/read/respond/configuration, shared runtime adapter and command; thin UI.
- `apps/payroll/apps.py`, `urls.py`: adapter binding and ESS routes.
- `apps/workflows/registry.py`: registered inquiry type/adapter/response command,
  with no seeded tenant workflow/review depth. `personal_workspaces.py`: own inquiry
  rows with raw authoritative Workflow status in My Requests.
- `apps/organizations/models.py`, `authorization.py`, `permission_registry.py`,
  migration `0111_*`: explicit inquiry view/request/respond BusinessPermissionCodes,
  object-scope registration/catalogue, no default role grants or implied roles.
- `apps/documents/models.py` only if needed by the existing typed-link base;
  `link_registry.py`, `services.py`: new registered inquiry target and bounded
  own/assignment privacy on list/read/link/download; no change to other targets.
- `templates/payroll/ess_*.html`, reusable existing payslip source template,
  `templates/workforce/_ess_navigation.html`: own history and inquiry forms/detail,
  generic handler source actions, Persian/RTL/Jalali/empty/error/denial.
- `apps/payroll/test_cep054.py`, `test_cep054_migration.py`: focused source, workflow,
  transaction, permission, tenant, DMS/privacy, history and UI tests; migration
  rollback/reapply preserving existing finalized output.
- CEP-054 acceptance/evidence/change manifests, screenshots, report and Registry.

No unrelated model changes, financial mutation, alternate work-item mechanism,
legacy-field removal, new statutory values, production action or Human Sign-off.
Validate sufficient focused/affected regression, lint/check/drift/whitespace and
required UI screenshots; retain remaining broad runtime UTV explicitly.

Before shared-runtime mutation: `apps/workflows/runtime.py` and the registered
DomainCommandSpec gain an opt-in trusted work-item argument for the new inquiry
response command. Existing commands keep their current call contract. The response
must retain the actual locked completing WorkItem, never a client-supplied item ID.
This is bounded coordination plumbing, not a new state/assignment mechanism.

Before own-access permission mutation: existing PAYSLIPS_VIEW/EXPORT protect
source-domain project/tenant access, not employee-only access. ESS therefore adds
distinct `payroll_ess.view_own` / `payroll_ess.export_own` BusinessPermissionCodes
with no default grants. Own artifact wrappers retain the existing source snapshot
and audit actions without granting back-office permissions. The existing payslip
template receives an ESS export URL/context; no new payslip artifact/template.
`apps/workforce/ess_dashboard.py` additionally composes only authorized inquiry
source rows, preserving its existing current-episode filter.

Before default-grant correction: `apps/organizations/role_defaults.py` must classify
all five new Payroll capabilities in the existing sensitive-permission exclusion.
The generic ALL_PERMISSIONS baseline otherwise implicitly grants them to built-in
roles. No default grant is authorized; focused validation must prove exclusion.

Validation delta: generic built-in role grants were excluded for the five new
sensitive codes before closeout. Eight legacy Workflow runtime scope failures
reproduce under the unmodified HEAD runtime loaded in memory (no checkout or
source mutation); keep these as baseline debt, never weaken scope enforcement.
The first 390px screenshot exposed existing source-template hash overflow; bounded
`min-w-0` repair and recapture are required for the touched source artifact.
